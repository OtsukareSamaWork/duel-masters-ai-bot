import json

with open('duel_masters/data/cards_db.json', 'r', encoding='utf-8') as f:
    cards = json.load(f)

for civ in ["FIRE", "NATURE", "WATER", "DARKNESS", "LIGHT"]:
    civ_cards = [c for c in cards if civ in c.get("civilization", [])]
    print(f"\n=== {civ} ({len(civ_cards)} cards) ===")
    for c in sorted(civ_cards, key=lambda x: (x.get("cost", 0), x.get("name", ""))):
        tr = " [ST]" if c.get("shield_trigger") else ""
        pw = f" ({c.get('power')}pw)" if c.get("power") else ""
        print(f"  Cost {c.get('cost')}: {c.get('name')}{pw}{tr} - {', '.join(c.get('abilities', []))}")
