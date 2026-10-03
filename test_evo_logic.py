import json
import re

with open('duel_masters/data/cards_db.json', 'r', encoding='utf-8') as f:
    db = json.load(f)

def get_evolution_requirements(card: dict) -> list[str]:
    txt = card.get('effect_text', '').lower()
    ctype = card.get('card_type', '')
    
    # Check if evolution creature
    is_evo = (ctype == 'EVOLUTION_CREATURE') or ('evolution' in txt)
    if not is_evo:
        return []
        
    # Check standard evolution: 'put on one of your <race>'
    m = re.search(r'put on (?:one|1) of your (.*?)(?:\.|\n|$)', txt)
    if m:
        raw_race = m.group(1).strip()
        return [raw_race]
        
    # Check vortex evolution: 'put on 2 of your <races>'
    m_vortex = re.search(r'put on 2 of your (.*?)(?:\.|\n|$)', txt)
    if m_vortex:
        return [m_vortex.group(1).strip()]
        
    return []

def matches_race(creature_races: list[str], required_base: str) -> bool:
    """Check if creature's race satisfies the evolution base requirement."""
    req = required_base.lower().strip()
    # Normalize plural forms (e.g. 'angel commands' -> 'angel command', 'humans' -> 'human')
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

evos = [c for c in db if c.get('card_type') == 'EVOLUTION_CREATURE' or 'evolution' in c.get('effect_text', '').lower()]
print(f"Total evolution cards: {len(evos)}")
for c in evos:
    reqs = get_evolution_requirements(c)
    if not reqs:
        print(f"NO REQ: {c['name']:35} -> Type: {c.get('card_type')} | Text: {repr(c.get('effect_text'))}")

