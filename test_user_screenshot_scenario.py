import json
import os
import sys

sys.path.insert(0, os.path.join(os.getcwd(), 'duel_masters'))
from duel_masters.app import app, enrich_card_dict, find_card_in_db
from duel_masters.models.card import Card, CardInstance
from duel_masters.models.enums import Civilization, GamePhase, CardType
from duel_masters.models.game_state import GameState, PlayerState
from duel_masters.engine.advisor import GameAdvisor

def test_screenshot_state():
    print("============================================================")
    print("TESTING USER SCREENSHOT EXACT SCENARIO")
    print("============================================================")

    # Simulating what reader.js sends to /api/analyze from the screenshot:
    # 7 cards in hand (Spiral Gate, Dia Nork, Corile, Brain Serum, La Ura Giga, Aqua Surfer, Alcadeias)
    # Mana tray: 4 cards (Light, Water, Light, Light)
    # Opponent board: Braid Claw (1000 Tapped), Mini Titan Gett (2000 Tapped), Bronze-Arm Tribe (3000 Untapped)
    # Turn: 8, Your Turn, Main Phase, 4/4 Available Mana

    raw_payload = {
        "turn_number": 8,
        "is_player_turn": True,
        "current_phase": "MAIN",
        "can_charge_mana": False,  # User is in main phase with 4/4 mana ready
        "player": {
            "name": "Player",
            "hand": [
                {"id": "spiral_gate", "name": "Spiral Gate", "cost": 2, "is_playable": True},
                {"id": "dia_nork_moonlight_guardian", "name": "Dia Nork, Moonlight Guardian", "cost": 4, "is_playable": True},
                {"id": "corile", "name": "Corile", "cost": 5, "is_playable": False},
                {"id": "brain_serum", "name": "Brain Serum", "cost": 4, "is_playable": True},
                {"id": "la_ura_giga_sky_guardian", "name": "La Ura Giga, Sky Guardian", "cost": 1, "is_playable": True},
                {"id": "aqua_surfer", "name": "Aqua Surfer", "cost": 6, "is_playable": False},
                {"id": "alcadeias_lord_of_spirits", "name": "Alcadeias, Lord of Spirits", "cost": 6, "is_playable": False},
            ],
            "mana_zone": [
                {"id": "la_ura_giga_sky_guardian", "name": "La Ura Giga, Sky Guardian", "is_tapped": False},
                {"id": "aqua_hulcus", "name": "Aqua Hulcus", "is_tapped": False},
                {"id": "holy_awe", "name": "Holy Awe", "is_tapped": False},
                {"id": "dia_nork_moonlight_guardian", "name": "Dia Nork, Moonlight Guardian", "is_tapped": False},
            ],
            "battle_zone": [],
            "shields_count": 5,
            "deck_count": 26,
            "graveyard": [{"id": "brain_serum", "name": "Brain Serum"}]
        },
        "opponent": {
            "name": "AI Duelist",
            "hand_size": 2,
            "mana_zone": [
                {"id": "braid_claw", "name": "Braid Claw", "is_tapped": True},
                {"id": "crimson_hammer", "name": "Crimson Hammer", "is_tapped": True},
                {"id": "mini_titan_gett", "name": "Mini Titan Gett", "is_tapped": True},
                {"id": "bronze_arm_tribe", "name": "Bronze-Arm Tribe", "is_tapped": True},
            ],
            "battle_zone": [
                {"id": "braid_claw", "name": "Braid Claw", "power": 1000, "is_tapped": True, "can_attack": False},
                {"id": "mini_titan_gett", "name": "Mini Titan Gett", "power": 2000, "is_tapped": True, "can_attack": False},
                {"id": "bronze_arm_tribe", "name": "Bronze-Arm Tribe", "power": 3000, "is_tapped": False, "can_attack": True},
            ],
            "shields_count": 5,
            "deck_count": 27,
            "graveyard": []
        }
    }

    client = app.test_client()
    resp = client.post("/api/analyze", json=raw_payload)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.data}"

    data = resp.get_json()
    assert data["success"] is True

    recs = data["recommendations"]
    turn_plan = recs["turn_plan"]
    print("Turn Plan Steps Count:", len(turn_plan))
    print("Turn Plan Decision:", turn_plan[0]["action"])
    print("Turn Plan Detail:  ", turn_plan[0]["detail"])

    # Ensure it did NOT say "Selesai Main -> Klik End Turn" or "Tidak ada kartu yang bisa dimainkan"
    assert "Klik End Turn" not in turn_plan[0]["action"], "ERROR: AI still wrongly advised End Turn when playable cards exist!"
    assert "Mainkan:" in turn_plan[0]["action"], f"ERROR: Expected Play Card action, got: {turn_plan[0]['action']}"

    print("\nPlays recommendations:")
    for p in recs.get("plays", []):
        card_names = [c["name"] for c in p.get("cards", [])]
        print(f"  - Score {p.get('score')}: {' + '.join(card_names)} | {p.get('reasoning')}")

    print("\n>>> TEST USER SCREENSHOT SCENARIO PASSED 100%! <<<")

if __name__ == "__main__":
    test_screenshot_state()
