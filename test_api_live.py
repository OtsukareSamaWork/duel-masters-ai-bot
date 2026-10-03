import urllib.request
import json

base = 'http://127.0.0.1:5000'

# Test Combat Scenario 1: Pyrofighter (3000) vs Tapped Bolshack (6000)
# Expected: Do NOT attack Bolshack, attack shields or hold
combat_state_1 = {
    'turn_number': 5,
    'current_phase': 'ATTACK',
    'is_player_turn': True,
    'player': {
        'name': 'P', 'hand': [], 'mana_zone': [], 'graveyard': [],
        'battle_zone': [{
            'id': 'a1', 'name': 'Pyrofighter Magnus', 'cost': 3, 'power': 3000,
            'card_type': 'CREATURE', 'civilization': ['FIRE'], 'abilities': ['SPEED_ATTACKER'],
            'can_attack': True, 'is_tapped': False
        }],
        'shields_count': 4, 'deck_count': 25
    },
    'opponent': {
        'name': 'O', 'hand': [], 'mana_zone': [], 'graveyard': [],
        'battle_zone': [{
            'id': 'e1', 'name': 'Bolshack Dragon', 'cost': 6, 'power': 6000,
            'card_type': 'CREATURE', 'civilization': ['FIRE'], 'abilities': ['DOUBLE_BREAKER'],
            'can_attack': False, 'is_tapped': True
        }],
        'shields_count': 3, 'deck_count': 25
    }
}

payload_1 = json.dumps(combat_state_1).encode('utf-8')
req_1 = urllib.request.Request(f'{base}/api/analyze', data=payload_1, headers={'Content-Type': 'application/json'}, method='POST')
res_1 = json.loads(urllib.request.urlopen(req_1).read())

assert res_1['success'] is True
tp_1 = res_1['recommendations']['turn_plan']
print("Test 1 Turn Plan Steps:", len(tp_1))
print("Action 1:", tp_1[0]['icon'], tp_1[0]['action'])
print("Detail 1:", tp_1[0]['detail'])
assert len(tp_1) == 1, "Must return exactly 1 step!"
assert 'Bolshack' not in tp_1[0]['action'], "Must NOT attack stronger creature!"

# Test Combat Scenario 2: Bolshack (6000) vs Tapped Enemy Breaker (4000) threatening shields
# Expected: Attack Enemy Breaker to protect shields next turn
combat_state_2 = {
    'turn_number': 5,
    'current_phase': 'ATTACK',
    'is_player_turn': True,
    'player': {
        'name': 'P', 'hand': [], 'mana_zone': [], 'graveyard': [],
        'battle_zone': [{
            'id': 'a1', 'name': 'Bolshack Dragon', 'cost': 6, 'power': 6000,
            'card_type': 'CREATURE', 'civilization': ['FIRE'], 'abilities': ['DOUBLE_BREAKER'],
            'can_attack': True, 'is_tapped': False
        }],
        'shields_count': 2, 'deck_count': 25
    },
    'opponent': {
        'name': 'O', 'hand': [], 'mana_zone': [], 'graveyard': [],
        'battle_zone': [{
            'id': 'e1', 'name': 'Corile', 'cost': 5, 'power': 2000,
            'card_type': 'CREATURE', 'civilization': ['WATER'], 'abilities': [],
            'can_attack': False, 'is_tapped': True
        }],
        'shields_count': 3, 'deck_count': 25
    }
}

payload_2 = json.dumps(combat_state_2).encode('utf-8')
req_2 = urllib.request.Request(f'{base}/api/analyze', data=payload_2, headers={'Content-Type': 'application/json'}, method='POST')
res_2 = json.loads(urllib.request.urlopen(req_2).read())

assert res_2['success'] is True
tp_2 = res_2['recommendations']['turn_plan']
print("\nTest 2 Turn Plan Steps:", len(tp_2))
print("Action 2:", tp_2[0]['icon'], tp_2[0]['action'])
print("Detail 2:", tp_2[0]['detail'])
assert len(tp_2) == 1, "Must return exactly 1 step!"
assert 'Corile' in tp_2[0]['action'] or 'Serang' in tp_2[0]['action']

print("\n>>> ALL API TESTS PASSED SUCCESSFULLY! <<<")
