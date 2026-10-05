import sys

with open("c:/Users/user/Documents/antigravity/brave-bose/browser_extension/reader.js", "r", encoding="utf-8") as f:
    text = f.read()

# 1. SMART POLLING
state_str = "lastGameState = {"
start_idx = text.find(state_str)
end_idx = text.find("};", start_idx) + 2

smart_poll = """
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
if "SMART POLLING" not in text:
    text = text[:end_idx] + "\n" + smart_poll + text[end_idx:]

# 2. WAIT FOR ELEMENT FUNCTION
wait_fn = """
const waitForElementAndClick = (selector, label, fallbackSelector = null, actionFn = null, timeout = 3000) => {
  const start = Date.now();
  const check = () => {
    let el = null;
    if (typeof selector === 'function') el = selector();
    else el = document.querySelector(selector);
    
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
if "waitForElementAndClick" not in text:
    va_idx = text.find("const VirtualAgent = {")
    text = text[:va_idx] + wait_fn + "\n" + text[va_idx:]


# 3. REFACTOR MULTIPLE TARGETS IN SPELLS
target_regex = "const targetMatch = planAction.match(/Target:\\\\s*([^\\\\n\\\\r]+)/i);"
multi_target = "const targetMatches = [...planAction.matchAll(/Target:\\\\s*([^\\\\n\\\\r,]+)/gi)];"
text = text.replace(target_regex, multi_target)

target_name = "const targetName = targetMatch ? targetMatch[1].trim() : '';"
multi_target_names = "const targetNames = targetMatches.map(m => m[1].trim());"
text = text.replace(target_name, multi_target_names)

# In the `if (targetName)` block
old_target_click = """              } else if (targetName) {
                setTimeout(() => {
                  const targetEl = findBattleCardEl(targetName, false) || findBattleCardEl(targetName, true) || document.querySelector('.zone.battle .card.choice, .zone.battle .card.selectable, .zone.battle .card.target');
                  if (targetEl) {
                    VirtualAgent.clickTarget(targetEl, `Target ${targetName}`);
                    logAutoplay(`🎯 Target Efek: ${targetName}`);
                  }
                }, 400);
              }"""
              
new_target_click = """              } else if (targetNames.length > 0) {
                const clickNextTarget = (idx) => {
                  if (idx >= targetNames.length) return;
                  const tName = targetNames[idx];
                  waitForElementAndClick(
                    () => findBattleCardEl(tName, false) || findBattleCardEl(tName, true) || document.querySelector('.zone.battle .card.choice, .zone.battle .card.selectable, .zone.battle .card.target'),
                    `Target ${tName}`,
                    null,
                    (tEl) => {
                      VirtualAgent.clickTarget(tEl, `Target ${tName}`, () => {
                        logAutoplay(`🎯 Target Efek: ${tName}`);
                        setTimeout(() => clickNextTarget(idx + 1), 250);
                      });
                    }
                  );
                };
                clickNextTarget(0);
              }"""
text = text.replace(old_target_click, new_target_click)

# In the RECOVERY block
old_recovery = """      if (targetName) {
        const possibleTarget = findBattleCardEl(targetName, false) || findBattleCardEl(targetName, true) || document.querySelector('.zone.battle .card.choice, .zone.battle .card.selectable, .zone.battle .card.target');
        if (possibleTarget && (possibleTarget.classList.contains('choice') || possibleTarget.classList.contains('target') || possibleTarget.classList.contains('selectable'))) {
          VirtualAgent.clickTarget(possibleTarget, `Recover Target ${targetName}`);
          logAutoplay(`🎯 Pulihkan Target Efek: ${targetName}`);
          return;
        }
      }"""
new_recovery = """      if (targetNames.length > 0) {
        // Just click the first available target to recover
        const tName = targetNames[0];
        const possibleTarget = findBattleCardEl(tName, false) || findBattleCardEl(tName, true) || document.querySelector('.zone.battle .card.choice, .zone.battle .card.selectable, .zone.battle .card.target');
        if (possibleTarget && (possibleTarget.classList.contains('choice') || possibleTarget.classList.contains('target') || possibleTarget.classList.contains('selectable'))) {
          VirtualAgent.clickTarget(possibleTarget, `Recover Target ${tName}`);
          logAutoplay(`🎯 Pulihkan Target Efek: ${tName}`);
          return;
        }
      }"""
text = text.replace(old_recovery, new_recovery)

with open("c:/Users/user/Documents/antigravity/brave-bose/browser_extension/reader.js", "w", encoding="utf-8") as f:
    f.write(text)

print("Reader.js successfully patched!")
