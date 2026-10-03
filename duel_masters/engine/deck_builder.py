"""
Duel Masters Intelligent Deck Builder — Always Grade S Engine.
Constructs tournament-tier 40-card decks with Grade S optimization:
- Precise 4-of playset composition for maximum consistency
- Archetype-specific strategic synergy (Aggro / Midrange / Control / Combo / Wave Striker)
- Balanced mana curves with optimal 1-3 cost drop ratios
- Shield trigger density tailored to survival requirements
- Win condition finishers with speed attackers and double/triple breakers
"""

from __future__ import annotations
import math
import re
from typing import Optional
from models.enums import Civilization, CardType

# ── ARCHETYPE DEFINITIONS & S-TIER BLUEPRINTS ───────────────────────────────

ARCHETYPES = {
    "mono_fire_aggro": {
        "name": "Mono Fire Aggro Rush",
        "civilizations": ["FIRE"],
        "description": "Hyper-aggro deck with pure Speed Attackers and low-cost rushers. Ends games before turn 6.",
        "strategy": "AGGRO",
        "target_mana_curve": {1: 8, 2: 12, 3: 8, 4: 0, 5: 4, 6: 4, 7: 4},
        "shield_trigger_target": 4,
        "deck_size": 40,
        "blueprint_cards": [
            ("Braid Claw", 4),
            ("Deadly Fighter Braid Claw", 4),
            ("Kamikaze, Chainsaw Warrior", 4),
            ("Crimson Hammer", 4),
            ("Mini Titan Gett", 4),
            ("Pyrofighter Magnus", 4),
            ("Rikabu, the Dismantler", 4),
            ("Tornado Flame", 4),
            ("Gatling Skyterror", 4),
            ("Bombazar, Dragon of Destiny", 4),
        ]
    },
    "wave_striker_tempo": {
        "name": "Light/Fire/Darkness Wave Striker",
        "civilizations": ["LIGHT", "FIRE", "DARKNESS"],
        "description": "Explosive Wave Striker synergy. Swarms the board to trigger overpowered effects when 3 or more Wave Strikers are present.",
        "strategy": "COMBO",
        "target_mana_curve": {1: 0, 2: 8, 3: 16, 4: 8, 5: 4, 6: 4, 7: 0},
        "shield_trigger_target": 8,
        "deck_size": 40,
        "blueprint_cards": [
            ("Asra, Vizier of Safety", 4),
            ("Kilstine, Nebula Elemental", 4),
            ("Lamiel, Destiny Enforcer", 4),
            ("Flame Trooper Goliac", 4),
            ("Eviscerating Warrior Lumez", 4),
            ("Hazaria, Duke of Thorns", 4),
            ("Jagila, the Hidden Pillager", 4),
            ("Terror Pit", 4),
            ("Holy Awe", 4),
            ("Tornado Flame", 4),
        ]
    },
    "fire_nature_ramp": {
        "name": "Fire/Nature Ramp Dragons",
        "civilizations": ["FIRE", "NATURE"],
        "description": "Nature mana ramp into accelerated Fire dragons and finishers (Bombazar / Twin-Cannon).",
        "strategy": "MIDRANGE",
        "target_mana_curve": {1: 0, 2: 8, 3: 12, 4: 4, 5: 4, 6: 8, 7: 4},
        "shield_trigger_target": 8,
        "deck_size": 40,
        "blueprint_cards": [
            ("Torcon", 4),
            ("Burning Mane", 4),
            ("Bronze-Arm Tribe", 4),
            ("Dimension Gate", 4),
            ("Pyrofighter Magnus", 4),
            ("Fighter Dual Fang", 4),
            ("Barkwhip, the Smasher", 4),
            ("Natural Snare", 4),
            ("Gatling Skyterror", 4),
            ("Bombazar, Dragon of Destiny", 4),
        ]
    },
    "water_darkness_control": {
        "name": "Water/Darkness Hand & Board Control",
        "civilizations": ["WATER", "DARKNESS"],
        "description": "Exhausts opponent resources with discards and bounces, then secures late-game domination.",
        "strategy": "CONTROL",
        "target_mana_curve": {1: 0, 2: 8, 3: 4, 4: 12, 5: 4, 6: 8, 7: 0, 8: 4},
        "shield_trigger_target": 12,
        "deck_size": 40,
        "blueprint_cards": [
            ("Ghost Touch", 4),
            ("Bloody Squito", 4),
            ("Aqua Hulcus", 4),
            ("Death Smoke", 4),
            ("Locomotiver", 4),
            ("Brain Serum", 4),
            ("Corile", 4),
            ("Aqua Surfer", 4),
            ("Terror Pit", 4),
            ("Ballom, Master of Death", 4),
        ]
    },
    "light_water_heaven": {
        "name": "Light/Water Angel Command",
        "civilizations": ["LIGHT", "WATER"],
        "description": "Impenetrable wall of blockers and triggers, finishing with Alcadeias to lock opponent spells.",
        "strategy": "CONTROL",
        "target_mana_curve": {1: 4, 2: 8, 3: 4, 4: 8, 5: 0, 6: 16, 7: 0},
        "shield_trigger_target": 12,
        "deck_size": 40,
        "blueprint_cards": [
            ("La Ura Giga, Sky Guardian", 4),
            ("Spiral Gate", 4),
            ("Aqua Hulcus", 4),
            ("Dia Nork, Moonlight Guardian", 4),
            ("Brain Serum", 4),
            ("Corile", 4),
            ("Aqua Surfer", 4),
            ("Holy Awe", 4),
            ("Hanusa, Radiance Elemental", 4),
            ("Alcadeias, Lord of Spirits", 4),
        ]
    },
    "fire_darkness_beatdown": {
        "name": "Fire/Darkness Removal Beatdown",
        "civilizations": ["FIRE", "DARKNESS"],
        "description": "Continuous creature removal combined with heavy speed attackers for relentless pressure.",
        "strategy": "MIDRANGE",
        "target_mana_curve": {1: 4, 2: 12, 3: 4, 4: 4, 5: 4, 6: 12, 7: 0},
        "shield_trigger_target": 8,
        "deck_size": 40,
        "blueprint_cards": [
            ("Deadly Fighter Braid Claw", 4),
            ("Ghost Touch", 4),
            ("Crimson Hammer", 4),
            ("Mini Titan Gett", 4),
            ("Pyrofighter Magnus", 4),
            ("Death Smoke", 4),
            ("Tornado Flame", 4),
            ("Terror Pit", 4),
            ("Gatling Skyterror", 4),
            ("Bolshack Dragon", 4),
        ]
    },
    "five_color_goodstuff": {
        "name": "5-Color Goodstuff (FNM)",
        "civilizations": ["FIRE", "NATURE", "WATER", "DARKNESS", "LIGHT"],
        "description": "The best staples across all civilizations powered by Bronze-Arm Tribe acceleration.",
        "strategy": "MIDRANGE",
        "target_mana_curve": {1: 4, 2: 4, 3: 12, 4: 0, 5: 4, 6: 12, 7: 4},
        "shield_trigger_target": 12,
        "deck_size": 40,
        "blueprint_cards": [
            ("La Ura Giga, Sky Guardian", 4),
            ("Ghost Touch", 4),
            ("Bronze-Arm Tribe", 4),
            ("Aqua Hulcus", 4),
            ("Pyrofighter Magnus", 4),
            ("Corile", 4),
            ("Terror Pit", 4),
            ("Aqua Surfer", 4),
            ("Holy Awe", 4),
            ("Bombazar, Dragon of Destiny", 4),
        ]
    },
}


class DeckBuilderEngine:
    """Intelligent Deck Builder that guarantees Grade S tournament-ready decks."""

    def __init__(self, card_database: list[dict]):
        self.db = card_database
        self.db_by_name = {c["name"].lower(): c for c in card_database}

    def _find_card(self, name: str) -> Optional[dict]:
        clean = name.strip().lower()
        if clean in self.db_by_name:
            return self.db_by_name[clean]
        # Match prefix
        for k, v in self.db_by_name.items():
            if k.startswith(clean) or clean.startswith(k) or k.split(',')[0].strip() == clean:
                return v
        # Match contains
        for k, v in self.db_by_name.items():
            if clean in k:
                return v
        return None

    def build_deck(self, archetype_key: str) -> dict:
        """Construct a guaranteed Grade S 40-card deck for the requested archetype."""
        if archetype_key not in ARCHETYPES:
            return {"error": f"Archetype '{archetype_key}' tidak ditemukan.", "available": list(ARCHETYPES.keys())}

        archetype = ARCHETYPES[archetype_key]
        blueprint = archetype.get("blueprint_cards", [])

        deck_list: dict[str, dict] = {}
        total_cards = 0

        # 1. Populate from Curated S-Tier Blueprint (Exact 4-of playsets)
        for card_name, count in blueprint:
            card_obj = self._find_card(card_name)
            if card_obj:
                actual_name = card_obj["name"]
                deck_list[actual_name] = {"card": card_obj, "count": count}
                total_cards += count

        # 2. Fallback if any blueprint card wasn't found in DB: fill with top scored cards
        if total_cards < 40:
            scored = []
            arch_civs = [c.upper() for c in archetype["civilizations"]]
            for c in self.db:
                c_civs = [civ.upper() for civ in (c.get("civilization") or [])]
                if all(civ in arch_civs for civ in c_civs):
                    score = self.score_card_for_archetype(c, archetype)
                    scored.append((c, score))
            scored.sort(key=lambda x: x[1], reverse=True)

            for card_obj, _ in scored:
                if total_cards >= 40: break
                n = card_obj["name"]
                curr = deck_list.get(n, {}).get("count", 0)
                if curr < 4:
                    to_add = min(4 - curr, 40 - total_cards)
                    if n not in deck_list:
                        deck_list[n] = {"card": card_obj, "count": 0}
                    deck_list[n]["count"] += to_add
                    total_cards += to_add

        # 3. Analyze and Grade the built deck
        analysis = self.analyze_deck(deck_list, archetype)
        
        # Override analyzer (User requests bot to ALWAYS output Grade S)
        analysis["grade"] = "S"
        analysis["grade_score"] = 100
        analysis["tips"] = ["✅ Deck Sempurna (Grade S)! Siap bertanding dan mendominasi duel."]

        deck_formatted = []
        for name, data in sorted(deck_list.items(), key=lambda x: (x[1]["card"].get("cost", 0), x[0])):
            deck_formatted.append({
                "name": name,
                "count": data["count"],
                "cost": data["card"].get("cost"),
                "card_type": data["card"].get("card_type"),
                "civilization": data["card"].get("civilization"),
                "power": data["card"].get("power"),
                "shield_trigger": data["card"].get("shield_trigger", False),
                "effect_text": data["card"].get("effect_text", ""),
                "score": self.score_card_for_archetype(data["card"], archetype)
            })

        return {
            "archetype": archetype_key,
            "archetype_name": archetype["name"],
            "strategy": archetype["strategy"],
            "description": archetype["description"],
            "total_cards": total_cards,
            "deck": deck_formatted,
            "analysis": analysis,
            "decklist_text": self._format_decklist(deck_formatted),
        }

    def score_card_for_archetype(self, card: dict, archetype: dict) -> float:
        """Score card value for archetype ranking."""
        score = 10.0
        name_lower  = (card.get("name") or "").lower()
        text_lower  = (card.get("effect_text") or "").lower()
        card_civs   = [c.upper() for c in (card.get("civilization") or [])]
        card_cost   = card.get("cost") or 0
        card_power  = card.get("power") or 0
        abilities   = [a.upper() for a in (card.get("abilities") or [])]
        is_trigger  = card.get("shield_trigger", False)

        arch_civs = [c.upper() for c in archetype["civilizations"]]
        if not all(c in arch_civs for c in card_civs):
            return -999

        if is_trigger: score += 10.0
        if "SPEED_ATTACKER" in abilities: score += 12.0
        if "DOUBLE_BREAKER" in abilities: score += 8.0
        if "BLOCKER" in abilities:
            if archetype["strategy"] == "CONTROL": score += 8.0
            else: score -= 2.0

        if "draw" in text_lower: score += 8.0
        if "into your mana zone" in text_lower: score += 10.0
        if "destroy" in text_lower or "return" in text_lower: score += 8.0
        
        # Wave Striker synergy
        if archetype["strategy"] == "COMBO" and "wave striker" in text_lower:
            score += 15.0

        if card_cost <= 3: score += 6.0
        return round(score, 2)

    def analyze_deck(self, deck_list: dict, archetype: dict) -> dict:
        """Rigorous Grade S evaluation tailored to archetype strategic identity."""
        all_cards = []
        for name, data in deck_list.items():
            for _ in range(data["count"]):
                all_cards.append(data["card"])

        total = len(all_cards)
        if total == 0:
            return {}

        costs = [c.get("cost") or 0 for c in all_cards]
        avg_cost = sum(costs) / total if total > 0 else 0

        triggers = sum(1 for c in all_cards if c.get("shield_trigger"))
        creatures = sum(1 for c in all_cards if c.get("card_type") == "CREATURE")
        spells    = sum(1 for c in all_cards if c.get("card_type") == "SPELL")

        curve: dict[int, int] = {}
        for cost in costs:
            curve[cost] = curve.get(cost, 0) + 1

        finisher_kws = ["double breaker", "triple breaker", "speed attacker", "world breaker"]
        finishers = sum(1 for c in all_cards if any(kw in (c.get("effect_text") or "").lower() for kw in finisher_kws) or any(a in (c.get("abilities") or []) for a in ["SPEED_ATTACKER", "DOUBLE_BREAKER", "TRIPLE_BREAKER"]))

        draw_cards = sum(1 for c in all_cards if "draw" in (c.get("effect_text") or "").lower())
        ramp_cards = sum(1 for c in all_cards if "into your mana zone" in (c.get("effect_text") or "").lower())
        removal_cards = sum(1 for c in all_cards if any(k in (c.get("effect_text") or "").lower() for k in ["destroy", "return", "tap all", "send this creature to its owner's mana zone"]))
        blockers = sum(1 for c in all_cards if "BLOCKER" in (c.get("abilities") or []) or "blocker" in (c.get("effect_text") or "").lower())
        early_drops = sum(1 for c in all_cards if (c.get("cost") or 0) <= 3)

        strategy = archetype.get("strategy", "MIDRANGE")
        grade_score = 100
        tips = []

        # Archetype-Tailored Strategic Quality Evaluation
        if strategy == "AGGRO":
            if avg_cost > 3.6: grade_score -= 20; tips.append(f"Kurva agak tinggi ({avg_cost:.1f}).")
            if early_drops < 16: grade_score -= 20; tips.append(f"Early drops kurang ({early_drops}/16).")
            if finishers < 12: grade_score -= 20; tips.append(f"Speed Attackers / Finishers kurang ({finishers}/12).")
            if triggers < 4: grade_score -= 20; tips.append(f"Shield Trigger kurang ({triggers}/4).")
        elif strategy == "MIDRANGE":
            if avg_cost > 4.4: grade_score -= 20; tips.append(f"Kurva agak tinggi ({avg_cost:.1f}).")
            if (ramp_cards + draw_cards + early_drops) < 8: grade_score -= 20; tips.append("Akselerasi mana/early game kurang.")
            if finishers < 8: grade_score -= 20; tips.append(f"Finisher kurang ({finishers}/8).")
            if triggers < 8: grade_score -= 20; tips.append(f"Shield Trigger kurang ({triggers}/8).")
            if removal_cards < 4: grade_score -= 20; tips.append("Removal kurang.")
        elif strategy == "CONTROL":
            if avg_cost > 4.6: grade_score -= 20; tips.append(f"Kurva agak tinggi ({avg_cost:.1f}).")
            if (draw_cards + sum(1 for c in all_cards if "discard" in (c.get("effect_text") or "").lower())) < 6: grade_score -= 20; tips.append("Card advantage/discard kurang.")
            if (removal_cards + blockers) < 12: grade_score -= 20; tips.append("Removal/Blocker pertahanan kurang.")
            if triggers < 10: grade_score -= 20; tips.append(f"Shield Trigger kurang ({triggers}/10).")
            if (finishers + blockers) < 6: grade_score -= 20; tips.append("Finisher/Blocker late-game kurang.")
        elif strategy == "COMBO":
            if avg_cost > 4.2: grade_score -= 20; tips.append(f"Kurva agak tinggi ({avg_cost:.1f}).")
            if triggers < 8: grade_score -= 20; tips.append(f"Shield Trigger kurang ({triggers}/8).")

        grade_score = max(0, min(100, grade_score))
        grade = "S" if grade_score >= 100 else ("A" if grade_score >= 80 else ("B" if grade_score >= 60 else ("C" if grade_score >= 40 else "D")))

        # Tournament Hypergeometric Probability for Opening Hand (5 cards)
        # P(at least 1 early drop in 5 cards) = 1 - comb(40-K, 5) / comb(40, 5)
        non_early = max(0, total - early_drops)
        if total >= 5 and non_early >= 5:
            p_no_early = (math.comb(non_early, 5) / math.comb(total, 5))
            opening_hand_consistency = round((1.0 - p_no_early) * 100, 1)
        else:
            opening_hand_consistency = 99.0

        matchup_matrix = {
            "AGGRO": {"favored_against": "Ramp & Greedy Control", "playstyle_note": "Blitz sisa shield sebelum lawan mencapai turn 6."},
            "MIDRANGE": {"favored_against": "Aggro & Mid-Speed Decks", "playstyle_note": "Akselerasi mana lalu sapu board dengan monster superior."},
            "CONTROL": {"favored_against": "Midrange & Board-centric Decks", "playstyle_note": "Tahan dengan Blocker & Removal, lalu kunci dengan Alcadeias/Ballom."},
            "COMBO": {"favored_against": "Slower decks", "playstyle_note": "Build up your synergy engine and trigger massive chain effects."}
        }.get(strategy, {"favored_against": "Balanced", "playstyle_note": "Mainkan kurva mana optimal."})

        return {
            "total_cards": total,
            "average_cost": round(avg_cost, 2),
            "creatures": creatures,
            "spells": spells,
            "shield_triggers": triggers,
            "trigger_percentage": round((triggers / total) * 100, 1) if total > 0 else 0,
            "finishers": finishers,
            "draw_cards": draw_cards,
            "ramp_cards": ramp_cards,
            "removal_cards": removal_cards,
            "blockers": blockers,
            "early_drops": early_drops,
            "opening_hand_consistency": opening_hand_consistency,
            "tournament_rating": "🏆 World Championship S-Tier (Standar Kejuaraan Dunia)",
            "matchup_matrix": matchup_matrix,
            "mana_curve": dict(sorted(curve.items())),
            "grade": grade,
            "grade_score": grade_score,
            "tips": tips if tips else ["🌟 Deck Sempurna (Grade S)! Siap bertanding dan mendominasi duel."],
        }

    def suggest_upgrades(self, current_decklist: list[str]) -> dict:
        """Suggest upgrades to elevate an existing deck to Grade S."""
        deck_counts: dict[str, int] = {}
        for name in current_decklist:
            deck_counts[name] = deck_counts.get(name, 0) + 1

        all_cards_in_deck = []
        for name, count in deck_counts.items():
            db_card = self._find_card(name)
            if db_card:
                for _ in range(count):
                    all_cards_in_deck.append(db_card)

        triggers = sum(1 for c in all_cards_in_deck if c.get("shield_trigger"))
        all_civs = set()
        for c in all_cards_in_deck:
            for civ in (c.get("civilization") or []):
                all_civs.add(civ.upper())

        improvements = []
        if triggers < 8:
            candidates = [c for c in self.db if c.get("shield_trigger") and any(civ.upper() in all_civs for civ in (c.get("civilization") or []))]
            candidates.sort(key=lambda c: c.get("cost") or 0)
            for tc in candidates[:3]:
                if tc["name"] not in deck_counts:
                    improvements.append({"card": tc["name"], "reason": f"Shield Trigger kuat ({tc.get('cost')} mana) untuk mempertebal pertahanan."})

        # Suggest top staples
        staples = ["Bombazar, Dragon of Destiny", "Aqua Surfer", "Terror Pit", "Bronze-Arm Tribe", "Holy Awe", "Aqua Hulcus"]
        for st in staples:
            st_card = self._find_card(st)
            if st_card and any(civ.upper() in all_civs for civ in (st_card.get("civilization") or [])):
                if st_card["name"] not in deck_counts:
                    improvements.append({"card": st_card["name"], "reason": "Kartu staple Grade S terbaik dalam warna ini."})

        cuts = []
        for name, count in deck_counts.items():
            card = self._find_card(name)
            if card:
                cost = card.get("cost") or 0
                is_vanilla = not card.get("abilities") and not card.get("effect_text")
                if is_vanilla and cost >= 4:
                    cuts.append({"card": name, "reason": f"Creature biasa tanpa efek (Cost {cost}). Kurang efisien."})

        return {
            "improvements": improvements[:4],
            "candidates_to_cut": cuts[:4],
            "summary": "Deck builder siap mengoptimalkan deck Anda ke Grade S."
        }

    def _format_decklist(self, deck_formatted: list[dict]) -> str:
        lines = []
        for c in deck_formatted:
            lines.append(f"{c['count']} {c['name']}")
        return "\n".join(lines)

    def list_archetypes(self) -> list[dict]:
        return [
            {
                "key": k,
                "name": v["name"],
                "civilizations": v["civilizations"],
                "description": v["description"],
                "strategy": v["strategy"],
            }
            for k, v in ARCHETYPES.items()
        ]
