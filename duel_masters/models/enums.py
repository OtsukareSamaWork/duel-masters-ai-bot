"""Enums for Duel Masters game concepts."""

from enum import Enum


class Civilization(str, Enum):
    """The five civilizations in Duel Masters."""
    LIGHT = "LIGHT"
    WATER = "WATER"
    DARKNESS = "DARKNESS"
    FIRE = "FIRE"
    NATURE = "NATURE"

    @property
    def display_name(self) -> str:
        return {
            "LIGHT": "Light",
            "WATER": "Water",
            "DARKNESS": "Darkness",
            "FIRE": "Fire",
            "NATURE": "Nature",
        }[self.value]

    @property
    def color(self) -> str:
        return {
            "LIGHT": "#FFD700",
            "WATER": "#4169E1",
            "DARKNESS": "#8B008B",
            "FIRE": "#FF4500",
            "NATURE": "#228B22",
        }[self.value]


class CardType(str, Enum):
    """Types of cards in Duel Masters."""
    CREATURE = "CREATURE"
    SPELL = "SPELL"
    EVOLUTION_CREATURE = "EVOLUTION_CREATURE"
    CROSS_GEAR = "CROSS_GEAR"


class Ability(str, Enum):
    """Keyword abilities."""
    BLOCKER = "BLOCKER"
    SPEED_ATTACKER = "SPEED_ATTACKER"
    DOUBLE_BREAKER = "DOUBLE_BREAKER"
    TRIPLE_BREAKER = "TRIPLE_BREAKER"
    SHIELD_TRIGGER = "SHIELD_TRIGGER"
    SLAYER = "SLAYER"
    POWER_ATTACKER = "POWER_ATTACKER"
    SURVIVOR = "SURVIVOR"
    SILENT_SKILL = "SILENT_SKILL"
    TURBO_RUSH = "TURBO_RUSH"
    UNBLOCKABLE = "UNBLOCKABLE"
    WORLD_BREAKER = "WORLD_BREAKER"
    WAVE_STRIKER = "WAVE_STRIKER"
    STEALTH = "STEALTH"
    SYMPATHY = "SYMPATHY"
    CHARGER = "CHARGER"
    G_ZERO = "G_ZERO"
    METEORBURN = "METEORBURN"

    @property
    def description(self) -> str:
        return {
            "BLOCKER": "Can block attacking creatures",
            "SPEED_ATTACKER": "Can attack on the turn it is summoned",
            "DOUBLE_BREAKER": "Breaks 2 shields when attacking",
            "TRIPLE_BREAKER": "Breaks 3 shields when attacking",
            "SHIELD_TRIGGER": "Can be used for free when shield is broken",
            "SLAYER": "Destroys any creature it battles",
            "POWER_ATTACKER": "Gets bonus power when attacking",
            "SURVIVOR": "Shares abilities with other Survivors",
            "SILENT_SKILL": "Triggers effect if kept tapped",
            "TURBO_RUSH": "Triggers effect if another shield was broken",
            "UNBLOCKABLE": "Cannot be blocked",
            "WORLD_BREAKER": "Breaks all shields when attacking",
            "WAVE_STRIKER": "Triggers effect if you have 2+ Wave Strikers",
            "STEALTH": "Unblockable if opponent has specific mana",
            "SYMPATHY": "Costs less for each creature of a race",
            "CHARGER": "Goes to mana zone instead of graveyard after cast",
            "G_ZERO": "Can be cast/summoned for free if condition met",
            "METEORBURN": "Trigger effect by discarding cards under this",
        }[self.value]


class Zone(str, Enum):
    """Game zones."""
    HAND = "HAND"
    MANA_ZONE = "MANA_ZONE"
    BATTLE_ZONE = "BATTLE_ZONE"
    SHIELD_ZONE = "SHIELD_ZONE"
    GRAVEYARD = "GRAVEYARD"
    DECK = "DECK"


class GamePhase(str, Enum):
    """Phases of a turn."""
    UNTAP = "UNTAP"
    DRAW = "DRAW"
    CHARGE = "CHARGE"
    MAIN = "MAIN"
    ATTACK = "ATTACK"
    END = "END"


class ActionType(str, Enum):
    """Types of player actions."""
    CHARGE_MANA = "CHARGE_MANA"
    SUMMON_CREATURE = "SUMMON_CREATURE"
    CAST_SPELL = "CAST_SPELL"
    ATTACK_CREATURE = "ATTACK_CREATURE"
    ATTACK_PLAYER = "ATTACK_PLAYER"
    BLOCK = "BLOCK"
    END_TURN = "END_TURN"
    SKIP_MANA = "SKIP_MANA"
    EVOLVE = "EVOLVE"
