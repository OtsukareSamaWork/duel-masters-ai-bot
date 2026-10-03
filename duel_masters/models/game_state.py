"""Game state representation for Duel Masters."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Optional

from .card import CardInstance, can_evolve_on
from .enums import Civilization, GamePhase


@dataclass
class PlayerState:
    """Complete state of one player."""
    name: str = "Player"
    hand: list[CardInstance] = field(default_factory=list)
    mana_zone: list[CardInstance] = field(default_factory=list)
    battle_zone: list[CardInstance] = field(default_factory=list)
    shield_zone: list[CardInstance] = field(default_factory=list)
    graveyard: list[CardInstance] = field(default_factory=list)
    deck_count: int = 30
    shields_count: int = 5
    hand_size_override: int = -1  # -1 = use len(hand); >=0 = use this value (for opponent)

    @property
    def total_mana(self) -> int:
        return len(self.mana_zone)

    @property
    def available_mana(self) -> int:
        return sum(1 for c in self.mana_zone if not c.is_tapped)

    @property
    def available_civilizations(self) -> set[Civilization]:
        civs: set[Civilization] = set()
        for c in self.mana_zone:
            if not c.is_tapped:
                civs.update(c.card.civilization)
        return civs

    @property
    def all_civilizations(self) -> set[Civilization]:
        civs: set[Civilization] = set()
        for c in self.mana_zone:
            civs.update(c.card.civilization)
        return civs

    @property
    def board_power(self) -> int:
        return sum(c.current_power for c in self.battle_zone)

    @property
    def creature_count(self) -> int:
        return len(self.battle_zone)

    @property
    def hand_size(self) -> int:
        if self.hand_size_override >= 0:
            return self.hand_size_override
        return len(self.hand)

    @hand_size.setter
    def hand_size(self, val: int):
        self.hand_size_override = max(0, val)

    @property
    def blockers(self) -> list[CardInstance]:
        return [c for c in self.battle_zone if c.can_block]

    @property
    def attackers(self) -> list[CardInstance]:
        return [c for c in self.battle_zone if c.can_attack]

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "hand": [c.to_dict() for c in self.hand],
            "mana_zone": [c.to_dict() for c in self.mana_zone],
            "battle_zone": [c.to_dict() for c in self.battle_zone],
            "graveyard": [c.to_dict() for c in self.graveyard],
            "deck_count": self.deck_count,
            "shields_count": self.shields_count,
            "total_mana": self.total_mana,
            "available_mana": self.available_mana,
            "board_power": self.board_power,
        }

    @classmethod
    def from_dict(cls, data: dict) -> PlayerState:
        return cls(
            name=data.get("name", "Player"),
            hand=[CardInstance.from_dict(c) for c in data.get("hand", [])],
            mana_zone=[CardInstance.from_dict(c) for c in data.get("mana_zone", [])],
            battle_zone=[CardInstance.from_dict(c) for c in data.get("battle_zone", [])],
            graveyard=[CardInstance.from_dict(c) for c in data.get("graveyard", [])],
            deck_count=data.get("deck_count", 30),
            shields_count=data.get("shields_count", 5),
        )


@dataclass
class GameState:
    """Complete game state for both players."""
    player: PlayerState = field(default_factory=PlayerState)
    opponent: PlayerState = field(default_factory=lambda: PlayerState(name="Opponent"))
    turn_number: int = 1
    current_phase: GamePhase = GamePhase.MAIN
    is_player_turn: bool = True
    can_charge_mana: bool = True
    decklist: list[str] = field(default_factory=list)  # Full decklist for draw probability
    active_prompt: Optional[dict] = None  # Active modal/effect decision in-game

    def get_playable_cards(self) -> list[CardInstance]:
        """Cards in player's hand that can be played with available mana and valid evolution requirements."""
        available = self.player.available_mana
        available_civs = self.player.all_civilizations
        playable = []
        for card_inst in self.player.hand:
            # 0. Evolution requirement check: must have valid bait in battle zone!
            if card_inst.card.is_evolution:
                can_evo, _ = can_evolve_on(card_inst.card, self.player.battle_zone)
                if not can_evo:
                    continue  # Cannot play evolution creature without matching base!

            # 1. Direct in-game glowing indicator from Duel Online DOM
            if getattr(card_inst, "is_playable", False) and card_inst.card.cost <= available:
                playable.append(card_inst)
                continue

            # 2. Mana and civilization rules check
            if card_inst.card.cost <= available:
                card_civs = set(card_inst.card.civilization)
                # If we have the required civ or no civ restriction or empty available_civs
                if not card_civs or not available_civs or card_civs.issubset(available_civs):
                    playable.append(card_inst)
                elif getattr(card_inst, "is_playable", False):
                    playable.append(card_inst)
        return playable

    def get_remaining_deck(self) -> list[str]:
        """Calculate which cards are still in the deck based on decklist minus visible zones."""
        if not self.decklist:
            return []
        remaining = list(self.decklist)
        # Remove cards visible in hand, mana, battle, graveyard
        for zone in [self.player.hand, self.player.mana_zone, self.player.battle_zone, self.player.graveyard]:
            for card in zone:
                name = card.name.lower()
                for i, dk in enumerate(remaining):
                    if dk.lower() == name:
                        remaining.pop(i)
                        break
        return remaining

    def get_draw_probabilities(self, top_n: int = 5) -> list[dict]:
        """Calculate probability of drawing specific cards next turn."""
        remaining = self.get_remaining_deck()
        if not remaining:
            return []
        total = len(remaining)
        # Count occurrences
        from collections import Counter
        counts = Counter(r.lower() for r in remaining)
        probs = []
        for card_name, count in counts.most_common():
            probs.append({
                "name": card_name.title(),
                "count_in_deck": count,
                "probability": round(count / total * 100, 1),
            })
        return probs[:top_n]

    def clone(self) -> GameState:
        return copy.deepcopy(self)

    def to_dict(self) -> dict:
        return {
            "player": self.player.to_dict(),
            "opponent": self.opponent.to_dict(),
            "turn_number": self.turn_number,
            "current_phase": self.current_phase.value,
            "is_player_turn": self.is_player_turn,
        }

    @classmethod
    def from_dict(cls, data: dict) -> GameState:
        return cls(
            player=PlayerState.from_dict(data.get("player", {})),
            opponent=PlayerState.from_dict(data.get("opponent", {})),
            turn_number=data.get("turn_number", 1),
            current_phase=GamePhase(data.get("current_phase", "MAIN")),
            is_player_turn=data.get("is_player_turn", True),
        )
