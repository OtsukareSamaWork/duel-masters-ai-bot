"""Test script for the simulation-based advisor."""
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

results = []

# TEST 1: Don't suicide into stronger enemy
print("=" * 60)
print("TEST 1: Attack phase - tapped 6000 enemy vs our 3000 creature")
state1 = GameState(
    turn_number=5, is_player_turn=True, current_phase=GamePhase.ATTACK,
    player=PlayerState(hand=[], mana_zone=[], battle_zone=[
        mkc('a1', 'Pyrofighter', 3, 3000, [Civilization.FIRE])
    ], shields_count=4),
    opponent=PlayerState(battle_zone=[
        mkc('e1', 'Bolshack Dragon', 6, 6000, [Civilization.FIRE], abilities=[Ability.DOUBLE_BREAKER], tapped=True)
    ], shields_count=3)
)
plan = advisor.plan_turn(state1)
print(f"Steps: {len(plan)}")
for s in plan:
    print(f"  {s['icon']} {s['action']}")
    print(f"     -> {s['detail'][:100]}")
assert len(plan) == 1, f"Expected 1 step, got {len(plan)}"
assert 'Bolshack' not in plan[0]['action'], 'FAIL: Recommended attacking stronger creature!'
print("PASSED: No suicide attack")
results.append("TEST 1: PASSED")

# TEST 2: Kill weaker tapped enemy
print()
print("=" * 60)
print("TEST 2: Our 6000 creature vs tapped 3000 enemy")
state2 = GameState(
    turn_number=5, is_player_turn=True, current_phase=GamePhase.ATTACK,
    player=PlayerState(hand=[], mana_zone=[], battle_zone=[
        mkc('a1', 'Bolshack Dragon', 6, 6000, [Civilization.FIRE], abilities=[Ability.DOUBLE_BREAKER])
    ], shields_count=4),
    opponent=PlayerState(battle_zone=[
        mkc('e1', 'Enemy Soldier', 3, 3000, [Civilization.FIRE], tapped=True)
    ], shields_count=3)
)
plan = advisor.plan_turn(state2)
print(f"Steps: {len(plan)}")
for s in plan:
    print(f"  {s['icon']} {s['action']}")
    print(f"     -> {s['detail'][:100]}")
assert len(plan) == 1
print("PASSED: Single action returned")
results.append("TEST 2: PASSED")

# TEST 3: Prioritize killing tapped Double Breaker (next-turn threat)
print()
print("=" * 60)
print("TEST 3: Kill tapped Double Breaker threatening our shields (2 left)")
state3 = GameState(
    turn_number=5, is_player_turn=True, current_phase=GamePhase.ATTACK,
    player=PlayerState(hand=[], mana_zone=[], battle_zone=[
        mkc('a1', 'Our Fighter', 5, 5000, [Civilization.FIRE])
    ], shields_count=2),
    opponent=PlayerState(battle_zone=[
        mkc('e1', 'Enemy Breaker', 5, 4000, [Civilization.WATER], abilities=[Ability.DOUBLE_BREAKER], tapped=True)
    ], shields_count=3)
)
plan = advisor.plan_turn(state3)
print(f"Steps: {len(plan)}")
for s in plan:
    print(f"  {s['icon']} {s['action']}")
    print(f"     -> {s['detail'][:120]}")
assert len(plan) == 1
assert 'Enemy Breaker' in plan[0]['action'], f"Expected to attack Enemy Breaker, got: {plan[0]['action']}"
print("PASSED: Killed the next-turn shield threat")
results.append("TEST 3: PASSED")

# TEST 4: Main phase - single best play
print()
print("=" * 60)
print("TEST 4: Main phase - only 1 play instruction")
state4 = GameState(
    turn_number=4, is_player_turn=True, current_phase=GamePhase.MAIN,
    player=PlayerState(hand=[
        mkc('h1', 'Aqua Hulcus', 3, 2000, [Civilization.WATER], sickness=True),
        mkc('h2', 'La Ura Giga', 1, 2000, [Civilization.LIGHT], sickness=True),
    ], mana_zone=[
        mkc('m1', 'M1', 1, 0, [Civilization.WATER]),
        mkc('m2', 'M2', 1, 0, [Civilization.WATER]),
        mkc('m3', 'M3', 1, 0, [Civilization.FIRE]),
    ], battle_zone=[], shields_count=5),
    opponent=PlayerState(battle_zone=[], shields_count=5)
)
plan = advisor.plan_turn(state4)
print(f"Steps: {len(plan)}")
for s in plan:
    print(f"  {s['icon']} {s['action']}")
    print(f"     -> {s['detail'][:100]}")
assert len(plan) == 1
print("PASSED: Single play decision returned")
results.append("TEST 4: PASSED")

# TEST 5: Charge phase - single decision
print()
print("=" * 60)
print("TEST 5: Charge phase - only 1 charge instruction")
state5 = GameState(
    turn_number=3, is_player_turn=True, current_phase=GamePhase.CHARGE,
    player=PlayerState(hand=[
        mkc('h1', 'Aqua Hulcus', 3, 2000, [Civilization.WATER], sickness=True),
        mkc('h2', 'Bronze-Arm Tribe', 3, 1000, [Civilization.NATURE], sickness=True),
        mkc('h3', 'La Ura Giga', 1, 2000, [Civilization.LIGHT], sickness=True),
    ], mana_zone=[
        mkc('m1', 'M1', 1, 0, [Civilization.WATER]),
        mkc('m2', 'M2', 1, 0, [Civilization.NATURE]),
    ], battle_zone=[], shields_count=5),
    opponent=PlayerState(battle_zone=[], shields_count=5)
)
plan = advisor.plan_turn(state5)
print(f"Steps: {len(plan)}")
for s in plan:
    print(f"  {s['icon']} {s['action']}")
    print(f"     -> {s['detail'][:100]}")
assert len(plan) == 1
print("PASSED: Single charge decision returned")
results.append("TEST 5: PASSED")

print()
print("=" * 60)
print("SUMMARY:")
for r in results:
    print(f"  {r}")
print("ALL TESTS PASSED!")
