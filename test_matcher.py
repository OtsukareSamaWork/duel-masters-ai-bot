import json
import re

with open('duel_masters/data/cards_db.json', 'r', encoding='utf-8') as f:
    db = json.load(f)

def normalize_key(s: str) -> str:
    if not s:
        return ""
    s = s.lower().replace("_", " ").replace("-", " ").replace(",", " ").replace("'", "").replace("·", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s

def find_card(query: str):
    if not query or query == "(Kartu)":
        return None
    q_norm = normalize_key(query)
    q_alpha = re.sub(r"[^a-z0-9]", "", query.lower())
    
    # 1. Exact canonical name match
    for c in db:
        if c["name"].lower() == query.strip().lower():
            return c
            
    # 2. Exact normalized match
    for c in db:
        if normalize_key(c["name"]) == q_norm:
            return c
            
    # 3. ID match
    for c in db:
        if c.get("id", "").lower() == query.strip().lower() or normalize_key(c.get("id", "")) == q_norm:
            return c
            
    # 4. Alphanumeric match (ignoring all spaces, hyphens, punctuation)
    for c in db:
        c_alpha = re.sub(r"[^a-z0-9]", "", c["name"].lower())
        if c_alpha == q_alpha:
            return c
        c_id_alpha = re.sub(r"[^a-z0-9]", "", c.get("id", "").lower())
        if c_id_alpha == q_alpha:
            return c

    # 5. Prefix match on normalized name (e.g. 'la ura giga' matches 'la ura giga sky guardian')
    for c in db:
        c_norm = normalize_key(c["name"])
        c_prefix = normalize_key(c["name"].split(",")[0])
        if c_norm.startswith(q_norm) or c_prefix == q_norm:
            return c

    # 6. Alphanumeric prefix
    for c in db:
        c_alpha = re.sub(r"[^a-z0-9]", "", c["name"].lower())
        if c_alpha.startswith(q_alpha) and len(q_alpha) >= 4:
            return c

    # 7. Substring
    for c in db:
        if q_norm in normalize_key(c["name"]):
            return c

    return None

test_names = [
    'la_ura_giga',
    'la_ura_giga_sky_guardian',
    'la-ura-giga-sky-guardian',
    'spiral_gate',
    'dia_nork_moonlight_guardian',
    'aqua_hulcus',
    'holy_awe',
    'brain_serum',
    'corile',
    'aqua_surfer',
    'alcadeias_lord_of_spirits',
    'La Ura Giga',
    'La Ura Giga, Sky Guardian',
    'Dia Nork, Moonlight Guardian',
    'bronzearmtribe',
    'bronze_arm_tribe',
    'bombazar',
    'bolshack'
]

for name in test_names:
    found = find_card(name)
    r = found["name"] if found else "NOT FOUND!"
    civ = found["civilization"] if found else "N/A"
    print(f"{name:30} -> {r:30} | {civ}")
