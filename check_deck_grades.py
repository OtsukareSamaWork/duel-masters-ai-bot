import sys
sys.path.insert(0, 'duel_masters')
import json
from engine.deck_builder import DeckBuilderEngine, ARCHETYPES

with open('duel_masters/data/cards_db.json', 'r', encoding='utf-8') as f:
    cards = json.load(f)

engine = DeckBuilderEngine(cards)

for key in ARCHETYPES:
    d = engine.build_deck(key)
    a = d.get('analysis', {})
    print(f"Archetype: {key:25} -> Grade: {a.get('grade')} ({a.get('grade_score')}/100), Avg Cost: {a.get('average_cost')}, Triggers: {a.get('shield_triggers')}, Finishers: {a.get('finishers')}, Cards: {d.get('total_cards')}")
    if a.get('tips'):
        print(f"   Tips: {a.get('tips')}")
