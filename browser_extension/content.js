'use strict';

// ── DMA PRO: Direct S.game State Reader ──
// Website ini menggunakan objek global window.S yang menyimpan
// seluruh game state secara real-time. Kita baca langsung dari sana!

const ANALYZE_URL = 'https://revarend.pythonanywhere.com/api/analyze';
const CARDS_URL   = 'https://revarend.pythonanywhere.com/api/cards';

let syncInterval  = null;
let localCardsDB  = [];  // fallback DB dari server kita

// Load fallback DB
fetch(CARDS_URL).then(r => r.json()).then(d => { localCardsDB = d; }).catch(() => {});

// ── MESSAGE HANDLER ──
chrome.runtime.onMessage.addListener((req) => {
  if (req.action === 'toggleSync') req.state ? startSyncing() : stopSyncing();
});

chrome.storage.local.get(['syncEnabled'], r => { if (r.syncEnabled) startSyncing(); });

function startSyncing() {
  if (syncInterval) clearInterval(syncInterval);
  injectOverlay();
  syncInterval = setInterval(readAndAnalyze, 2000);
}

function stopSyncing() {
  if (syncInterval) clearInterval(syncInterval);
  syncInterval = null;
  const el = document.getElementById('dma-overlay');
  if (el) el.remove();
}

// ── DIRECT STATE READER ──
function readAndAnalyze() {
  // Langsung baca dari objek global milik website
  const S = window.S;
  if (!S || !S.game || !S.cards) {
    updateStatus('🟡 Menunggu game dimulai...');
    return;
  }

  const v   = S.game;
  const you = v.you;  // seat index pemain kita (0 atau 1)

  if (you === null || you === undefined || v.winner !== null) {
    updateStatus(v.winner !== null ? '🏁 Game Selesai' : '👀 Mode Spectator');
    return;
  }

  const opp = 1 - you;
  const myPl  = v.players[you];
  const oppPl = v.players[opp];

  // Fungsi untuk resolve ID kartu ke definisi dari Map website
  function def(cardId) {
    return S.cards.get(cardId) || localCardsDB.find(c => c.id === cardId) || { name: cardId, cost: 0, power: null };
  }

  function mapCard(c, isTapped) {
    const d = def(c.card);
    const kw = (d.keywords || d.abilities || []);
    return {
      id:          c.card,
      name:        d.name || c.card,
      cost:        d.cost || 0,
      power:       c.power ?? d.power ?? null,
      card_type:   d.type === 'spell' ? 'SPELL' : d.type === 'evolution' ? 'EVOLUTION_CREATURE' : 'CREATURE',
      civilization: [d.civ || (d.civs && d.civs[0]) || 'FIRE'],
      abilities:   mapKeywords(kw),
      race:        d.races || d.race || [],
      effect_text: d.text || d.effect_text || '',
      shield_trigger: kw.includes('shield_trigger'),
      instance_id: String(c.uid),
      is_tapped:   isTapped || c.tapped || false,
      can_attack:  !c.sick && !c.tapped,
    };
  }

  function mapKeywords(kw) {
    const map = {
      'blocker': 'BLOCKER', 'double_breaker': 'DOUBLE_BREAKER', 'triple_breaker': 'TRIPLE_BREAKER',
      'speed_attacker': 'SPEED_ATTACKER', 'shield_trigger': 'SHIELD_TRIGGER', 'slayer': 'SLAYER',
      'cant_be_blocked': 'UNBLOCKABLE', 'world_breaker': 'WORLD_BREAKER', 'power_attacker': 'POWER_ATTACKER',
      'wave_striker': 'WAVE_STRIKER', 'survivor': 'SURVIVOR', 'silent_skill': 'SILENT_SKILL',
      'sympathy': 'SYMPATHY', 'charger': 'CHARGER',
    };
    return (kw || []).map(k => map[k]).filter(Boolean);
  }

  // Build game state dari data live website
  const gameState = {
    turn_number:    v.turn || 1,
    current_phase:  (v.phase || 'main').toUpperCase(),
    is_player_turn: v.active === you,
    player: {
      name:         myPl.name || 'Player',
      hand:         (myPl.hand  || []).map(c => mapCard(c, false)),
      mana_zone:    (myPl.mana  || []).map(c => mapCard(c, c.tapped)),
      battle_zone:  (myPl.battle|| []).map(c => mapCard(c, c.tapped)),
      graveyard:    (myPl.graveyard || []).map(c => mapCard(c, false)),
      shields_count: (myPl.shields || []).length,
      deck_count:    myPl.deck_count ?? 30,
    },
    opponent: {
      name:         oppPl.name || 'Opponent',
      hand:         [],  // kartu lawan disembunyikan (hand_count saja)
      hand_size:    oppPl.hand_count ?? (oppPl.hand || []).length,
      mana_zone:    (oppPl.mana   || []).map(c => mapCard(c, c.tapped)),
      battle_zone:  (oppPl.battle || []).map(c => mapCard(c, c.tapped)),
      graveyard:    (oppPl.graveyard || []).map(c => mapCard(c, false)),
      shields_count: (oppPl.shields || []).length,
      deck_count:    oppPl.deck_count ?? 30,
    }
  };

  const totalCards = gameState.player.hand.length + gameState.player.battle_zone.length +
                     gameState.player.mana_zone.length + gameState.opponent.battle_zone.length;

  if (totalCards === 0) {
    updateStatus('🟡 Board kosong, mulai game dulu');
    return;
  }

  updateStatus('🔄 Menganalisa...');

  fetch(ANALYZE_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(gameState)
  })
  .then(r => r.json())
  .then(data => {
    if (data.success) {
      renderAdvice(data.recommendations, totalCards, gameState);
      updateStatus('🟢 Live Pro');
    }
  })
  .catch(() => updateStatus('🔴 Bot Offline (jalankan run.py)'));
}

// ── OVERLAY ──
function injectOverlay() {
  if (document.getElementById('dma-overlay')) return;

  const el = document.createElement('div');
  el.id = 'dma-overlay';
  el.style.cssText = `
    position:fixed; right:12px; top:55px; width:290px;
    background:rgba(14,10,4,0.78); border:1px solid #c8963c;
    border-radius:8px; color:#e8dcc8; z-index:2147483647;
    font-family:'Segoe UI',Tahoma,sans-serif; font-size:12px;
    box-shadow:0 4px 24px rgba(0,0,0,0.6);
    backdrop-filter:blur(8px); -webkit-backdrop-filter:blur(8px);
    pointer-events:auto; user-select:none;
  `;
  el.innerHTML = `
    <div id="dma-hdr" style="display:flex;justify-content:space-between;align-items:center;
         padding:6px 10px;cursor:grab;border-bottom:1px solid #3a2e18;">
      <span style="color:#e8c547;font-weight:bold;font-size:12px;">⚔ DMA Advisor Pro</span>
      <div style="display:flex;gap:8px;align-items:center;">
        <span id="dma-opacity-btn" title="Ganti transparansi" style="cursor:pointer;font-size:13px;opacity:0.7;">👁</span>
        <span id="dma-status" style="font-size:10px;color:#f0c040;">🟡 Menunggu...</span>
      </div>
    </div>
    <div id="dma-advice" style="padding:8px 10px; max-height:400px; overflow-y:auto;"></div>
  `;
  document.body.appendChild(el);

  // Drag
  const hdr = el.querySelector('#dma-hdr');
  let drag=false, sx=0, sy=0, ix=0, iy=0;
  hdr.addEventListener('mousedown', e => {
    drag=true; sx=e.clientX; sy=e.clientY;
    const r=el.getBoundingClientRect(); ix=r.left; iy=r.top;
    el.style.right='auto'; hdr.style.cursor='grabbing'; e.preventDefault();
  });
  document.addEventListener('mousemove', e => {
    if(!drag) return;
    el.style.left=(ix+e.clientX-sx)+'px';
    el.style.top=(iy+e.clientY-sy)+'px';
  });
  document.addEventListener('mouseup', () => { drag=false; hdr.style.cursor='grab'; });

  // Opacity cycle
  const opacities = ['0.78','0.45','0.93'];
  let opIdx = 0;
  el.querySelector('#dma-opacity-btn').addEventListener('click', () => {
    opIdx = (opIdx+1) % opacities.length;
    el.style.background = `rgba(14,10,4,${opacities[opIdx]})`;
  });
}

function updateStatus(text) {
  const el = document.getElementById('dma-status');
  if (el) el.textContent = text;
}

function renderAdvice(rec, totalCards, state) {
  const panel = document.getElementById('dma-advice');
  if (!panel) return;
  let html = '';

  // Info bar
  const pt = state.is_player_turn ? '⚡ Giliran Anda' : '⏳ Giliran Lawan';
  html += `<div style="font-size:10px;color:#9a8b73;margin-bottom:6px;">${pt} · Turn ${state.turn_number} · ${totalCards} kartu terbaca</div>`;

  // LETHAL
  if (rec.board_analysis?.lethal_info?.has_lethal) {
    html += `<div style="background:#8b1a1a;color:#fff;padding:7px 10px;border-radius:5px;text-align:center;font-weight:bold;margin-bottom:8px;border:1px solid #e74c3c;">
      🏆 LETHAL TERDETEKSI! SERANG SEKARANG!
    </div>`;
  }

  // Board score
  const score = rec.board_analysis?.overall_score || 0;
  const adv   = rec.board_analysis?.advantage || 'Seimbang';
  const col   = score > 0 ? '#2ecc71' : (score < 0 ? '#e74c3c' : '#f39c12');
  html += `<div style="display:flex;justify-content:space-between;margin-bottom:6px;padding:5px 7px;background:rgba(255,255,255,0.04);border-radius:4px;">
    <span>📊 ${adv}</span>
    <strong style="color:${col}">${score > 0 ? '+' : ''}${score}</strong>
  </div>`;

  // Trigger risk
  if (rec.board_analysis?.trigger_risk) {
    const r  = rec.board_analysis.trigger_risk;
    const rc = r.percentage > 40 ? '#e74c3c' : (r.percentage > 20 ? '#e67e22' : '#2ecc71');
    html += `<div style="font-size:10px;margin-bottom:8px;padding:4px 7px;background:rgba(255,255,255,0.03);border-radius:4px;">
      🛡 Shield Trigger Risk: <strong style="color:${rc}">${r.percentage}% — ${r.risk_level}</strong>
    </div>`;
  }

  // Turn Plan
  if (rec.turn_plan?.length) {
    html += `<div style="color:#e8c547;font-size:11px;font-weight:bold;margin-bottom:4px;border-top:1px solid #3a2e18;padding-top:6px;">📋 RENCANA GILIRAN INI:</div>`;
    rec.turn_plan.forEach((s, i) => {
      html += `<div style="display:flex;gap:6px;margin-bottom:5px;padding:5px 7px;background:rgba(255,255,255,${i===0?'0.08':'0.03'});border-radius:5px;border-left:2px solid ${i===0?'#e8c547':'#3a2e18'};">
        <span style="font-size:16px;flex-shrink:0;">${s.icon}</span>
        <div>
          <div style="font-weight:bold;font-size:11px;">${s.action}</div>
          <div style="font-size:10px;color:#9a8b73;margin-top:1px;">${s.detail}</div>
        </div>
      </div>`;
    });
  }

  // Mana Charge
  if (rec.mana_charge?.action === 'CHARGE' && rec.mana_charge?.card) {
    html += `<div style="margin-top:6px;padding:5px 7px;background:rgba(232,197,71,0.08);border-radius:5px;border:1px solid #3a2e18;">
      <span style="color:#e8c547;font-size:10px;font-weight:bold;">⚡ CHARGE MANA:</span>
      <div style="font-size:11px;margin-top:2px;"><b>${rec.mana_charge.card.name}</b></div>
      <div style="font-size:10px;color:#9a8b73;">${rec.mana_charge.reason}</div>
    </div>`;
  }

  // Strategy
  if (rec.overall_strategy?.name) {
    html += `<div style="margin-top:6px;padding:5px 7px;background:rgba(255,255,255,0.03);border-radius:5px;font-size:10px;">
      🎯 <b>${rec.overall_strategy.name}:</b> <span style="color:#9a8b73;">${rec.overall_strategy.description}</span>
    </div>`;
  }

  panel.innerHTML = html;
}
