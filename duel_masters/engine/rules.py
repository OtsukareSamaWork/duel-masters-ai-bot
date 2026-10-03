"""Duel Masters rules engine."""

from __future__ import annotations

from models.card import CardInstance, can_evolve_on
from models.enums import Ability, CardType, Civilization
from models.game_state import GameState, PlayerState


def can_play_card(state: GameState, card: CardInstance) -> bool:
    """Check if a card can be played from hand."""
    player = state.player
    if card not in player.hand:
        return False
    if card.card.cost > player.available_mana:
        return False
    # Check civilization requirement: player must have at least one mana
    # of each civilization the card belongs to
    available_civs = player.all_civilizations
    for civ in card.card.civilization:
        if civ not in available_civs:
            return False

    # Check Evolution requirement: must have matching creature in battle zone
    if card.card.is_evolution:
        can_evo, _ = can_evolve_on(card.card, player.battle_zone)
        if not can_evo:
            return False

    return True


def can_attack_with(creature: CardInstance) -> bool:
    """Check if a creature can attack."""
    return creature.can_attack


def can_block_with(blocker: CardInstance) -> bool:
    """Check if a creature can block."""
    return blocker.can_block


def get_blockers(state: GameState, defending_player: PlayerState) -> list[CardInstance]:
    """Get all available blockers for the defending player."""
    return [c for c in defending_player.battle_zone if c.can_block]


def charge_mana(state: GameState, card: CardInstance) -> GameState:
    """Move a card from hand to mana zone."""
    new_state = state.clone()
    hand = new_state.player.hand
    for i, c in enumerate(hand):
        if c.instance_id == card.instance_id:
            charged = hand.pop(i)
            charged.is_tapped = False
            new_state.player.mana_zone.append(charged)
            break
    return new_state


def summon_creature(state: GameState, card: CardInstance) -> GameState:
    """Pay mana cost and put creature into battle zone."""
    new_state = state.clone()
    player = new_state.player

    # Find and remove card from hand
    card_in_hand = None
    for i, c in enumerate(player.hand):
        if c.instance_id == card.instance_id:
            card_in_hand = player.hand.pop(i)
            break
    if card_in_hand is None:
        return state

    # Pay mana - tap cards to pay cost
    cost = card_in_hand.card.cost
    tapped = 0
    for mana_card in player.mana_zone:
        if tapped >= cost:
            break
        if not mana_card.is_tapped:
            mana_card.tap()
            tapped += 1

    # Put into battle zone
    card_in_hand.summoning_sickness = True
    card_in_hand.turn_summoned = new_state.turn_number
    card_in_hand.is_tapped = False
    player.battle_zone.append(card_in_hand)
    return new_state


def cast_spell(state: GameState, card: CardInstance) -> GameState:
    """Pay mana and put spell into graveyard."""
    new_state = state.clone()
    player = new_state.player

    card_in_hand = None
    for i, c in enumerate(player.hand):
        if c.instance_id == card.instance_id:
            card_in_hand = player.hand.pop(i)
            break
    if card_in_hand is None:
        return state

    cost = card_in_hand.card.cost
    tapped = 0
    for mana_card in player.mana_zone:
        if tapped >= cost:
            break
        if not mana_card.is_tapped:
            mana_card.tap()
            tapped += 1

    player.graveyard.append(card_in_hand)
    return new_state


def resolve_combat(
    attacker: CardInstance, defender: CardInstance
) -> tuple[bool, bool]:
    """Resolve combat: returns (attacker_survives, defender_survives)."""
    atk_power = attacker.attack_power
    def_power = defender.current_power

    attacker_survives = atk_power > def_power
    defender_survives = def_power > atk_power

    # Slayer kills regardless of power
    if attacker.card.has_slayer:
        defender_survives = False
    if defender.card.has_slayer:
        attacker_survives = False

    return attacker_survives, defender_survives


def break_shields(shields: int, breaker_count: int) -> int:
    """Calculate remaining shields after attack."""
    return max(0, shields - breaker_count)


def check_win_condition(state: GameState) -> str | None:
    """Check if someone has won. Returns winner name or None."""
    if state.opponent.shields_count <= 0:
        # Player can do a direct attack
        attackers = state.player.attackers
        if attackers:
            return state.player.name
    if state.player.shields_count <= 0:
        defenders = state.opponent.attackers
        if defenders:
            return state.opponent.name
    if state.player.deck_count <= 0:
        return state.opponent.name
    if state.opponent.deck_count <= 0:
        return state.player.name
    return None
