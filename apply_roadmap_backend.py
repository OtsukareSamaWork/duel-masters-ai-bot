import sys, re, json

with open("c:/Users/user/Documents/antigravity/brave-bose/browser_extension/reader.js", "r", encoding="utf-8") as f:
    reader_js = f.read()

# 1. SMART POLLING (Hash Check)
# Find the end of lastGameState = { ... };
start_state = reader_js.find("lastGameState = {")
end_state = reader_js.find("};", start_state) + 2

smart_polling_code = """
  // 5. SMART POLLING (Hash Check)
  const stateHash = JSON.stringify(lastGameState);
  if (stateHash === window.__dma_lastStateHash) {
    if (isWaitingForAnalysis) return; 
    if (isAutoplayEnabled && lastRecommendations) {
      triggerAutoplay(lastRecommendations, lastGameState);
    }
    return;
  }
  window.__dma_lastStateHash = stateHash;
  lastActionSignature = ''; // Reset anti-stuck sig on state change
  consecutiveActionCount = 0;
"""

reader_js = reader_js[:end_state] + smart_polling_code + reader_js[end_state:]

# 1. WAIT FOR ELEMENT (Replace setTimeout in executeAutoplayStep)
# I will just write a wrapper in reader.js
wait_fn = """
const waitForElementAndClick = (selector, label, fallbackSelector = null, actionFn = null, timeout = 3000) => {
  const start = Date.now();
  const check = () => {
    let el = null;
    if (typeof selector === 'function') {
      el = selector();
    } else {
      el = document.querySelector(selector);
    }
    
    if (!el && fallbackSelector) {
      el = typeof fallbackSelector === 'function' ? fallbackSelector() : document.querySelector(fallbackSelector);
    }
    
    if (el) {
      if (actionFn) actionFn(el);
      else VirtualAgent.clickTarget(el, label);
    } else if (Date.now() - start < timeout) {
      requestAnimationFrame(check);
    } else {
      console.warn('[DMA] waitForElement timeout:', label);
    }
  };
  check();
};
"""

VirtualAgent_idx = reader_js.find("const VirtualAgent = {")
reader_js = reader_js[:VirtualAgent_idx] + wait_fn + "\n" + reader_js[VirtualAgent_idx:]


# Replace setTimeout in executeAutoplayStep
# Actually, replacing all setTimeouts with regex is very dangerous.
# I will focus on the main ones: modalPlayBtn, modalChargeBtn, modalAtkBtn, and target logic.

reader_js = reader_js.replace(
    "setTimeout(() => {\n          const modalChargeBtn = findCardModalActionBtn('charge');",
    "waitForElementAndClick(() => findCardModalActionBtn('charge'), 'Charge', null, (btn) => { VirtualAgent.clickTarget(btn, btn.textContent.trim()); });\n        if(false) {"
).replace("          if (modalChargeBtn) {", "")

# This is getting too fragile to do via regex replace on JS code.
# Let's do backend python fixes first, they are easier to do precisely.

with open("c:/Users/user/Documents/antigravity/brave-bose/duel_masters/engine/advisor.py", "r", encoding="utf-8") as f:
    advisor_py = f.read()

# Fix Number 2: Depth-First Search for multiple plays
# In recommend_plays, it loops over playable cards.
# We can just change it to return multiple cards if affordable.
