"""
Duel Masters Continuous Learning & Match Adaptation Engine.
Analyzes finished matches to evolve AI intelligence over time:
- Tracks card effectiveness and win rates
- Discovers new multi-card combos from real matches
- Profiles opponent meta and common deck archetypes
- Dynamically adapts combat, charge, and trigger caution weights
"""

from __future__ import annotations
import json
import os
import time
from typing import Optional

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
LEARNED_FILE = os.path.join(DATA_DIR, "learned_knowledge.json")

DEFAULT_KNOWLEDGE = {
    "total_matches": 0,
    "wins": 0,
    "losses": 0,
    "win_rate": 0.0,
    "experience_points": 0,
    "ai_level": 1,
    "archetype_frequencies": {},
    "opponent_common_cards": {},
    "card_performance": {},
    "learned_combos": [],
    "learned_weights": {
        "mana_charge": {},
        "combat_threat": {},
        "trigger_caution": 1.0
    },
    "match_history": []
}


class LearningEngine:
    """Manages persistent AI learning and real-time knowledge evolution."""

    def __init__(self, file_path: str = LEARNED_FILE):
        self.file_path = file_path
        self.data = self._load()

    def _load(self) -> dict:
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    # Merge with default structure for backwards compatibility
                    for k, v in DEFAULT_KNOWLEDGE.items():
                        if k not in loaded:
                            loaded[k] = v
                    return loaded
            except Exception as e:
                print(f"[LearningEngine] Error loading {self.file_path}: {e}")
        return json.loads(json.dumps(DEFAULT_KNOWLEDGE))

    def save(self):
        try:
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[LearningEngine] Error saving {self.file_path}: {e}")

    def process_match_result(self, match_data: dict) -> dict:
        """
        Process a finished match to learn and evolve AI heuristics.
        match_data schema:
        {
          "result": "WIN" | "LOSS" | "DRAW",
          "total_turns": 7,
          "player_deck": ["Bombazar...", "Aqua Surfer..."],
          "player_cards_played": ["Aqua Hulcus", "Terror Pit"],
          "opponent_cards_seen": ["Bolshack Dragon", "Pyrofighter Magnus"],
          "combos_executed": [["Bronze-Arm Tribe", "Fighter Dual Fang"]],
          "triggers_hit_by_player": 1,
          "triggers_hit_by_opp": 2,
          "opponent_archetype": "Mono Fire / Aggro Rush"
        }
        """
        result = match_data.get("result", "UNKNOWN").upper()
        turns = match_data.get("total_turns", 1)
        player_cards = match_data.get("player_cards_played", [])
        opp_cards = match_data.get("opponent_cards_seen", [])
        combos = match_data.get("combos_executed", [])
        opp_archetype = match_data.get("opponent_archetype", "Unknown")

        # 1. Update Match Record
        self.data["total_matches"] += 1
        is_win = (result == "WIN")
        if is_win:
            self.data["wins"] += 1
        elif result == "LOSS":
            self.data["losses"] += 1

        total = self.data["total_matches"]
        self.data["win_rate"] = round((self.data["wins"] / total) * 100, 1) if total > 0 else 0.0

        # XP and AI Level
        xp_gain = 100 if is_win else 50
        self.data["experience_points"] += xp_gain
        self.data["ai_level"] = max(1, 1 + (self.data["experience_points"] // 300))

        new_insights = []

        # 2. Learn Opponent Meta & Archetypes
        if opp_archetype and opp_archetype != "Belum Terdeteksi":
            freq = self.data["archetype_frequencies"].get(opp_archetype, 0) + 1
            self.data["archetype_frequencies"][opp_archetype] = freq

        for card_name in opp_cards:
            if not card_name or card_name in ["(Kartu)", "__shield_pickup__"]:
                continue
            prev_opp = self.data["opponent_common_cards"].get(card_name, 0)
            self.data["opponent_common_cards"][card_name] = prev_opp + 1

        # 3. Learn Card Performance
        for card_name in set(player_cards):
            if not card_name: continue
            stats = self.data["card_performance"].get(card_name, {"played": 0, "wins": 0, "losses": 0, "impact_score": 5.0})
            stats["played"] += 1
            if is_win:
                stats["wins"] += 1
                stats["impact_score"] = min(10.0, round(stats["impact_score"] + 0.3, 2))
            else:
                stats["losses"] += 1
                stats["impact_score"] = max(1.0, round(stats["impact_score"] - 0.2, 2))
            self.data["card_performance"][card_name] = stats

        # 4. Discover & Reinforce Combos
        for combo_cards in combos:
            if isinstance(combo_cards, list) and len(combo_cards) >= 2:
                combo_key = " + ".join(sorted(combo_cards))
                existing = next((c for c in self.data["learned_combos"] if c["key"] == combo_key), None)
                if existing:
                    existing["times_seen"] += 1
                    if is_win: existing["wins"] += 1
                    existing["win_rate"] = round((existing["wins"] / existing["times_seen"]) * 100, 1)
                else:
                    new_combo = {
                        "key": combo_key,
                        "cards": combo_cards,
                        "name": f"Kombo {combo_cards[0].split(',')[0]} & {combo_cards[1].split(',')[0]}",
                        "times_seen": 1,
                        "wins": 1 if is_win else 0,
                        "win_rate": 100.0 if is_win else 0.0,
                        "discovered_at": time.strftime("%Y-%m-%d %H:%M")
                    }
                    self.data["learned_combos"].append(new_combo)
                    new_insights.append(f"✨ Kombo Baru Dipelajari: {new_combo['name']}")

        # 5. Adapt Heuristic Weights
        # 5a. Threat adaptation: Opponent cards in losses get higher threat rating
        if not is_win:
            for opp_card in opp_cards:
                if not opp_card or opp_card in ["(Kartu)", "__shield_pickup__"]: continue
                curr_threat = self.data["learned_weights"]["combat_threat"].get(opp_card, 1.0)
                self.data["learned_weights"]["combat_threat"][opp_card] = round(min(2.5, curr_threat + 0.15), 2)
            # Adapt trigger caution if loss was due to triggers
            if match_data.get("triggers_hit_by_player", 0) >= 2:
                self.data["learned_weights"]["trigger_caution"] = round(min(2.0, self.data["learned_weights"]["trigger_caution"] + 0.1), 2)
                new_insights.append("⚠️ AI meningkatkan kewaspadaan Shield Trigger lawan (+10%).")
        else:
            # Player cards in wins get positive mana charge priority protection
            for p_card in player_cards:
                if not p_card: continue
                curr_protect = self.data["learned_weights"]["mana_charge"].get(p_card, 0.0)
                self.data["learned_weights"]["mana_charge"][p_card] = round(curr_protect - 0.2, 2)  # Negative charge score = prioritize holding

        # 6. Log Match History (Last 20 matches)
        history_entry = {
            "match_id": self.data["total_matches"],
            "timestamp": time.strftime("%Y-%m-%d %H:%M"),
            "result": result,
            "turns": turns,
            "opponent_archetype": opp_archetype,
            "cards_played_count": len(player_cards),
            "xp_earned": xp_gain
        }
        self.data["match_history"].insert(0, history_entry)
        self.data["match_history"] = self.data["match_history"][:20]

        # Save to disk
        self.save()

        return {
            "success": True,
            "xp_gained": xp_gain,
            "current_xp": self.data["experience_points"],
            "ai_level": self.data["ai_level"],
            "total_matches": self.data["total_matches"],
            "win_rate": self.data["win_rate"],
            "new_insights": new_insights,
            "learned_combos_count": len(self.data["learned_combos"])
        }

    def get_threat_modifier(self, card_name: str) -> float:
        """Returns learned threat multiplier for an opponent card (1.0 - 2.5x)."""
        if not card_name: return 1.0
        return self.data["learned_weights"]["combat_threat"].get(card_name, 1.0)

    def get_mana_charge_modifier(self, card_name: str) -> float:
        """Returns learned mana charge penalty/bonus for our cards."""
        if not card_name: return 0.0
        return self.data["learned_weights"]["mana_charge"].get(card_name, 0.0)

    def get_trigger_caution_factor(self) -> float:
        """Returns learned multiplier for trigger risk evaluation."""
        return self.data["learned_weights"].get("trigger_caution", 1.0)

    def get_summary(self) -> dict:
        """Returns full learning stats for popup and in-game display."""
        top_cards = sorted(
            [{"name": k, **v} for k, v in self.data["card_performance"].items()],
            key=lambda x: (x["impact_score"], x["played"]),
            reverse=True
        )[:5]

        top_opp_cards = sorted(
            [{"name": k, "seen": v} for k, v in self.data["opponent_common_cards"].items()],
            key=lambda x: x["seen"],
            reverse=True
        )[:5]

        top_archetypes = sorted(
            [{"name": k, "count": v} for k, v in self.data["archetype_frequencies"].items()],
            key=lambda x: x["count"],
            reverse=True
        )[:3]

        return {
            "total_matches": self.data["total_matches"],
            "wins": self.data["wins"],
            "losses": self.data["losses"],
            "win_rate": self.data["win_rate"],
            "ai_level": self.data["ai_level"],
            "experience_points": self.data["experience_points"],
            "learned_combos": self.data["learned_combos"][:6],
            "top_performing_cards": top_cards,
            "top_opponent_cards": top_opp_cards,
            "top_archetypes": top_archetypes,
            "match_history": self.data["match_history"][:5],
            "trigger_caution": self.data["learned_weights"].get("trigger_caution", 1.0)
        }
