import sys, re
with open('c:/Users/user/Documents/antigravity/brave-bose/browser_extension/reader.js', 'r', encoding='utf-8') as f:
    text = f.read()

start_idx = text.find("if (isPlayAction && currentPhase === 'MAIN') {")
end_idx = text.find('}', text.find('tidak ditemukan di tangan', start_idx)) + 1

if start_idx == -1 or end_idx == 0:
    print('Could not find block')
    sys.exit(1)

new_code = """if (isPlayAction && currentPhase === 'MAIN') {
    let cardName = rec.plays?.[0]?.cards?.[0]?.name || '';
    const playMatch = planAction.match(/Mainkan:\\s*([^\\n\\r]+)/i);
    if (playMatch) {
      let rawName = playMatch[1].trim();
      const arrMatch = rawName.match(/^(.*?)\\s*->/);
      if (arrMatch) rawName = arrMatch[1].trim();
      cardName = rawName;
    }

    const targetMatch = planAction.match(/Target:\\s*([^\\n\\r]+)/i);
    const targetName = targetMatch ? targetMatch[1].trim() : '';

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
                const baseMatch = planDetail.match(/di atas ([^+\\n\\r]+)/i) || planAction.match(/Target:\\s*([^+\\n\\r]+)/i);
                if (baseMatch) baseName = baseMatch[1].trim();

                setTimeout(() => {
                  const baitEl = findBattleCardEl(baseName, true) || document.querySelector('.side.me .zone.battle .card.choice, .side.me .zone.battle .card.selectable');
                  if (baitEl) {
                    VirtualAgent.clickTarget(baitEl, `Evolusi ${baseName || 'Bait'}`);
                    logAutoplay(`🎯 Evolusi ${cardName} ke atas ${baseName || 'Bait'}`);
                  }
                }, 350);
              } else if (targetName) {
                setTimeout(() => {
                  const targetEl = findBattleCardEl(targetName, false) || findBattleCardEl(targetName, true) || document.querySelector('.zone.battle .card.choice, .zone.battle .card.selectable, .zone.battle .card.target');
                  if (targetEl) {
                    VirtualAgent.clickTarget(targetEl, `Target ${targetName}`);
                    logAutoplay(`🎯 Target Efek: ${targetName}`);
                  }
                }, 400);
              }
            });
            logAutoplay(`🎯 Konfirmasi Mainkan: ${modalPlayBtn.textContent.trim()}`);
          } else {
            const battleZone = findBattleZoneEl();
            if (battleZone) {
              VirtualAgent.dragTarget(cardEl, battleZone, cardName);
            }
          }
        }, 250);
      });

      logAutoplay(`🎯 Mainkan: ${cardName}`);
      return;
    } else {
      if (targetName) {
        const possibleTarget = findBattleCardEl(targetName, false) || findBattleCardEl(targetName, true) || document.querySelector('.zone.battle .card.choice, .zone.battle .card.selectable, .zone.battle .card.target');
        if (possibleTarget && (possibleTarget.classList.contains('choice') || possibleTarget.classList.contains('target') || possibleTarget.classList.contains('selectable'))) {
          VirtualAgent.clickTarget(possibleTarget, `Recover Target ${targetName}`);
          logAutoplay(`🎯 Pulihkan Target Efek: ${targetName}`);
          return;
        }
      }
      logAutoplay(`⚠️ Kartu "${cardName}" tidak ditemukan di tangan.`);
    }
  }"""

text = text[:start_idx] + new_code + text[end_idx:]
with open('c:/Users/user/Documents/antigravity/brave-bose/browser_extension/reader.js', 'w', encoding='utf-8') as f:
    f.write(text)
print('Success')
