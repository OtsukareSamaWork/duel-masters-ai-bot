import urllib.request
import json
import os
import re

url = 'https://raw.githubusercontent.com/Latepate64/duel-masters-json/master/DuelMastersCards.json'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
raw_data = json.loads(urllib.request.urlopen(req).read().decode('utf-8'))
source_cards = raw_data.get('cards', [])

our_db = []
for c in source_cards:
    name = c.get('name')
    civs = [civ.upper() for civ in c.get('civilizations', [])]
    cost = c.get('cost', 0)
    
    ctype = c.get('type', 'Creature').upper().replace(' ', '_')
    if 'EVOLUTION' in ctype:
        ctype = 'EVOLUTION_CREATURE'
    elif 'SPELL' in ctype:
        ctype = 'SPELL'
    elif 'CROSS_GEAR' in ctype:
        ctype = 'CROSS_GEAR'
    else:
        ctype = 'CREATURE'
        
    power = c.get('power')
    if isinstance(power, str):
        power_digits = re.sub(r'\D', '', power)
        power = int(power_digits) if power_digits else 0
        
    text = c.get('text', '')
    text_lower = text.lower()
    
    abilities = []
    
    # Simple keyword extraction (very basic)
    if 'blocker' in text_lower and ctype == 'CREATURE' and not text_lower.startswith('destroy'):
        if re.search(r'\bblocker\b', text.split('\n')[0].lower()):
            abilities.append('BLOCKER')
    if 'speed attacker' in text_lower: abilities.append('SPEED_ATTACKER')
    if 'double breaker' in text_lower: abilities.append('DOUBLE_BREAKER')
    if 'triple breaker' in text_lower: abilities.append('TRIPLE_BREAKER')
    if 'shield trigger' in text_lower: abilities.append('SHIELD_TRIGGER')
    if 'slayer' in text_lower: abilities.append('SLAYER')
    if "can't be blocked" in text_lower or 'cannot be blocked' in text_lower: abilities.append('UNBLOCKABLE')
    if 'power attacker' in text_lower: abilities.append('POWER_ATTACKER')
    if 'world breaker' in text_lower: abilities.append('WORLD_BREAKER')
    
    # Advanced abilities extraction
    if 'wave striker' in text_lower: abilities.append('WAVE_STRIKER')
    if 'stealth' in text_lower: abilities.append('STEALTH')
    if 'charger' in text_lower: abilities.append('CHARGER')
    if 'turbo rush' in text_lower: abilities.append('TURBO_RUSH')
    if 'silent skill' in text_lower: abilities.append('SILENT_SKILL')
    if 'survivor' in text_lower: abilities.append('SURVIVOR')
    if 'sympathy' in text_lower: abilities.append('SYMPATHY')
    if 'g-zero' in text_lower: abilities.append('G_ZERO')
    if 'meteorburn' in text_lower: abilities.append('METEORBURN')
    
    shield_trigger = 'SHIELD_TRIGGER' in abilities
    
    race = c.get('race')
    if isinstance(race, str):
        race = [r.strip() for r in race.split('/')]
    elif race is None:
        race = []
        
    rarity = 'Common'
    if c.get('printings'):
        rarity = c['printings'][0].get('rarity', 'Common')
        
    our_card = {
        'id': name.lower().replace(' ', '_').replace(',', '').replace("'", ""),
        'name': name,
        'civilization': civs,
        'cost': cost,
        'power': power,
        'card_type': ctype,
        'abilities': list(set(abilities)),
        'race': race,
        'effect_text': text,
        'shield_trigger': shield_trigger,
        'rarity': rarity
    }
    our_db.append(our_card)

output_path = os.path.join(os.path.dirname(__file__), 'duel_masters', 'data', 'cards_db.json')
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(our_db, f, indent=2)

print(f"Successfully converted and saved {len(our_db)} cards!")
