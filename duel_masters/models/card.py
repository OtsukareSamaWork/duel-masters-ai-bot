"""Card data models for Duel Masters."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Optional

from .enums import Ability, CardType, Civilization


RACE_PATTERNS = [
    (r'\b(?:radiance|purifying|holy|flight|light|solar|sun|nebula|aegis|aless|adomis|amnis|aeris)\s+elemental\b', ['Angel Command']),
    (r'\b(?:alcadeias|alphadios|hanusa|urth|elixia|sirius|justinian|rayla|gradius|ladia bale|ophidian|milporo|kilstine|aura pegasus)\b', ['Angel Command']),
    (r'\b(?:master of death|knight of darkness|general of fury|shadow|death|demon|darkness)\b.*\b(?:ballom|zagaan|daidalos|dorballom|death cruzer|photocide|vampire silphy|gillian|baraga)\b', ['Demon Command']),
    (r'\b(?:ballom|zagaan|daidalos|dorballom|death cruzer|photocide|vampire silphy|gillian|baraga)\b', ['Demon Command']),
    (r'\b(?:guardian|space guardian|sky guardian|twilight guardian|moonlight guardian|dawn guardian|barrier guardian|silver rift guardian)\b', ['Guardian']),
    (r'\b(?:la ura giga|dia nork|gran gure|szubs kin|phal eega|arc bine|creis dober|lu gila|rikabu|alek)\b', ['Guardian']),
    (r'\b(?:aqua|crystal|candy drop|reconnaissance vehicle|splash queen|liquid)\b', ['Liquid People']),
    (r'\b(?:corile|emeral|marinomancer|king depthcon|king ponitas|pikados|plasma)\b', ['Cyber Lord']),
    (r'\b(?:astral warper|marine flower|angler cluster|pecton|faerie child|cosmic nebula)\b', ['Cyber Virus']),
    (r'\b(?:bronze-arm|barkwhip|dual fang|burning mane|torcon|golden wing|popple|coiling vines|beast folk)\b', ['Beast Folk']),
    (r'\b(?:bolshack|bolmeteus|bombazar|gatling|dragon|dragons|wyvern|armored dragon|earth dragon)\b', ['Armored Dragon']),
    (r'\b(?:braid claw|pyrofighter magnus|deadly fighter|marrow ooze|dragonoid)\b', ['Dragonoid']),
    (r'\b(?:mini titan gett|armored walker urherion|valdios|balbaro|valkaizer|gandaval|immortal baron vorg|human)\b', ['Human']),
    (r'\b(?:chaos worm|ultracide worm|swamp worm|worm gowagon|parasite worm)\b', ['Parasite Worm']),
    (r'\b(?:azaghast|belzeber|garkago|abduction|deathliger|dark lord)\b', ['Dark Lord']),
    (r'\b(?:craze valkyrie|magris|miele|toel|lia bail|iere|sarius|smaragd|initiate)\b', ['Initiate']),
    (r'\b(?:skeleton soldier|living dead|ghost bauble|stinger worm|gregoria)\b', ['Living Dead']),
    (r'\b(?:writhing bone ghoul|bone ghost|bone spider)\b', ['Bone Ghost']),
    (r'\b(?:locomotiver|hedrian|chainsaw mutant)\b', ['Hedrian']),
    (r'\b(?:bloody squito|stinger ball|brain jacker)\b', ['Brain Jacker']),
    (r'\b(?:roaring great-horn|aura pegasus|silver axe|stampeding longhorn|horn beast|horned beast)\b', ['Horned Beast']),
    (r'\b(?:scissor eye|thorny mandra|obsidian beetle|scarab|giant insect)\b', ['Giant Insect']),
    (r'\b(?:cocco lupia|totto pipicchi|lupia|fire bird)\b', ['Fire Bird']),
    (r'\b(?:agira|giland|earth eater)\b', ['Earth Eater']),
    (r'\b(?:admiral queen|splash queen|mermaid)\b', ['Splash Queen']),
]


@dataclass
class Card:
    """Template definition of a Duel Masters card."""
    id: str
    name: str
    civilization: list[Civilization]
    cost: int
    card_type: CardType
    power: Optional[int] = None
    abilities: list[Ability] = field(default_factory=list)
    race: list[str] = field(default_factory=list)
    effect_text: str = ""
    shield_trigger: bool = False
    power_attacker_bonus: int = 0
    rarity: str = "Common"

    @property
    def is_creature(self) -> bool:
        return self.card_type in (CardType.CREATURE, CardType.EVOLUTION_CREATURE)

    @property
    def is_evolution(self) -> bool:
        if self.card_type == CardType.EVOLUTION_CREATURE:
            return True
        txt = self.effect_text.lower()
        return ("evolution" in txt or "vortex evolution" in txt) and "put on" in txt

    @property
    def is_spell(self) -> bool:
        return self.card_type == CardType.SPELL

    @property
    def effective_races(self) -> list[str]:
        if self.race:
            return list(self.race)
        name_l = self.name.lower()
        text_l = self.effect_text.lower()
        races = []
        for pat, r_list in RACE_PATTERNS:
            if re.search(pat, name_l) or re.search(pat, text_l):
                for r in r_list:
                    if r not in races:
                        races.append(r)
        return races

    @property
    def evolution_bases(self) -> list[str]:
        txt = self.effect_text.lower()
        txt = txt.replace("\u00e2\u20ac\u201d", "-").replace("\u2014", "-").replace("—", "-")
        
        m = re.search(r'put on (?:one|1) of your (.*?)(?:\.|\n|$)', txt)
        if m:
            base_txt = m.group(1).strip()
            # Extract race if formatted as "creatures that has X in its race"
            m2 = re.search(r'has (.*?) in its race', base_txt)
            if m2:
                return [m2.group(1).strip()]
            return [base_txt]
            
        m_vortex = re.search(r'put on 2 of your (.*?)(?:\.|\n|$)', txt)
        if m_vortex:
            return [m_vortex.group(1).strip()]
        return []

    @property
    def has_blocker(self) -> bool:
        return Ability.BLOCKER in self.abilities

    @property
    def has_speed_attacker(self) -> bool:
        return Ability.SPEED_ATTACKER in self.abilities

    @property
    def has_double_breaker(self) -> bool:
        return Ability.DOUBLE_BREAKER in self.abilities

    @property
    def has_triple_breaker(self) -> bool:
        return Ability.TRIPLE_BREAKER in self.abilities

    @property
    def has_slayer(self) -> bool:
        return Ability.SLAYER in self.abilities

    @property
    def has_unblockable(self) -> bool:
        return Ability.UNBLOCKABLE in self.abilities

    @property
    def shields_broken(self) -> int:
        if Ability.WORLD_BREAKER in self.abilities:
            return 99
        if Ability.TRIPLE_BREAKER in self.abilities:
            return 3
        if Ability.DOUBLE_BREAKER in self.abilities:
            return 2
        return 1

    @property
    def effective_power(self) -> int:
        """Base power (without attack bonuses)."""
        return self.power or 0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "civilization": [c.value for c in self.civilization],
            "cost": self.cost,
            "power": self.power,
            "card_type": self.card_type.value,
            "abilities": [a.value for a in self.abilities],
            "race": self.race,
            "effect_text": self.effect_text,
            "shield_trigger": self.shield_trigger,
            "power_attacker_bonus": self.power_attacker_bonus,
            "rarity": self.rarity,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Card:
        civs = data.get("civilization", [])
        if isinstance(civs, str):
            civs = [civs]
        return cls(
            id=data.get("id", str(uuid.uuid4())[:8]),
            name=data["name"],
            civilization=[Civilization(c) for c in civs],
            cost=data.get("cost", 0),
            power=data.get("power"),
            card_type=CardType(data.get("card_type", "CREATURE")),
            abilities=[Ability(a) for a in data.get("abilities", [])],
            race=data.get("race", []),
            effect_text=data.get("effect_text", ""),
            shield_trigger=data.get("shield_trigger", False),
            power_attacker_bonus=data.get("power_attacker_bonus", 0),
            rarity=data.get("rarity", "Common"),
        )


@dataclass
class CardInstance:
    """A specific instance of a card on the field with mutable state."""
    card: Card
    instance_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    is_tapped: bool = False
    summoning_sickness: bool = True
    power_modifier: int = 0
    turn_summoned: int = 0
    is_playable: bool = False

    @property
    def name(self) -> str:
        return self.card.name

    @property
    def current_power(self) -> int:
        base = self.card.effective_power + self.power_modifier
        return base

    @property
    def attack_power(self) -> int:
        """Power when attacking (includes Power Attacker bonus)."""
        base = self.current_power
        if Ability.POWER_ATTACKER in self.card.abilities:
            base += self.card.power_attacker_bonus
        return base

    @property
    def can_attack(self) -> bool:
        if self.is_tapped:
            return False
        if self.summoning_sickness and not self.card.has_speed_attacker:
            return False
        if not self.card.is_creature:
            return False
        return True

    @property
    def can_block(self) -> bool:
        return (
            self.card.has_blocker
            and not self.is_tapped
            and self.card.is_creature
        )

    def tap(self) -> None:
        self.is_tapped = True

    def untap(self) -> None:
        self.is_tapped = False
        self.summoning_sickness = False

    def to_dict(self) -> dict:
        d = self.card.to_dict()
        d.update({
            "instance_id": self.instance_id,
            "is_tapped": self.is_tapped,
            "summoning_sickness": self.summoning_sickness,
            "current_power": self.current_power,
            "attack_power": self.attack_power,
            "can_attack": self.can_attack,
            "can_block": self.can_block,
            "is_playable": self.is_playable,
        })
        return d

    @classmethod
    def from_dict(cls, data: dict) -> CardInstance:
        card = Card.from_dict(data)
        # If reader.js says can_attack=True (no .sick class), trust it and clear summoning sickness
        js_can_attack = data.get("can_attack", None)
        is_tapped = data.get("is_tapped", False)
        if js_can_attack is True:
            sickness = False
        elif js_can_attack is False and not is_tapped:
            sickness = True  # Has sick class but not tapped = freshly summoned
        else:
            sickness = data.get("summoning_sickness", True)
        return cls(
            card=card,
            instance_id=data.get("instance_id", str(uuid.uuid4())[:8]),
            is_tapped=is_tapped,
            summoning_sickness=sickness,
            power_modifier=data.get("power_modifier", 0),
            turn_summoned=data.get("turn_summoned", 0),
            is_playable=bool(data.get("is_playable", False)),
        )


def matches_evolution_base(creature_races: list[str], required_base: str) -> bool:
    """Check if creature's races satisfy an evolution base requirement string."""
    req = required_base.lower().strip()
    if req.endswith('s') and not req.endswith('people') and not req.endswith('virus'):
        req_singular = req[:-1]
    else:
        req_singular = req

    for r in creature_races:
        r_clean = r.lower().strip()
        if r_clean == req or r_clean == req_singular or req.startswith(r_clean) or r_clean.startswith(req_singular):
            return True
        if r_clean.replace(" ", "") == req.replace(" ", "") or r_clean.replace(" ", "") == req_singular.replace(" ", ""):
            return True
    return False


def can_evolve_on(evo_card: Card, battle_zone: list[CardInstance]) -> tuple[bool, list[CardInstance]]:
    """
    Check if the player has valid creatures in battle zone to evolve onto.
    Returns: (can_evolve: bool, valid_targets: list[CardInstance])
    """
    if not evo_card.is_evolution:
        return True, []

    bases = evo_card.evolution_bases
    if not bases:
        # We couldn't parse the bases from the text. Safer to assume we CANNOT evolve
        # rather than hallucinating we can.
        return False, []

    valid_creatures = []
    for creature in battle_zone:
        # Universal bait creatures (Innocent Hunter, etc.)
        if "any race" in creature.card.effect_text.lower():
            valid_creatures.append(creature)
            continue

        c_races = creature.card.effective_races
        for base_req in bases:
            parts = re.split(r'\b(?:or|and|and/or)\b', base_req)
            if any(matches_evolution_base(c_races, part.strip()) for part in parts if part.strip()):
                valid_creatures.append(creature)
                break

    if "vortex evolution" in evo_card.effect_text.lower():
        return len(valid_creatures) >= 2, valid_creatures
    return len(valid_creatures) >= 1, valid_creatures

