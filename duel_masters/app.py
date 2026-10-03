"""Flask web application for Duel Masters Game Advisor."""

import json
import os
import sys

from flask import Flask, jsonify, render_template, request

# Ensure package imports work
sys.path.insert(0, os.path.dirname(__file__))

from models.card import Card, CardInstance
from models.enums import Ability, CardType, Civilization, GamePhase
from models.game_state import GameState, PlayerState
from engine.analyzer import BoardAnalyzer
from engine.advisor import GameAdvisor
from engine.deck_builder import DeckBuilderEngine
from engine.learning import LearningEngine

app = Flask(__name__)

# ── CORS: izinkan request dari duelonline.online & chrome-extension → localhost ──
@app.after_request
def add_cors(response):
    origin = request.headers.get('Origin', '')
    response.headers['Access-Control-Allow-Origin']  = origin or '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response

# ── Load card database ──────────────────────────────────
CARDS_DB: list[dict] = []
CARDS_BY_ID: dict[str, dict] = {}


def load_cards():
    global CARDS_DB, CARDS_BY_ID
    db_path = os.path.join(os.path.dirname(__file__), "data", "cards_db.json")
    with open(db_path, "r", encoding="utf-8") as f:
        CARDS_DB = json.load(f)
    CARDS_BY_ID = {c["id"]: c for c in CARDS_DB}


load_cards()

import re

def normalize_key(s: str) -> str:
    if not s:
        return ""
    s = s.lower().replace("_", " ").replace("-", " ").replace(",", " ").replace("'", "").replace("·", " ")
    return re.sub(r"\s+", " ", s).strip()


def find_card_in_db(name: str) -> dict | None:
    """Smart fuzzy/prefix/slug search for card in CARDS_DB."""
    if not name or name == "(Kartu)":
        return None
    name_clean = name.strip().lower()
    q_norm = normalize_key(name)
    q_alpha = re.sub(r"[^a-z0-9]", "", name.lower())

    # 1. Exact canonical name match
    for c in CARDS_DB:
        if c.get("name", "").lower() == name_clean:
            return c

    # 2. Exact normalized match
    for c in CARDS_DB:
        if normalize_key(c.get("name", "")) == q_norm:
            return c

    # 3. ID / slug match
    for c in CARDS_DB:
        c_id = c.get("id", "")
        if c_id.lower() == name_clean or normalize_key(c_id) == q_norm:
            return c

    # 4. Alphanumeric match (ignoring spaces, hyphens, punctuation)
    for c in CARDS_DB:
        c_alpha = re.sub(r"[^a-z0-9]", "", c.get("name", "").lower())
        if c_alpha == q_alpha:
            return c
        c_id_alpha = re.sub(r"[^a-z0-9]", "", c.get("id", "").lower())
        if c_id_alpha == q_alpha:
            return c

    # 5. Prefix match (e.g. 'la ura giga' matches 'la ura giga sky guardian')
    for c in CARDS_DB:
        c_norm = normalize_key(c.get("name", ""))
        c_prefix = normalize_key(c.get("name", "").split(",")[0])
        if c_norm.startswith(q_norm) or c_prefix == q_norm or (len(q_norm) >= 4 and q_norm.startswith(c_prefix)):
            return c

    # 6. Alphanumeric prefix
    for c in CARDS_DB:
        c_alpha = re.sub(r"[^a-z0-9]", "", c.get("name", "").lower())
        if c_alpha.startswith(q_alpha) and len(q_alpha) >= 4:
            return c

    # 7. Substring
    for c in CARDS_DB:
        if q_norm in normalize_key(c.get("name", "")):
            return c

    return None


def enrich_card_dict(card_data: dict) -> dict:
    """Enriches incomplete card data received from browser extension with cards_db.json."""
    if not isinstance(card_data, dict):
        return card_data
    name = card_data.get("name", "").strip()
    db_card = find_card_in_db(name)
    if not db_card and card_data.get("id"):
        db_card = find_card_in_db(card_data["id"]) or CARDS_BY_ID.get(card_data["id"])
    
    if db_card:
        enriched = dict(card_data)
        # Always use canonical attributes from cards_db.json
        enriched["name"] = db_card["name"]
        enriched["cost"] = db_card["cost"]
        if enriched.get("power") is None or enriched.get("power") == 0:
            enriched["power"] = db_card.get("power")
        enriched["effect_text"] = db_card.get("effect_text", "")
        enriched["abilities"] = db_card.get("abilities", [])
        race = db_card.get("race", [])
        if not race:
            temp_card = Card.from_dict(db_card)
            race = temp_card.effective_races
        enriched["race"] = race
        enriched["shield_trigger"] = db_card.get("shield_trigger", False)
        enriched["card_type"] = db_card.get("card_type", "CREATURE")
        enriched["civilization"] = db_card.get("civilization", ["FIRE"])
        if "is_playable" in card_data:
            enriched["is_playable"] = card_data["is_playable"]
        return enriched
    return card_data

learning_engine = LearningEngine()
analyzer = BoardAnalyzer(learning_engine=learning_engine)
advisor  = GameAdvisor(analyzer=analyzer, learning_engine=learning_engine)
deck_builder: DeckBuilderEngine | None = None  # initialized after DB load

def init_deck_builder():
    global deck_builder
    deck_builder = DeckBuilderEngine(CARDS_DB)

init_deck_builder()


# ── Routes ──────────────────────────────────────────────

@app.route('/api/<path:path>', methods=['OPTIONS'])
def preflight(path):
    return '', 204



@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/cards")
def get_cards():
    return jsonify(CARDS_DB)


@app.route("/api/cards/search")
def search_cards():
    q = request.args.get("q", "").lower().strip()
    if not q:
        return jsonify(CARDS_DB[:20])
    results = [c for c in CARDS_DB if q in c["name"].lower()]
    return jsonify(results[:20])


@app.route("/api/analyze", methods=["POST"])
def analyze():
    """Receive game state and return full analysis + recommendations."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    try:
        state = _build_game_state(data)
        recommendations = advisor.get_recommendations(state)
        return jsonify({
            "success": True,
            "recommendations": _serialize(recommendations),
        })
    except Exception as e:
        import traceback
        import json
        tb = traceback.format_exc()
        try:
            with open("crash_dump.json", "w") as f:
                json.dump(data, f, indent=2)
        except:
            pass
        return jsonify({"error": str(e), "traceback": tb}), 500


# ── Sync State ──────────────────────────────────────────
SYNCED_STATE = None

@app.route("/api/sync", methods=["GET", "POST"])
def sync_state():
    global SYNCED_STATE
    if request.method == "POST":
        # Extension sends data here
        data = request.get_json()
        if data:
            SYNCED_STATE = data
            return jsonify({"success": True, "message": "State synced"})
        return jsonify({"success": False, "error": "No data"}), 400
    else:
        # Frontend reads data from here
        return jsonify({"success": True, "state": SYNCED_STATE})

# ── Helpers ─────────────────────────────────────────────

def _parse_decklist(decklist_raw):
    """Parses decklist format like '4 Bombazar, Dragon of Destiny' into individual cards."""
    import re
    parsed = []
    if isinstance(decklist_raw, str):
        decklist_raw = decklist_raw.splitlines()
    for item in decklist_raw:
        item = str(item).strip()
        if not item or item.startswith(("#", "//")):
            continue
        match = re.match(r"^(\d+)\s*[xX*]?\s+(.+)$", item)
        if match:
            qty = int(match.group(1))
            name = match.group(2).strip()
            parsed.extend([name] * qty)
        else:
            parsed.append(item)
    return parsed


def _build_game_state(data: dict) -> GameState:
    """Build a GameState from the posted JSON with enriched card database properties."""
    player_data = data.get("player", {})
    opponent_data = data.get("opponent", {})

    player = PlayerState(
        name=player_data.get("name", "Player"),
        hand=[CardInstance.from_dict(enrich_card_dict(c)) for c in player_data.get("hand", [])],
        mana_zone=[CardInstance.from_dict(enrich_card_dict(c)) for c in player_data.get("mana_zone", [])],
        battle_zone=[CardInstance.from_dict(enrich_card_dict(c)) for c in player_data.get("battle_zone", [])],
        graveyard=[CardInstance.from_dict(enrich_card_dict(c)) for c in player_data.get("graveyard", [])],
        deck_count=player_data.get("deck_count", 30),
        shields_count=player_data.get("shields_count", 5),
    )

    opp_hand_size = opponent_data.get("hand_size", len(opponent_data.get("hand", [])))
    opponent = PlayerState(
        name=opponent_data.get("name", "Opponent"),
        hand=[CardInstance.from_dict(enrich_card_dict(c)) for c in opponent_data.get("hand", [])],
        mana_zone=[CardInstance.from_dict(enrich_card_dict(c)) for c in opponent_data.get("mana_zone", [])],
        battle_zone=[CardInstance.from_dict(enrich_card_dict(c)) for c in opponent_data.get("battle_zone", [])],
        graveyard=[CardInstance.from_dict(enrich_card_dict(c)) for c in opponent_data.get("graveyard", [])],
        deck_count=opponent_data.get("deck_count", 30),
        shields_count=opponent_data.get("shields_count", 5),
        hand_size_override=opp_hand_size,
    )

    # Parse decklist if provided (supports '4 Bombazar, Dragon of Destiny')
    decklist = _parse_decklist(player_data.get("decklist", []))

    # Map game phase names from duelonline to our enums
    phase_map = {
        "MANA": "CHARGE", "DRAW": "DRAW", "UNTAP": "UNTAP",
        "MAIN": "MAIN", "ATTACK": "ATTACK", "END": "END",
        "CHARGE": "CHARGE", "SUMMON": "MAIN", "BLOCK": "ATTACK",
    }
    raw_phase = data.get("current_phase", "MAIN").upper()
    mapped_phase = phase_map.get(raw_phase, "MAIN")

    active_prompt = data.get("active_prompt")

    return GameState(
        player=player,
        opponent=opponent,
        turn_number=data.get("turn_number", 1),
        current_phase=GamePhase(mapped_phase),
        is_player_turn=data.get("is_player_turn", True),
        can_charge_mana=data.get("can_charge_mana", True),
        decklist=decklist,
        active_prompt=active_prompt,
    )


def _serialize(obj):
    """Recursively convert any non-serializable objects."""
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serialize(i) for i in obj]
    if isinstance(obj, (Civilization, CardType, Ability, GamePhase)):
        return obj.value
    return obj


# ── Deck Builder Routes ─────────────────────────────────

@app.route("/api/deck/archetypes", methods=["GET"])
def api_deck_archetypes():
    """List all available deck archetypes."""
    try:
        archetypes = deck_builder.list_archetypes()
        return jsonify({"success": True, "archetypes": archetypes})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/deck/build", methods=["POST"])
def api_deck_build():
    """Build an optimized deck for the given archetype.
    POST body: { "archetype": "fire_nature_ramp" }
    """
    try:
        data = request.get_json() or {}
        archetype_key = data.get("archetype", "fire_nature_ramp")
        result = deck_builder.build_deck(archetype_key)
        return jsonify({"success": True, **result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/deck/analyze", methods=["POST"])
def api_deck_analyze():
    """Analyze an existing deck from a decklist string.
    POST body: { "decklist": "4 Bronze-Arm Tribe\\n4 Terror Pit\\n..." }
    """
    try:
        data = request.get_json() or {}
        decklist_text = data.get("decklist", "")
        # Parse decklist text into list of card names
        card_names = []
        for line in decklist_text.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("#"): continue
            import re
            m = re.match(r'^(\d+)\s*[xX*]?\s+(.+)$', line)
            if m:
                count = int(m.group(1))
                name  = m.group(2).strip()
                card_names.extend([name] * count)
            else:
                card_names.append(line)
        
        upgrade_suggestions = deck_builder.suggest_upgrades(card_names)
        
        # Also do a quick count analysis
        deck_counts = {}
        for name in card_names:
            deck_counts[name] = deck_counts.get(name, 0) + 1
        
        deck_list_formatted = {}
        for name, count in deck_counts.items():
            db_card = find_card_in_db(name) or {"name": name, "cost": 0}
            deck_list_formatted[name] = {"card": db_card, "count": count}
        
        # Use default archetype for analysis (best match)
        from engine.deck_builder import ARCHETYPES
        analysis = deck_builder.analyze_deck(deck_list_formatted, ARCHETYPES.get("fire_nature_ramp", list(ARCHETYPES.values())[0]))
        
        return jsonify({"success": True, "analysis": analysis, "upgrade_suggestions": upgrade_suggestions, "total_cards": len(card_names)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/deck/upgrade", methods=["POST"])
def api_deck_upgrade():
    """Suggest specific card upgrades for an existing deck.
    POST body: { "decklist": "4 Bronze-Arm Tribe\\n..." }
    """
    try:
        data = request.get_json() or {}
        decklist_text = data.get("decklist", "")
        card_names = []
        for line in decklist_text.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("#"): continue
            import re
            m = re.match(r'^(\d+)\s*[xX*]?\s+(.+)$', line)
            if m:
                count = int(m.group(1))
                name  = m.group(2).strip()
                card_names.extend([name] * count)
            else:
                card_names.append(line)
        
        result = deck_builder.suggest_upgrades(card_names)
        return jsonify({"success": True, **result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ── Continuous Learning & Meta Adaptation Routes ───────

@app.route("/api/learn/match", methods=["POST"])
def api_learn_match():
    """Process finished match result and evolve AI heuristics."""
    try:
        match_data = request.get_json() or {}
        summary = learning_engine.process_match_result(match_data)
        return jsonify({"success": True, **summary})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/learn/stats", methods=["GET"])
def api_learn_stats():
    """Retrieve full AI learning statistics and discovered meta insights."""
    try:
        stats = learning_engine.get_summary()
        return jsonify({"success": True, "data": stats})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/learn/reset", methods=["POST"])
def api_learn_reset():
    """Reset learned AI knowledge base to default."""
    try:
        from engine.learning import DEFAULT_KNOWLEDGE
        learning_engine.data = json.loads(json.dumps(DEFAULT_KNOWLEDGE))
        learning_engine.save()
        return jsonify({"success": True, "message": "Memori pembelajaran AI telah di-reset."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)

