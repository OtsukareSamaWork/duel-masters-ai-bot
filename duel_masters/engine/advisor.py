"""AI advisor for Duel Masters game decisions with Deep Simulation, Combo Detection, and Effect Resolution."""

from __future__ import annotations

import re
from itertools import combinations
from typing import Optional

from models.card import CardInstance, can_evolve_on
from models.enums import Ability, CardType, GamePhase
from models.game_state import GameState
from engine.analyzer import BoardAnalyzer
import engine.rules as rules


class GameAdvisor:
    """Provides advanced strategic recommendations for Duel Masters gameplay with Continuous Learning AI."""

    def __init__(self, analyzer: Optional[BoardAnalyzer] = None, learning_engine = None):
        self.learning_engine = learning_engine
        self.analyzer = analyzer or BoardAnalyzer(learning_engine=learning_engine)

    def get_recommendations(self, state: GameState) -> dict:
        board_analysis = self.analyzer.evaluate_board(state)
        recs = {
            "board_analysis": board_analysis,
            "mana_charge": self.recommend_mana_charge(state),
            "plays": self.recommend_plays(state),
            "attacks": self.recommend_attacks(state),
            "overall_strategy": self.recommend_strategy(state),
            "combos": self.find_combos(state),
            "turn_plan": self.plan_turn(state),
        }
        # Evaluasi pilihan efek aktif jika game sedang membuka dialog/pilihan
        if state.active_prompt:
            recs["active_effect"] = self.recommend_effect_choice(state)

        # Add draw probabilities if decklist is available
        draw_probs = state.get_draw_probabilities(top_n=5)
        if draw_probs:
            recs["draw_probabilities"] = draw_probs
            remaining = state.get_remaining_deck()
            recs["deck_remaining"] = len(remaining)
        return recs

    def _get_needed_evolution_bases(self, state: GameState) -> set[str]:
        """Evolution Logic: Detects what races we need to keep alive for evolution cards in hand."""
        needed = set()
        for c in state.player.hand:
            if c.card.card_type == CardType.EVOLUTION_CREATURE or 'evolution' in c.card.effect_text.lower():
                match = re.search(r'put on one of your (.*?)\.', c.card.effect_text.lower())
                if match:
                    race = match.group(1).strip()
                    needed.add(race)
        return needed

    # ── Active Effect Choice Advisor ────────────────────────

    def recommend_effect_choice(self, state: GameState) -> dict:
        """Advises the player what card or action to pick in an active game prompt/modal with deep card effect comprehension."""
        prompt = state.active_prompt or {}
        src = prompt.get("source", "")
        title = prompt.get("title", "Pilihan Efek Aktif")
        instruction = prompt.get("instruction", "")
        options = prompt.get("options", [])
        src_lower = src.lower()
        instr_lower = instruction.lower()

        # ── 1. NO OPTIONS MODAL: TARGETING ON BATTLE ZONE ──
        if not options:
            # Check if effect targets our OWN creature (e.g., Rothus, sacrifice, bounce to hand)
            is_friendly_target = any(k in src_lower for k in ["rothus", "vashuna", "aqua soldier", "emeral"]) or (
                any(k in instr_lower for k in ["your creature", "creature you control", "destroy 1 of your", "destroy one of your"])
                and not any(k in instr_lower for k in ["opponent", "enemy"])
            )

            if is_friendly_target and state.player.battle_zone:
                # Rank friendly creatures from LOWEST value to HIGHEST value for sacrifice
                friendly_candidates = []
                evo_bases = self._get_needed_evolution_bases(state)
                ws_count = sum(1 for c in state.player.battle_zone if "WAVE_STRIKER" in c.card.abilities)

                for fc in state.player.battle_zone:
                    # Lower value = better to sacrifice
                    val = (fc.current_power / 1000.0)
                    reason = f"Korbankan creature terkecil ({fc.current_power}⚔)"
                    
                    if fc.is_tapped:
                        val -= 2.0  # Tapped is already vulnerable
                        reason += " [Sudah Tapped]"
                    if fc.summoning_sickness and not fc.card.has_speed_attacker:
                        val -= 1.0  # Cannot attack anyway this turn
                    
                    # Penalties for sacrificing important pieces:
                    if any(r.lower() in [eb.lower() for eb in evo_bases] for r in fc.card.race):
                        val += 50.0  # NEVER sacrifice evolution base!
                    if "WAVE_STRIKER" in fc.card.abilities and ws_count <= 3:
                        val += 30.0  # Protect Wave Striker formation!
                    if fc.card.has_blocker and state.player.shields_count <= 2:
                        val += 20.0  # Protect Blocker when shields low!
                    if any(k in fc.name.lower() for k in ["bolmeteus", "bombazar", "alcadeias", "ballom"]):
                        val += 100.0 # NEVER sacrifice finisher!

                    friendly_candidates.append({
                        "id": fc.instance_id,
                        "name": fc.name,
                        "score": -val,  # Higher score = recommended sacrifice
                        "reason": reason
                    })

                friendly_candidates.sort(key=lambda x: x["score"], reverse=True)
                best_fc = friendly_candidates[0]
                return {
                    "source": src,
                    "title": title,
                    "instruction": instruction or f"Pilih creature sendiri untuk efek {src}",
                    "recommended_pick": f"Korbankan: {best_fc['name']}",
                    "reason": best_fc["reason"],
                    "priority": "TERTINGGI",
                    "ranked_options": friendly_candidates[:4]
                }

            # Otherwise, target enemy creature on battle zone
            if state.opponent.battle_zone:
                enemy_candidates = []
                is_untapped_only = "untapped" in instr_lower or "death smoke" in src_lower
                power_cap = 99999
                if "crimson hammer" in src_lower or "phantom dragon" in src_lower:
                    power_cap = 2000
                elif "tornado flame" in src_lower:
                    power_cap = 4000
                elif "searing wave" in src_lower:
                    power_cap = 3000

                for ec in state.opponent.battle_zone:
                    if is_untapped_only and ec.is_tapped:
                        continue
                    if ec.current_power > power_cap:
                        continue

                    danger = self.analyzer._calculate_danger(ec, state)
                    score = danger["score"] * 3.0 + (ec.current_power / 1000.0)
                    if ec.card.has_blocker and state.opponent.shields_count <= 2:
                        score += 5.0  # Blocker priority for lethal
                    if "WAVE_STRIKER" in ec.card.abilities or "SURVIVOR" in ec.card.abilities:
                        score += 8.0  # Disrupt enemy synergy!

                    reason = f"Singkirkan ancaman level {danger['level']} ({ec.current_power}⚔)"
                    enemy_candidates.append({
                        "id": ec.instance_id,
                        "name": ec.name,
                        "score": score,
                        "reason": reason
                    })

                if enemy_candidates:
                    enemy_candidates.sort(key=lambda x: x["score"], reverse=True)
                    best_enemy = enemy_candidates[0]
                    action_verb = "Singkirkan"
                    if any(k in src_lower for k in ["terror pit", "destroy", "death smoke", "pit", "hammer", "flame"]):
                        action_verb = "Hancurkan"
                    elif any(k in src_lower for k in ["surfer", "spiral", "return", "bounce", "teleportation"]):
                        action_verb = "Pantulkan (Bounce)"
                    elif "corile" in src_lower:
                        action_verb = "Kunci ke Deck"
                    elif any(k in src_lower for k in ["tap", "solar", "holy awe"]):
                        action_verb = "Tap"
                    elif "snare" in src_lower:
                        action_verb = "Kirim ke Mana"

                    return {
                        "source": src,
                        "title": title,
                        "instruction": instruction or f"Pilih target lawan untuk {src}",
                        "recommended_pick": f"{action_verb}: {best_enemy['name']}",
                        "reason": best_enemy["reason"],
                        "priority": "TERTINGGI",
                        "ranked_options": enemy_candidates[:4]
                    }

            if prompt.get("has_yes_no"):
                return {
                    "source": src,
                    "title": title,
                    "instruction": instruction,
                    "recommended_pick": "YA / AKTIFKAN",
                    "reason": "Gunakan efek gratis ini untuk mendapatkan keunggulan tempo dan kartu!",
                    "priority": "TERTINGGI"
                }

            return {
                "source": src,
                "title": title,
                "instruction": instruction,
                "recommended_pick": "Lanjutkan Pilihan",
                "reason": "Selesaikan efek yang sedang berlangsung di layar.",
                "priority": "SEDANG"
            }

        # ── 2. OPTIONS PROVIDED (SELECTION MODAL) ──
        scored_options = []
        is_graveyard_retrieval = any(k in src_lower for k in ["turnip", "reversal", "medicine", "graveyard", "return a creature from your graveyard"]) or "graveyard" in instr_lower
        is_tutor_search = any(k in src_lower for k in ["dimension gate", "totem", "logic", "search", "deck"]) or "deck" in instr_lower
        ws_count = sum(1 for c in state.player.battle_zone if "WAVE_STRIKER" in c.card.abilities)

        for opt in options:
            opt_name = opt.get("name", "")
            name_lower = opt_name.lower()
            score = 0.0
            reasons = []

            # Shield Trigger & Mandatory usage
            if "summon for free" in name_lower or "use it now" in name_lower or "cast for free" in name_lower or "use" in name_lower:
                score += 50.0
                reasons.append("Aktifkan Shield Trigger gratis untuk membalikkan keadaan!")
            elif "keep in hand" in name_lower:
                score -= 10.0
                reasons.append("Jangan simpan di tangan jika bisa digunakan gratis!")

            # Check if options are graveyard cards
            if is_graveyard_retrieval:
                if any(k in name_lower for k in ["kilstine", "bolmeteus", "bombazar", "alcadeias", "ballom"]):
                    score += 25.0
                    reasons.append("Ambil kembali FINISHER utama duel dari graveyard!")
                elif any(k in name_lower for k in ["terror pit", "aqua surfer", "holy awe"]):
                    score += 18.0
                    reasons.append("Ambil kembali removal/blocker krusial")
                elif any(k in name_lower for k in ["turnip", "merlee", "adomis", "wave striker"]):
                    score += 20.0 if ws_count < 3 else 12.0
                    reasons.append("Ambil Wave Striker untuk melengkapi formasi!")
                else:
                    score += 8.0
                    reasons.append("Kembalikan creature ke tangan")

            # Check if options are search/tutor cards from deck
            elif is_tutor_search:
                if state.opponent.battle_zone and len(state.opponent.battle_zone) >= 2:
                    if any(k in name_lower for k in ["terror pit", "aqua surfer", "holy awe"]):
                        score += 22.0
                        reasons.append("Cari removal untuk membersihkan board lawan!")
                if state.opponent.shields_count <= 2:
                    if any(k in name_lower for k in ["bombazar", "bolmeteus", "twin-cannon", "speed"]):
                        score += 25.0
                        reasons.append("Cari finisher mematikan penentu lethal!")
                if ws_count == 2 and any(k in name_lower for k in ["kilstine", "merlee", "turnip", "wave striker"]):
                    score += 24.0
                    reasons.append("Cari Wave Striker ke-3 untuk memicu formasi super!")

            # Check if option is an opponent creature on board (removal target)
            matching_enemy = next((c for c in state.opponent.battle_zone if c.name.lower() in name_lower or name_lower in c.name.lower()), None)
            if matching_enemy:
                danger = self.analyzer._calculate_danger(matching_enemy, state)
                score += danger["score"] * 3.0
                reasons.append(f"Singkirkan ancaman level {danger['level']} ({matching_enemy.current_power}⚔)")

            # Check card archetype weights
            if any(k in name_lower for k in ["bombazar", "bolmeteus", "alcadeias", "ballom", "twin-cannon"]):
                score += 15.0
                reasons.append("Finisher penentu kemenangan")
            elif any(k in name_lower for k in ["aqua surfer", "terror pit", "holy awe", "corile"]):
                score += 12.0
                reasons.append("Kartu removal/penyelamat terbaik")
            elif any(k in name_lower for k in ["kilstine", "merlee", "turnip"]):
                score += 14.0
                reasons.append("Sinergi Wave Striker")
            elif any(k in name_lower for k in ["crystal lancer", "fighter dual fang", "barkwhip"]):
                score += 10.0
                reasons.append("Kartu evolusi penekan lawan")
            elif any(k in name_lower for k in ["bronze-arm", "faerie life"]):
                score += 8.0 if state.turn_number <= 4 else 3.0
                reasons.append("Ramp mana untuk akselerasi kurva")
            elif any(k in name_lower for k in ["aqua hulcus", "brain serum", "energy stream"]):
                score += 8.0
                reasons.append("Draw engine kartu")

            if not score:
                score = 5.0
                reasons.append("Opsi kartu solid")

            scored_options.append({
                "id": opt.get("id"),
                "name": opt_name,
                "score": score,
                "reason": " + ".join(reasons) if reasons else "Opsi kartu"
            })

        scored_options.sort(key=lambda x: x["score"], reverse=True)
        best = scored_options[0]

        return {
            "source": src,
            "title": title,
            "instruction": instruction,
            "recommended_pick": best["name"],
            "reason": best["reason"],
            "priority": "TERTINGGI",
            "ranked_options": scored_options[:4]
        }

    # ── Combo Detection Engine ──────────────────────────────

    def find_combos(self, state: GameState) -> list[dict]:
        """Identifies synergistic combos available in player's current hand and board with step-by-step execution order."""
        combos = []
        p_hand = state.player.hand
        p_board = state.player.battle_zone
        p_mana = state.player.available_mana
        opp_shields = state.opponent.shields_count
        opp_board = state.opponent.battle_zone

        # 1. Evolution Combos
        for h in p_hand:
            if h.card.card_type == CardType.EVOLUTION_CREATURE or "evolution" in h.card.effect_text.lower():
                evo_races = h.card.race
                matching_bases = [b for b in p_board if any(r.lower() in [er.lower() for er in evo_races] for r in b.card.race)]
                if matching_bases:
                    base = matching_bases[0]
                    base_name = base.name
                    can_afford = h.card.cost <= p_mana
                    
                    steps = [
                        f"1. Pastikan mana tersedia {h.card.cost} (Tersedia: {p_mana}).",
                        f"2. Drag {h.name} dari tangan dan letakkan tepat di atas {base_name}.",
                        f"3. Creature evolusi tidak terpengaruh summoning sickness: langsung serang Shield lawan atau creature ter-tap!"
                    ]
                    
                    combos.append({
                        "name": f"Evolusi: {h.name}",
                        "cards": [base_name, h.name],
                        "icon": "🌟",
                        "status": "SIAP DIMAINKAN!" if can_afford else f"Butuh {h.card.cost} Mana (Tersedia {p_mana})",
                        "can_execute_now": can_afford,
                        "description": f"Tumpuk {h.name} di atas {base_name}! Menyerang seketika dengan Double/Triple Breaker.",
                        "steps": steps
                    })

        # 2. Tap & Kill Combat Combo
        tap_cards = [c for c in p_hand if any(k in c.card.effect_text.lower() for k in ["tap all", "tap one", "tap 1"])]
        strong_attackers = [c for c in p_board if c.can_attack]
        if tap_cards and strong_attackers and opp_board:
            tap_spell = tap_cards[0]
            attacker = max(strong_attackers, key=lambda c: c.attack_power)
            biggest_enemy = max(opp_board, key=lambda c: c.current_power)
            can_afford = tap_spell.card.cost <= p_mana
            
            steps = [
                f"1. Cast {tap_spell.name} (Cost {tap_spell.card.cost}) untuk men-tap {biggest_enemy.name}.",
                f"2. Pilih {attacker.name} ({attacker.attack_power}⚔) yang siap menyerang di battle zone.",
                f"3. Serang {biggest_enemy.name} yang ter-tap dan musnahkan tanpa memberi lawan shield trigger!"
            ]

            combos.append({
                "name": "Tap & Tabrak (Board Clear)",
                "cards": [tap_spell.name, attacker.name],
                "icon": "⚔️",
                "status": "SIAP DIMAINKAN!" if can_afford else f"Butuh {tap_spell.card.cost} Mana",
                "can_execute_now": can_afford,
                "description": f"Tap {biggest_enemy.name} lalu tabrak dengan {attacker.name}!",
                "steps": steps
            })

        # 3. Corile Deck-Lock Combo
        coriles = [c for c in p_hand if "on top of his deck" in c.card.effect_text.lower() or c.name.lower() == "corile"]
        if coriles and opp_board:
            corile = coriles[0]
            biggest_opp = max(opp_board, key=lambda c: c.current_power)
            can_afford = corile.card.cost <= p_mana
            
            steps = [
                f"1. Summon {corile.name} (Cost {corile.card.cost}) ke battle zone.",
                f"2. Saat jendela pilihan efek muncul di layar, pilih {biggest_opp.name}.",
                f"3. {biggest_opp.name} terlempar ke atas deck lawan. Giliran berikutnya lawan terpaksa draw kartu itu lagi!"
            ]

            combos.append({
                "name": "Deck-Lock (Corile)",
                "cards": [corile.name, biggest_opp.name],
                "icon": "🔒",
                "status": "SIAP DIMAINKAN!" if can_afford else f"Butuh {corile.card.cost} Mana",
                "can_execute_now": can_afford,
                "description": f"Kirim {biggest_opp.name} ke atas deck lawan untuk mengunci draw mereka!",
                "steps": steps
            })

        # 4. Speed Attacker Rush to Lethal
        speed_attackers = [c for c in p_hand if c.card.has_speed_attacker]
        if speed_attackers and opp_shields <= 2:
            sp_card = speed_attackers[0]
            can_afford = sp_card.card.cost <= p_mana
            
            steps = [
                f"1. Bayar {sp_card.card.cost} mana dan summon {sp_card.name}.",
                f"2. Karena Speed Attacker, langsung drag {sp_card.name} ke Shield musuh.",
                f"3. Jika semua shield habis, serang langsung Player lawan untuk menang!"
            ]

            combos.append({
                "name": "Speed Attacker Lethal Push",
                "cards": [sp_card.name],
                "icon": "⚡",
                "status": "SIAP DIMAINKAN!" if can_afford else f"Butuh {sp_card.card.cost} Mana",
                "can_execute_now": can_afford,
                "description": f"Panggil {sp_card.name} dan serang seketika untuk mengakhiri duel!",
                "steps": steps
            })

        # 5. Hand Destruction Lock (Cranium Clamp / Discard)
        clamps = [c for c in p_hand if "discards 2 cards" in c.card.effect_text.lower() or c.name.lower() == "cranium clamp"]
        if clamps and state.opponent.hand_size >= 2:
            clamp = clamps[0]
            can_afford = clamp.card.cost <= p_mana
            
            steps = [
                f"1. Cast {clamp.name} (Cost {clamp.card.cost}) SEBELUM menyerang shield.",
                f"2. Musuh wajib membuang 2 kartu dari tangan mereka ke graveyard.",
                f"3. Tangan musuh terkuras habis, mencegah mereka merespons giliran depan!"
            ]

            combos.append({
                "name": "Hand Destruction Lock",
                "cards": [clamp.name],
                "icon": "🖐️",
                "status": "SIAP DIMAINKAN!" if can_afford else f"Butuh {clamp.card.cost} Mana",
                "can_execute_now": can_afford,
                "description": f"Kuras 2 kartu tangan musuh dengan {clamp.name}!",
                "steps": steps
            })

        # 6. Ramp into Big Bomb Curve
        ramp_cards = [c for c in p_hand if any(k in c.card.effect_text.lower() for k in ["into your mana zone", "into mana zone"])]
        bombs = [c for c in p_hand if c.card.cost >= state.player.total_mana + 2]
        if ramp_cards and bombs and state.player.total_mana <= 5:
            ramp = ramp_cards[0]
            bomb = bombs[0]
            can_afford = ramp.card.cost <= p_mana
            
            steps = [
                f"1. Mainkan {ramp.name} turn ini untuk menambah 1 mana dari deck.",
                f"2. Tahan {bomb.name} (Cost {bomb.card.cost}) di tangan, JANGAN di-charge!",
                f"3. Turn depan Anda bisa memanggil {bomb.name} 1 turn lebih awal dari normal!"
            ]

            combos.append({
                "name": f"Kurva Ramp ➔ {bomb.name}",
                "cards": [ramp.name, bomb.name],
                "icon": "🌱",
                "status": "SIAP DIMAINKAN!" if can_afford else f"Butuh {ramp.card.cost} Mana",
                "can_execute_now": can_afford,
                "description": f"Akselerasi mana dengan {ramp.name} untuk mempercepat pemanggilan {bomb.name}!",
                "steps": steps
            })

        # 5. Dynamically Learned Combos from Past Matches
        if self.learning_engine and hasattr(self.learning_engine, "data"):
            hand_names = {c.name.lower() for c in p_hand}
            for l_combo in self.learning_engine.data.get("learned_combos", []):
                req_cards = [n.lower() for n in l_combo.get("cards", [])]
                if all(any(req in hn for hn in hand_names) for req in req_cards):
                    combos.append({
                        "name": f"🧠 {l_combo['name']}",
                        "cards": l_combo.get("cards", []),
                        "icon": "💡",
                        "status": f"DIPELAJARI (Win Rate {l_combo.get('win_rate', 100)}%)",
                        "can_execute_now": True,
                        "description": f"Kombo hasil adaptasi duel sebelumnya! Berhasil {l_combo.get('wins', 1)}x dari {l_combo.get('times_seen', 1)} duel.",
                        "steps": [f"{i+1}. Mainkan {c}." for i, c in enumerate(l_combo.get("cards", []))]
                    })

        return combos[:4]

    # ── Mana Charge ──────────────────────────────────────────

    def recommend_mana_charge(self, state: GameState) -> dict:
        hand = state.player.hand
        if not hand:
            return {"action": "SKIP", "reason": "Tidak ada kartu di tangan.", "card": None, "alternatives": []}

        scored: list[tuple[CardInstance, float, str]] = []
        p_mana = state.player.total_mana
        
        # Cari tahu kebutuhan cost turn depan (Mana Curve)
        hand_costs = sorted([c.card.cost for c in hand])
        needs_mana = False
        target_cost = 0
        for cost in hand_costs:
            if cost == p_mana + 1:
                needs_mana = True
                target_cost = cost
                break
            elif cost > p_mana + 1:
                needs_mana = True
                target_cost = cost
                break  # FIX: ambil target_cost pertama, bukan overwrite sampai tertinggi

        evo_bases = self._get_needed_evolution_bases(state)

        for card in hand:
            score, reason = self._evaluate_mana_charge(card, state, needs_mana, target_cost, evo_bases)
            scored.append((card, score, reason))

        scored.sort(key=lambda x: x[1], reverse=True)
        best = scored[0]

        # ── ATURAN SKIP MANA GRANDMASTER ──
        # 1. JANGAN PERNAH skip mana di early/mid-game (mana < 5)! Mana adalah fondasi mutlak.
        # 2. Hanya boleh skip mana jika:
        #    - Mana sudah melimpah (>= 7), tangan tinggal 1-2 kartu, dan tidak ada kartu yang butuh mana lebih tinggi
        #    - ATAU mana sudah >= 5, semua kartu di tangan bisa dimainkan turn ini, dan tangan tipis (<= 2)
        should_skip = False
        skip_reason = ""

        if p_mana >= 7 and len(hand) <= 2 and not needs_mana:
            should_skip = True
            skip_reason = f"Mana sudah melimpah ({p_mana}). Simpan kartu untuk fleksibilitas permainan."
        elif p_mana >= 5 and len(hand) <= 2 and not needs_mana:
            should_skip = True
            skip_reason = f"Mana sudah cukup ({p_mana}) untuk memainkan semua kartu di tangan. Pertahankan jumlah kartu."

        if should_skip:
            return {
                "action": "SKIP",
                "reason": skip_reason,
                "card": None,
                "alternatives": [{"card": s[0].to_dict(), "score": s[1], "reason": s[2]} for s in scored[:3]],
            }

        return {
            "action": "CHARGE",
            "card": best[0].to_dict(),
            "reason": best[2],
            "score": best[1],
            "alternatives": [{"card": s[0].to_dict(), "score": s[1], "reason": s[2]} for s in scored[1:4]],
        }

    def _evaluate_mana_charge(self, card: CardInstance, state: GameState, needs_mana: bool, target_cost: int, evo_bases: set[str]) -> tuple[float, str]:
        score = 10.0
        reasons = []
        c = card.card
        name_lower = c.name.lower()
        duplicates = sum(1 for h in state.player.hand if h.card.name == c.name)

        # ── ATURAN KECERDASAN MANA CHARGE (PREDIKSI MASA DEPAN) ──

        # 1. Duplikat adalah prioritas utama untuk di-charge
        if duplicates > 1:
            score += 15.0
            reasons.append("Terdapat duplikat di tangan, sangat ideal untuk dijadikan mana!")

        # 2. Jika ini adalah satu-satunya kopi, evaluasi SEMUA aspek (KUMULATIF, bukan if-elif)
        if duplicates == 1:
            # A. Cek apakah ini bahan Evolusi yang dibutuhkan
            if any(r.lower() in [eb.lower() for eb in evo_bases] for r in c.race):
                score -= 10.0
                reasons.append("⚠️ TAHAN: Jangan di-charge! Ini adalah bahan dasar Evolusi untuk kartu di tangan Anda.")

            # B. Cek perlindungan Finisher
            if any(k in name_lower for k in ["bombazar", "bolmeteus", "alcadeias", "ballom", "twin-cannon", "crystal lancer", "fighter dual fang", "gatling skyterror"]):
                score -= 12.0
                reasons.append("⭐ FINISHER UTAMA: Tahan di tangan, jangan dijadikan mana unless kepepet!")

            # C. Cek Spell Removal / Pertahanan Krusial (KUMULATIF dengan lainnya)
            if any(k in name_lower for k in ["terror pit", "aqua surfer", "corile", "natural snare", "holy awe", "spiral gate", "crimson hammer", "death smoke", "tornado flame"]):
                # Jika lawan punya ancaman atau shield kita sedikit, tahan!
                if state.opponent.battle_zone or state.player.shields_count <= 2:
                    score -= 8.0
                    reasons.append("🛡️ PERTAHANAN KRUSIAL: Simpan untuk meng-counter ancaman musuh nanti.")
                else:
                    score -= 2.0
                    reasons.append("Kartu removal penting, lebih baik ditahan jika tidak butuh mana.")

            # D. Sinergi Spesifik (Wave Striker)
            if "WAVE_STRIKER" in c.abilities or "wave striker" in c.effect_text.lower():
                score -= 6.0
                reasons.append("⚠️ SINERGI: Tahan untuk melengkapi formasi combo Wave Striker!")

            # E. Kartu Murah (Cost 1-3) yang Berguna di Early Game
            if c.cost <= 3 and state.turn_number <= 3:
                score -= 4.0
                reasons.append(f"Kartu early-game ({c.cost} Cost), lebih baik dimainkan daripada di-charge.")

            # F. Shield Trigger (KUMULATIF)
            if c.shield_trigger:
                score -= 3.0
                reasons.append("Kartu Shield Trigger berharga, sayang jika dibuang ke mana tanpa efek.")
            
            # G. Draw engine cards — jangan charge di early/mid game
            if any(k in c.effect_text.lower() for k in ["draw a card", "draw 2", "draw cards"]):
                if state.turn_number <= 5:
                    score -= 3.0
                    reasons.append("Draw engine, simpan untuk card advantage.")

            # H. Mana ramp cards — lebih berguna dimainkan daripada di-charge
            if any(k in c.effect_text.lower() for k in ["into your mana zone", "into mana zone"]):
                if state.turn_number <= 4:
                    score -= 5.0
                    reasons.append("Kartu ramp mana, lebih berharga dimainkan untuk akselerasi!")

            # I. Blocker saat shields sedikit
            if c.has_blocker and state.player.shields_count <= 3:
                score -= 4.0
                reasons.append("🛡️ Blocker dibutuhkan untuk pertahanan saat shields tipis.")

        # 3. Kebutuhan Warna Mana (Civilization)
        missing_civ = [civ for civ in c.civilization if civ not in state.player.all_civilizations]
        if missing_civ:
            score += 5.0
            civ_name = missing_civ[0].display_name if hasattr(missing_civ[0], 'display_name') else str(missing_civ[0])
            reasons.append(f"Membuka akses elemen warna {civ_name} yang belum ada di Mana Zone.")

        # 4. Evaluasi Kurva Mana (Mana Curve)
        if needs_mana:
            if duplicates == 1 and c.cost == target_cost and not missing_civ:
                score -= 5.0
                reasons.append(f"KARTU TARGET: Simpan {c.name} untuk dimainkan turn ini (Cost {c.cost}).")
            elif c.cost > state.player.total_mana + 2:
                # Terlalu mahal untuk dimainkan dalam 2 turn ke depan
                if duplicates == 1:
                    score += 4.0
                    reasons.append("Kartu terlalu mahal untuk digunakan dalam waktu dekat.")
            elif c.cost > target_cost and duplicates == 1:
                score += 1.0
                reasons.append("Tidak bisa dimainkan turn ini, bisa dialokasikan sebagai mana.")

        # 5. Kartu yang SUDAH bisa dimainkan turn ini — penalty charge
        if c.cost <= state.player.available_mana and duplicates == 1:
            score -= 3.0
            reasons.append(f"Bisa dimainkan turn ini (Cost {c.cost} ≤ Mana {state.player.available_mana}), sayang jika di-charge.")

        # 6. Modifikator dari Pembelajaran AI (Learning Engine)
        if getattr(self, 'learning_engine', None):
            l_mod = self.learning_engine.get_mana_charge_modifier(c.name)
            if l_mod != 0:
                score += l_mod
                if l_mod < -2:
                    reasons.append("🧠 Analisis Memori: Statistik masa lalu membuktikan kartu ini sangat krusial saat dimainkan, JANGAN DI-CHARGE!")
                elif l_mod > 2:
                    reasons.append("🧠 Analisis Memori: Kartu ini lebih efisien dijadikan mana berdasarkan riwayat duel.")

        if not reasons:
            reasons.append("Kartu opsional, aman untuk di-charge jika butuh mana.")

        return round(score, 2), "; ".join(reasons)

    def recommend_plays(self, state: GameState) -> list[dict]:
        playable = state.get_playable_cards()
        if not playable:
            return [{"cards": [], "score": 0, "reasoning": "Tidak ada mana yang cukup atau kartu di tangan."}]

        plays = []
        # 1. Single card plays
        for card in playable:
            play_options = self._simulate_card_with_targets(card, state)
            for opt in play_options:
                plays.append(opt)

        # 2. Multi-card combinations (Smart Tempo: play 2 cards in 1 turn if mana allows!)
        avail_mana = state.player.available_mana
        if len(playable) >= 2 and avail_mana >= 4:
            for c1, c2 in combinations(playable, 2):
                if c1.instance_id == c2.instance_id:
                    continue
                total_c = c1.card.cost + c2.card.cost
                if total_c <= avail_mana:
                    # Check civilization requirements
                    all_civs = set(c1.card.civilization + c2.card.civilization)
                    if all_civs.issubset(state.player.all_civilizations):
                        # Determine smart order: Draw first -> Discard second -> Removal third -> Summon fourth
                        def play_prio(c):
                            txt = c.card.effect_text.lower()
                            if "draw" in txt: return 0
                            if "discard" in txt: return 1
                            if "destroy" in txt or "return" in txt: return 2
                            if "into your mana zone" in txt: return 3
                            return 4
                        
                        ordered = sorted([c1, c2], key=play_prio)
                        first_c, second_c = ordered[0], ordered[1]
                        
                        opt1 = self._simulate_card_with_targets(first_c, state)
                        opt2 = self._simulate_card_with_targets(second_c, state)
                        if opt1 and opt2:
                            base_board_score = self.analyzer.calculate_board_score(state)
                            # FIX: opt1 and opt2 both include the full base_board_score. 
                            # Adding them double-counts the board state! We must subtract it once.
                            combo_score = opt1[0]["score"] + opt2[0]["score"] - base_board_score + 3.0  # +3.0 tempo efficiency bonus
                            plays.append({
                                "cards": [first_c.to_dict(), second_c.to_dict()],
                                "total_cost": total_c,
                                "score": round(combo_score, 2),
                                "reasoning": f"1. {first_c.name} ➔ 2. {second_c.name} (Maksimalkan penggunaan {total_c} mana!)",
                            })

        plays.sort(key=lambda p: p["score"], reverse=True)
        return plays[:8]

    def _simulate_card_with_targets(self, card: CardInstance, state: GameState) -> list[dict]:
        options = []
        raw_text = card.card.effect_text.lower()
        # Strip reminder text in parentheses so Blocker / Shield Trigger text doesn't trigger effect matches
        text = re.sub(r'\(.*?\)', '', raw_text, flags=re.DOTALL)
        opp_board = state.opponent.battle_zone

        # 0. Evolution Creature Check & Simulation
        if card.card.is_evolution:
            can_evo, valid_bases = can_evolve_on(card.card, state.player.battle_zone)
            if not can_evo:
                return []  # Cannot play evolution card without a valid base!

            # Evolve onto the best/weakest valid base
            best_base = min(valid_bases, key=lambda c: c.current_power or 1000)
            sim_state = state.clone()
            sim_state.player.battle_zone = [c for c in sim_state.player.battle_zone if c.instance_id != best_base.instance_id]
            evo_inst = CardInstance(card=card.card, instance_id=card.instance_id, is_tapped=False, summoning_sickness=False)
            sim_state.player.battle_zone.append(evo_inst)

            score = self.analyzer.calculate_board_score(sim_state) + 5.0
            reasons = [f"🌟 Evolusi {card.name} di atas {best_base.name}"]
            if card.card.has_double_breaker: reasons.append("Double Breaker")
            if card.card.has_triple_breaker: reasons.append("Triple Breaker")

            return [{
                "cards": [card.to_dict()],
                "total_cost": card.card.cost,
                "score": round(score, 2),
                "reasoning": " + ".join(reasons),
                "target": best_base.name
            }]

        # 1. Deck Search / Tutor Effects (Dimension Gate, Whispering Totem, etc.)
        if any(k in text for k in ["search your deck", "search deck", "take an armored dragon"]):
            sim_state = state.clone()
            target_recommendation = "Finisher / Removal"
            remaining = state.get_remaining_deck()
            if remaining:
                for dk_card in remaining:
                    if any(fin.lower() in dk_card.lower() for fin in ["bombazar", "bolmeteus", "alcadeias", "ballom", "aqua surfer", "terror pit"]):
                        target_recommendation = dk_card.title()
                        break
            sim_score = self.analyzer.calculate_board_score(sim_state) + 4.5
            return [{
                "cards": [card.to_dict()],
                "total_cost": card.card.cost,
                "score": round(sim_score, 2),
                "reasoning": f"Mainkan {card.name} ➔ Cari {target_recommendation} dari Deck ke Tangan (Tutor)",
                "target": target_recommendation
            }]

        # 2. Mana Ramp Effects (Bronze-Arm Tribe, Faerie Life, Mana Nexus)
        if any(k in text for k in ["into your mana zone", "into mana zone"]):
            sim_state = state.clone()
            if card.card.is_creature:
                sim_state = rules.summon_creature(sim_state, card)
            sim_state.player.total_mana += 1 # Fake ramp for analyzer
            sim_score = self.analyzer.calculate_board_score(sim_state) + 3.0
            return [{
                "cards": [card.to_dict()],
                "total_cost": card.card.cost,
                "score": round(sim_score, 2),
                "reasoning": f"Mainkan {card.name} ➔ Ramp +1 Mana dari Deck (Akselerasi Kurva)",
            }]

        # 3. Draw Engine (Aqua Hulcus, Brain Serum, Energy Stream)
        if any(k in text for k in ["draw a card", "draw 2 cards", "draw up to 2 cards", "draw cards"]):
            sim_state = state.clone()
            if card.card.is_creature:
                sim_state = rules.summon_creature(sim_state, card)
            sim_state.player.hand_size += 1 # Fake draw for analyzer
            sim_score = self.analyzer.calculate_board_score(sim_state) + 3.5
            return [{
                "cards": [card.to_dict()],
                "total_cost": card.card.cost,
                "score": round(sim_score, 2),
                "reasoning": f"Mainkan {card.name} ➔ Draw Kartu (Pertahankan Card Advantage)",
            }]

        # 4. Hand Discard (Cranium Clamp, Ghost Touch)
        if any(k in text for k in ["discards a card", "discards 2 cards", "discard"]):
            sim_state = state.clone()
            if card.card.is_creature:
                sim_state = rules.summon_creature(sim_state, card)
            sim_state.opponent.hand_size = max(0, sim_state.opponent.hand_size - 1)
            sim_score = self.analyzer.calculate_board_score(sim_state) + 3.5
            return [{
                "cards": [card.to_dict()],
                "total_cost": card.card.cost,
                "score": round(sim_score, 2),
                "reasoning": f"Mainkan {card.name} ➔ Kuras Kartu Tangan Musuh",
            }]

        # 5. Wave Striker Formation Trigger
        if "WAVE_STRIKER" in card.card.abilities or "wave striker" in text:
            ws_board = sum(1 for c in state.player.battle_zone if "WAVE_STRIKER" in c.card.abilities)
            if ws_board == 2:
                sim_state = state.clone()
                if card.card.is_creature:
                    sim_state = rules.summon_creature(sim_state, card)
                sim_score = self.analyzer.calculate_board_score(sim_state) + 14.0
                return [{
                    "cards": [card.to_dict()],
                    "total_cost": card.card.cost,
                    "score": round(sim_score, 2),
                    "reasoning": f"🌟 MAINKAN {card.name}! Memicu FORMASI 3 WAVE STRIKER (Aktifkan efek super untuk semua monster Anda)!",
                }]
            elif ws_board == 1:
                sim_state = state.clone()
                if card.card.is_creature:
                    sim_state = rules.summon_creature(sim_state, card)
                sim_score = self.analyzer.calculate_board_score(sim_state) + 4.5
                return [{
                    "cards": [card.to_dict()],
                    "total_cost": card.card.cost,
                    "score": round(sim_score, 2),
                    "reasoning": f"Mainkan {card.name} ➔ Melangkah ke Formasi Wave Striker (2/3)",
                }]

        # 6. Targeted Removal (Destroy, Bounce to Hand/Deck, Tap) & AoE
        needs_target = False
        is_removal = False
        is_bounce_deck = False
        is_tap = False
        is_aoe = False
        power_limit = 99999
        
        if "destroy all" in text or "destroy any" in text:
            needs_target = True
            is_removal = True
            is_aoe = True
            match = re.search(r'power (\d+) or less', text)
            if match: power_limit = int(match.group(1))
        elif "tap all" in text and "opponent" in text:
            needs_target = True
            is_tap = True
            is_aoe = True
        elif "on top of his deck" in text or "on top of deck" in text:
            needs_target = True
            is_bounce_deck = True
        elif re.search(r'\bdestroy\b', text) and ("creature" in text or "opponent" in text):
            needs_target = True
            is_removal = True
            match = re.search(r'power (\d+) or less', text)
            if match: power_limit = int(match.group(1))
        elif ("return" in text and "hand" in text and ("creature" in text or "opponent" in text)) or ("choose a creature" in text and "return" in text):
            needs_target = True
            is_removal = True
        elif ("tap " in text or "tap all" in text) and "opponent" in text and not card.card.has_blocker:
            needs_target = True
            is_tap = True

        if needs_target and opp_board:
            valid_targets = []
            for opp_c in opp_board:
                if is_removal and opp_c.current_power > power_limit:
                    continue
                valid_targets.append(opp_c)
                
            if valid_targets:
                if is_aoe:
                    # AoE affects all valid targets at once
                    sim_state = state.clone()
                    if is_removal:
                        sim_state.opponent.battle_zone = [c for c in sim_state.opponent.battle_zone if c.instance_id not in [v.instance_id for v in valid_targets]]
                        action_desc = f"Mainkan {card.name} ➔ Hancurkan {len(valid_targets)} Creature Lawan!"
                    elif is_tap:
                        for c in sim_state.opponent.battle_zone:
                            if any(v.instance_id == c.instance_id for v in valid_targets):
                                c.is_tapped = True
                        action_desc = f"Mainkan {card.name} ➔ Tap {len(valid_targets)} Creature Lawan!"
                    
                    if card.card.is_creature:
                        sim_state = rules.summon_creature(sim_state, card)
                    else:
                        sim_state = rules.cast_spell(sim_state, card)
                    
                    anticipation_penalty = self.analyzer.estimate_opponent_response(sim_state)
                    sim_score = self.analyzer.calculate_board_score(sim_state) + anticipation_penalty + (len(valid_targets) * 2.0)
                    return [{
                        "cards": [card.to_dict()],
                        "total_cost": card.card.cost,
                        "score": round(sim_score, 2),
                        "reasoning": action_desc,
                        "target": "ALL ENEMIES"
                    }]

                for target in valid_targets:
                    sim_state = state.clone()
                    if is_bounce_deck:
                        sim_state.opponent.battle_zone = [c for c in sim_state.opponent.battle_zone if c.instance_id != target.instance_id]
                        action_desc = f"Mainkan {card.name} ➔ Taruh {target.name} ke Atas Deck Lawan"
                    elif is_removal:
                        sim_state.opponent.battle_zone = [c for c in sim_state.opponent.battle_zone if c.instance_id != target.instance_id]
                        action_desc = f"Mainkan {card.name} ➔ Singkirkan {target.name}"
                    elif is_tap:
                        for c in sim_state.opponent.battle_zone:
                            if c.instance_id == target.instance_id:
                                c.is_tapped = True
                        action_desc = f"Mainkan {card.name} ➔ Tap {target.name}"
                    
                    if card.card.is_creature:
                        sim_state = rules.summon_creature(sim_state, card)
                    else:
                        sim_state = rules.cast_spell(sim_state, card)
                        
                    score = self.analyzer.calculate_board_score(sim_state)
                    anticipation_penalty = self.analyzer.estimate_opponent_response(sim_state)
                    score += anticipation_penalty
                    
                    threat = self.analyzer._calculate_danger(target, state)
                    score += threat["score"] * 1.5
                    if is_bounce_deck: score += 2.0  # Deck lock is extremely strong
                    
                    options.append({
                        "cards": [card.to_dict()],
                        "total_cost": card.card.cost,
                        "score": round(score, 2),
                        "reasoning": action_desc + f" (Menghilangkan ancaman level {threat['level']})",
                        "target": target.name
                    })
                return options

        # Standard creature/spell
        sim_state = state.clone()
        reasons = [f"Mainkan {card.name}"]
        if card.card.is_creature:
            sim_state = rules.summon_creature(sim_state, card)
            if card.card.has_speed_attacker: reasons.append("Speed Attacker siap serang")
            if card.card.has_blocker: reasons.append("Tambah blocker")
            if card.card.has_double_breaker: reasons.append("Double Breaker")
        else:
            sim_state = rules.cast_spell(sim_state, card)

        score = self.analyzer.calculate_board_score(sim_state)
        anticipation_penalty = self.analyzer.estimate_opponent_response(sim_state)
        score += anticipation_penalty

        if "bombazar" in card.name.lower():
            opp_shields = state.opponent.shields_count
            our_attackers = len([c for c in state.player.battle_zone if c.can_attack or c.card.has_speed_attacker])
            total_possible_attacks = (our_attackers + 1) * 2
            
            if opp_shields <= 2 or total_possible_attacks >= (opp_shields + 2):
                score += 25.0
                reasons = [f"🔥 FINISHER MUTLAK: Mainkan {card.name}! Ambil EXTRA TURN dan tuntaskan kemenangan duel sekarang!"]
            else:
                score -= 35.0
                reasons = [f"⚠️ JANGAN MAINKAN {card.name} SEKARANG! Sisa shields lawan ({opp_shields}) masih terlalu banyak. Jika gagal membunuh lawan di turn ekstra, Anda langsung KALAH!"]

        options.append({
            "cards": [card.to_dict()],
            "total_cost": card.card.cost,
            "score": round(score, 2),
            "reasoning": " + ".join(reasons)
        })
        
        return options

    # ── Attack Recommendations ──────────────────────────────

    def recommend_attacks(self, state: GameState) -> list[dict]:
        attackers = state.player.attackers
        if not attackers:
            return [{"action": "NONE", "reasoning": "Tidak ada creature yang bisa menyerang."}]

        analysis = self.analyzer.evaluate_board(state)
        lethal = analysis["lethal_info"]
        trigger_risk = analysis["trigger_risk"]

        if lethal["has_lethal"]:
            if trigger_risk["risk_level"] == "TINGGI" and analysis["overall_score"] > 3:
                return [{
                    "action": "HOLD_LETHAL",
                    "priority": "SEDANG",
                    "reasoning": f"🛑 Bisa LETHAL, TAPI risiko Shield Trigger sangat tinggi ({trigger_risk['percentage']}%). Karena posisi Anda sedang unggul, bersihkan board lawan dulu!",
                }]
            else:
                return [{
                    "action": "GO_FOR_LETHAL",
                    "priority": "TERTINGGI",
                    "reasoning": f"🏆 LETHAL TERDETEKSI! Risiko Trigger {trigger_risk['percentage']}%. Semua serang Shields / Player secara langsung!",
                    "attack_plan": lethal["attack_plan"],
                }]

        recommendations = []
        opp_blockers = state.opponent.blockers
        tapped_enemies = [c for c in state.opponent.battle_zone if c.is_tapped]
        evo_bases = self._get_needed_evolution_bases(state)

        for attacker in attackers:
            rec = self._evaluate_attack(attacker, state, opp_blockers, tapped_enemies, evo_bases)
            recommendations.append(rec)

        order = {"DIRECT": 0, "CREATURE": 1, "SHIELDS": 2, "HOLD": 3}
        recommendations.sort(key=lambda r: (order.get(r.get("target"), 3), -r.get("score", 0)))
        
        return recommendations

    def _evaluate_attack(self, attacker: CardInstance, state: GameState, blockers: list[CardInstance], tapped_enemies: list[CardInstance], evo_bases: set[str]) -> dict:
        atk_power = attacker.attack_power
        atk_name  = attacker.name
        text = attacker.card.effect_text.lower()
        
        # Wave Striker Active Power Buffs
        ws_count = sum(1 for c in state.player.battle_zone if "WAVE_STRIKER" in c.card.abilities)
        if ws_count >= 3:
            if any("kilstine" in c.name.lower() for c in state.player.battle_zone if c.instance_id != attacker.instance_id):
                atk_power += 5000
            if any("merlee" in c.name.lower() for c in state.player.battle_zone):
                atk_power += 1000

        can_attack_players = not ("can't attack players" in text or "cannot attack players" in text)
        can_attack_untapped = "can attack untapped" in text

        # Evolution Protection Check
        is_evo_base = False
        for needed_race in evo_bases:
            if any(r.lower() in needed_race.lower() or needed_race.lower() in r.lower() for r in attacker.card.race):
                # How many of this race do we have on board?
                same_race_count = sum(1 for c in state.player.battle_zone if any(r.lower() in needed_race.lower() or needed_race.lower() in r.lower() for r in c.card.race))
                if same_race_count <= 1:
                    is_evo_base = True
                    break

        if is_evo_base:
            return {
                "attacker": attacker.to_dict(),
                "action": "HOLD",
                "target": "HOLD",
                "priority": "TINGGI",
                "reasoning": "🛑 JANGAN MENYERANG! Tahan creature ini sebagai satu-satunya Tumbal Evolusi di arena!",
                "score": -100
            }

        attack_options = []

        # ── OPTION A: ATTACK CREATURE (Only legal targets: tapped, or if has special ability) ──
        # HARD RULE: Only attack TAPPED enemies (in standard Duel Masters, untapped = defender)
        targetable_enemies = list(state.opponent.battle_zone) if can_attack_untapped else list(tapped_enemies)

        for enemy in targetable_enemies:
            e_power  = enemy.current_power
            if e_power <= 0:
                # Fallback: estimate from cost so we never treat an unparsed creature as 0 power
                e_power = max(1000, (enemy.card.cost or 3) * 1000)
            e_name   = enemy.name
            e_danger = self.analyzer._calculate_danger(enemy, state)["score"]
            has_slayer = attacker.card.has_slayer

            # HARD RULE: NEVER attack someone stronger — it's a suicide move!
            if e_power > atk_power and not has_slayer:
                continue  # Skip — suicidal attack, never recommend this

            # Equal power: mutual destruction (both die)
            if e_power == atk_power and not has_slayer:
                # Only worth it if enemy is a serious board threat
                if e_danger >= 6.0:
                    trade_score = e_danger * 1.5 - (atk_power / 1000) * 0.5
                    reason = f"⚖️ Trade setara dengan {e_name} ({e_power}⚔) — keduanya hancur, tapi ancamannya cukup tinggi!"
                    attack_options.append({"type": "CREATURE", "target": enemy, "score": trade_score, "reason": reason})
                continue  # Not worth equal trade for small threats

            # We WIN and SURVIVE (our power > enemy power, or Slayer)
            if has_slayer and e_power >= atk_power:
                trade_score = e_danger * 3.5 + 3.0
                reason = f"🗡️ Slayer! Hancurkan {e_name} ({e_power}⚔) dengan {atk_power}⚔!"
            else:
                # atk_power > e_power — we survive the fight
                power_advantage = (atk_power - e_power) / 1000
                trade_score = e_danger * 3.0 + (e_power / 1000) * 2.0 + 5.0 + power_advantage
                reason = f"⚔️ Serang & Hancurkan {e_name} ({e_power}⚔) — {atk_name} ({atk_power}⚔) selamat!"

            # Bonus for removing high-value targets
            if enemy.card.has_double_breaker: trade_score += 3.0
            if enemy.card.has_triple_breaker: trade_score += 5.0
            if enemy.card.has_blocker:        trade_score += 2.5
            if enemy.card.has_speed_attacker: trade_score += 2.0

            # ══ NEXT-TURN THREAT ANALYSIS ══
            # If this enemy is TAPPED, it will UNTAP next turn and can attack our shields.
            # Killing it NOW prevents shield damage + free card to opponent.
            if enemy.is_tapped:
                shields_it_breaks = enemy.card.shields_broken
                next_turn_threat = shields_it_breaks * 4.0  # Each shield broken = 4 pts
                # Double Breaker enemies are CRITICAL to kill — they break 2 shields
                if shields_it_breaks >= 2:
                    next_turn_threat += 6.0
                # If we have few shields, killing attackers is even more urgent
                if state.player.shields_count <= 2:
                    next_turn_threat += 8.0
                elif state.player.shields_count <= 3:
                    next_turn_threat += 4.0
                # If enemy has big power, it's a repeated threat every turn
                if e_power >= 6000:
                    next_turn_threat += 3.0
                trade_score += next_turn_threat
                reason += f" [⚠ Ancaman turn depan: break {shields_it_breaks} shield!]"

            # Penalize if after we tap, bigger untapped enemies can kill us next turn
            bigger_untapped_after = [e for e in state.opponent.battle_zone
                                     if not e.is_tapped and e.current_power > atk_power
                                     and e.instance_id != enemy.instance_id]
            if bigger_untapped_after:
                trade_score -= 2.0  # Risk: we become tapped and vulnerable

            attack_options.append({"type": "CREATURE", "target": enemy, "score": trade_score, "reason": reason})

        if can_attack_players:
            breaks = attacker.card.shields_broken
            if ws_count >= 3 and any("kilstine" in c.name.lower() for c in state.player.battle_zone if c.instance_id != attacker.instance_id):
                breaks = max(breaks, 2)
            if state.opponent.shields_count == 0:
                direct_score = 100.0
                if blockers and not attacker.card.has_unblockable:
                    strongest_blocker = max(blockers, key=lambda b: b.current_power)
                    if strongest_blocker.current_power >= atk_power and not attacker.card.has_slayer:
                        direct_score = -5.0
                attack_options.append({
                    "type": "DIRECT",
                    "target": None,
                    "score": direct_score,
                    "reason": "🏆 DIRECT ATTACK KE LAWAN! Menangkan Duel Sekarang!",
                })
            else:
                should_push, shield_advice = self.analyzer.should_attack_shields(attacker, state)
                if not should_push:
                    shield_score = -25.0  # Heavy penalty: do NOT blindly attack shields!
                    shield_reason = shield_advice
                else:
                    shield_score = breaks * 5.0
                    if "bolmeteus" in attacker.name.lower():
                        shield_score += 35.0  # Bolmeteus burning shields is top tier
                    if state.opponent.shields_count <= 2:
                        shield_score += 5.0
                    if attacker.card.has_double_breaker or attacker.card.has_triple_breaker:
                        shield_score += 3.5
                    if attacker.card.has_speed_attacker:
                        shield_score += 2.5
                    shield_reason = f"🛡️ Serang Shield Lawan (Break {breaks}) — {shield_advice}"

                if blockers and not attacker.card.has_unblockable:
                    strongest_blocker = max(blockers, key=lambda b: b.current_power)
                    if strongest_blocker.current_power >= atk_power and not attacker.card.has_slayer:
                        shield_score -= 20.0  # Blocked and dies for nothing!

                attack_options.append({
                    "type": "SHIELDS",
                    "target": None,
                    "score": shield_score,
                    "reason": shield_reason,
                })

        # ── OPTION C: HOLD AS DEFENDER / AVOID TRADE ──
        hold_score = 0.0
        hold_reason = "Tahan — simpan creature di papan."
        if attacker.card.has_blocker:
            hold_score += 6.0
            hold_reason = f"🛑 Tahan {attacker.name} — Siaga sebagai Blocker untuk menahan serangan musuh turn depan!"
        else:
            untapped_threats = [e for e in state.opponent.battle_zone if not e.is_tapped and e.current_power >= atk_power]
            if untapped_threats and state.opponent.shields_count > 3:
                hold_score += 2.5
                hold_reason = f"🛑 Tahan {attacker.name} — Hindari diserang balik oleh {untapped_threats[0].name} turn depan!"

        # === DECIDE BEST ACTION ===
        if not attack_options:
            return {
                "attacker": attacker.to_dict(),
                "action": "HOLD",
                "target": "HOLD",
                "priority": "SEDANG",
                "reasoning": hold_reason,
                "score": hold_score
            }

        best = max(attack_options, key=lambda o: o["score"])
        
        if best["score"] < hold_score:
            return {
                "attacker": attacker.to_dict(),
                "action": "HOLD",
                "target": "HOLD",
                "priority": "SEDANG",
                "reasoning": hold_reason,
                "score": hold_score
            }

        if best["type"] == "CREATURE":
            return {
                "attacker": attacker.to_dict(),
                "action": "ATTACK",
                "target": "CREATURE",
                "target_creature": best["target"].to_dict(),
                "priority": "TINGGI" if best["score"] > 5 else "SEDANG",
                "reasoning": best["reason"],
                "score": best["score"]
            }
        elif best["type"] == "DIRECT":
            return {
                "attacker": attacker.to_dict(),
                "action": "ATTACK",
                "target": "DIRECT",
                "target_creature": None,
                "priority": "TERTINGGI",
                "reasoning": best["reason"],
                "score": best["score"]
            }
        else:
            breaks = attacker.card.shields_broken
            return {
                "attacker": attacker.to_dict(),
                "action": "ATTACK",
                "target": "SHIELDS",
                "target_creature": None,
                "priority": "TINGGI" if breaks >= 2 or state.opponent.shields_count <= 2 else "SEDANG",
                "reasoning": best["reason"],
                "score": best["score"]
            }

    # ── Strategy ────────────────────────────────

    def recommend_strategy(self, state: GameState) -> dict:
        """Deep Strategic AI: Formulates macro strategy considering Wave Striker synergies, lethal math, and archetype matchups."""
        analysis = self.analyzer.evaluate_board(state)
        p = state.player
        o = state.opponent
        lethal_info = analysis.get("lethal_info", {})

        # 1. Lethal Opportunity
        if lethal_info.get("has_lethal"):
            return {
                "strategy": "LETHAL",
                "name": "⚡ EKSEKUSI LETHAL!",
                "description": "Lawan sudah di ambang kekalahan! Hancurkan sisa shields lalu lakukan Direct Attack untuk memenangkan duel!"
            }

        # 2. Wave Striker Synergy Evaluation
        ws_board = sum(1 for c in p.battle_zone if "WAVE_STRIKER" in c.card.abilities)
        ws_hand = sum(1 for c in p.hand if "WAVE_STRIKER" in c.card.abilities)
        if ws_board >= 3:
            return {
                "strategy": "WAVE_STRIKER_DOMINANCE",
                "name": "🌟 Formasi Wave Striker Aktif!",
                "description": "3+ Wave Striker di arena! Semua creature Anda mendapatkan efek super (+5000⚔, Blocker, Double Breaker). Bersihkan board lawan dan tekan shields!"
            }
        elif ws_board == 2 and ws_hand >= 1:
            return {
                "strategy": "WAVE_STRIKER_THRESHOLD",
                "name": "🎯 Pemicu Formasi Wave Striker (2/3)",
                "description": "Anda memiliki 2 Wave Striker di arena dan kartu WS di tangan. Prioritaskan summon Wave Striker ke-3 untuk memicu kekuatan penuh!"
            }

        # 3. Emergency Defense
        if p.shields_count <= 1 and o.creature_count >= 2:
            return {
                "strategy": "DEFENSE_EMERGENCY",
                "name": "🚨 Darurat Bertahan Hidup",
                "description": "Shields Anda kritis! Pasang Blocker, singkirkan creature penyerang lawan, dan jangan serang shield musuh jika berisiko counterattack."
            }

        # 4. Anti-Aggro Stabilization
        archetype = analysis.get("opponent_archetype", {})
        if archetype.get("playstyle") == "AGGRO" and p.shields_count <= 3:
            return {
                "strategy": "ANTI_AGGRO",
                "name": "🛡️ Stabilisasi Anti-Aggro",
                "description": "Lawan bertipe agresif kilat. Kunci serangan mereka dengan Blocker dan tabrak creature musuh yang ter-tap!"
            }

        # 5. Card Advantage Overwhelm
        if p.hand_size >= o.hand_size + 2 and p.total_mana >= 6:
            return {
                "strategy": "RESOURCE_OVERWHELM",
                "name": "💎 Keunggulan Sumber Daya",
                "description": "Anda unggul jauh dalam mana dan jumlah kartu. Mainkan kartu-kartu ber-cost tinggi untuk mengunci kemenangan secara bertahap."
            }

        # 6. Board Control & Pressure
        if p.creature_count > o.creature_count and p.shields_count >= 3:
            return {
                "strategy": "BOARD_CONTROL",
                "name": "⚔️ Kendali Board Penuh",
                "description": "Papan Anda lebih solid. Utamakan menghabisi creature musuh yang ter-tap tanpa memberi lawan kartu shield cuma-cuma."
            }

        # 7. Defense / Survival
        if o.creature_count > p.creature_count and p.shields_count <= 2:
            return {
                "strategy": "DEFENSE",
                "name": "🛡️ Bertahan & Rebut Kendali",
                "description": "Musuh memiliki lebih banyak monster di arena. Fokus menghapus board lawan dengan Removal atau Blocker."
            }

        # 8. Midrange Balanced
        return {
            "strategy": "MIDRANGE",
            "name": "⚖️ Kontrol & Tukar Menguntungkan",
            "description": "Permainan seimbang. Cari trade creature yang menguntungkan dan kikis shield lawan secara terukur."
        }
        
    def plan_turn(self, state: GameState) -> list[dict]:
        """
        SIMULATION-BASED SINGLE BEST DECISION ENGINE
        
        For each phase, simulates ALL possible actions behind the scenes,
        scores every resulting board state, and returns ONLY the single
        best action the player should take RIGHT NOW.
        
        Output: Always a list with exactly 1 step (the best action).
        """
        steps = []

        # ── ACTIVE PROMPT: Always top priority ──
        if state.active_prompt:
            choice = self.recommend_effect_choice(state)
            steps.append({
                "icon": "🎯",
                "action": f"PILIH: {choice['recommended_pick']}",
                "detail": f"{choice['title']}: {choice['reason']}"
            })
            return steps

        # ── OPPONENT'S TURN ──
        if not state.is_player_turn:
            threats = self.analyzer.analyze_revealed_hand(state)
            critical = [t for t in threats if t["severity"] in ["KRITIS", "TINGGI"]]
            if critical:
                t = critical[0]
                return [{"icon": "👁️", "action": f"Lawan Pegang {t['name']}", "detail": t['warning']}]
            if state.opponent.battle_zone:
                biggest = max(state.opponent.battle_zone, key=lambda c: c.current_power if c.current_power > 0 else (c.card.cost or 3) * 1000)
                return [{"icon": "⏳", "action": "Giliran Lawan", "detail": f"Waspadai {biggest.name} ({biggest.current_power}⚔)"}]
            return [{"icon": "⏳", "action": "Giliran Lawan", "detail": "Menunggu giliran lawan selesai..."}]

        phase = state.current_phase
        can_charge = getattr(state, "can_charge_mana", True)

        # ════════════════════════════════════════════════
        # 1. CHARGE PHASE / MANA CHARGE STEP
        # Di Duel Masters, pemain men-charge mana di awal giliran.
        # Prioritaskan Charge Mana jika masih bisa charge dan ada kartu di tangan!
        # ════════════════════════════════════════════════
        if (phase == GamePhase.CHARGE or (phase == GamePhase.MAIN and can_charge)) and state.player.hand:
            charge_advice = self._simulate_best_charge(state)
            if charge_advice and charge_advice[0].get("action", "").startswith("Charge Mana:"):
                return charge_advice

        # ════════════════════════════════════════════════
        # 2. MAIN PHASE: Simulate all playable cards
        # ════════════════════════════════════════════════
        if phase in [GamePhase.MAIN, GamePhase.CHARGE]:
            return self._simulate_best_play(state)

        # ════════════════════════════════════════════════
        # 3. ATTACK PHASE: Simulate all attack options
        # ════════════════════════════════════════════════
        if phase == GamePhase.ATTACK:
            return self._simulate_best_attack(state)

        # ════════════════════════════════════════════════
        # 4. END PHASE
        # ════════════════════════════════════════════════
        return [{"icon": "🏁", "action": "Klik End Turn", "detail": "Giliran selesai. Klik tombol 'End Turn'."}]

    # ── CHARGE SIMULATION ────────────────────────────────────

    def _simulate_best_charge(self, state: GameState) -> list[dict]:
        """Simulate charging each card in hand vs skipping, pick the single best."""
        mc = self.recommend_mana_charge(state)

        if mc["action"] == "CHARGE" and mc.get("card"):
            charge_name = mc["card"]["name"]
            # Check if we'd rather play this card than charge it
            plays = self.recommend_plays(state)
            best_play_cards = set()
            if plays and plays[0].get("cards"):
                best_play_cards = {c["name"] for c in plays[0]["cards"]}

            # If the charge card is our ONLY copy and it's the best play, DON'T charge it!
            # Tapi JANGAN LEWATI CHARGE! Cari alternatif dari sisa kartu di tangan!
            copies_in_hand = sum(1 for c in state.player.hand if c.name == charge_name)
            if charge_name in best_play_cards and copies_in_hand == 1:
                alt_chosen = None
                for alt in mc.get("alternatives", []):
                    alt_name = alt.get("card", {}).get("name")
                    if alt_name and alt_name not in best_play_cards:
                        alt_chosen = alt
                        break
                    elif alt_name and sum(1 for c in state.player.hand if c.name == alt_name) > 1:
                        alt_chosen = alt
                        break

                if alt_chosen:
                    charge_name = alt_chosen["card"]["name"]
                    return [{"icon": "⚡", "action": f"Charge Mana: {charge_name}",
                             "detail": f"Simpan {list(best_play_cards)[0]} untuk dimainkan; charge alternatif: {charge_name}."}]
                else:
                    return [{"icon": "⏭️", "action": f"LEWATI Charge (Jangan buang {charge_name}!)",
                             "detail": f"Tahan {charge_name} di tangan — dimainkan giliran ini."}]

            return [{"icon": "⚡", "action": f"Charge Mana: {charge_name}",
                     "detail": mc["reason"]}]
        else:
            return [{"icon": "⏭️", "action": "Lewati Charge Mana",
                     "detail": mc["reason"]}]

    # ── MAIN PHASE SIMULATION ────────────────────────────────

    def _simulate_best_play(self, state: GameState) -> list[dict]:
        """Simulate playing each possible card, score resulting boards, pick single best."""
        can_charge = getattr(state, "can_charge_mana", True)
        
        # Jika belum charge mana dan ada kartu di tangan, periksa apakah charge kartu lebih prioritas
        if can_charge and state.player.hand:
            charge_advice = self._simulate_best_charge(state)
            if charge_advice and charge_advice[0].get("action", "").startswith("Charge Mana:"):
                return charge_advice

        playable = state.get_playable_cards()

        if not playable or state.player.available_mana <= 0:
            attackers = [c for c in state.player.battle_zone if c.can_attack and not c.is_tapped]
            if attackers:
                return [{"icon": "⚔️", "action": "Masuk ke Attack Phase",
                         "detail": "Klik tombol 'Attack Phase' karena masih ada creature yang bisa menyerang."}]
            return [{"icon": "🏁", "action": "Selesai Main → Klik End Turn",
                     "detail": "Tidak ada kartu yang bisa dimainkan dan tidak ada creature yang bisa menyerang."}]

        # Simulate each playable card → score the resulting board
        candidates = []
        plays_recs = self.recommend_plays(state)

        if plays_recs:
            # Take the #1 recommendation from recommend_plays (already simulated & scored)
            best = plays_recs[0]
            if best.get("cards"):
                card_names = [c["name"] for c in best["cards"]]
                total_cost = best.get("total_cost", 0)
                score = best.get("score", 0)
                reasoning = best.get("reasoning", "")
                target_name = best.get("target", "")

                # Build a concise action string
                if len(card_names) == 1:
                    action_str = f"Mainkan: {card_names[0]}"
                    if target_name:
                        action_str += f" → Target: {target_name}"
                else:
                    action_str = f"Mainkan: {' + '.join(card_names)}"

                # Trim detail
                detail = reasoning
                if len(detail) > 80:
                    detail = detail[:77] + "..."

                return [{"icon": "🃏", "action": action_str, "detail": detail}]

        # Fallback: just suggest the cheapest playable
        cheapest = min(playable, key=lambda c: c.card.cost)
        return [{"icon": "🃏", "action": f"Mainkan: {cheapest.name}",
                 "detail": f"Cost {cheapest.card.cost} — kartu terbaik yang tersedia."}]

    # ── ATTACK PHASE SIMULATION ──────────────────────────────

    def _simulate_best_attack(self, state: GameState) -> list[dict]:
        """
        The heart of the combat AI. For EACH untapped attacker:
        1. Simulate attacking each legal target (tapped enemies, shields, direct)
        2. Score the resulting board state including NEXT TURN SAFETY
        3. Return ONLY the single best attack action.
        
        KEY INSIGHT: If an opponent creature is tapped now, it will UNTAP next turn
        and potentially attack our shields. Killing it NOW prevents that threat.
        """
        attackers = [c for c in state.player.battle_zone if c.can_attack and not c.is_tapped]

        if not attackers:
            return [{"icon": "🏁", "action": "Semua Serangan Selesai → End Turn",
                     "detail": "Semua creature sudah menyerang. Klik 'End Turn'."}]

        # Check for lethal first
        analysis = self.analyzer.evaluate_board(state)
        lethal = analysis["lethal_info"]
        
        # We only force early return if it's a safe/guaranteed lethal.
        # If trigger risk is high, we let it fall through to normal combat evaluation 
        # so it can choose to attack creatures instead of deadlocking.
        if lethal["has_lethal"]:
            trigger_risk = analysis["trigger_risk"]
            if not (trigger_risk["risk_level"] == "TINGGI" and analysis["overall_score"] > 3):
                return [{"icon": "🏆", "action": "LETHAL! SERANG PLAYER LANGSUNG!",
                         "detail": f"Risiko trigger {trigger_risk['percentage']}%. Serang semua shield lalu direct attack!"}]

        # Simulate all attack options for all attackers, pick single best
        all_options = []  # (score, attacker, action_dict)

        # FIX: Only consider untapped blockers!
        opp_blockers = [b for b in state.opponent.blockers if not b.is_tapped]
        tapped_enemies = [c for c in state.opponent.battle_zone if c.is_tapped]
        evo_bases = self._get_needed_evolution_bases(state)

        for attacker in attackers:
            rec = self._evaluate_attack(attacker, state, opp_blockers, tapped_enemies, evo_bases)
            all_options.append((rec.get("score", 0), attacker, rec))

        # Sort by score descending
        all_options.sort(key=lambda x: x[0], reverse=True)

        if not all_options:
            return [{"icon": "🏁", "action": "Tidak ada serangan aman → End Turn",
                     "detail": "Tidak ada serangan yang menguntungkan. Klik 'End Turn'."}]

        best_score, best_attacker, best_rec = all_options[0]

        # ── FORMAT THE SINGLE BEST ACTION ──

        action = best_rec.get("action", "HOLD")
        target = best_rec.get("target", "HOLD")
        target_creature = best_rec.get("target_creature")
        atk_name = best_rec.get("attacker", {}).get("name", best_attacker.name)
        atk_power = best_rec.get("attacker", {}).get("attack_power", best_attacker.attack_power)
        reasoning = best_rec.get("reasoning", "")

        if action == "HOLD":
            # Check if ALL attackers should hold
            all_hold = all(opt[2].get("action") == "HOLD" for opt in all_options)
            if all_hold:
                return [{"icon": "🛑", "action": "Tahan Semua Creature → End Turn",
                         "detail": reasoning}]
            # Find the next non-hold option
            for sc, atk, rec in all_options:
                if rec.get("action") != "HOLD":
                    best_score, best_attacker, best_rec = sc, atk, rec
                    action = rec.get("action")
                    target = rec.get("target")
                    target_creature = rec.get("target_creature")
                    atk_name = rec.get("attacker", {}).get("name", atk.name)
                    atk_power = rec.get("attacker", {}).get("attack_power", atk.attack_power)
                    reasoning = rec.get("reasoning", "")
                    break
            else:
                return [{"icon": "🛑", "action": f"Tahan {atk_name} → End Turn",
                         "detail": reasoning}]

        if target == "CREATURE" and target_creature:
            tc_name = target_creature.get("name", "?")
            tc_power = target_creature.get("current_power", target_creature.get("power", "?"))
            return [{"icon": "⚔️",
                     "action": f"{atk_name} ({atk_power}⚔) → Serang {tc_name} ({tc_power}⚔)",
                     "detail": reasoning}]
        elif target == "DIRECT":
            return [{"icon": "🏆",
                     "action": f"{atk_name} → DIRECT ATTACK ke Player Lawan!",
                     "detail": reasoning}]
        elif target == "SHIELDS":
            return [{"icon": "🛡️",
                     "action": f"{atk_name} ({atk_power}⚔) → Serang Shield Lawan",
                     "detail": reasoning}]
        else:
            return [{"icon": "🛑", "action": f"Tahan {atk_name}",
                     "detail": reasoning}]

