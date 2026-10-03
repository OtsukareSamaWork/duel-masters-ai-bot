// background.js — SERVICE WORKER
// Menjalankan fetch API dari background untuk bypass CSP dan Mixed Content limit di website

const ANALYZE_URL   = 'https://revarend.pythonanywhere.com/api/analyze';
const CARDS_URL     = 'https://revarend.pythonanywhere.com/api/cards';
const LEARN_MATCH_URL = 'https://revarend.pythonanywhere.com/api/learn/match';
const LEARN_STATS_URL = 'https://revarend.pythonanywhere.com/api/learn/stats';

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'fetchCards') {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 5000);
    fetch(CARDS_URL, { signal: controller.signal })
      .then(r => r.json())
      .then(data => {
        clearTimeout(timeoutId);
        sendResponse({ success: true, data });
      })
      .catch(err => {
        clearTimeout(timeoutId);
        sendResponse({ success: false, error: 'Server offline / ' + err.toString() });
      });
    return true;
  }
  
  if (request.action === 'analyzeGame') {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 6000);
    fetch(ANALYZE_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request.gameState),
      signal: controller.signal
    })
      .then(r => r.json())
      .then(data => {
        clearTimeout(timeoutId);
        sendResponse({ success: true, data });
      })
      .catch(err => {
        clearTimeout(timeoutId);
        sendResponse({ success: false, error: 'Server offline / ' + err.toString() });
      });
    return true;
  }

  if (request.action === 'learnMatch') {
    fetch(LEARN_MATCH_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request.matchData)
    })
      .then(r => r.json())
      .then(data => sendResponse({ success: true, data }))
      .catch(err => sendResponse({ success: false, error: err.toString() }));
    return true;
  }

  if (request.action === 'getLearnStats') {
    fetch(LEARN_STATS_URL)
      .then(r => r.json())
      .then(data => sendResponse({ success: true, data }))
      .catch(err => sendResponse({ success: false, error: err.toString() }));
    return true;
  }
});
