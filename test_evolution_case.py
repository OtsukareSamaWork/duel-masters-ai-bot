import json
import os
import sys

sys.path.insert(0, os.path.join(os.getcwd(), 'duel_masters'))
from duel_masters.app import app
from duel_masters.models.card import Card, CardInstance, can_evolve_on
from duel_masters.models.enums import Civilization, GamePhase, CardType
from duel_masters.models.game_state import GameState, PlayerState
from duel_masters.engine.advisor import GameAdvisor
import engine.rules as rules

def test_evolution_rules():
    print("============================================================")
    print("TESTING EVOLUTION VALIDATION RULES & ADVISOR")
    print("============================================================")

    # 1. Test case from User Screenshot:
    # Player has 7 mana, Alcadeias in hand, but ONLY Aqua Hulcus & Aqua Surfer on board (no Angel Command)
    raw_payload = {
        "turn_number": 9,
        "is_player_turn": True,
        "current_phase": "MAIN",
        "can_charge_mana": False,
        "player": {
            "name": "Player",
            "hand": [
                {"id": "alcadeias_lord_of_spirits", "name": "Alcadeias, Lord of Spirits", "cost": 6, "is_playable": False}
            ],
            "mana_zone": [
                {"id": "la_ura_giga_sky_guardian", "name": "La Ura Giga, Sky Guardian", "is_tapped": False},
                {"id": "aqua_hulcus", "name": "Aqua Hulcus", "is_tapped": False},
                {"id": "holy_awe", "name": "Holy Awe", "is_tapped": False},
                {"id": "dia_nork_moonlight_guardian", "name": "Dia Nork, Moonlight Guardian", "is_tapped": False},
                {"id": "brain_serum", "name": "Brain Serum", "is_tapped": False},
                {"id": "spiral_gate", "name": "Spiral Gate", "is_tapped": False},
                {"id": "aqua_surfer", "name": "Aqua Surfer", "is_tapped": False},
            ],
            "battle_zone": [
                {"id": "aqua_hulcus", "name": "Aqua Hulcus", "power": 2000, "is_tapped": False, "can_attack": False},
                {"id": "aqua_surfer", "name": "Aqua Surfer", "power": 2000, "is_tapped": False, "can_attack": True}
            ],
            "shields_count": 5,
            "deck_count": 21,
            "graveyard": [{"id": "la_ura_giga_sky_guardian", "name": "La Ura Giga, Sky Guardian"}]
        },
        "opponent": {
            "name": "AI Duelist",
            "hand_size": 2,
            "mana_zone": [
                {"id": "senatine_jade_tree", "name": "Senatine Jade Tree", "is_tapped": True}
            ],
            "battle_zone": [
                {"id": "senatine_jade_tree", "name": "Senatine Jade Tree", "power": 4000, "is_tapped": False, "can_attack": False},
                {"id": "dia_nork_moonlight_guardian", "name": "Dia Nork, Moonlight Guardian", "power": 5000, "is_tapped": False, "can_attack": False},
            ],
            "shields_count": 5,
            "deck_count": 24,
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
    print("Turn Plan Decision:", turn_plan[0]["action"])
    print("Turn Plan Detail:  ", turn_plan[0]["detail"])

    # MUST NOT recommend summoning Alcadeias!
    assert "Alcadeias" not in turn_plan[0]["action"], f"CRITICAL ERROR: AI still recommended Alcadeias without Angel Command on board! Got: {turn_plan[0]['action']}"
    print("PASSED: Alcadeias was properly blocked because no Angel Command exists on board!")

    # 2. Test case when Angel Command (e.g. Hanusa, Radiance Elemental) IS on board:
    raw_payload_with_angel = dict(raw_payload)
    raw_payload_with_angel["player"]["battle_zone"].append(
        {"id": "hanusa_radiance_elemental", "name": "Hanusa, Radiance Elemental", "power": 9500, "is_tapped": False, "can_attack": True}
    )

    resp2 = client.post("/api/analyze", json=raw_payload_with_angel)
    data2 = resp2.get_json()
    turn_plan2 = data2["recommendations"]["turn_plan"]
    print("\nTurn Plan with Angel Command on board:")
    print("Decision:", turn_plan2[0]["action"])
    print("Detail:  ", turn_plan2[0]["detail"])

    assert "Alcadeias" in turn_plan2[0]["action"], f"Expected Alcadeias to evolve onto Hanusa, got: {turn_plan2[0]['action']}"
    print("PASSED: Alcadeias evolved properly onto Hanusa when Angel Command exists!")

    # 3. Test case for other evolution creatures (Crystal Lancer onto Liquid People, Dual Fang onto Beast Folk, Ballom onto Demon Command)
    print("\nTesting other Evolution creatures:")
    evo_tests = [
        ("crystal_lancer", "Crystal Lancer", "aqua_hulcus", "Aqua Hulcus", True),
        ("crystal_lancer", "Crystal Lancer", "bronze_arm_tribe", "Bronze-Arm Tribe", False),
        ("fighter_dual_fang", "Fighter Dual Fang", "bronze_arm_tribe", "Bronze-Arm Tribe", True),
        ("fighter_dual_fang", "Fighter Dual Fang", "aqua_hulcus", "Aqua Hulcus", False),
        ("ballom_master_of_death", "Ballom, Master of Death", "zagaan_knight_of_darkness", "Zagaan, Knight of Darkness", True),
        ("ballom_master_of_death", "Ballom, Master of Death", "aqua_hulcus", "Aqua Hulcus", False),
    ]

    for evo_id, evo_name, base_id, base_name, should_pass in evo_tests:
        payload = {
            "turn_number": 10,
            "is_player_turn": True,
            "current_phase": "MAIN",
            "can_charge_mana": False,
            "player": {
                "name": "Player",
                "hand": [{"id": evo_id, "name": evo_name, "cost": 6}],
                "mana_zone": [
                    {"id": "holy_awe", "name": "Holy Awe", "is_tapped": False},
                    {"id": "aqua_hulcus", "name": "Aqua Hulcus", "is_tapped": False},
                    {"id": "bronze_arm_tribe", "name": "Bronze-Arm Tribe", "is_tapped": False},
                    {"id": "terror_pit", "name": "Terror Pit", "is_tapped": False},
                    {"id": "bolshack_dragon", "name": "Bolshack Dragon", "is_tapped": False},
                    {"id": "mana_6", "name": "Holy Awe", "is_tapped": False},
                    {"id": "mana_7", "name": "Holy Awe", "is_tapped": False},
                    {"id": "mana_8", "name": "Holy Awe", "is_tapped": False},
                ],
                "battle_zone": [{"id": base_id, "name": base_name, "power": 2000, "is_tapped": False}],
                "shields_count": 5
            },
            "opponent": {
                "name": "Opponent",
                "shields_count": 5,
                "battle_zone": []
            }
        }
        res = client.post("/api/analyze", json=payload).get_json()
        p = res["recommendations"]["turn_plan"][0]["action"]
        is_recommended = evo_name in p
        assert is_recommended == should_pass, f"Failed for {evo_name} on {base_name}: expected {should_pass}, got {is_recommended} ({p})"
        print(f"  ✓ {evo_name} on {base_name:28} -> {'EVOLVED!' if is_recommended else 'BLOCKED (Correct!)'}")

    print("\n>>> ALL EVOLUTION VALIDATION TESTS PASSED 100%! <<<")

if __name__ == "__main__":
    test_evolution_rules()
