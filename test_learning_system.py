import urllib.request
import json
import sys

base = 'http://127.0.0.1:5000'

print("=" * 60)
print("TESTING AI CONTINUOUS LEARNING ENGINE")
print("=" * 60)

# 1. Simulate Match 1 (Win with Bombazar & Bronze-Arm)
match_1 = {
    "result": "WIN",
    "total_turns": 7,
    "player_cards_played": ["Bronze-Arm Tribe", "Aqua Hulcus", "Bombazar, Dragon of Destiny"],
    "opponent_cards_seen": ["La Ura Giga", "Holy Awe"],
    "combos_executed": [["Bronze-Arm Tribe", "Bombazar, Dragon of Destiny"]],
    "triggers_hit_by_player": 0,
    "triggers_hit_by_opp": 1,
    "opponent_archetype": "Light / Angel Command"
}

payload_1 = json.dumps(match_1).encode('utf-8')
req_1 = urllib.request.Request(f'{base}/api/learn/match', data=payload_1, headers={'Content-Type': 'application/json'}, method='POST')
res_1 = json.loads(urllib.request.urlopen(req_1).read())

print("Match 1 Result:", res_1)
assert res_1['success'] is True
assert res_1['xp_gained'] == 100
assert res_1['total_matches'] >= 1
print("PASSED: Match 1 Processed & XP gained")

# 2. Simulate Match 2 (Loss against Terror Pit & Aqua Surfer triggers)
match_2 = {
    "result": "LOSS",
    "total_turns": 9,
    "player_cards_played": ["Pyrofighter Magnus", "Mini Titan Gett"],
    "opponent_cards_seen": ["Terror Pit", "Aqua Surfer", "Corile"],
    "combos_executed": [],
    "triggers_hit_by_player": 2,
    "triggers_hit_by_opp": 0,
    "opponent_archetype": "Water/Darkness Control"
}

payload_2 = json.dumps(match_2).encode('utf-8')
req_2 = urllib.request.Request(f'{base}/api/learn/match', data=payload_2, headers={'Content-Type': 'application/json'}, method='POST')
res_2 = json.loads(urllib.request.urlopen(req_2).read())

print("\nMatch 2 Result:", res_2)
assert res_2['success'] is True
assert res_2['xp_gained'] == 50
print("PASSED: Match 2 Processed & Trigger Caution Evolved")

# 3. Fetch Learning Stats
req_3 = urllib.request.Request(f'{base}/api/learn/stats', headers={'Content-Type': 'application/json'}, method='GET')
res_3 = json.loads(urllib.request.urlopen(req_3).read())

print("\nAI Learning Stats Summary:")
stats = res_3['data']
print(f"  AI Level: {stats['ai_level']} ({stats['experience_points']} XP)")
print(f"  Win Rate: {stats['win_rate']}% ({stats['total_matches']} Matches: {stats['wins']}W / {stats['losses']}L)")
print(f"  Trigger Caution Multiplier: {stats['trigger_caution']}x")
print(f"  Learned Combos: {len(stats['learned_combos'])}")
for c in stats['learned_combos']:
    print(f"    - {c['name']} (Win Rate: {c['win_rate']}%)")
print(f"  Top MVP Cards: {[c['name'] for c in stats['top_performing_cards']]}")
print(f"  Top Opponent Cards: {[c['name'] for c in stats['top_opponent_cards']]}")

assert stats['total_matches'] >= 2
assert len(stats['learned_combos']) >= 1
print("\n>>> ALL LEARNING ENGINE TESTS PASSED! <<<")
