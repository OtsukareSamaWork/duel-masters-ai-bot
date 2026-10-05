"""Board state analyzer with Probabilistic and Anticipation AI."""

from __future__ import annotations
import math

from models.card import CardInstance
from models.enums import Ability
from models.game_state import GameState, PlayerState


class BoardAnalyzer:
    def __init__(self, learning_engine=None):
        self.learning_engine = learning_engine

    def evaluate_board(self, state: GameState) -> dict:
        """Returns comprehensive board evaluation with advanced stats and opponent profiling."""
        trigger_risk = self.calculate_trigger_risk(state)
        score = self.calculate_board_score(state)
        archetype = self.detect_opponent_archetype(state)
        
        advantage = "Seimbang"
        if score > 5: advantage = "Sangat Diuntungkan"
        elif score > 2: advantage = "Sedikit Unggul"
        elif score < -5: advantage = "Kritis / Terdesak"
        elif score < -2: advantage = "Tertinggal"

        threats = self.analyze_revealed_hand(state)
        tempo_clock = self.calculate_tempo_clock(state)
        trigger_ev = self.calculate_shield_trigger_expected_value(state, shields_to_break=1)
        next_turn = self.predict_opponent_next_turn(state)

        return {
            "overall_score": round(score, 2),
            "advantage": advantage,
            "lethal_info": self.calculate_lethal(state),
            "trigger_risk": trigger_risk,
            "tempo_clock": tempo_clock,
            "trigger_ev": trigger_ev,
            "predicted_next_turn": next_turn,
            "opponent_archetype": archetype,
            "revealed_hand_threats": threats
        }

    def analyze_revealed_hand(self, state: GameState) -> list[dict]:
        """Analyzes known cards held in opponent's hand from memory (bounced, searched, or broken shields)."""
        threats = []
        opp = state.opponent
        opp_mana = opp.total_mana
        
        for c in opp.hand:
            c_name = c.name
            c_cost = c.card.cost
            name_lower = c_name.lower()
            can_cast = (opp_mana >= c_cost)
            
            threat_type = "CREATURE"
            warning = "Monster di tangan lawan."
            icon = "🃏"
            severity = "SEDANG"
            
            if any(k in name_lower for k in ["terror pit", "death smoke", "natural snare", "spiral gate"]):
                threat_type = "HARD_REMOVAL"
                warning = f"Removal mematikan siap cast ({c_cost} Mana)!"
                icon = "☠️"
                severity = "KRITIS" if can_cast else "TINGGI"
            elif any(k in name_lower for k in ["aqua surfer", "corile"]):
                threat_type = "BOUNCE"
                warning = f"Akan memantulkan kartu Anda ({c_cost} Mana)!"
                icon = "🌊"
                severity = "TINGGI" if can_cast else "SEDANG"
            elif any(k in name_lower for k in ["cranium clamp", "ghost touch", "lost soul"]):
                threat_type = "DISCARD"
                warning = f"Akan membuang kartu tangan Anda ({c_cost} Mana)!"
                icon = "🖐️"
                severity = "TINGGI" if can_cast else "SEDANG"
            elif any(k in name_lower for k in ["bombazar", "bolmeteus", "alcadeias", "ballom", "twin-cannon"]):
                threat_type = "FINISHER"
                warning = f"Finisher mematikan lawan ({c_cost} Mana)!"
                icon = "🔥"
                severity = "KRITIS" if can_cast else "TINGGI"
            elif c.card.has_speed_attacker:
                threat_type = "SPEED_ATTACKER"
                warning = f"Speed Attacker siap serang seketika ({c_cost} Mana)!"
                icon = "⚡"
                severity = "TINGGI" if can_cast else "SEDANG"
            elif c.card.has_blocker:
                threat_type = "BLOCKER"
                warning = f"Blocker pertahanan lawan ({c_cost} Mana)."
                icon = "🛡️"
                severity = "SEDANG"

            threats.append({
                "name": c_name,
                "cost": c_cost,
                "can_cast": can_cast,
                "icon": icon,
                "type": threat_type,
                "warning": warning,
                "severity": severity
            })

        order = {"KRITIS": 0, "TINGGI": 1, "SEDANG": 2}
        threats.sort(key=lambda t: (order.get(t["severity"], 3), not t["can_cast"]))
        return threats

    def detect_opponent_archetype(self, state: GameState) -> dict:
        """Profiles the opponent's deck archetype based on their visible civilizations, mana, and board."""
        opp = state.opponent
        known_cards = opp.mana_zone + opp.battle_zone + opp.graveyard
        
        if not known_cards:
            return {
                "name": "Belum Terdeteksi",
                "civilizations": [],
                "playstyle": "UNKNOWN",
                "threat_cards": [],
                "predicted_triggers": ["Shield Triggers standar (~25%)"],
                "strategic_advice": "Amati kartu mana pertama yang dipasang lawan."
            }

        civ_counts = {}
        for c in known_cards:
            for civ in c.card.civilization:
                civ_str = civ.name if hasattr(civ, 'name') else str(civ)
                civ_counts[civ_str] = civ_counts.get(civ_str, 0) + 1

        active_civs = set(civ_counts.keys())
        
        if active_civs.issubset({"FIRE"}) or (active_civs == {"FIRE", "NATURE"} and opp.total_mana <= 4):
            return {
                "name": "Mono Fire / Aggro Rush",
                "civilizations": list(active_civs),
                "playstyle": "AGGRO",
                "threat_cards": ["Braid Claw", "Pyrofighter Magnus", "Gatling Skyterror"],
                "predicted_triggers": ["Tornado Flame", "Crimson Hammer", "Burst Shot"],
                "strategic_advice": "Lawan bertempo sangat cepat! Pasang Blocker dan pertahankan shields."
            }
        elif "DARKNESS" in active_civs and "WATER" in active_civs:
            return {
                "name": "Water/Darkness Hand Control",
                "civilizations": list(active_civs),
                "playstyle": "CONTROL",
                "threat_cards": ["Cranium Clamp", "Ghost Touch", "Corile", "Lost Soul"],
                "predicted_triggers": ["Terror Pit", "Aqua Surfer", "Spiral Gate"],
                "strategic_advice": "Waspadai Hand Destruction! Habiskan kartu tangan sebelum dikuras musuh."
            }
        elif "LIGHT" in active_civs and ("WATER" in active_civs or "DARKNESS" in active_civs):
            return {
                "name": "Light Control / Angel Command",
                "civilizations": list(active_civs),
                "playstyle": "CONTROL",
                "threat_cards": ["Alcadeias", "Hanusa", "Urth", "Heaven's Gate"],
                "predicted_triggers": ["Holy Awe", "Sundrop Armor", "Aqua Surfer"],
                "strategic_advice": "Waspadai Holy Awe! Hancurkan Angel Command musuh sebelum berevolusi."
            }
        elif "NATURE" in active_civs and ("FIRE" in active_civs or "WATER" in active_civs):
            return {
                "name": "Nature Ramp / Midrange Tempo",
                "civilizations": list(active_civs),
                "playstyle": "MIDRANGE",
                "threat_cards": ["Fighter Dual Fang", "Twin-Cannon Skyterror", "Bombazar"],
                "predicted_triggers": ["Natural Snare", "Aqua Surfer", "Dimension Gate"],
                "strategic_advice": "Lawan cepat menambah mana. Ambil kendali board sebelum monster besar mereka turun."
            }
        elif len(active_civs) >= 3:
            return {
                "name": "Multicolor Control / Goodstuff",
                "civilizations": list(active_civs),
                "playstyle": "CONTROL",
                "threat_cards": ["Bombazar", "Bolmeteus", "Lost Soul", "Terror Pit"],
                "predicted_triggers": ["Terror Pit", "Aqua Surfer", "Holy Awe"],
                "strategic_advice": "Lawan memiliki kartu-kartu late-game kuat. Tekan pertahanan secara terukur."
            }
        else:
            civ_list = ", ".join(active_civs)
            return {
                "name": f"Deck {civ_list}",
                "civilizations": list(active_civs),
                "playstyle": "BALANCED",
                "threat_cards": [],
                "predicted_triggers": ["Shield Triggers standar"],
                "strategic_advice": "Fokus pada trade menguntungkan di battle zone."
            }

    def calculate_trigger_risk(self, state: GameState) -> dict:
        """Probabilistic AI: Card Counting for Shield Triggers."""
        opp = state.opponent
        # Cards visible to us (assuming standard 40 card deck)
        known_cards = opp.mana_zone + opp.graveyard + opp.battle_zone
        visible_count = len(known_cards)
        
        # Count known shield triggers
        seen_triggers = sum(1 for c in known_cards if c.card.shield_trigger)
        
        # Assumption: A standard competitive deck runs about 10 shield triggers
        # Dynamic trigger assumption based on revealed civilizations
        opp_civs = set()
        for c in known_cards:
            for civ in c.card.civilization:
                civ_name = civ.name if hasattr(civ, 'name') else str(civ)
                opp_civs.add(civ_name)
        
        assumed_total_triggers = 10
        if 'WATER' in opp_civs or 'LIGHT' in opp_civs or 'DARKNESS' in opp_civs:
            assumed_total_triggers = 12
        if 'WATER' in opp_civs and 'LIGHT' in opp_civs:
            assumed_total_triggers = 16
        if opp_civs.issubset({'FIRE', 'NATURE'}):
            assumed_total_triggers = 8

        remaining_triggers_est = max(0, assumed_total_triggers - seen_triggers)
        
        unknown_cards = max(1, 40 - visible_count - opp.hand_size) 
        
        # Probability of a single unknown card being a trigger
        prob_per_card = min(1.0, remaining_triggers_est / unknown_cards)
        
        # Probability of hitting at least 1 trigger if we break all their shields
        shields_left = opp.shields_count
        prob_no_triggers = (1 - prob_per_card) ** shields_left if shields_left > 0 else 1.0
        risk_percentage = (1 - prob_no_triggers) * 100

        if self.learning_engine:
            risk_percentage = min(100.0, risk_percentage * self.learning_engine.get_trigger_caution_factor())

        return {
            "percentage": round(risk_percentage, 1),
            "seen_triggers": seen_triggers,
            "risk_level": "TINGGI" if risk_percentage > 40 else ("SEDANG" if risk_percentage > 20 else "RENDAH")
        }

    def estimate_opponent_response(self, sim_state: GameState) -> float:
        """Opponent Turn Anticipation: Evaluates how easily opponent can destroy our board next turn."""
        penalty = 0.0
        opp = sim_state.opponent
        player = sim_state.player
        
        # Check opponent's untapped creatures against our tapped (or smaller) creatures
        untapped_enemies = [c for c in opp.battle_zone if not c.is_tapped]
        
        for our_c in player.battle_zone:
            # If we are tapped, ANY bigger enemy can kill us for free
            if our_c.is_tapped:
                killers = [e for e in untapped_enemies if e.current_power >= our_c.current_power]
                if killers:
                    penalty -= (our_c.current_power / 1000) * 1.5 # Heavy penalty for leaving a valuable card vulnerable
            else:
                # If we are untapped, opponent can still attack us if they have effects or if we lack blockers
                # but it's less direct. We penalize if opponent has massive creatures.
                pass
                
        # Anticipate spell removal based on opponent mana
        opp_mana = opp.total_mana
        has_darkness = any('DARKNESS' in c.card.civilization for c in opp.mana_zone)
        has_fire = any('FIRE' in c.card.civilization for c in opp.mana_zone)
        
        if opp_mana >= 6 and has_darkness:
            # High chance of Terror Pit
            penalty -= 2.0
            
        return penalty

    def calculate_board_score(self, state: GameState) -> float:
        """Numeric score: positive = player advantage, negative = opponent advantage."""
        score = 0.0

        def evaluate_player(p: PlayerState) -> float:
            p_score = 0.0
            wave_strikers = 0
            survivors = 0
            
            for c in p.battle_zone:
                base_c_score = c.current_power / 1000
                if c.card.has_blocker: base_c_score += 1.5
                if c.card.has_double_breaker: base_c_score += 2.0
                if c.card.has_triple_breaker: base_c_score += 4.0
                
                # Penalize vulnerability and inability to act
                if c.is_tapped: 
                    base_c_score -= 1.0
                if getattr(c, 'summoning_sickness', False) and not c.card.has_speed_attacker:
                    base_c_score -= 0.5
                    
                p_score += max(0.1, base_c_score) # Ensure score doesn't go below 0 for a creature on board
                
                # Synergies tracking
                if "WAVE_STRIKER" in c.card.abilities: wave_strikers += 1
                if "SURVIVOR" in c.card.abilities: survivors += 1
                
            # Apply synergy multipliers
            if wave_strikers >= 3:
                p_score += wave_strikers * 3.0  # Massive boost for full wave striker formation
            elif wave_strikers == 2:
                p_score += 1.0  # Close to formation
                
            if survivors >= 2:
                p_score += survivors * 2.0  # Survivors stack heavily
                
            p_score += p.hand_size * 1.5
            p_score += p.total_mana * 0.5
            p_score += p.shields_count * 2.5
            return p_score

        player_score = evaluate_player(state.player)
        opponent_score = evaluate_player(state.opponent)
        
        score = player_score - opponent_score
        return score

    def calculate_lethal(self, state: GameState) -> dict:
        """Accurate Duel Masters combat lethal physics:
        Requires breaking ALL shields PLUS having at least ONE unblocked attacker remaining for Direct Attack.
        A creature that breaks shields CANNOT direct attack in the same turn.
        """
        attackers = [c for c in state.player.attackers if not ("can't attack players" in c.card.effect_text.lower() or "cannot attack players" in c.card.effect_text.lower())]
        opp_blockers = [b for b in state.opponent.blockers if not b.is_tapped]
        shields = state.opponent.shields_count
        
        # Case A: Opponent already has 0 shields
        if shields == 0:
            unblockables = [a for a in attackers if a.card.has_unblockable]
            can_win = bool(unblockables or (len(attackers) > len(opp_blockers)))
            return {
                "has_lethal": can_win,
                "shields_remaining": 0,
                "available_attackers": len(attackers),
                "attack_plan": "🏆 Shields lawan 0! Lakukan Direct Attack untuk memenangkan duel!" if can_win else "Pancing blocker lawan lebih dulu!"
            }

        # Case B: Opponent has shields.
        # Order attackers to break shields efficiently, reserving at least one for final strike.
        # We use `not a.card.has_unblockable` because with `reverse=True`, True (1) comes before False (0).
        # This ensures blockable creatures attack shields first, saving unblockables for the direct attack.
        sorted_atks = sorted(attackers, key=lambda a: (not a.card.has_unblockable, a.card.shields_broken, a.current_power), reverse=True)
        
        remaining_shields = shields
        blockers_left = len(opp_blockers)
        attackers_used = 0
        
        for atk in sorted_atks:
            attackers_used += 1
            if blockers_left > 0 and not atk.card.has_unblockable:
                # Opponent blocks this attack
                blockers_left -= 1
                continue
            
            breaks = atk.card.shields_broken
            remaining_shields = max(0, remaining_shields - breaks)
            if remaining_shields == 0:
                break
                
        # Must have at least 1 UNUSED attacker remaining who can get past any leftover blockers
        unused_attackers = len(sorted_atks) - attackers_used
        has_lethal = (remaining_shields == 0) and (unused_attackers > blockers_left)

        return {
            "has_lethal": has_lethal,
            "shields_remaining": remaining_shields,
            "available_attackers": len(attackers),
            "attack_plan": "🏆 LETHAL TERJAMIN! Habisi shields lalu serang langsung ke player!" if has_lethal else ""
        }

    def should_attack_shields(self, attacker: CardInstance, state: GameState) -> tuple[bool, str]:
        """Strategic Decision: Board Control vs Face Damage.
        In Duel Masters, breaking opponent shields gives them +1 CARD IN HAND and risks Shield Triggers.
        Never blindly attack shields early game without board control!
        """
        opp = state.opponent
        text = attacker.card.effect_text.lower()
        
        # 1. Bolmeteus burns shields to graveyard (NO triggers, NO cards to opponent hand!)
        if "bolmeteus" in attacker.name.lower():
            return True, "🔥 Bolmeteus membakar shield ke graveyard! (Lawan TIDAK dapat kartu & Trigger batal)"

        # 2. Blockers should never attack shields unless lethal
        if attacker.card.has_blocker and not self.calculate_lethal(state)["has_lethal"]:
            return False, f"🛑 {attacker.name} adalah Blocker! Tahan dalam posisi untap untuk menjaga shields Anda."

        # 3. If opponent has HIGH VALUE tapped creatures on board, prioritize them.
        def get_effective_power(c: CardInstance) -> int:
            return c.current_power if c.current_power > 0 else max(1000, (c.card.cost or 3) * 1000)

        my_power = get_effective_power(attacker)
        tapped_enemies = [e for e in opp.battle_zone if e.is_tapped and my_power >= get_effective_power(e)]
        
        if tapped_enemies:
            strongest_tapped = max(tapped_enemies, key=lambda e: get_effective_power(e))
            # Only FORCE attacking tapped enemies if they are a real threat, or we are a small creature.
            # Double/Triple breakers should prioritize shields unless the enemy is a massive threat or Blocker.
            is_big_breaker = attacker.card.has_double_breaker or attacker.card.has_triple_breaker
            is_enemy_threat = get_effective_power(strongest_tapped) >= 4000 or strongest_tapped.card.has_blocker or strongest_tapped.card.has_slayer
            
            if not is_big_breaker or is_enemy_threat:
                return False, f"⚔️ Prioritas Kontrol Board: Hancurkan {strongest_tapped.name} ({get_effective_power(strongest_tapped)}⚔) dulu!"

        # 4. Vulnerability check: If we attack and become tapped, will opponent kill us for free next turn?
        # Only fear untapped killers if we don't have board swarm advantage
        untapped_killers = [e for e in opp.battle_zone if not e.is_tapped and get_effective_power(e) > my_power]
        if untapped_killers and opp.shields_count >= 3:
            my_attackers = sum(1 for c in state.player.battle_zone if c.can_attack)
            if my_attackers <= 1 and not (attacker.card.has_double_breaker or attacker.card.has_triple_breaker):
                strongest_killer = max(untapped_killers, key=lambda e: get_effective_power(e))
                return False, f"⚠️ Bahaya: Jika {attacker.name} tap untuk serang shield, {strongest_killer.name} akan membunuhnya gratis turn depan!"

        return True, "Aman untuk menekan shield lawan."

    def _calculate_danger(self, card: CardInstance, state: GameState) -> dict:
        """Evaluate threat level of a single opponent card."""
        power = card.current_power if card.current_power > 0 else max(1000, (card.card.cost or 3) * 1000)
        score = power / 1000
        
        # Base stats
        if card.card.has_double_breaker: score *= 1.5
        if card.card.has_triple_breaker: score *= 2.0
        if card.card.has_blocker: score += 2
        
        # Advanced Synergy Threats (Kill on Sight!)
        if "SURVIVOR" in card.card.abilities or "WAVE_STRIKER" in card.card.abilities:
            score += 5.0  # Massive priority to disrupt their synergy
        if "SILENT_SKILL" in card.card.abilities:
            score += 3.0  # Destructive if left alone
        if "STEALTH" in card.card.abilities:
            score += 2.0  # Hard to block
            
        # Learned threat modifier from real match history
        if self.learning_engine:
            score *= self.learning_engine.get_threat_modifier(card.name)

        level = "Rendah"
        if score > 10: level = "KRITIS (Sinergi / Mematikan)"
        elif score > 5: level = "Tinggi"
        
        return {"score": round(score, 1), "level": level}

    def calculate_tempo_clock(self, state: GameState) -> dict:
        """
        World Championship Tempo Clock Analysis:
        Calculates how many turns each player needs to achieve victory.
        """
        p_attackers = [c for c in state.player.battle_zone if not c.is_tapped and c.can_attack]
        # Exclude purely defensive blockers from opponent's attack force calculation
        o_attackers = [c for c in state.opponent.battle_zone if not (c.card.has_blocker and c.current_power <= 3000 and not c.card.has_double_breaker)]

        p_shield_dmg = sum(c.card.shields_broken for c in p_attackers) if p_attackers else 0
        o_shield_dmg = sum(c.card.shields_broken for c in o_attackers) if o_attackers else 0

        p_shields = state.player.shields_count
        o_shields = state.opponent.shields_count

        # Player clock
        if o_shields == 0 and len(p_attackers) > 0:
            player_clock = "1-Turn (Direct Attack LETHAL!)"
            p_turns = 1
        elif p_shield_dmg >= o_shields + 1:
            player_clock = "1-Turn LETHAL"
            p_turns = 1
        elif p_shield_dmg > 0:
            p_turns = math.ceil((o_shields + 1) / max(1, p_shield_dmg))
            player_clock = f"{p_turns}-Turn Clock"
        else:
            p_turns = 99
            player_clock = "Belum Ada Clock"

        # Opponent clock
        if p_shields == 0 and len(o_attackers) > 0:
            opp_clock = "🚨 1-Turn (Musuh bisa Direct Attack!)"
            o_turns = 1
        elif o_shield_dmg >= p_shields + 1:
            opp_clock = "🚨 1-Turn Bahaya Mematikan"
            o_turns = 1
        elif o_shield_dmg > 0:
            o_turns = math.ceil((p_shields + 1) / max(1, o_shield_dmg))
            opp_clock = f"{o_turns}-Turn Clock Musuh"
        else:
            o_turns = 99
            opp_clock = "Aman (Musuh Pasif)"

        # Race evaluation
        if p_turns < o_turns:
            race_status = "👑 UNGGUL TEMPO (Dominasi & Tekan)"
        elif p_turns == o_turns and p_turns <= 2:
            race_status = "⚡ BALAPAN LETHAL KETAT (Hitung Trade Cermat)"
        else:
            race_status = "🛡️ STABILISASI DIPERLUKAN (Kendalikan Board)"

        return {
            "player_clock": player_clock,
            "player_turns": p_turns,
            "opponent_clock": opp_clock,
            "opponent_turns": o_turns,
            "race_status": race_status,
            "player_turn_damage": p_shield_dmg,
            "opponent_turn_damage": o_shield_dmg
        }

    def predict_opponent_next_turn(self, state: GameState) -> dict:
        """
        World Championship Prediction Matrix:
        Anticipates opponent's exact next-turn curve plays based on their upcoming mana and civilizations.
        """
        opp = state.opponent
        next_mana = opp.total_mana + 1
        active_civs = set()
        for c in opp.mana_zone:
            for civ in c.card.civilization:
                active_civs.add(civ.name if hasattr(civ, "name") else str(civ))

        threat_pool = []
        if next_mana >= 2:
            if "WATER" in active_civs: threat_pool.append("Emeral / Spiral Gate")
            if "DARKNESS" in active_civs: threat_pool.append("Ghost Touch / Bloody Squito")
            if "LIGHT" in active_civs: threat_pool.append("La Ura Giga / Szubs Kin")
        if next_mana >= 3:
            if "NATURE" in active_civs: threat_pool.append("Bronze-Arm Tribe (Mana Ramp)")
            if "WATER" in active_civs: threat_pool.append("Aqua Hulcus (Draw Engine)")
            if "FIRE" in active_civs: threat_pool.append("Pyrofighter Magnus (Speed Attacker)")
        if next_mana >= 4:
            if "DARKNESS" in active_civs: threat_pool.append("Cranium Clamp (Hand Wipe) / Death Smoke")
            if "WATER" in active_civs: threat_pool.append("Brain Serum (Draw 2)")
            if "LIGHT" in active_civs: threat_pool.append("Dia Nork (5000 Blocker)")
        if next_mana >= 5:
            if "WATER" in active_civs: threat_pool.append("Corile (Deck Lock)")
            if "NATURE" in active_civs: threat_pool.append("Barkwhip (Speed Beatdown)")
            if "DARKNESS" in active_civs: threat_pool.append("Locomotiver")
        if next_mana >= 6:
            if "LIGHT" in active_civs: threat_pool.append("Alcadeias (Spell Lock) / Holy Awe / Hanusa")
            if "WATER" in active_civs: threat_pool.append("Aqua Surfer / Crystal Lancer")
            if "DARKNESS" in active_civs: threat_pool.append("Terror Pit (Hard Removal)")
            if "FIRE" in active_civs: threat_pool.append("Bolshack Dragon / Gatling Skyterror")
        if next_mana >= 7:
            if "FIRE" in active_civs and "NATURE" in active_civs: threat_pool.append("Bombazar (Extra Turn Finisher)")
            if "FIRE" in active_civs: threat_pool.append("Bolmeteus Steel Dragon (Shield Burn)")
            if "DARKNESS" in active_civs: threat_pool.append("Lost Soul (Full Hand Discard) / Ballom")

        danger_level = "RENDAH"
        if next_mana >= 6: danger_level = "KRITIS (Zona Finisher & Hard Removal)"
        elif next_mana >= 4: danger_level = "TINGGI (Zona Tempo & Discard)"
        elif next_mana >= 3: danger_level = "SEDANG (Zona Ramp & Draw)"

        return {
            "expected_mana": next_mana,
            "danger_level": danger_level,
            "likely_plays": threat_pool[-4:] if threat_pool else ["Kartu Standar"],
            "counterplay": "Habisi monster musuh sekarang sebelum combo mereka aktif." if next_mana >= 5 else "Jaga tempo mana dan pertahankan board."
        }

    def calculate_shield_trigger_expected_value(self, state: GameState, shields_to_break: int = 1) -> dict:
        """
        Grandmaster Trigger Math:
        Calculates exact hypergeometric probability distribution of hitting triggers per shield.
        """
        risk_info = self.calculate_trigger_risk(state)
        pct = risk_info.get("percentage", 25.0)

        # Single shield trigger chance
        # We must convert percentage to decimal before exponentiating
        single_shield_chance = round((1.0 - (1.0 - pct / 100.0) ** (1.0 / max(1, state.opponent.shields_count))) * 100.0, 1)
        # N shields trigger chance
        n_shield_chance = round((1.0 - (1.0 - single_shield_chance / 100.0) ** shields_to_break) * 100.0, 1)

        return {
            "single_shield_risk": single_shield_chance,
            "combined_risk": n_shield_chance,
            "shields_analyzed": shields_to_break,
            "recommendation": "Gunakan creature kecil (1000-2000⚔) untuk memancing (bait) trigger lebih dulu!" if n_shield_chance > 30 else "Aman untuk diserang secara langsung."
        }
