import sys
sys.path.insert(0, 'duel_masters')
from models.game_state import GameState, PlayerState
from models.card import CardInstance, Card
from models.enums import Civilization, CardType, Ability, GamePhase
from engine.advisor import GameAdvisor

advisor = GameAdvisor()

def mkc(id, name, cost, power, civs, abilities=None, sickness=False, tapped=False):
    c = Card(id=id, name=name, cost=cost, power=power, civilization=civs, card_type=CardType.CREATURE, abilities=abilities or [])
    return CardInstance(c, summoning_sickness=sickness, is_tapped=tapped)

print("=" * 60)
print("TESTING FULL TURN STEP-BY-STEP PROGRESSION")
print("=" * 60)

# STEP 1: Turn Starts - Player has NOT charged mana yet
print("\n--- STEP 1: Turn Starts (Belum Charge Mana) ---")
state_step1 = GameState(
    turn_number=4, is_player_turn=True, current_phase=GamePhase.MAIN,
    can_charge_mana=True,
    player=PlayerState(
        hand=[
            mkc('h1', 'Aqua Hulcus', 3, 2000, [Civilization.WATER], sickness=True),
            mkc('h2', 'La Ura Giga', 1, 2000, [Civilization.LIGHT], sickness=True)
        ],
        mana_zone=[
            mkc('m1', 'M1', 1, 0, [Civilization.WATER]),
            mkc('m2', 'M2', 1, 0, [Civilization.WATER])
        ],
        battle_zone=[
            mkc('b1', 'Pyrofighter Magnus', 3, 3000, [Civilization.FIRE], abilities=[Ability.SPEED_ATTACKER])
        ],
        shields_count=5
    ),
    opponent=PlayerState(battle_zone=[], shields_count=5)
)

plan1 = advisor.plan_turn(state_step1)
print(f"Decision: {plan1[0]['icon']} {plan1[0]['action']}")
print(f"Detail:   {plan1[0]['detail']}")
assert len(plan1) == 1
assert 'Charge' in plan1[0]['action'], f"Expected Charge recommendation, got: {plan1[0]['action']}"
print("PASSED: Step 1 recommends Mana Charge")

# STEP 2: Player has charged mana (now 3 mana available), can play Aqua Hulcus
print("\n--- STEP 2: Player Sudah Charge Mana (Mainkan Kartu) ---")
state_step2 = GameState(
    turn_number=4, is_player_turn=True, current_phase=GamePhase.MAIN,
    can_charge_mana=False, # Already charged!
    player=PlayerState(
        hand=[
            mkc('h1', 'Aqua Hulcus', 3, 2000, [Civilization.WATER], sickness=True)
        ],
        mana_zone=[
            mkc('m1', 'M1', 1, 0, [Civilization.WATER]),
            mkc('m2', 'M2', 1, 0, [Civilization.WATER]),
            mkc('m3', 'La Ura Giga', 1, 0, [Civilization.LIGHT]) # Just charged
        ],
        battle_zone=[
            mkc('b1', 'Pyrofighter Magnus', 3, 3000, [Civilization.FIRE], abilities=[Ability.SPEED_ATTACKER])
        ],
        shields_count=5
    ),
    opponent=PlayerState(battle_zone=[], shields_count=5)
)

plan2 = advisor.plan_turn(state_step2)
print(f"Decision: {plan2[0]['icon']} {plan2[0]['action']}")
print(f"Detail:   {plan2[0]['detail']}")
assert len(plan2) == 1
assert 'Mainkan: Aqua Hulcus' in plan2[0]['action'], f"Expected Play Aqua Hulcus, got: {plan2[0]['action']}"
print("PASSED: Step 2 recommends Play Card")

# STEP 3: Card is played, mana is spent (0 available), Pyrofighter is ready to attack
print("\n--- STEP 3: Kartu Selesai Dimainkan (Serang Target Spesifik) ---")
state_step3 = GameState(
    turn_number=4, is_player_turn=True, current_phase=GamePhase.MAIN,
    can_charge_mana=False,
    player=PlayerState(
        hand=[],
        mana_zone=[
            mkc('m1', 'M1', 1, 0, [Civilization.WATER], tapped=True),
            mkc('m2', 'M2', 1, 0, [Civilization.WATER], tapped=True),
            mkc('m3', 'La Ura Giga', 1, 0, [Civilization.LIGHT], tapped=True)
        ],
        battle_zone=[
            mkc('b1', 'Pyrofighter Magnus', 3, 3000, [Civilization.FIRE], abilities=[Ability.SPEED_ATTACKER]),
            mkc('b2', 'Aqua Hulcus', 3, 2000, [Civilization.WATER], sickness=True) # Just summoned
        ],
        shields_count=5
    ),
    opponent=PlayerState(
        battle_zone=[
            mkc('e1', 'Locomotiver', 4, 4000, [Civilization.DARKNESS], tapped=True)
        ],
        shields_count=5
    )
)

plan3 = advisor.plan_turn(state_step3)
print(f"Decision: {plan3[0]['icon']} {plan3[0]['action']}")
print(f"Detail:   {plan3[0]['detail']}")
assert len(plan3) == 1
assert 'Shield Lawan' in plan3[0]['action'] or 'Pyrofighter' in plan3[0]['action'] or 'Attack Phase' in plan3[0]['action']
if 'Attack Phase' not in plan3[0]['action']:
    assert 'Locomotiver' not in plan3[0]['action'], "Must NOT suicide into 4000 power Locomotiver!"
print("PASSED: Step 3 recommends Attack Phase or Attack action")

# STEP 4: All attacks done (creature tapped)
print("\n--- STEP 4: Semua Serangan Selesai (End Turn) ---")
state_step4 = GameState(
    turn_number=4, is_player_turn=True, current_phase=GamePhase.MAIN,
    can_charge_mana=False,
    player=PlayerState(
        hand=[],
        mana_zone=[mkc('m1', 'M1', 1, 0, [Civilization.WATER], tapped=True)],
        battle_zone=[
            mkc('b1', 'Pyrofighter Magnus', 3, 3000, [Civilization.FIRE], tapped=True),
            mkc('b2', 'Aqua Hulcus', 3, 2000, [Civilization.WATER], sickness=True)
        ],
        shields_count=5
    ),
    opponent=PlayerState(battle_zone=[], shields_count=4)
)

plan4 = advisor.plan_turn(state_step4)
print(f"Decision: {plan4[0]['icon']} {plan4[0]['action']}")
print(f"Detail:   {plan4[0]['detail']}")
assert len(plan4) == 1
assert 'End Turn' in plan4[0]['action']
print("PASSED: Step 4 recommends End Turn")

print("\n>>> ALL 4 TURN PROGRESSION STEPS PASSED PERFECTLY! <<<")
