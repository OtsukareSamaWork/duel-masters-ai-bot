// bridge.js — ISOLATED WORLD
// Jembatan antara reader.js (DOM game) dan background.js (API Chrome)

// 1. Inisialisasi otomatis dari chrome.storage saat halaman dimuat
function initFromStorage() {
  chrome.storage.local.get(['syncEnabled', 'playerDeck', 'oppRevealedHand', 'autoplayEnabled', 'autoplaySpeed'], (r) => {
    const isSync = (r.syncEnabled !== false);
    window.postMessage({ dma_cmd: 'toggleSync', state: isSync }, '*');
    if (r.playerDeck) {
      window.postMessage({ dma_cmd: 'updateDeck', deck: r.playerDeck }, '*');
    }
    if (r.oppRevealedHand) {
      window.postMessage({ dma_cmd: 'initRevealedHand', oppRevealedHand: r.oppRevealedHand }, '*');
    }
    window.postMessage({
      dma_cmd: 'initAutoplay',
      state: (r.autoplayEnabled === true),
      speed: r.autoplaySpeed || 'normal'
    }, '*');
  });
}

// Jalankan inisialisasi segera
initFromStorage();
setTimeout(initFromStorage, 500);
setTimeout(initFromStorage, 1500);

// 2. Terima pesan dari popup (ON/OFF) lalu forward ke reader
chrome.runtime.onMessage.addListener((req) => {
  if (req.action === 'toggleSync') {
    window.postMessage({ dma_cmd: 'toggleSync', state: req.state }, '*');
  }
  if (req.action === 'updateDeck') {
    window.postMessage({ dma_cmd: 'updateDeck', deck: req.deck }, '*');
  }
  // Autoplay control
  if (req.action === 'toggleAutoplay') {
    window.postMessage({ dma_cmd: 'toggleAutoplay', state: req.state }, '*');
  }
  if (req.action === 'setAutoplaySpeed') {
    window.postMessage({ dma_cmd: 'setAutoplaySpeed', speed: req.speed }, '*');
  }
  // Hand Reveal Memory: popup → reader.js
  if (req.action === 'revealOppCard') {
    window.postMessage({ dma_cmd: 'revealOppCard', cardName: req.cardName, source: req.source || 'manual' }, '*');
  }
  if (req.action === 'resetRevealedHand') {
    window.postMessage({ dma_cmd: 'resetRevealedHand' }, '*');
  }
});

// 3. Terima request data (Cards / Analyze / Learn) dari reader.js, teruskan ke background.js
window.addEventListener('message', (e) => {
  if (!e.data || !e.data.dma_cmd) return;
  
  if (e.data.dma_cmd === 'fetchCards_req') {
    try {
      chrome.runtime.sendMessage({ action: 'fetchCards' }, (response) => {
        const err = chrome.runtime.lastError;
        window.postMessage({
          dma_cmd: 'fetchCards_res',
          response: err ? { success: false, error: err.message } : response
        }, '*');
      });
    } catch (ex) {
      window.postMessage({ dma_cmd: 'fetchCards_res', response: { success: false, error: ex.toString() } }, '*');
    }
  }
  
  if (e.data.dma_cmd === 'analyzeGame_req') {
    try {
      chrome.runtime.sendMessage({ action: 'analyzeGame', gameState: e.data.gameState }, (response) => {
        const err = chrome.runtime.lastError;
        window.postMessage({
          dma_cmd: 'analyzeGame_res',
          response: err ? { success: false, error: err.message } : response
        }, '*');
      });
    } catch (ex) {
      window.postMessage({ dma_cmd: 'analyzeGame_res', response: { success: false, error: ex.toString() } }, '*');
    }
  }

  if (e.data.dma_cmd === 'learnMatch_req') {
    try {
      chrome.runtime.sendMessage({ action: 'learnMatch', matchData: e.data.matchData }, (response) => {
        const err = chrome.runtime.lastError;
        window.postMessage({
          dma_cmd: 'learnMatch_res',
          response: err ? { success: false, error: err.message } : response
        }, '*');
      });
    } catch (ex) {
      window.postMessage({ dma_cmd: 'learnMatch_res', response: { success: false, error: ex.toString() } }, '*');
    }
  }
});
