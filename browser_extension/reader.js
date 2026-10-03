// reader.js — Berjalan di world MAIN (duelonline.online)

'use strict';

let syncInterval = null;
let localCardsDB = [];
let isWaitingForAnalysis = false;
let analysisSafetyTimer = null;
let playerDecklist = [];
let lastRecommendations = null;

// ── AUTOPLAY ENGINE VARIABLES ──
let isAutoplayEnabled = (localStorage.getItem('dma_autoplay_enabled') === 'true');
let autoplaySpeed = localStorage.getItem('dma_autoplay_speed') || 'normal';
let isAutoplayActionPending = false;
let autoplayLastLog = '';
let autoplayTimer = null;
let lastActionSignature = '';
let consecutiveActionCount = 0;

// ── HAND REVEAL & GRAVEYARD PERSISTENT MEMORY ──
// Menyimpan kartu-kartu lawan yang sudah kita lihat masuk ke tangannya
// dan melacak setiap kartu yang pernah masuk ke graveyard tanpa tertumpuk/hilang
let oppRevealedHand = {}; // { cardName: { count, source, turn } }
let lastOppShields   = 5;
let lastOppBoardIds  = new Set();
let turnTrackerForMana   = 0;
let initialManaThisTurn  = null;
let hasChargedThisTurn   = false;
let playerGraveyardMemory = new Map(); // instance_id or name -> cardObj
let oppGraveyardMemory    = new Map();

// Minta database kartu lewat bridge dengan persistent cache
try {
  const cachedDB = localStorage.getItem('dma_cached_cards_db');
  if (cachedDB) {
    const parsed = JSON.parse(cachedDB);
    if (Array.isArray(parsed) && parsed.length > 50) localCardsDB = parsed;
  }
} catch (e) {}

function requestCardsDB() {
  window.postMessage({ dma_cmd: 'fetchCards_req' }, '*');
}
requestCardsDB();
const cardsRetryInterval = setInterval(() => {
  if (localCardsDB && localCardsDB.length > 50) {
    clearInterval(cardsRetryInterval);
  } else {
    requestCardsDB();
  }
}, 1500);

// ══════════════════════════════════════════════════════════════
// 🎯 CODEX-STYLE VIRTUAL AGENT POINTER CONTROLLER
// ══════════════════════════════════════════════════════════════
const VirtualAgent = {
  el: null,
  badgeEl: null,
  rippleEl: null,
  currentX: window.innerWidth - 140,
  currentY: window.innerHeight - 90,

  init() {
    if (this.el || !document.body) return;
    const container = document.createElement('div');
    container.id = 'dma-virtual-agent-cursor';
    container.style.cssText = `
      position: fixed;
      left: ${this.currentX}px;
      top: ${this.currentY}px;
      pointer-events: none;
      z-index: 2147483647;
      transform: translate(-10px, -10px);
      transition: left 0.35s cubic-bezier(0.25, 1, 0.5, 1), top 0.35s cubic-bezier(0.25, 1, 0.5, 1);
      display: none;
      will-change: left, top;
    `;

    container.innerHTML = `
      <div style="position:relative;display:flex;align-items:center;pointer-events:none;user-select:none;">
        <!-- Reticle / Ping Ring -->
        <div id="dma-pointer-ripple" style="
          position: absolute;
          left: 12px;
          top: 12px;
          width: 38px;
          height: 38px;
          transform: translate(-50%, -50%) scale(0.8);
          border-radius: 50%;
          background: radial-gradient(circle, rgba(0,255,200,0.3) 0%, rgba(0,255,200,0) 70%);
          border: 1.5px solid rgba(0,255,200,0.7);
          box-shadow: 0 0 12px rgba(0,255,200,0.5);
          transition: transform 0.22s ease-out, border-color 0.22s, background 0.22s;
        "></div>

        <!-- Futuristic Glowing SVG Cursor -->
        <svg width="32" height="32" viewBox="0 0 32 32" fill="none" style="filter: drop-shadow(0 2px 10px rgba(0,0,0,0.9));">
          <path d="M5 4L27 16L17 18.5L12 28L5 4Z" fill="#00ffc8" stroke="#ffffff" stroke-width="2" stroke-linejoin="round"/>
          <circle cx="11" cy="11" r="3" fill="#ffffff" />
        </svg>

        <!-- Status Pill Badge attached to cursor -->
        <div id="dma-pointer-badge" style="
          margin-left: 10px;
          background: rgba(12, 18, 28, 0.94);
          border: 1.5px solid #00ffc8;
          border-radius: 12px;
          padding: 3px 10px;
          color: #00ffc8;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
          font-size: 11px;
          font-weight: 700;
          letter-spacing: 0.5px;
          white-space: nowrap;
          box-shadow: 0 4px 14px rgba(0,0,0,0.7), 0 0 10px rgba(0,255,200,0.35);
          text-shadow: 0 0 4px rgba(0,255,200,0.5);
          transition: all 0.2s;
        ">🤖 AI AGENT</div>
      </div>
    `;

    document.body.appendChild(container);
    this.el = container;
    this.badgeEl = container.querySelector('#dma-pointer-badge');
    this.rippleEl = container.querySelector('#dma-pointer-ripple');
  },

  show() {
    this.init();
    if (this.el) {
      this.el.style.display = 'block';
    }
  },

  hide() {
    if (this.el) {
      this.el.style.display = 'none';
    }
  },

  setBadge(text, state = 'normal') {
    if (!this.badgeEl) return;
    this.badgeEl.textContent = text;
    if (state === 'click') {
      this.badgeEl.style.borderColor = '#2ecc71';
      this.badgeEl.style.color = '#2ecc71';
      this.badgeEl.style.boxShadow = '0 0 15px rgba(46,204,113,0.7)';
    } else if (state === 'drag') {
      this.badgeEl.style.borderColor = '#f39c12';
      this.badgeEl.style.color = '#f39c12';
      this.badgeEl.style.boxShadow = '0 0 15px rgba(243,156,18,0.7)';
    } else if (state === 'warn') {
      this.badgeEl.style.borderColor = '#e74c3c';
      this.badgeEl.style.color = '#e74c3c';
      this.badgeEl.style.boxShadow = '0 0 15px rgba(231,76,60,0.7)';
    } else {
      this.badgeEl.style.borderColor = '#00ffc8';
      this.badgeEl.style.color = '#00ffc8';
      this.badgeEl.style.boxShadow = '0 0 10px rgba(0,255,200,0.35)';
    }
  },

  moveTo(x, y, badgeText = '', callback = null) {
    this.show();
    this.currentX = Math.max(10, Math.min(window.innerWidth - 30, x));
    this.currentY = Math.max(10, Math.min(window.innerHeight - 30, y));
    this.el.style.left = this.currentX + 'px';
    this.el.style.top = this.currentY + 'px';
    if (badgeText) this.setBadge(badgeText);

    if (callback) {
      setTimeout(() => callback(), 380);
    }
  },

  clickTarget(el, actionName = 'KLIK', callback = null) {
    if (!el) {
      if (callback) callback(false);
      return;
    }
    this.show();
    try {
      el.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'center' });
      const rect = el.getBoundingClientRect();
      const x = rect.left + rect.width / 2;
      const y = rect.top + rect.height / 2;

      this.moveTo(x, y, `🎯 ${actionName}`, () => {
        this.setBadge(`✓ ${actionName}`, 'click');
        if (this.rippleEl) {
          this.rippleEl.style.transform = 'translate(-50%, -50%) scale(1.8)';
          this.rippleEl.style.background = 'radial-gradient(circle, rgba(46,204,113,0.8) 0%, rgba(46,204,113,0) 70%)';
          this.rippleEl.style.borderColor = '#2ecc71';
        }

        const opts = { bubbles: true, cancelable: true, view: window, clientX: x, clientY: y, pointerId: 1, isPrimary: true, button: 0, buttons: 1 };
        el.dispatchEvent(new PointerEvent('pointerover', opts));
        el.dispatchEvent(new MouseEvent('mouseover', opts));
        el.dispatchEvent(new PointerEvent('pointerdown', opts));
        el.dispatchEvent(new MouseEvent('mousedown', opts));
        el.dispatchEvent(new PointerEvent('pointerup', { ...opts, buttons: 0 }));
        el.dispatchEvent(new MouseEvent('mouseup', { ...opts, buttons: 0 }));
        el.dispatchEvent(new MouseEvent('click', { ...opts, buttons: 0 }));

        const inner = el.querySelector('img, .card-inner, .card-image, span') || el;
        if (inner && inner !== el) {
          inner.dispatchEvent(new MouseEvent('click', { ...opts, buttons: 0 }));
        }
        if (typeof el.click === 'function') el.click();

        setTimeout(() => {
          if (this.rippleEl) {
            this.rippleEl.style.transform = 'translate(-50%, -50%) scale(0.8)';
            this.rippleEl.style.background = 'radial-gradient(circle, rgba(0,255,200,0.3) 0%, rgba(0,255,200,0) 70%)';
            this.rippleEl.style.borderColor = 'rgba(0,255,200,0.7)';
          }
          this.setBadge('🤖 AGENT STANDBY');
          if (callback) callback(true);
        }, 220);
      });
    } catch (err) {
      console.warn('[DMA VirtualAgent] Click error:', err);
      if (callback) callback(false);
    }
  },

  dragTarget(sourceEl, targetEl, actionName = 'DRAG', callback = null) {
    if (!sourceEl || !targetEl) {
      if (callback) callback(false);
      return;
    }
    this.show();
    try {
      sourceEl.scrollIntoView({ behavior: 'instant', block: 'center', inline: 'center' });
      const srcRect = sourceEl.getBoundingClientRect();
      const tgtRect = targetEl.getBoundingClientRect();
      const srcX = srcRect.left + srcRect.width / 2;
      const srcY = srcRect.top + srcRect.height / 2;
      const tgtX = tgtRect.left + tgtRect.width / 2;
      const tgtY = tgtRect.top + tgtRect.height / 2;

      this.moveTo(srcX, srcY, `✊ AMBIL: ${actionName}`, () => {
        this.setBadge(`🚚 GESER: ${actionName}`, 'drag');
        sourceEl.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, cancelable: true, clientX: srcX, clientY: srcY, pointerId: 1, isPrimary: true, button: 0, buttons: 1 }));
        sourceEl.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true, clientX: srcX, clientY: srcY, button: 0, buttons: 1 }));

        let dt;
        try {
          dt = new DataTransfer();
          sourceEl.dispatchEvent(new DragEvent('dragstart', { bubbles: true, cancelable: true, dataTransfer: dt, clientX: srcX, clientY: srcY }));
        } catch(e) {}

        this.moveTo(tgtX, tgtY, `🎯 DROP: ${actionName}`, () => {
          window.dispatchEvent(new PointerEvent('pointermove', { bubbles: true, cancelable: true, clientX: tgtX, clientY: tgtY, pointerId: 1, isPrimary: true, button: 0, buttons: 1 }));
          window.dispatchEvent(new MouseEvent('mousemove', { bubbles: true, cancelable: true, clientX: tgtX, clientY: tgtY, button: 0, buttons: 1 }));
          targetEl.dispatchEvent(new PointerEvent('pointermove', { bubbles: true, cancelable: true, clientX: tgtX, clientY: tgtY, pointerId: 1, isPrimary: true, button: 0, buttons: 1 }));

          targetEl.dispatchEvent(new PointerEvent('pointerup', { bubbles: true, cancelable: true, clientX: tgtX, clientY: tgtY, pointerId: 1, isPrimary: true, button: 0, buttons: 0 }));
          targetEl.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true, clientX: tgtX, clientY: tgtY, button: 0, buttons: 0 }));

          try {
            targetEl.dispatchEvent(new DragEvent('dragenter', { bubbles: true, cancelable: true, dataTransfer: dt, clientX: tgtX, clientY: tgtY }));
            targetEl.dispatchEvent(new DragEvent('dragover', { bubbles: true, cancelable: true, dataTransfer: dt, clientX: tgtX, clientY: tgtY }));
            targetEl.dispatchEvent(new DragEvent('drop', { bubbles: true, cancelable: true, dataTransfer: dt, clientX: tgtX, clientY: tgtY }));
            sourceEl.dispatchEvent(new DragEvent('dragend', { bubbles: true, cancelable: true, dataTransfer: dt, clientX: tgtX, clientY: tgtY }));
          } catch (e) {}

          // Fallback click on source then target
          this.clickTarget(sourceEl, 'Pilih', () => {
            setTimeout(() => {
              this.clickTarget(targetEl, 'Target', callback);
            }, 160);
          });
        });
      });
    } catch (err) {
      console.warn('[DMA VirtualAgent] Drag error:', err);
      if (callback) callback(false);
    }
  }
};

// Pastikan VirtualAgent siap saat DOM siap
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    if (isAutoplayEnabled) VirtualAgent.show();
  });
} else {
  if (isAutoplayEnabled) VirtualAgent.show();
}

function parseDecklistText(raw) {
  if (!raw) return [];
  const lines = raw.split('\n');
  const deck = [];
  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line || line.startsWith('#') || line.startsWith('//')) continue;
    const match = line.match(/^(\d+)\s*[xX*]?\s+(.+)$/);
    if (match) {
      const count = parseInt(match[1], 10);
      const cardName = match[2].trim();
      for (let i = 0; i < count; i++) deck.push(cardName);
    } else {
      deck.push(line);
    }
  }
  return deck;
}

// Coba ambil deck dari localStorage juga
const savedDeck = localStorage.getItem('dma_decklist');
if (savedDeck) playerDecklist = parseDecklistText(savedDeck);

// Dengar balasan dari bridge.js
window.addEventListener('message', (e) => {
  if (!e.data || !e.data.dma_cmd) return;
  
  if (e.data.dma_cmd === 'updateDeck') {
    playerDecklist = parseDecklistText(e.data.deck);
    localStorage.setItem('dma_decklist', e.data.deck);
  }
  
  if (e.data.dma_cmd === 'toggleSync') {
    e.data.state ? startSyncing() : stopSyncing();
  }

  // Autoplay messages from popup / bridge
  if (e.data.dma_cmd === 'initAutoplay') {
    isAutoplayEnabled = !!e.data.state;
    if (e.data.speed) autoplaySpeed = e.data.speed;
    updateAutoplayBadge();
    if (isAutoplayEnabled) {
      VirtualAgent.show();
      VirtualAgent.setBadge('🤖 AUTOPLAY AKTIF');
    } else {
      VirtualAgent.hide();
    }
  }

  if (e.data.dma_cmd === 'toggleAutoplay') {
    setAutoplayMode(!!e.data.state);
  }

  if (e.data.dma_cmd === 'setAutoplaySpeed') {
    autoplaySpeed = e.data.speed || 'normal';
    localStorage.setItem('dma_autoplay_speed', autoplaySpeed);
  }
  
  // Balasan data kartu
  if (e.data.dma_cmd === 'fetchCards_res') {
    if (e.data.response?.success && Array.isArray(e.data.response.data)) {
      localCardsDB = e.data.response.data;
      try {
        localStorage.setItem('dma_cached_cards_db', JSON.stringify(localCardsDB));
      } catch (err) {}
    }
  }
  
  // Balasan hasil analisa
  if (e.data.dma_cmd === 'analyzeGame_res') {
    if (analysisSafetyTimer) clearTimeout(analysisSafetyTimer);
    isWaitingForAnalysis = false;
    const res = e.data.response;
    if (res?.success && res.data?.success) {
      try {
        lastRecommendations = res.data.recommendations;
        renderAdvice(res.data.recommendations, lastTotalCards, lastGameState);
        updateStatus(`🟢 Live · ${lastTotalCards} kartu`);
      } catch (renderErr) {
        console.error("DMA Render Error:", renderErr);
        updateStatus(`⚠️ Render Error`);
      }
    } else {
      const errReason = res?.error || res?.data?.error || "Gagal menghubungi server";
      updateStatus(`🔴 ${errReason.substring(0, 22)}`);
      console.warn("DMA Error:", res);
    }
  }

  // Init revealed hand dari bridge
  if (e.data.dma_cmd === 'initRevealedHand') {
    if (e.data.oppRevealedHand) {
      oppRevealedHand = e.data.oppRevealedHand;
    }
  }

  // Manual: User/popup mengumumkan kartu yang terlihat di tangan lawan
  if (e.data.dma_cmd === 'revealOppCard') {
    const { cardName, source } = e.data;
    if (cardName) {
      if (!oppRevealedHand[cardName]) oppRevealedHand[cardName] = { count: 0, source: source || 'manual', turn: 0 };
      oppRevealedHand[cardName].count++;
      console.log(`[DMA] Revealed opp hand card: ${cardName} (${source})`);
    }
  }

  // Reset memori kartu tangan lawan & graveyard (misal di awal duel baru)
  if (e.data.dma_cmd === 'resetRevealedHand') {
    oppRevealedHand = {};
    playerGraveyardMemory.clear();
    oppGraveyardMemory.clear();
    lastOppShields = 5;
    lastOppBoardIds = new Set();
    matchTracker = {
      player_cards: new Set(),
      opp_cards: new Set(),
      combos: [],
      player_triggers: 0,
      opp_triggers: 0,
      turns: 1,
      learned: false
    };
    console.log('[DMA] Revealed hand, graveyard & match memory reset.');
  }

  // Hasil pembelajaran dari backend setelah duel selesai
  if (e.data.dma_cmd === 'learnMatch_res') {
    const d = e.data.response;
    if (d && d.success) {
      updateStatus(`🎓 AI Lv.${d.ai_level} (+${d.xp_gained} XP)`);
      renderLearningBanner(d);
    }
  }
});

let matchTracker = {
  player_cards: new Set(),
  opp_cards: new Set(),
  combos: [],
  player_triggers: 0,
  opp_triggers: 0,
  turns: 1,
  learned: false
};

// Auto-start: Default ON kecuali user mematikannya
if (localStorage.getItem('dma_sync_enabled') !== 'false') {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', startSyncing);
  } else {
    startSyncing();
  }
}

function startSyncing() {
  localStorage.setItem('dma_sync_enabled', 'true');
  if (syncInterval) clearInterval(syncInterval);
  injectOverlay();
  syncInterval = setInterval(scanDOM, 2000);
  setTimeout(scanDOM, 300);
}

function stopSyncing() {
  localStorage.setItem('dma_sync_enabled', 'false');
  if (syncInterval) clearInterval(syncInterval);
  syncInterval = null;
  const el = document.getElementById('dma-overlay');
  if (el) el.remove();
}

let lastTotalCards = 0;
let lastGameState = null;

// ── PEMBACA DOM UTAMA ──
function scanDOM() {
  if (isWaitingForAnalysis) return; // Jangan scan jika server belum balas

  // Pastikan overlay terpasang
  if (!document.getElementById('dma-overlay')) {
    injectOverlay();
  }

  const arena = document.querySelector('.arena, .table, .board, #arena, .duel-arena, .playmat, .centre-band, .side.me') || document.body;
  const hasGameZone = document.querySelector('.side.me, .zone.hand, .zone.mana, .mana-tray, .arena');
  if (!hasGameZone) {
    updateStatus('🟡 Menunggu duel...');
    return;
  }

  // ── DETEKSI GILIRAN & TURN NUMBER (ROCK-SOLID STONE BUTTON & WINDOW.S ENGINE) ──
  const S = window.S || window.game;
  let turnNum = 1;
  let isMyTurn = false;
  let phase = 'MAIN';

  if (S && S.game) {
    turnNum = S.game.turn || 1;
    const you = (S.game.you !== null && S.game.you !== undefined) ? S.game.you : 0;
    isMyTurn = (S.game.active === you);
    if (S.game.phase) {
      const p = S.game.phase.toUpperCase();
      if (p === 'MANA' || p === 'CHARGE') phase = 'CHARGE';
      else if (p === 'ATTACK') phase = 'ATTACK';
      else phase = 'MAIN';
    }
  }

  // Dual Check via Stone Button (Ground Truth di UI DuelOnline)
  const stoneBtn = document.querySelector('.stone-end, .btn-end-turn, #btn-end-phase, .end-turn, .turn-btn, .stone');
  const stoneText = (stoneBtn?.textContent || '').toUpperCase().trim();

  if (stoneText.includes('OPPONENT') || stoneText.includes('WAITING') || stoneText.includes('AI DUELIST') || stoneBtn?.classList.contains('waiting') || stoneBtn?.classList.contains('opponent')) {
    isMyTurn = false;
    phase = 'OPPONENT';
  } else if (stoneText.includes('SKIP MANA') || stoneText.includes('CHARGE MANA')) {
    isMyTurn = true;
    phase = 'CHARGE';
  } else if (stoneText.includes('ATTACK PHASE')) {
    isMyTurn = true;
    phase = 'MAIN';
  } else if (stoneText.includes('END TURN') || stoneText.includes('END PHASE') || stoneText.includes('PASS')) {
    isMyTurn = true;
    phase = 'ATTACK';
  } else if (!S || !S.game) {
    const pageText = (document.body.innerText || '').toUpperCase();
    const turnMatch = pageText.match(/TURN\s*(\d+)/i) || document.querySelector('.table-turn-name, .turn-label, .centre-band')?.textContent?.match(/Turn\s*(\d+)/i);
    turnNum = turnMatch ? parseInt(turnMatch[1]) : 1;
    if (pageText.includes("YOUR TURN") || stoneText.includes('YOUR TURN')) {
      isMyTurn = true;
    }
  }

  function normalizeCardKey(s) {
    if (!s) return '';
    return s.toLowerCase().replace(/[_,\-·']/g, ' ').replace(/\s+/g, ' ').trim();
  }

  function findInLocalCardsDB(rawName) {
    if (!rawName || !localCardsDB || !localCardsDB.length) return null;
    const clean = rawName.trim().toLowerCase();
    const qNorm = normalizeCardKey(rawName);
    const qAlpha = rawName.toLowerCase().replace(/[^a-z0-9]/g, '');

    // 1. Exact match
    let found = localCardsDB.find(c => c.name?.toLowerCase() === clean);
    if (found) return found;

    // 2. Normalized match
    found = localCardsDB.find(c => normalizeCardKey(c.name) === qNorm);
    if (found) return found;

    // 3. ID / slug match
    found = localCardsDB.find(c => c.id?.toLowerCase() === clean || normalizeCardKey(c.id) === qNorm);
    if (found) return found;

    // 4. Alphanumeric match
    found = localCardsDB.find(c => {
      const cAlpha = (c.name || '').toLowerCase().replace(/[^a-z0-9]/g, '');
      const cIdAlpha = (c.id || '').toLowerCase().replace(/[^a-z0-9]/g, '');
      return cAlpha === qAlpha || cIdAlpha === qAlpha;
    });
    if (found) return found;

    // 5. Prefix match on main title
    found = localCardsDB.find(c => {
      const cNorm = normalizeCardKey(c.name);
      const cPrefix = normalizeCardKey(c.name?.split(',')[0]);
      return cNorm.startsWith(qNorm) || qNorm.startsWith(cNorm) || cPrefix === qNorm || (qNorm.length >= 4 && qNorm.startsWith(cPrefix));
    });
    if (found) return found;

    // 6. Substring match
    found = localCardsDB.find(c => normalizeCardKey(c.name).includes(qNorm) || qNorm.includes(normalizeCardKey(c.name)));
    return found || null;
  }

  function parseCard(el, isManaImg = false) {
    const imgEl = el.querySelector('img') || (el.tagName === 'IMG' ? el : null);
    let cardId = el.dataset?.card || el.dataset?.cardId || el.dataset?.id || '';
    if (!cardId && imgEl) {
      cardId = imgEl.dataset?.card || imgEl.dataset?.cardId || imgEl.dataset?.id || '';
    }

    let name = '';
    if (isManaImg) {
      name = el.getAttribute('aria-label') || el.getAttribute('title') || el.getAttribute('alt') || '';
    } else {
      const label = el.getAttribute('aria-label') || '';
      name = label.split(',')[0].trim();
      if (!name) name = (el.getAttribute('title') || '').split(' — ')[0].trim();
    }
    
    // Check inner image attributes if outer element had no name
    if (!name && imgEl) {
      name = (imgEl.getAttribute('alt') || imgEl.getAttribute('title') || imgEl.getAttribute('aria-label') || '').split(',')[0].trim();
    }

    // Check inner text containers
    if (!name) {
      const textEl = el.querySelector('.name, .card-name, .title, .card-title, .caption, .label');
      if (textEl) name = textEl.textContent.trim();
    }

    // Extract slug from image src URL (e.g. /cards/aqua_hulcus.png -> aqua hulcus)
    if ((!name || name === '(Kartu)') && imgEl && imgEl.src) {
      const srcMatch = imgEl.src.match(/\/([^\/?#]+)\.(?:png|jpg|jpeg|webp|svg)/i);
      if (srcMatch) {
        const slug = srcMatch[1].replace(/[-_]/g, ' ');
        const dbCardSlug = findInLocalCardsDB(slug);
        if (dbCardSlug) {
          name = dbCardSlug.name;
          if (!cardId) cardId = dbCardSlug.id;
        } else if (!name) {
          name = slug;
        }
      }
    }

    // Bersihkan suffix seperti " · available", " · used", " (tapped)"
    name = name.split(' · ')[0].split(' (')[0].trim();
    if (!name && cardId) name = cardId;
    if (!name && !cardId) return null;

    const dbCard = findInLocalCardsDB(name) || findInLocalCardsDB(cardId) || {};
    
    // Robust power detection from multiple potential DOM elements/attributes
    let power = null;
    const labelText = (el.getAttribute('aria-label') || '') + ' ' + (el.getAttribute('title') || '') + ' ' + (imgEl?.getAttribute('alt') || '');
    const powerMatch = labelText.match(/power[:\s]+(\d+)/i) 
                    || labelText.match(/(\d{4,5})\s*⚔/i);
    if (powerMatch) {
      power = parseInt(powerMatch[1]);
    } else {
      const powerEl = el.querySelector('.power, .card-power, .stat-power, .pts, .val');
      if (powerEl) {
        const valMatch = powerEl.textContent.match(/(\d+)/);
        if (valMatch) power = parseInt(valMatch[1]);
      }
    }
    // Fallback to database power
    if (!power && dbCard.power) {
      power = dbCard.power;
    }

    // Glowing / Playable detection directly from Duel Online DOM
    const isPlayableGlow = el.classList.contains('glow') || 
                           el.classList.contains('playable') || 
                           el.classList.contains('available') || 
                           el.classList.contains('selectable') || 
                           el.classList.contains('can-play') || 
                           el.classList.contains('active') ||
                           el.getAttribute('data-playable') === 'true' ||
                           el.classList.contains('choice');

    // Detect civilization from element classes and image src
    const src = ((imgEl?.src || '') + ' ' + (imgEl?.getAttribute('src') || '')).toLowerCase();
    const cls = ((el.className || '') + ' ' + (imgEl?.className || '')).toLowerCase();
    
    const civMap = {
      'light': 'LIGHT', 'white': 'LIGHT', 'civ-w': 'LIGHT', 'yellow': 'LIGHT',
      'water': 'WATER', 'blue': 'WATER',  'civ-u': 'WATER',
      'dark':  'DARKNESS','black':'DARKNESS','civ-b':'DARKNESS', 'purple': 'DARKNESS',
      'fire':  'FIRE',   'red':  'FIRE',   'civ-r': 'FIRE',
      'nature':'NATURE', 'green':'NATURE', 'civ-g': 'NATURE',
    };
    
    let detectedCivs = [];
    for (const [key, civ] of Object.entries(civMap)) {
      if (src.includes(key) || cls.includes(key)) {
        if (!detectedCivs.includes(civ)) detectedCivs.push(civ);
      }
    }

    const finalCiv = dbCard.civilization || (detectedCivs.length ? detectedCivs : []);

    return {
      id:           dbCard.id || cardId,
      name:         dbCard.name || name || '(Kartu)',
      cost:         dbCard.cost !== undefined ? dbCard.cost : 0,
      power:        power,
      card_type:    dbCard.card_type || 'CREATURE',
      civilization: finalCiv,
      abilities:    dbCard.abilities || [],
      race:         dbCard.race || [],
      effect_text:  dbCard.effect_text || '',
      shield_trigger: dbCard.shield_trigger || false,
      instance_id:  el.dataset?.uid || cardId + '_' + Math.random().toString(36).slice(2,6),
      is_tapped:    el.classList.contains('tapped') || el.classList.contains('used'),
      can_attack:   !el.classList.contains('sick') && !(el.classList.contains('tapped') || el.classList.contains('used')),
      is_playable:  isPlayableGlow,
    };
  }

  function getZoneCards(selector) {
    const rawList = [...document.querySelectorAll(selector)];
    // Filter duplicates by DOM element
    const uniqueEls = [...new Set(rawList)];
    return uniqueEls.map(el => parseCard(el, false)).filter(Boolean);
  }
  function getManaCards(selector) {
    const rawList = [...document.querySelectorAll(selector)];
    const uniqueEls = [...new Set(rawList)];
    return uniqueEls.map(el => {
      const c = parseCard(el, true);
      if (!c) return null;
      c.is_tapped = el.classList.contains('used') || el.classList.contains('tapped') || el.classList.contains('spent');
      return c;
    }).filter(Boolean);
  }

  const playerHand   = getZoneCards('.side.me .zone.hand .card, .side.me .hand .card, .hand-dock .card, .zone.hand .card, [data-zone="hand"] .card');
  const playerBattle = getZoneCards('.side.me .zone.battle .card, .side.me .battle .card, .side.me [data-zone="battle"] .card');
  const playerMana   = getManaCards('.side.me .mana-tray .card, .side.me .mana-tray img, .side.me .zone.mana .card, .side.me .zone.mana img, .side.me .mana-dock .card, .side.me .mana .card, .side.me [data-zone="mana"] .card, .side.me .mana-tray > *');
  const oppBattle    = getZoneCards('.side.opp .zone.battle .card, .side.opp .battle .card, .side.opp [data-zone="battle"] .card');
  const oppMana      = getManaCards('.side.opp .mana-tray .card, .side.opp .mana-tray img, .side.opp .zone.mana .card, .side.opp .zone.mana img, .side.opp .mana-dock .card, .side.opp .mana .card, .side.opp [data-zone="mana"] .card, .side.opp .mana-tray > *');

  const playerShields = document.querySelectorAll('.side.me [data-shield]').length || 5;
  const oppShields    = document.querySelectorAll('.side.opp [data-shield]').length || 5;
  const myDeck  = parseInt(document.querySelector('.side.me  .pile.deck .count, .side.me  .deck-count')?.textContent) || 30;
  const oppDeck = parseInt(document.querySelector('.side.opp .pile.deck .count, .side.opp .deck-count')?.textContent) || 30;
  const oppHandCount = document.querySelectorAll('.side.opp .enemy-hand .back, .side.opp .hand .back').length;

  // Guard: don't fire if no cards are loaded yet (game not started)
  const totalCards = playerHand.length + playerMana.length + playerBattle.length;
  if (totalCards === 0 && playerHand.length === 0) {
    updateStatus('🟡 Menunggu kartu dimuat...');
    return;
  }
  lastTotalCards = totalCards;

  function scanActivePrompt() {
    // 1. Check effect decision (cards from deck, mana, graveyard, yes/no triggers)
    const effectDec = document.querySelector('.effect-decision');
    if (effectDec) {
      const srcName = effectDec.querySelector('.effect-copy strong')?.textContent?.trim() || '';
      const instruction = effectDec.querySelector('.effect-instruction, .effect-target-summary')?.textContent?.trim() || '';
      const eyebrow = effectDec.querySelector('.eyebrow')?.textContent?.trim() || '';
      
      const optionEls = effectDec.querySelectorAll('.effect-option');
      const options = [];
      optionEls.forEach(btn => {
        const cardId = btn.querySelector('img')?.dataset?.card || btn.dataset?.card || '';
        let name = btn.querySelector('span')?.textContent?.trim() || btn.querySelector('img')?.alt || btn.textContent?.trim() || '';
        name = name.split(' · ')[0].split(' (')[0].trim();
        if (name) options.push({ id: btn.dataset?.effectOption || cardId, name, card_id: cardId });
      });

      // Jika effect-decision tidak punya tombol (misal spell menargetkan arena langsung: Terror Pit, Corile, Aqua Surfer)
      if (options.length === 0) {
        const boardTargets = document.querySelectorAll('.arena .card.target, .arena .card.choice, .arena .card.selectable, .arena .card.glow, .arena .card.highlight, .side.opp .zone.battle .card[data-card]');
        boardTargets.forEach(el => {
          const label = el.getAttribute('aria-label') || el.getAttribute('title') || '';
          let name = label.split(',')[0].split(' · ')[0].split(' (')[0].trim();
          if (name && !options.some(o => o.name === name)) {
            options.push({ id: el.dataset?.uid || el.dataset?.card || name, name: name });
          }
        });
      }

      const hasYesNo = !!effectDec.querySelector('#effect-use, #effect-keep');

      return {
        type: 'EFFECT_DECISION',
        source: srcName,
        title: eyebrow || 'Resolusi Efek Kartu',
        instruction: instruction,
        options: options,
        has_yes_no: hasYesNo
      };
    }

    // 2. Check table choice (choose target creature on board or shield)
    const promptBar = document.querySelector('.situation.prompt-bar, .centre-band .situation');
    const tableChoices = document.querySelectorAll('.card.choice, .card.target, .shield.choice, .shield.shield-target, .card.base-opt');
    if (tableChoices.length > 0 && promptBar) {
      const title = promptBar.querySelector('.title')?.textContent?.trim() || '';
      const hint = promptBar.querySelector('.hint')?.textContent?.trim() || '';
      const options = [];
      tableChoices.forEach(el => {
        const name = el.getAttribute('aria-label') || el.getAttribute('title') || el.textContent?.trim() || '';
        options.push({ id: el.dataset?.uid || el.dataset?.card || el.dataset?.shield || '', name: name.split(' · ')[0].split(',')[0].trim() });
      });
      return {
        type: 'BOARD_CHOICE',
        source: '',
        title: title || 'Pilih Target di Arena',
        instruction: hint,
        options: options
      };
    }

    // 3. Check generic modal dialog
    const modal = document.querySelector('dialog.modal, .modal:not([style*="display: none"])');
    if (modal) {
      const h3 = modal.querySelector('h3')?.textContent?.trim() || 'Pilihan';
      const buttons = modal.querySelectorAll('button');
      const opts = [];
      buttons.forEach(b => opts.push({ id: b.id || b.textContent.trim(), name: b.textContent.trim() }));
      return {
        type: 'MODAL',
        source: '',
        title: h3,
        instruction: 'Tentukan pilihan pada dialog',
        options: opts,
        has_yes_no: !!modal.querySelector('#yes, #no')
      };
    }

    return null;
  }

  const activePrompt = scanActivePrompt();

  // ── GRAVEYARD SCANNING: S.game GROUND TRUTH + PERSISTENT MEMORY ACCUMULATOR ──
  let playerGraveyard = [];
  let oppGraveyard    = [];

  const youIdx = (S && S.game && S.game.you !== null && S.game.you !== undefined) ? S.game.you : 0;
  const oppIdx = 1 - youIdx;

  if (S && S.game && S.game.players && (S.game.players[youIdx]?.graveyard || S.game.players[oppIdx]?.graveyard)) {
    const rawMyGrave = S.game.players[youIdx]?.graveyard || [];
    const rawOppGrave = S.game.players[oppIdx]?.graveyard || [];

    playerGraveyard = rawMyGrave.map(c => {
      const cardId = typeof c === 'object' ? (c.card || c.id || '') : String(c);
      const dbCard = findInLocalCardsDB(cardId) || {};
      return {
        id: dbCard.id || cardId,
        name: dbCard.name || cardId,
        cost: dbCard.cost !== undefined ? dbCard.cost : 0,
        power: dbCard.power || null,
        card_type: dbCard.card_type || 'CREATURE',
        civilization: dbCard.civilization || [],
        abilities: dbCard.abilities || [],
        race: dbCard.race || [],
        effect_text: dbCard.effect_text || '',
        shield_trigger: dbCard.shield_trigger || false,
        instance_id: String(c.uid || cardId),
        is_tapped: false,
        can_attack: false
      };
    });

    oppGraveyard = rawOppGrave.map(c => {
      const cardId = typeof c === 'object' ? (c.card || c.id || '') : String(c);
      const dbCard = findInLocalCardsDB(cardId) || {};
      return {
        id: dbCard.id || cardId,
        name: dbCard.name || cardId,
        cost: dbCard.cost !== undefined ? dbCard.cost : 0,
        power: dbCard.power || null,
        card_type: dbCard.card_type || 'CREATURE',
        civilization: dbCard.civilization || [],
        abilities: dbCard.abilities || [],
        race: dbCard.race || [],
        effect_text: dbCard.effect_text || '',
        shield_trigger: dbCard.shield_trigger || false,
        instance_id: String(c.uid || cardId),
        is_tapped: false,
        can_attack: false
      };
    });

    // Sinkronkan ke memori persisten
    playerGraveyard.forEach(c => { if (c.name && c.name !== '(Kartu)') playerGraveyardMemory.set(c.instance_id || c.name, c); });
    oppGraveyard.forEach(c => { if (c.name && c.name !== '(Kartu)') oppGraveyardMemory.set(c.instance_id || c.name, c); });
  } else {
    // DOM Scanner + Memori Persisten (Mencegah kartu hilang saat tertumpuk di tumpukan graveyard)
    const domMyGrave = getZoneCards('.side.me .pile.graveyard .card[data-card], .side.me .graveyard .card[data-card], .side.me [data-zone="graveyard"] .card');
    const domOppGrave = getZoneCards('.side.opp .pile.graveyard .card[data-card], .side.opp .graveyard .card[data-card], .side.opp [data-zone="graveyard"] .card');

    domMyGrave.forEach(c => { if (c.name && c.name !== '(Kartu)') playerGraveyardMemory.set(c.instance_id || c.name, c); });
    domOppGrave.forEach(c => { if (c.name && c.name !== '(Kartu)') oppGraveyardMemory.set(c.instance_id || c.name, c); });

    playerGraveyard = Array.from(playerGraveyardMemory.values());
    oppGraveyard    = Array.from(oppGraveyardMemory.values());
  }

  // ── HAND REVEAL MEMORY: Detect new cards entering opp hand ──
  // 1. Shield break: if opp shields went down, the broken shield card enters their hand
  //    We can't see the card name from DOM, but we can note the event.
  const currentOppShields = oppShields;
  if (lastOppShields !== null && currentOppShields < lastOppShields) {
    const brokenCount = lastOppShields - currentOppShields;
    // We don't know card name, but we flag the event so advisor can account for it
    for (let b = 0; b < brokenCount; b++) {
      if (!oppRevealedHand['__shield_pickup__']) oppRevealedHand['__shield_pickup__'] = { count: 0, source: 'shield_broken', turn: turnNum };
      oppRevealedHand['__shield_pickup__'].count++;
    }
  }
  lastOppShields = currentOppShields;

  // 2. Card bounced off opp board (Aqua Surfer / Spiral Gate / Corile returning our card)
  //    If a card that was on OPP board is no longer there, it might have returned to their hand
  const currentOppBoardIds = new Set(oppBattle.map(c => c.id));
  for (const [bid] of lastOppBoardIds.entries()) {
    if (!currentOppBoardIds.has(bid)) {
      // Card disappeared from board — could be destroyed or bounced to hand
      // We can't tell for sure, but note it if it was untapped (not combat destroyed)
      // For now we won't track this — destruction vs bounce is indistinguishable from DOM
    }
  }
  lastOppBoardIds = currentOppBoardIds;

  // Build revealed hand list for backend (only named revealed cards)
  const revealedHandArray = Object.entries(oppRevealedHand)
    .filter(([k]) => k !== '__shield_pickup__')
    .map(([name, data]) => ({
      name,
      count:  data.count,
      source: data.source,
      turn:   data.turn,
      // Look up DB for full card data
      ...(() => {
        const db = findInLocalCardsDB(name) || {};
        return {
          cost:         db.cost || 0,
          power:        db.power || null,
          card_type:    db.card_type || 'SPELL',
          civilization: db.civilization || [],
          abilities:    db.abilities || [],
          race:         db.race || [],
          effect_text:  db.effect_text || '',
          shield_trigger: db.shield_trigger || false,
        };
      })()
    }));

  // Update match learning tracker
  matchTracker.turns = Math.max(matchTracker.turns, turnNum);
  playerHand.forEach(c => c.name && matchTracker.player_cards.add(c.name));
  playerBattle.forEach(c => c.name && matchTracker.player_cards.add(c.name));
  playerGraveyard.forEach(c => c.name && matchTracker.player_cards.add(c.name));
  oppBattle.forEach(c => c.name && matchTracker.opp_cards.add(c.name));
  oppMana.forEach(c => c.name && matchTracker.opp_cards.add(c.name));
  oppGraveyard.forEach(c => c.name && matchTracker.opp_cards.add(c.name));
  revealedHandArray.forEach(c => c.name && matchTracker.opp_cards.add(c.name));

  // ── MANA CHARGE STEP TRACKING ──
  if (isMyTurn) {
    if (turnNum !== turnTrackerForMana) {
      turnTrackerForMana = turnNum;
      initialManaThisTurn = playerMana.length;
      hasChargedThisTurn = false;
    } else {
      if (initialManaThisTurn !== null && playerMana.length > initialManaThisTurn) {
        hasChargedThisTurn = true;
      }
    }
  } else {
    turnTrackerForMana = 0;
    initialManaThisTurn = null;
    hasChargedThisTurn = false;
  }

  // canChargeNow HANYA benar jika game berada di fase CHARGE (stone button: SKIP MANA)
  const canChargeNow = isMyTurn && (phase === 'CHARGE') && !hasChargedThisTurn && playerHand.length > 0;
  let effectivePhase = phase;

  // ── DETEKSI PERTANDINGAN SELESAI (AUTO-LEARN MATCH) ──
  const isFinished = (arena.dataset?.finished === 'true') ||
                     !!document.querySelector('.winner, .victory, .defeat, .game-over, .post-game, .modal.victory, .modal.defeat, .win-banner');
  if (isFinished) {
    if (!matchTracker.learned) {
      matchTracker.learned = true;
      const bodyText = (document.body.innerText || '').toUpperCase();
      let res = "UNKNOWN";
      if (bodyText.includes('VICTORY') || bodyText.includes('YOU WIN') || bodyText.includes('MENANG')) {
        res = "WIN";
      } else if (bodyText.includes('DEFEAT') || bodyText.includes('YOU LOSE') || bodyText.includes('KALAH')) {
        res = "LOSS";
      } else if (playerShields > 0 && oppShields === 0) {
        res = "WIN";
      } else if (playerShields === 0 && oppShields > 0) {
        res = "LOSS";
      }

      const matchReport = {
        result: res,
        total_turns: turnNum || matchTracker.turns,
        player_deck: playerDecklist,
        player_cards_played: Array.from(matchTracker.player_cards).filter(n => n && n !== '(Kartu)'),
        opponent_cards_seen: Array.from(matchTracker.opp_cards).filter(n => n && n !== '(Kartu)'),
        combos_executed: matchTracker.combos,
        triggers_hit_by_player: matchTracker.player_triggers,
        triggers_hit_by_opp: matchTracker.opp_triggers,
        opponent_archetype: lastGameState?.opponent?.archetype?.name || "Belum Terdeteksi"
      };

      updateStatus('🎓 AI Mempelajari Duel...');
      window.postMessage({ dma_cmd: 'learnMatch_req', matchData: matchReport }, '*');
    }
    return;
  }

  lastGameState = {
    turn_number:    turnNum,
    current_phase:  effectivePhase,
    is_player_turn: isMyTurn,
    can_charge_mana: canChargeNow,
    active_prompt:  activePrompt,
    player: {
      name: 'Player', hand: playerHand, mana_zone: playerMana, battle_zone: playerBattle,
      graveyard: playerGraveyard, shields_count: playerShields, deck_count: myDeck, decklist: playerDecklist
    },
    opponent: {
      name: 'Opponent', hand: revealedHandArray, hand_size: oppHandCount,
      mana_zone: oppMana, battle_zone: oppBattle,
      graveyard: oppGraveyard, shields_count: oppShields, deck_count: oppDeck
    }
  };

  updateStatus(activePrompt ? `🎯 Efek Aktif!` : `🔄 Menganalisa...`);
  isWaitingForAnalysis = true;

  if (analysisSafetyTimer) clearTimeout(analysisSafetyTimer);
  analysisSafetyTimer = setTimeout(() => {
    if (isWaitingForAnalysis) {
      isWaitingForAnalysis = false;
      updateStatus('⚠️ Server Timeout / Cek run.py');
    }
  }, 7000);
  
  // Kirim data ke bridge untuk di-fetch oleh background.js
  window.postMessage({ dma_cmd: 'analyzeGame_req', gameState: lastGameState }, '*');
}

// ── OVERLAY & RENDER ──
function injectOverlay() {
  if (document.getElementById('dma-overlay')) return;
  if (!document.body) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', injectOverlay);
    } else {
      setTimeout(injectOverlay, 150);
    }
    return;
  }
  const el = document.createElement('div');
  el.id = 'dma-overlay';
  el.style.cssText = `
    position:fixed; right:20px; top:60px; width:310px;
    background: linear-gradient(180deg, rgba(16, 12, 20, 0.95) 0%, rgba(10, 8, 14, 0.9) 100%);
    border: 2px solid #00f0ff;
    border-radius: 12px; color: #e0f7fa; z-index: 2147483647;
    font-family: 'Consolas', 'Courier New', monospace; font-size: 12px;
    box-shadow: 0 0 20px rgba(0, 240, 255, 0.2), inset 0 0 15px rgba(0, 240, 255, 0.1);
    backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
    pointer-events: auto;
    transition: all 0.3s ease;
    overflow: hidden;
  `;
  el.innerHTML = `
    <!-- Top Cyberpunk Accent -->
    <div style="height:4px;width:100%;background:linear-gradient(90deg, transparent, #00f0ff, transparent);position:absolute;top:0;left:0;opacity:0.8;"></div>
    
    <div id="dma-hdr" style="display:flex;justify-content:space-between;align-items:center;
         padding:10px 14px;cursor:grab;border-bottom:1px solid rgba(0,240,255,0.3);
         background: rgba(0, 240, 255, 0.05);">
      <div style="display:flex;align-items:center;gap:8px;">
        <span style="color:#00f0ff;font-weight:bold;font-size:14px;text-shadow: 0 0 5px #00f0ff;">💠 DMA_AGENT</span>
        <button id="dma-auto-btn" style="cursor:pointer;font-size:9.5px;font-weight:bold;padding:3px 8px;border-radius:4px;border:1px solid #555;background:#2b2b2b;color:#aaa;transition:all 0.3s;box-shadow: 0 0 5px rgba(0,0,0,0.5);" title="Klik untuk On/Off Autoplay Bot">🤖 AUTO: OFF</button>
      </div>
      <div style="display:flex;gap:10px;align-items:center;">
        <span id="dma-op-btn" title="Ganti transparansi" style="cursor:pointer;font-size:14px;opacity:0.8;color:#00f0ff;transition:transform 0.2s;">👁️</span>
        <span id="dma-status" style="font-size:10px;color:#f1c40f;font-weight:bold;text-shadow: 0 0 4px #f1c40f;letter-spacing:1px;">INIT_</span>
      </div>
    </div>
    
    <!-- Background Grid -->
    <div style="position:absolute;top:40px;left:0;right:0;bottom:0;background-image:linear-gradient(rgba(0,240,255,0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(0,240,255,0.05) 1px, transparent 1px);background-size:20px 20px;pointer-events:none;z-index:0;"></div>
    
    <div id="dma-advice" style="padding:12px 14px;max-height:450px;overflow-y:auto;position:relative;z-index:1;scrollbar-width:thin;scrollbar-color:#00f0ff transparent;"></div>
  `;
  document.body.appendChild(el);

  const hdr = el.querySelector('#dma-hdr');
  let drag=false,sx=0,sy=0,ix=0,iy=0;
  hdr.addEventListener('mousedown', e => {
    drag=true; sx=e.clientX; sy=e.clientY;
    const r=el.getBoundingClientRect(); ix=r.left; iy=r.top;
    el.style.right='auto'; hdr.style.cursor='grabbing'; e.preventDefault();
  });
  document.addEventListener('mousemove', e => { if(drag){ el.style.left=(ix+e.clientX-sx)+'px'; el.style.top=(iy+e.clientY-sy)+'px'; }});
  document.addEventListener('mouseup', () => { drag=false; hdr.style.cursor='grab'; });

  const ops=['0.80','0.45','0.96']; let oi=0;
  el.querySelector('#dma-op-btn').addEventListener('click', () => {
    oi=(oi+1)%ops.length; el.style.background=`rgba(12,8,2,${ops[oi]})`;
  });

  const autoBtn = el.querySelector('#dma-auto-btn');
  if (autoBtn) {
    autoBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      setAutoplayMode(!isAutoplayEnabled);
    });
  }
  updateAutoplayBadge();

  if (!document.getElementById('dma-highlight-style')) {
    const style = document.createElement('style');
    style.id = 'dma-highlight-style';
    style.textContent = `
      @keyframes dmaPulse {
        0% { transform: translateX(-50%) scale(0.95); opacity: 0.9; }
        100% { transform: translateX(-50%) scale(1.08); opacity: 1; }
      }
      @keyframes dmaGlowCharge {
        0% { box-shadow: 0 0 6px #f39c12, inset 0 0 6px #f39c12; outline: 2px solid #f1c40f !important; }
        100% { box-shadow: 0 0 18px #f39c12, inset 0 0 10px #f1c40f; outline: 3px solid #ffd700 !important; }
      }
      @keyframes dmaGlowPlay {
        0% { box-shadow: 0 0 6px #3498db, inset 0 0 6px #3498db; outline: 2px solid #2980b9 !important; }
        100% { box-shadow: 0 0 18px #2980b9, inset 0 0 10px #5dade2; outline: 3px solid #00d2ff !important; }
      }
      @keyframes dmaGlowTarget {
        0% { box-shadow: 0 0 8px #e74c3c, inset 0 0 8px #e74c3c; outline: 2px solid #c0392b !important; }
        100% { box-shadow: 0 0 22px #ff0000, inset 0 0 14px #e74c3c; outline: 3px solid #ff3333 !important; }
      }
      .dma-glow-charge { animation: dmaGlowCharge 0.9s infinite alternate !important; border-radius: 6px !important; z-index: 100 !important; }
      .dma-glow-play   { animation: dmaGlowPlay 0.9s infinite alternate !important; border-radius: 6px !important; z-index: 100 !important; }
      .dma-glow-target { animation: dmaGlowTarget 0.8s infinite alternate !important; border-radius: 6px !important; z-index: 100 !important; }
    `;
    document.head.appendChild(style);
  }
}

function setAutoplayMode(enabled) {
  isAutoplayEnabled = enabled;
  localStorage.setItem('dma_autoplay_enabled', enabled ? 'true' : 'false');
  updateAutoplayBadge();
  if (enabled) {
    VirtualAgent.show();
    VirtualAgent.setBadge('🤖 AUTOPLAY AKTIF');
  } else {
    VirtualAgent.hide();
  }
  if (isAutoplayEnabled && lastRecommendations && lastGameState) {
    triggerAutoplay(lastRecommendations, lastGameState);
  }
}

function updateAutoplayBadge() {
  const btn = document.getElementById('dma-auto-btn');
  if (!btn) return;
  if (isAutoplayEnabled) {
    btn.textContent = '🤖 AUTO: ON';
    btn.style.background = '#27ae60';
    btn.style.color = '#fff';
    btn.style.borderColor = '#2ecc71';
    btn.style.boxShadow = '0 0 8px #2ecc71';
  } else {
    btn.textContent = '🤖 AUTO: OFF';
    btn.style.background = '#2b2b2b';
    btn.style.color = '#aaa';
    btn.style.borderColor = '#555';
    btn.style.boxShadow = 'none';
  }
}

function updateStatus(text) {
  const el = document.getElementById('dma-status');
  if (el) el.textContent = text;
}

function renderAdvice(rec, totalCards, state) {
  const panel = document.getElementById('dma-advice');
  if (!panel) return;

  const currentPhase = state?.current_phase || 'MAIN';
  const phaseLabels = {'CHARGE':'Charge Mana','DRAW':'Draw Kartu','MAIN':'Main Phase','ATTACK':'Attack Phase','END':'End Turn','UNTAP':'Untap'};
  const phaseLabel = phaseLabels[currentPhase] || currentPhase || 'Main';

  let html = '';

  // === AUTOPLAY GRANDMASTER STATUS BANNER ===
  if (isAutoplayEnabled) {
    const statusText = isAutoplayActionPending ? '⚡ Sedang Mengeksekusi...' : (autoplayLastLog || 'Memantau Giliran...');
    html += `<div style="background:linear-gradient(135deg, rgba(39,174,96,0.25) 0%, rgba(46,204,113,0.08) 100%);border:1px solid #2ecc71;border-radius:5px;padding:4px 8px;margin-bottom:6px;display:flex;justify-content:space-between;align-items:center;box-shadow:0 0 8px rgba(46,204,113,0.2);">
      <span style="font-size:10px;color:#2ecc71;font-weight:bold;">🤖 AUTOPLAY GRANDMASTER</span>
      <span style="font-size:9px;color:#a9dfbf;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:140px;" title="${statusText}">${statusText}</span>
    </div>`;
  }

  html += `<div style="font-size:10px;color:#9a8b73;margin-bottom:6px;display:flex;justify-content:space-between;align-items:center;">
    <span>${state.is_player_turn ? '<b style="color:#ffd700">⚡ GILIRAN ANDA</b>' : '<span style="color:#888">⏳ Giliran Lawan</span>'} · T${state.turn_number}</span>
    <span style="background:rgba(255,255,255,0.07);padding:1px 6px;border-radius:10px;font-size:9px;">${phaseLabel} · ${totalCards} kartu</span>
  </div>`;

  // === LETHAL ALERT ===
  if (rec.board_analysis?.lethal_info?.has_lethal) {
    html += `<div style="background:linear-gradient(135deg,#7b0000,#c0392b);color:#ffd7d7;padding:10px;border-radius:6px;text-align:center;font-weight:bold;margin-bottom:8px;border:1px solid #e74c3c;font-size:13px;animation:pulse 1s infinite;">
      🏆 LETHAL! SERANG PLAYER LANGSUNG SEKARANG!
    </div>`;
  }

  // === ACTIVE EFFECT DECISION BANNER (TOP PRIORITY) ===
  if (rec.active_effect) {
    const ae = rec.active_effect;
    html += `<div style="background:linear-gradient(135deg,#4a154b,#1e0826);border:2px solid #e8c547;padding:8px 10px;border-radius:6px;margin-bottom:8px;box-shadow:0 0 12px rgba(232,197,71,0.3);">
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <span style="color:#e8c547;font-weight:bold;font-size:11px;">🎯 ${ae.title || 'RESOLUSI EFEK'}</span>
        ${ae.source ? `<span style="font-size:9px;color:#d1c4e9;background:rgba(255,255,255,0.1);padding:1px 5px;border-radius:3px;">${ae.source}</span>` : ''}
      </div>
      ${ae.instruction ? `<div style="font-size:9px;color:#c5a8d4;margin-top:2px;font-style:italic;">${ae.instruction}</div>` : ''}
      <div style="margin-top:5px;font-size:12px;color:#fff;">PILIH: <b style="color:#ffd700;font-size:14px;text-decoration:underline;">${ae.recommended_pick}</b></div>
      <div style="font-size:10px;color:#e1bee7;margin-top:2px;">${ae.reason}</div>
      ${ae.ranked_options?.length > 1 ? `<div style="margin-top:4px;font-size:9px;color:#9a8b73;">Ranking: ${ae.ranked_options.slice(0,3).map((o,i)=>`<span style="color:${i===0?'#ffd700':'#aaa'}">${i+1}.${o.name}</span>`).join(' ')}</div>` : ''}
    </div>`;
  }

  // === PAPAN SKOR ===
  const score = rec.board_analysis?.overall_score || 0;
  const adv   = rec.board_analysis?.advantage || 'Seimbang';
  const col   = score > 2 ? '#2ecc71' : (score < -2 ? '#e74c3c' : '#f39c12');
  const tr    = rec.board_analysis?.trigger_risk;
  const trCol = tr?.percentage > 40 ? '#e74c3c' : (tr?.percentage > 20 ? '#e67e22' : '#27ae60');
  html += `<div style="display:flex;gap:5px;margin-bottom:6px;">
    <div style="flex:1;padding:5px 8px;background:rgba(255,255,255,0.05);border-radius:5px;text-align:center;">
      <div style="font-size:9px;color:#9a8b73;">Posisi</div>
      <div style="font-weight:bold;color:${col};">${score>0?'+':''}${score}</div>
      <div style="font-size:9px;">${adv}</div>
    </div>
    ${tr ? `<div style="flex:1;padding:5px 8px;background:rgba(255,255,255,0.05);border-radius:5px;text-align:center;">
      <div style="font-size:9px;color:#9a8b73;">Trigger Risk</div>
      <div style="font-weight:bold;color:${trCol};">${tr.percentage}%</div>
      <div style="font-size:9px;">${tr.risk_level}</div>
    </div>` : ''}
  </div>`;

  // === TEMPO CLOCK (WORLD CHAMPIONSHIP GRANDMASTER ANALYTICS) ===
  const tc = rec.board_analysis?.tempo_clock;
  if (tc) {
    const pTurns = tc.player_turns > 90 ? '∞' : tc.player_turns + 'T';
    const oTurns = tc.opponent_turns > 90 ? '∞' : tc.opponent_turns + 'T';
    const badgeCol = tc.race_status.includes('UNGGUL') ? '#2ecc71' : (tc.race_status.includes('KETAT') ? '#f39c12' : '#e74c3c');
    html += `<div style="margin-bottom:6px;padding:5px 8px;background:rgba(232,197,71,0.08);border-radius:5px;border:1px solid rgba(232,197,71,0.3);">
      <div style="display:flex;justify-content:space-between;align-items:center;font-size:9px;">
        <span style="color:#ffd700;font-weight:bold;">⏱️ TEMPO RACE:</span>
        <span style="font-weight:bold;color:${badgeCol};font-size:8.5px;">${tc.race_status}</span>
      </div>
      <div style="display:flex;justify-content:space-between;align-items:center;margin-top:3px;font-size:10px;">
        <span>Player: <b style="color:#2ecc71;">${pTurns}</b></span>
        <span style="color:#666;">vs</span>
        <span>Lawan: <b style="color:#e74c3c;">${oTurns}</b></span>
      </div>
    </div>`;
  }

  // === PREDIKSI TURN DEPAN LAWAN (WORLD CHAMPIONSHIP PREDICTION MATRIX) ===
  const pnt = rec.board_analysis?.predicted_next_turn;
  if (pnt && pnt.likely_plays?.length) {
    html += `<div style="margin-bottom:6px;padding:5px 8px;background:rgba(52,152,219,0.08);border-radius:5px;border:1px solid rgba(52,152,219,0.3);">
      <div style="display:flex;justify-content:space-between;align-items:center;font-size:9px;">
        <span style="color:#3498db;font-weight:bold;">🔮 PREDIKSI TURN DEPAN (${pnt.expected_mana} Mana):</span>
        <span style="font-size:8px;color:#ffd700;">${pnt.danger_level.split(' ')[0]}</span>
      </div>
      <div style="font-size:9px;color:#d6eaf8;margin-top:2px;">Potensi: <b>${pnt.likely_plays.join(', ')}</b></div>
      <div style="font-size:8px;color:#85c1e9;margin-top:1px;font-style:italic;">🛡️ ${pnt.counterplay}</div>
    </div>`;
  }

  // === PROFIL ARCHETYPE LAWAN ===
  const arch = rec.board_analysis?.opponent_archetype;
  if (arch && arch.name !== 'Belum Terdeteksi') {
    html += `<div style="margin-bottom:6px;padding:6px 8px;background:rgba(142,68,173,0.12);border-radius:5px;border:1px solid #8e44ad;">
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <span style="font-size:10px;color:#d2b4de;font-weight:bold;">🎭 LAWAN: ${arch.name}</span>
        <span style="font-size:8px;background:#8e44ad;color:#fff;padding:1px 4px;border-radius:3px;">${arch.playstyle}</span>
      </div>
      <div style="font-size:9px;color:#e8dcc8;margin-top:2px;">⚠️ Prediksi Trigger: <b style="color:#f39c12;">${arch.predicted_triggers.join(', ')}</b></div>
      <div style="font-size:8px;color:#bbb;margin-top:1px;font-style:italic;">💡 ${arch.strategic_advice}</div>
    </div>`;
  }

  // === HAND REVEAL MEMORY: Kartu Tangan Lawan Yang Kita Tahu ===
  const revealedThreats = rec.board_analysis?.revealed_hand_threats || [];
  if (revealedThreats.length > 0) {
    html += `<div style="margin-bottom:6px;padding:6px 8px;background:rgba(231,76,60,0.10);border-radius:5px;border:1px solid #922b21;">
      <div style="font-size:10px;color:#f1948a;font-weight:bold;margin-bottom:4px;">👁️ KARTU TANGAN LAWAN YANG DIKETAHUI:</div>`;
    revealedThreats.forEach(t => {
      const sevColor = t.severity === 'KRITIS' ? '#e74c3c' : t.severity === 'TINGGI' ? '#e67e22' : '#7f8c8d';
      const castable  = t.can_cast
        ? `<span style="font-size:8px;background:#e74c3c;color:#fff;padding:1px 4px;border-radius:2px;margin-left:4px;">BISA CAST!</span>`
        : `<span style="font-size:8px;color:#555;">(${t.cost} Mana)</span>`;
      html += `<div style="display:flex;align-items:center;gap:5px;margin-bottom:3px;padding:3px 5px;background:rgba(0,0,0,0.25);border-radius:4px;border-left:2px solid ${sevColor};">
        <span style="font-size:13px;">${t.icon}</span>
        <div style="flex:1;min-width:0;">
          <div style="font-size:10px;font-weight:bold;color:#f0e6d2;">${t.name} ${castable}</div>
          <div style="font-size:9px;color:#aaa;">${t.warning}</div>
        </div>
        <span style="font-size:8px;font-weight:bold;color:${sevColor};white-space:nowrap;">${t.severity}</span>
      </div>`;
    });
    html += `<div style="font-size:8px;color:#666;margin-top:2px;font-style:italic;">
      💡 Klik "Reset Memori" di popup ekstensi jika duel baru dimulai.
    </div></div>`;
  }

  // === KEPUTUSAN TERBAIK (Single Best Action) ===
  if (rec.turn_plan?.length) {
    const s = rec.turn_plan[0]; // Always exactly 1 step from simulation engine
    html += `<div style="margin:4px 0;border-top:1px solid #2e2210;padding-top:6px;">
      <div style="color:#e8c547;font-size:10px;font-weight:bold;margin-bottom:5px;letter-spacing:0.5px;">🧠 KEPUTUSAN AI:</div>
      <div style="display:flex;gap:8px;padding:8px 10px;
        background:linear-gradient(135deg, rgba(232,197,71,0.15) 0%, rgba(255,215,0,0.05) 100%);
        border-radius:6px;
        border:1px solid rgba(232,197,71,0.4);
        box-shadow:0 2px 8px rgba(0,0,0,0.3);">
        <div style="font-size:22px;flex-shrink:0;display:flex;align-items:center;">${s.icon}</div>
        <div style="flex:1;min-width:0;">
          <div style="font-weight:bold;font-size:12px;color:#fff;line-height:1.3;">${s.action}</div>
          <div style="font-size:9px;color:#bbb;margin-top:3px;line-height:1.4;">${s.detail}</div>
        </div>
      </div>
    </div>`;
  }

  // === ATTACK DETAILS (Hanya tampil saat FASE SERANGAN) ===
  const isAttackPhase = (currentPhase === 'ATTACK');
  const hasRealAttacks = state.is_player_turn && isAttackPhase && rec.attacks?.length && rec.attacks[0]?.action !== 'NONE';
  if (hasRealAttacks) {
    const hasAnyAttack = rec.attacks.some(a => a.action === 'ATTACK');
    html += `<div style="color:#ff6b35;font-size:11px;font-weight:bold;margin:6px 0 4px;border-top:1px solid #2e2210;padding-top:6px;">
      ${hasAnyAttack ? '⚔️ DETAIL TARGET SERANGAN:' : '🛑 FASE SERANGAN:'}
    </div>`;
    
    const sortedAtk = [...rec.attacks].sort((a,b) => {
      const order = {GO_FOR_LETHAL:0, HOLD_LETHAL:1, ATTACK:2, HOLD:3, NONE:4};
      const tOrder = {DIRECT:0, CREATURE:1, SHIELDS:2, HOLD:3};
      if (a.action === b.action) return (tOrder[a.target]||9) - (tOrder[b.target]||9);
      return (order[a.action]||9) - (order[b.action]||9);
    });

    sortedAtk.forEach(atk => {
      let tgtName, icon, prioCol, bgColor;
      if (atk.action === 'GO_FOR_LETHAL' || atk.action === 'HOLD_LETHAL') {
        html += `<div style="padding:6px 8px;background:rgba(231,76,60,0.15);border-radius:5px;border:1px solid #e74c3c;margin-bottom:4px;font-size:10px;color:#ff6b6b;">
          <b>${atk.action === 'GO_FOR_LETHAL' ? '🏆 SERANG HABIS!' : '⚠️ BAHAYA TRIGGER'}</b><br>${atk.reasoning}
        </div>`;
        return;
      }
      if (atk.action === 'HOLD') {
        tgtName = 'Tahan'; icon = '🛑'; prioCol = '#95a5a6'; bgColor = '0.03';
      } else if (atk.target === 'DIRECT') {
        tgtName = 'Player Lawan (Direct!)'; icon = '🏆'; prioCol = '#e74c3c'; bgColor = '0.10';
      } else if (atk.target_creature) {
        const tc = atk.target_creature;
        tgtName = `${tc.name} (${tc.current_power || tc.power || '?'} pw)`; icon = '⚔️'; prioCol = '#e67e22'; bgColor = '0.06';
      } else {
        tgtName = 'Shield Lawan'; icon = '🛡️'; prioCol = '#2ecc71'; bgColor = '0.05';
      }
      const atkName = atk.attacker?.name || '?';
      const atkPow  = atk.attacker?.attack_power || atk.attacker?.power || '?';
      html += `<div style="display:flex;gap:6px;margin-bottom:4px;padding:5px 8px;background:rgba(255,107,53,${bgColor});border-radius:5px;border-left:2px solid ${prioCol};">
        <span style="font-size:14px;flex-shrink:0;">${icon}</span>
        <div style="flex:1;min-width:0;">
          <div style="font-size:11px;"><b>${atkName}</b> <span style="color:#aaa;font-size:9px;">(${atkPow}pw)</span> → <b style="color:${prioCol}">${tgtName}</b></div>
          <div style="font-size:9px;color:#9a8b73;margin-top:2px;">${atk.reasoning}</div>
        </div>
      </div>`;
    });
  }

  // === DRAW PROBABILITY ===
  if (rec.draw_probabilities?.length) {
    html += `<div style="margin-top:6px;padding:5px 8px;background:rgba(65,105,225,0.07);border-radius:5px;border:1px solid #1a2a44;">
      <div style="color:#6ba3ff;font-size:10px;font-weight:bold;margin-bottom:3px;">🎲 PELUANG DRAW (${rec.deck_remaining || '?'} kartu di deck):</div>`;
    rec.draw_probabilities.forEach(dp => {
      const barW = Math.min(dp.probability, 100);
      const bColor = dp.probability >= 20 ? '#2ecc71' : dp.probability >= 10 ? '#f39c12' : '#4169E1';
      html += `<div style="display:flex;align-items:center;gap:4px;margin-bottom:2px;font-size:10px;">
        <span style="min-width:100px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;" title="${dp.name}">${dp.name}</span>
        <span style="font-size:9px;color:#aaa;min-width:20px;">${dp.count_in_deck}x</span>
        <div style="flex:1;background:rgba(255,255,255,0.05);border-radius:2px;height:7px;">
          <div style="width:${barW}%;background:${bColor};height:100%;border-radius:2px;"></div>
        </div>
        <span style="color:#6ba3ff;min-width:35px;text-align:right;font-weight:bold;">${dp.probability}%</span>
      </div>`;
    });
    html += `</div>`;
  }

  // === KOMBO & SINERGI (Hanya saat Fase MAIN) ===
  if (rec.combos?.length && currentPhase === 'MAIN') {
    html += `<div style="margin-top:6px;padding:6px 8px;background:rgba(241,196,15,0.06);border-radius:5px;border:1px solid #4a3d10;">
      <div style="color:#f1c40f;font-size:10px;font-weight:bold;margin-bottom:4px;">🔥 KOMBO TERSEDIA:</div>`;
    rec.combos.forEach(cb => {
      const isReady = cb.can_execute_now || cb.status?.includes('SIAP');
      const bColor = isReady ? '#2ecc71' : '#f39c12';
      html += `<div style="margin-bottom:6px;padding:5px 6px;background:rgba(255,255,255,0.02);border-radius:4px;border-left:2px solid ${bColor};">
        <div style="display:flex;justify-content:space-between;align-items:center;">
          <b style="font-size:11px;">${cb.icon} ${cb.name}</b>
          <span style="font-size:9px;color:${bColor};font-weight:bold;background:rgba(0,0,0,0.3);padding:1px 5px;border-radius:3px;">${cb.status}</span>
        </div>
        <div style="font-size:9px;color:#9a8b73;margin:2px 0 3px;">${cb.description}</div>`;
      if (cb.steps?.length) {
        html += `<div style="padding:4px 6px;background:rgba(0,0,0,0.35);border-radius:3px;margin-top:3px;">
          <div style="font-size:8px;color:#ffd700;font-weight:bold;letter-spacing:0.5px;">URUTAN LANGKAH:</div>`;
        cb.steps.forEach(st => {
          html += `<div style="font-size:9px;color:#f0e6d2;margin-top:2px;line-height:1.4;">${st}</div>`;
        });
        html += `</div>`;
      }
      html += `</div>`;
    });
    html += `</div>`;
  }

  // === STRATEGI ===
  if (rec.overall_strategy?.name) {
    html += `<div style="margin-top:6px;padding:5px 8px;background:rgba(255,255,255,0.02);border-radius:5px;font-size:10px;border-top:1px solid #2e2210;padding-top:8px;">
      🎯 Strategi: <b>${rec.overall_strategy.name}</b><br>
      <span style="color:#9a8b73;">${rec.overall_strategy.description}</span>
    </div>`;
  }

  panel.innerHTML = html;

  // Terapkan highlight visual langsung pada kartu di arena dan tangan
  applyInGameHighlights(rec, state);

  // Jalankan langkah Autoplay otomatis jika aktif
  triggerAutoplay(rec, state);
}

// ── IN-GAME VISUAL CARD HIGHLIGHTER ──
function applyInGameHighlights(rec, state) {
  // 1. Bersihkan highlight dan badge lama
  document.querySelectorAll('.dma-highlight').forEach(el => {
    el.classList.remove('dma-highlight', 'dma-glow-charge', 'dma-glow-play', 'dma-glow-target');
    const badge = el.querySelector('.dma-card-badge');
    if (badge) badge.remove();
  });

  if (!state.is_player_turn && !rec.active_effect) return;

  function highlightEl(el, glowClass, badgeText, badgeColor) {
    if (!el) return;
    el.classList.add('dma-highlight', glowClass);
    if (!el.querySelector('.dma-card-badge')) {
      const b = document.createElement('div');
      b.className = 'dma-card-badge';
      b.textContent = badgeText;
      b.style.cssText = `
        position:absolute; top:-10px; left:50%; transform:translateX(-50%);
        background:${badgeColor}; color:#fff; font-size:10px; font-weight:bold;
        padding:2px 7px; border-radius:4px; box-shadow:0 0 8px rgba(0,0,0,0.85);
        z-index:99999; pointer-events:none; white-space:nowrap;
        letter-spacing:0.5px; animation:dmaPulse 1.1s infinite alternate;
        border:1px solid rgba(255,255,255,0.4);
      `;
      el.style.position = 'relative';
      el.appendChild(b);
    }
  }

  // 1. Highlight Kartu untuk Charge Mana (fase CHARGE)
  if (state.current_phase === 'CHARGE' && rec.mana_charge?.action === 'CHARGE' && rec.mana_charge?.card) {
    const chargeCardName = (rec.mana_charge.card.name || '').toLowerCase();
    const handEls = document.querySelectorAll('.side.me .zone.hand .card, .hand-dock .card');
    for (const el of handEls) {
      const label = (el.getAttribute('aria-label') || el.getAttribute('title') || '').toLowerCase();
      if (label.includes(chargeCardName)) {
        highlightEl(el, 'dma-glow-charge', '⚡ CHARGE INI', '#f39c12');
        break; // Cukup tandai 1 kartu
      }
    }
  }

  // 2. Highlight Kartu untuk Dimainkan (fase MAIN)
  if (state.current_phase === 'MAIN' && rec.plays?.length && rec.plays[0]?.cards?.length) {
    const playCards = rec.plays[0].cards.map(c => (c.name || '').toLowerCase());
    const handEls = document.querySelectorAll('.side.me .zone.hand .card, .hand-dock .card');
    handEls.forEach(el => {
      const label = (el.getAttribute('aria-label') || el.getAttribute('title') || '').toLowerCase();
      for (let i = 0; i < playCards.length; i++) {
        if (label.includes(playCards[i])) {
          const badgeLabel = playCards.length > 1 ? `🃏 PLAY #${i+1}` : `🃏 MAINKAN`;
          highlightEl(el, 'dma-glow-play', badgeLabel, '#2980b9');
          break;
        }
      }
    });
  }

  // 3. Highlight Target di Arena:
  // A. Pilihan Efek Aktif (Terror Pit, Corile, Aqua Surfer, dsb)
  if (rec.active_effect) {
    const pickText = (rec.active_effect.recommended_pick || '').toLowerCase();
    const oppBoardEls = document.querySelectorAll('.side.opp .zone.battle .card, .arena .card.target, .arena .card.choice');
    oppBoardEls.forEach(el => {
      const label = (el.getAttribute('aria-label') || el.getAttribute('title') || '').toLowerCase();
      const cleanName = label.split(',')[0].split(' · ')[0].trim();
      if (cleanName && pickText.includes(cleanName)) {
        highlightEl(el, 'dma-glow-target', '🎯 TARGET INI!', '#e74c3c');
      }
    });
  }

  // B. Target Serangan Musuh (fase ATTACK)
  if (state.current_phase === 'ATTACK' && rec.attacks?.length) {
    const enemyAtks = rec.attacks.filter(a => a.action === 'ATTACK' && a.target_creature);
    if (enemyAtks.length > 0) {
      const targetEnemyName = (enemyAtks[0].target_creature.name || '').toLowerCase();
      const oppBoardEls = document.querySelectorAll('.side.opp .zone.battle .card');
      oppBoardEls.forEach(el => {
        const label = (el.getAttribute('aria-label') || el.getAttribute('title') || '').toLowerCase();
        if (label.includes(targetEnemyName)) {
          highlightEl(el, 'dma-glow-target', '⚔️ SERANG INI!', '#e74c3c');
        }
      });
    }
  }
}

// ── BANNER PEMBELAJARAN AI ──
function renderLearningBanner(d) {
  const panel = document.getElementById('dma-advice');
  if (!panel) return;
  const insights = (d.new_insights || []).map(i => `<div style="font-size:10px;color:#ffd700;margin-top:2px;">${i}</div>`).join('')
    || '<div style="font-size:9px;color:#ccc;margin-top:2px;">Statistik kartu dan taktik duel ini telah disimpan ke memori AI.</div>';

  panel.innerHTML = `
    <div style="background:linear-gradient(135deg, rgba(39,174,96,0.25) 0%, rgba(46,204,113,0.10) 100%);border:2px solid #2ecc71;border-radius:6px;padding:10px;margin-bottom:8px;box-shadow:0 0 15px rgba(46,204,113,0.3);">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
        <span style="font-size:12px;font-weight:bold;color:#2ecc71;">🎓 DUEL SELESAI — AI NAIK LEVEL!</span>
        <span style="font-size:10px;background:#2ecc71;color:#000;font-weight:bold;padding:1px 6px;border-radius:3px;">Lv. ${d.ai_level || 1}</span>
      </div>
      <div style="font-size:10px;color:#e8dcc8;line-height:1.4;">
        <b>+${d.xp_gained || 50} XP</b> didapatkan (Total: ${d.current_xp || 0} XP)<br>
        Rekor AI: <b>${d.total_matches || 1} Match</b> · Win Rate: <b>${d.win_rate || 0}%</b>
      </div>
      <div style="margin-top:6px;padding-top:6px;border-top:1px solid rgba(46,204,113,0.3);">
        <b style="font-size:9px;color:#a9dfbf;">HASIL ANALISA & ADAPTASI:</b>
        ${insights}
      </div>
      <div style="font-size:8px;color:#888;margin-top:6px;font-style:italic;">
        AI otomatis berevolusi dan makin cerdas di duel selanjutnya!
      </div>
    </div>
  `;
}

// ══════════════════════════════════════════════════════════════
// 🤖 GRANDMASTER WORLD CHAMPIONSHIP AUTOPLAY ENGINE
// ══════════════════════════════════════════════════════════════

function triggerAutoplay(rec, state) {
  if (!isAutoplayEnabled) return;
  if (!state.is_player_turn && !rec.active_effect) return;
  if (isAutoplayActionPending) return;

  if (autoplayTimer) clearTimeout(autoplayTimer);

  const speedDelays = { fast: 450, normal: 900, slow: 1800 };
  const delay = speedDelays[autoplaySpeed] || 900;

  isAutoplayActionPending = true;
  autoplayTimer = setTimeout(() => {
    try {
      executeAutoplayStep(rec, state);
    } catch (err) {
      console.error('[DMA Autoplay Error]', err);
    } finally {
      setTimeout(() => {
        isAutoplayActionPending = false;
      }, 1500); // Wait for virtual agent animations to finish
    }
  }, delay);
}

function executeAutoplayStep(rec, state) {
  if (!isAutoplayEnabled) {
    VirtualAgent.hide();
    return;
  }
  VirtualAgent.show();

  if (!state.is_player_turn && !rec.active_effect) {
    VirtualAgent.setBadge('⏳ MENUNGGU LAWAN');
    logAutoplay('⏳ Menunggu giliran pemain...');
    return;
  }

  const plan = rec.turn_plan?.[0] || {};
  const planAction = plan.action || '';
  const planDetail = plan.detail || '';
  const planActionLower = planAction.toLowerCase();
  const currentPhase = state.current_phase || 'MAIN';

  function findHandCardEl(cardName) {
    if (!cardName) return null;
    const qNorm = normalizeCardKey(cardName);
    const qAlpha = cardName.toLowerCase().replace(/[^a-z0-9]/g, '');
    const qWords = qNorm.split(' ').filter(w => w.length >= 3);
    const handEls = document.querySelectorAll('.side.me .zone.hand .card, .hand-dock .card, .zone.hand .card, .side.me .hand .card, .hand .card, [data-zone="hand"] .card, .side.me .hand-dock .card');

    for (const el of handEls) {
      const parsed = parseCard(el, false);
      if (parsed && parsed.name) {
        const pNorm = normalizeCardKey(parsed.name);
        const pAlpha = parsed.name.toLowerCase().replace(/[^a-z0-9]/g, '');
        const pId = normalizeCardKey(parsed.id || '');
        if (pNorm === qNorm || pAlpha === qAlpha || pId === qNorm) return el;
        if (pNorm.includes(qNorm) || qNorm.includes(pNorm)) return el;
      }
      const raw = ((el.getAttribute('aria-label') || '') + ' ' + (el.getAttribute('title') || '') + ' ' + (el.dataset?.card || '')).toLowerCase();
      const rawNorm = normalizeCardKey(raw);
      if (rawNorm.includes(qNorm) || (qAlpha.length >= 4 && raw.replace(/[^a-z0-9]/g, '').includes(qAlpha))) {
        return el;
      }
      const img = el.querySelector('img');
      if (img && img.src) {
        const srcLower = img.src.toLowerCase();
        if (qWords.some(w => srcLower.includes(w))) return el;
      }
    }
    return null;
  }

  function findBattleCardEl(cardName, isPlayer = true) {
    if (!cardName) return null;
    const qNorm = normalizeCardKey(cardName);
    const qAlpha = cardName.toLowerCase().replace(/[^a-z0-9]/g, '');
    const qWords = qNorm.split(' ').filter(w => w.length >= 3);
    const selector = isPlayer ? '.side.me .zone.battle .card, .side.me .battle .card, .side.me [data-zone="battle"] .card' : '.side.opp .zone.battle .card, .side.opp .battle .card, .side.opp [data-zone="battle"] .card';
    const bEls = document.querySelectorAll(selector);

    for (const el of bEls) {
      const parsed = parseCard(el, false);
      if (parsed && parsed.name) {
        const pNorm = normalizeCardKey(parsed.name);
        const pAlpha = parsed.name.toLowerCase().replace(/[^a-z0-9]/g, '');
        const pId = normalizeCardKey(parsed.id || '');
        if (pNorm === qNorm || pAlpha === qAlpha || pId === qNorm) return el;
        if (pNorm.includes(qNorm) || qNorm.includes(pNorm)) return el;
      }
      const raw = ((el.getAttribute('aria-label') || '') + ' ' + (el.getAttribute('title') || '') + ' ' + (el.dataset?.card || '')).toLowerCase();
      const rawNorm = normalizeCardKey(raw);
      if (rawNorm.includes(qNorm) || (qAlpha.length >= 4 && raw.replace(/[^a-z0-9]/g, '').includes(qAlpha))) {
        return el;
      }
      const img = el.querySelector('img');
      if (img && img.src) {
        const srcLower = img.src.toLowerCase();
        if (qWords.some(w => srcLower.includes(w))) return el;
      }
    }
    if (isPlayer) {
      return document.querySelector('.side.me .zone.battle .card:not(.used):not(.tapped):not(.sick), .side.me .battle .card:not(.used):not(.tapped):not(.sick)') || null;
    }
    return null;
  }

  function findManaZoneEl() {
    const el = document.querySelector('.side.me .mana-zone, .mana-zone, .side.me .mana-tray, .side.me .zone.mana, .side.me .mana, .mana-tray, [data-zone="mana"], [data-zone="manazone"], .side.me .zone-mana, .side.me .mana-dock, .mana-dock, .side.me .tray-mana, .tray-mana');
    if (el) return el;
    for (const d of document.querySelectorAll('.side.me div, .arena div, div')) {
      if ((d.textContent || '').trim().toUpperCase() === 'MANA ZONE') return d;
    }
    return null;
  }

  function findBattleZoneEl() {
    return document.querySelector('.side.me .zone.battle, .side.me .battle, [data-zone="battle"], .battle-zone, .arena, .table, .board, #arena, .battlefield');
  }

  function findOpponentTargetEl() {
    const shield = document.querySelector('.side.opp [data-shield], .side.opp .zone.shield .card, .side.opp .shield, .side.opp .shields .card, .side.opp .shield-tray [data-shield], .side.opp .shield-dock [data-shield]');
    if (shield) return shield;
    const avatar = document.querySelector('.side.opp .avatar, .side.opp .player-avatar, .side.opp .hero, .side.opp .shield-tray, .side.opp .zone.shield, .side.opp');
    return avatar || document.querySelector('.side.opp');
  }

  function findCardModalActionBtn(preferredAction = '') {
    // HANYA cari tombol di modal dialog terbuka / popover kartu!
    // JANGAN PERNAH cari tombol umum seperti stone button!
    const modalContainers = document.querySelectorAll(
      'dialog[open], .modal:not([style*="display: none"]), [role="dialog"], .card-actions, .card-menu, .popover:not([style*="display: none"]), .card-modal, .card-popup, .card-options, .choice-menu'
    );
    if (!modalContainers.length) return null;

    const actionKeywords = {
      charge: ['charge', 'to mana', 'put in mana', 'mana', 'taruh di mana', 'ke mana'],
      play:   ['summon', 'cast', 'evolve', 'play', 'mainkan', 'panggil', 'gunakan'],
      evolve: ['evolve', 'evolusi'],
      attack: ['attack', 'serang', 'strike']
    };

    let searchList = [];
    if (preferredAction === 'charge') searchList = actionKeywords.charge;
    else if (preferredAction === 'play') searchList = actionKeywords.play;
    else if (preferredAction === 'evolve') searchList = actionKeywords.evolve;
    else if (preferredAction === 'attack') searchList = actionKeywords.attack;
    else searchList = [...actionKeywords.play, ...actionKeywords.charge, ...actionKeywords.attack];

    for (const container of modalContainers) {
      if (container.closest('#dma-overlay') || container.id === 'dma-overlay') continue;
      const buttons = container.querySelectorAll('button, .btn, [role="button"]');
      for (const btn of buttons) {
        if (btn.disabled || btn.getAttribute('disabled') !== null) continue;
        if (btn.classList.contains('stone-end') || btn.classList.contains('stone') || btn.closest('.stone')) continue;

        const txt = (btn.textContent || btn.getAttribute('aria-label') || '').toLowerCase().trim();
        if (txt.includes('inspect') || txt.includes('cancel') || txt.includes('batal') || txt.includes('close') || 
            txt.includes('tutup') || txt.includes('surrender') || txt.includes('settings') || txt.includes('auto:')) continue;
        // Tolak tombol stone yang mungkin tertangkap
        if (txt.includes('skip') || txt.includes('phase')) continue;

        for (const kw of searchList) {
          if (txt === kw || txt.startsWith(kw + ' ') || txt.endsWith(' ' + kw) || txt.includes(kw)) {
            return btn;
          }
        }
      }
    }
    return null;
  }

  function findEndTurnBtn() {
    const candidates = document.querySelectorAll('.stone-end, .btn-end-turn, #btn-end-phase, .end-turn, .pass-btn, button.end-turn, [data-action="end-turn"], #btn-pass, .btn.end, button');
    for (const btn of candidates) {
      if (btn.disabled || btn.getAttribute('disabled') !== null) continue;
      if (btn.closest('#dma-overlay') || btn.id?.startsWith('dma-')) continue;
      const txt = (btn.textContent || btn.getAttribute('aria-label') || '').toLowerCase();
      if (txt.includes('opponent') || txt.includes('waiting') || txt.includes('ai duelist') || txt.includes('musuh')) continue;
      if (btn.classList.contains('waiting') || btn.classList.contains('opponent')) continue;

      if (txt.includes('end turn') || txt.includes('end phase') || txt.includes('pass') || txt.includes('your turn') || btn.classList.contains('stone-end')) {
        return btn;
      }
    }
    const stone = document.querySelector('.stone-end:not([disabled]), .stone:not([disabled])');
    if (stone) {
      const txt = (stone.textContent || '').toLowerCase();
      if (!txt.includes('opponent') && !txt.includes('waiting') && !txt.includes('ai duelist')) {
        return stone;
      }
    }
    return null;
  }

  function logAutoplay(msg) {
    autoplayLastLog = msg;
    const logEl = document.querySelector('#dma-advice span[style*="a9dfbf"]');
    if (logEl) logEl.textContent = msg;
    console.log(`[DMA Grandmaster Autoplay] ${msg}`);
  }

  function trackAction(signature) {
    if (lastActionSignature === signature) {
      consecutiveActionCount++;
    } else {
      lastActionSignature = signature;
      consecutiveActionCount = 1;
    }
    if (consecutiveActionCount >= 4) {
      logAutoplay('⚠️ Mencoba pulihkan giliran...');
      const openBtn = findCardModalActionBtn();
      if (openBtn) {
        VirtualAgent.clickTarget(openBtn, 'Batal/Pulihkan');
        consecutiveActionCount = 0;
        return false;
      }
      const closeBtn = document.querySelector('button.close, button.cancel, [data-action="close"], .btn-cancel');
      if (closeBtn) VirtualAgent.clickTarget(closeBtn, 'Tutup Dialog');
      
      if (state.is_player_turn) {
        const eb = findEndTurnBtn();
        if (eb) VirtualAgent.clickTarget(eb, 'End Turn');
      }
      consecutiveActionCount = 0;
      return false;
    }
    return true;
  }

  // ══════════════════════════════════════════════════════════════
  // 0. DIALOG / MODAL ACTION CONFIRMATION (TOP PRIORITY BILA MODAL TERBUKA)
  // ══════════════════════════════════════════════════════════════
  const openModalBtn = findCardModalActionBtn();
  if (openModalBtn) {
    const btnTxt = openModalBtn.textContent.trim();
    VirtualAgent.clickTarget(openModalBtn, btnTxt);
    logAutoplay(`⚡ Konfirmasi Modal: "${btnTxt}"`);
    return;
  }

  // ══════════════════════════════════════════════════════════════
  // 1. ACTIVE EFFECT RESOLUTION (TOP PRIORITY)
  // ══════════════════════════════════════════════════════════════
  if (rec.active_effect) {
    const pick = rec.active_effect.recommended_pick;
    const sig = `EFFECT_${pick}`;
    if (!trackAction(sig)) return;

    const optionBtns = document.querySelectorAll('.effect-option, #effect-use, #effect-keep, .effect-decision button, .choice-btn, button.btn');
    for (const btn of optionBtns) {
      const txt = (btn.textContent || btn.getAttribute('aria-label') || '').toLowerCase();
      if (txt.includes(pick.toLowerCase()) || pick.toLowerCase().includes(txt)) {
        VirtualAgent.clickTarget(btn, pick);
        logAutoplay(`🎯 Efek: Memilih "${pick}"`);
        return;
      }
    }
    if (optionBtns.length > 0) {
      VirtualAgent.clickTarget(optionBtns[0], 'Opsi 1');
      logAutoplay(`🎯 Efek: Memilih opsi pertama`);
      return;
    }

    const boardTargets = document.querySelectorAll('.arena .card.target, .arena .card.choice, .arena .card.selectable, .arena .card.glow, .side.opp .zone.battle .card');
    for (const el of boardTargets) {
      const label = (el.getAttribute('aria-label') || el.getAttribute('title') || '').toLowerCase();
      if (label.includes(pick.toLowerCase())) {
        VirtualAgent.clickTarget(el, pick);
        logAutoplay(`🎯 Efek: Target board "${pick}"`);
        return;
      }
    }
    if (boardTargets.length > 0) {
      VirtualAgent.clickTarget(boardTargets[0], 'Target Board');
      logAutoplay(`🎯 Efek: Memilih target board`);
      return;
    }
    return;
  }

  // ══════════════════════════════════════════════════════════════
  // 2. CHARGE MANA (FASE CHARGE)
  // ══════════════════════════════════════════════════════════════
  const isChargeAction = planActionLower.includes('charge mana') || planActionLower.includes('charge:');
  
  if (isChargeAction && (currentPhase === 'CHARGE' || state.can_charge_mana)) {
    let cardName = rec.mana_charge?.card?.name || '';
    const match = planAction.match(/Charge Mana:\s*(.+)$/i) || planAction.match(/Charge:\s*(.+)$/i);
    if (match) cardName = match[1].trim();

    const sig = `CHARGE_${cardName || 'CARD'}_T${state.turn_number}`;
    if (!trackAction(sig)) return;

    const cardEl = findHandCardEl(cardName);
    if (cardEl) {
      VirtualAgent.clickTarget(cardEl, `Charge ${cardName}`, () => {
        setTimeout(() => {
          const modalChargeBtn = findCardModalActionBtn('charge');
          if (modalChargeBtn) {
            VirtualAgent.clickTarget(modalChargeBtn, modalChargeBtn.textContent.trim());
            logAutoplay(`⚡ Konfirmasi Charge Mana: ${modalChargeBtn.textContent.trim()}`);
          } else {
            const manaTray = findManaZoneEl();
            if (manaTray) {
              VirtualAgent.dragTarget(cardEl, manaTray, cardName);
            }
          }
        }, 250);
      });

      hasChargedThisTurn = true;
      logAutoplay(`⚡ Charge Mana: ${cardName}`);
      return;
    } else {
      logAutoplay(`⚠️ Kartu "${cardName}" tidak ditemukan di tangan.`);
    }
  }

  // Jika AI memutuskan untuk LEWATI Charge Mana, klik tombol "SKIP MANA" di stone button
  if (rec.mana_charge?.action === 'SKIP' && !hasChargedThisTurn && currentPhase === 'CHARGE') {
    for (const b of document.querySelectorAll('.stone-end, .stone, button')) {
      const bText = (b.textContent || '').toLowerCase();
      if (bText.includes('skip mana')) {
        VirtualAgent.clickTarget(b, 'SKIP MANA');
        hasChargedThisTurn = true;
        logAutoplay(`⏭️ Lewati Mana: Klik SKIP MANA`);
        return;
      }
    }
  }

  // ══════════════════════════════════════════════════════════════
  // 3. MAINKAN KARTU / SPELL / EVOLUSI (FASE MAIN)
  // ══════════════════════════════════════════════════════════════
  const isPlayAction = planActionLower.includes('mainkan') || planActionLower.includes('evolusi');

  if (isPlayAction && currentPhase === 'MAIN') {
    let cardName = rec.plays?.[0]?.cards?.[0]?.name || '';
    const playMatch = planAction.match(/Mainkan:\s*([^→+\n\r]+)/i);
    if (playMatch) cardName = playMatch[1].trim();

    const sig = `PLAY_${cardName || 'CARD'}_T${state.turn_number}`;
    if (!trackAction(sig)) return;

    const cardEl = findHandCardEl(cardName);
    if (cardEl) {
      VirtualAgent.clickTarget(cardEl, `Mainkan ${cardName}`, () => {
        setTimeout(() => {
          const modalPlayBtn = findCardModalActionBtn('play');
          if (modalPlayBtn) {
            VirtualAgent.clickTarget(modalPlayBtn, modalPlayBtn.textContent.trim(), () => {
              if (planActionLower.includes('evolusi') || planDetail.includes('di atas')) {
                let baseName = '';
                const baseMatch = planDetail.match(/di atas ([^+\n\r]+)/i) || planAction.match(/Target:\s*([^+\n\r]+)/i);
                if (baseMatch) baseName = baseMatch[1].trim();

                setTimeout(() => {
                  const baitEl = findBattleCardEl(baseName, true) || document.querySelector('.side.me .zone.battle .card.choice, .side.me .zone.battle .card.selectable');
                  if (baitEl) {
                    VirtualAgent.clickTarget(baitEl, `Evolusi ${baseName || 'Bait'}`);
                    logAutoplay(`🌟 Evolusi ${cardName} ke atas ${baseName || 'Bait'}`);
                  }
                }, 350);
              }
            });
            logAutoplay(`🃏 Konfirmasi Mainkan: ${modalPlayBtn.textContent.trim()}`);
          } else {
            const battleZone = findBattleZoneEl();
            if (battleZone) {
              VirtualAgent.dragTarget(cardEl, battleZone, cardName);
            }
          }
        }, 250);
      });

      logAutoplay(`🃏 Mainkan: ${cardName}`);
      return;
    } else {
      logAutoplay(`⚠️ Kartu "${cardName}" tidak ditemukan di tangan.`);
    }
  }

  // Jika AI merekomendasikan transisi ke ATTACK PHASE:
  if (planActionLower.includes('attack phase') || planActionLower.includes('masuk ke attack')) {
    for (const b of document.querySelectorAll('.stone-end, .stone, button')) {
      const bText = (b.textContent || '').toLowerCase();
      if (bText.includes('attack phase')) {
        VirtualAgent.clickTarget(b, 'ATTACK PHASE');
        logAutoplay(`⚔️ Masuk ke Attack Phase`);
        return;
      }
    }
  }

  // ══════════════════════════════════════════════════════════════
  // 4. COMBAT & LETHAL (FASE ATTACK)
  // ══════════════════════════════════════════════════════════════
  const isAttackAction = planActionLower.includes('serang') || planActionLower.includes('direct attack') || planActionLower.includes('lethal');
  const validAttacks = (rec.attacks || []).filter(a => a.action === 'ATTACK' || a.action === 'GO_FOR_LETHAL');

  if (isAttackAction) {
    // Bila masih di fase MAIN tetapi mau serang, klik tombol ATTACK PHASE dulu
    if (currentPhase !== 'ATTACK') {
      for (const b of document.querySelectorAll('.stone-end, .stone, button')) {
        const bText = (b.textContent || '').toLowerCase();
        if (bText.includes('attack phase')) {
          VirtualAgent.clickTarget(b, 'ATTACK PHASE');
          logAutoplay(`⚔️ Masuk ke Attack Phase`);
          return;
        }
      }
    }

    if (validAttacks.length > 0) {
      const atk = validAttacks[0];
      let attackerName = atk.attacker?.name;
      
      const atkMatch = planAction.match(/^(?:🛡️|⚔️|🏆)?\s*([^(→]+)/i);
      if (atkMatch && !atkMatch[1].toLowerCase().includes('lethal') && !atkMatch[1].toLowerCase().includes('mainkan') && !atkMatch[1].toLowerCase().includes('tahan')) {
        attackerName = atkMatch[1].trim();
      }

      const sig = `ATK_${attackerName || 'CREATURE'}_T${state.turn_number}`;
      if (!trackAction(sig)) return;

      const attackerEl = findBattleCardEl(attackerName, true);
      if (attackerEl) {
        VirtualAgent.clickTarget(attackerEl, `Pilih ${attackerName}`, () => {
          setTimeout(() => {
            const modalAtkBtn = findCardModalActionBtn('attack');
            const doTarget = () => {
              if (atk.target_creature) {
                const targetEl = findBattleCardEl(atk.target_creature.name, false) || document.querySelector('.side.opp .zone.battle .card.target, .side.opp .zone.battle .card.choice');
                if (targetEl) {
                  VirtualAgent.clickTarget(targetEl, `Serang ${atk.target_creature.name}`);
                  logAutoplay(`⚔️ Serang Creature: ${attackerName} ➔ ${atk.target_creature.name}`);
                }
              } else {
                const targetEl = findOpponentTargetEl();
                if (targetEl) {
                  VirtualAgent.clickTarget(targetEl, 'Serang Shield/Player');
                  logAutoplay(`🛡️ Serang Shield/Direct: ${attackerName} ➔ Lawan`);
                }
              }
            };

            if (modalAtkBtn) {
              VirtualAgent.clickTarget(modalAtkBtn, 'Serang', () => {
                setTimeout(doTarget, 200);
              });
            } else {
              doTarget();
            }
          }, 200);
        });

        return;
      } else {
        logAutoplay(`⚠️ Penyerang "${attackerName}" tidak ditemukan di arena.`);
      }
    }
  }

  // ══════════════════════════════════════════════════════════════
  // 5. END TURN (Hanya dieksekusi saat giliran benar-benar selesai!)
  // ══════════════════════════════════════════════════════════════

  // ANTI-SKIP GUARD: JANGAN PERNAH End Turn jika belum charge mana dan masih punya kartu di tangan!
  if (!hasChargedThisTurn && currentPhase === 'CHARGE' && (state.player.hand || []).length > 0 && rec.mana_charge?.action === 'CHARGE') {
    logAutoplay('⏳ Menahan End Turn — bersiap Charge Mana...');
    return;
  }

  // ANTI-SKIP GUARD: JANGAN End Turn jika masih ada kartu playable di tangan saat fase MAIN!
  if (currentPhase === 'MAIN' && (rec.plays || []).length > 0 && (state.player.available_mana || 0) > 0) {
    logAutoplay('⏳ Menahan End Turn — masih ada kartu yang bisa dimainkan...');
    return;
  }

  // ANTI-SKIP GUARD: JANGAN End Turn jika masih ada penyerang aktif yang belum menyerang!
  if (validAttacks.length > 0 && !planActionLower.includes('tahan semua') && !planActionLower.includes('hold')) {
    logAutoplay('⏳ Menahan End Turn — masih ada creature yang bisa menyerang...');
    return;
  }

  const isEndTurnExplicit = planActionLower.includes('end turn') || planActionLower.includes('selesai main') || planActionLower.includes('tahan semua');
  const hasNoRemainingPlays = (!rec.plays || rec.plays.length === 0) && (!rec.mana_charge || rec.mana_charge.action !== 'CHARGE' || hasChargedThisTurn);
  const hasNoAttackers = (validAttacks.length === 0);

  if (state.is_player_turn && (isEndTurnExplicit || (hasNoRemainingPlays && hasNoAttackers))) {
    const sig = `END_TURN_T${state.turn_number}`;
    if (!trackAction(sig)) return;

    const endBtn = findEndTurnBtn();
    if (endBtn) {
      VirtualAgent.clickTarget(endBtn, 'END TURN');
      logAutoplay(`🏁 Mengakhiri Giliran (End Turn)`);
      consecutiveActionCount = 0;
    }
  }
}


