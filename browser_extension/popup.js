document.addEventListener('DOMContentLoaded', () => {
  const toggleBtn    = document.getElementById('toggleSync');
  const statusDot    = document.getElementById('statusDot');
  const statusLabel  = document.getElementById('statusLabel');
  const statusDetail = document.getElementById('statusDetail');
  const deckInput    = document.getElementById('deckInput');
  const saveDeck     = document.getElementById('saveDeck');
  const deckStatus   = document.getElementById('deckStatus');

  function updateDeckCount() {
    const text = deckInput.value;
    let count = 0;
    const lines = text.split('\n');
    for (const raw of lines) {
      const line = raw.trim();
      if (!line || line.startsWith('#') || line.startsWith('//')) continue;
      const m = line.match(/^(\d+)\s*[xX*]?\s+(.+)$/);
      if (m) {
        count += parseInt(m[1], 10);
      } else {
        count += 1;
      }
    }
    const badge = document.getElementById('deckCountBadge');
    if (badge) badge.textContent = `${count} kartu`;
  }

  deckInput.addEventListener('input', updateDeckCount);

  let isSyncOn = false;

  function checkServerHealth() {
    fetch('https://duel-masters-ai-bot.onrender.com/api/cards', { method: 'GET' })
      .then(res => res.json())
      .then(data => {
        if (isSyncOn) {
          statusDot.className = 'dot on';
          statusLabel.textContent = 'ON';
          statusDetail.textContent = '🟢 Server Terhubung';
          statusDetail.style.color = '#2ecc71';
        } else {
          statusDetail.textContent = '🟢 Server Terhubung (Siap)';
          statusDetail.style.color = '#2ecc71';
        }
      })
      .catch(() => {
        if (isSyncOn) {
          statusDot.className = 'dot off';
          statusLabel.textContent = 'ERR';
          statusDetail.textContent = '🔴 Server Offline (Jalankan run.py)';
          statusDetail.style.color = '#e74c3c';
        } else {
          statusDetail.textContent = '🔴 Server Belum Jalan';
          statusDetail.style.color = '#e74c3c';
        }
      });
  }

  // ── AUTOPLAY CONTROLS ──
  const toggleAutoplayBtn  = document.getElementById('toggleAutoplayBtn');
  const autoplayStatusBadge = document.getElementById('autoplayStatusBadge');
  const autoplaySpeedSelect = document.getElementById('autoplaySpeedSelect');
  let isAutoplayOn = false;

  function updateAutoplayUI(on) {
    if (!toggleAutoplayBtn || !autoplayStatusBadge) return;
    if (on) {
      autoplayStatusBadge.textContent = 'ON';
      autoplayStatusBadge.style.background = '#27ae60';
      toggleAutoplayBtn.textContent = '⏸ Jeda / Matikan Autoplay';
      toggleAutoplayBtn.style.background = '#c0392b';
    } else {
      autoplayStatusBadge.textContent = 'OFF';
      autoplayStatusBadge.style.background = '#555';
      toggleAutoplayBtn.textContent = '▶ Aktifkan Autoplay';
      toggleAutoplayBtn.style.background = '#27ae60';
    }
  }

  chrome.storage.local.get(['syncEnabled', 'playerDeck', 'autoplayEnabled', 'autoplaySpeed'], (r) => {
    isSyncOn = (r.syncEnabled !== false); // Default ON
    if (r.syncEnabled === undefined) {
      chrome.storage.local.set({ syncEnabled: true });
    }
    isAutoplayOn = (r.autoplayEnabled === true);
    updateUI(isSyncOn);
    updateAutoplayUI(isAutoplayOn);
    if (r.autoplaySpeed && autoplaySpeedSelect) {
      autoplaySpeedSelect.value = r.autoplaySpeed;
    }
    checkServerHealth();
    if (r.playerDeck) {
      deckInput.value = r.playerDeck;
      updateDeckCount();
    }
  });

  if (toggleAutoplayBtn) {
    toggleAutoplayBtn.addEventListener('click', () => {
      chrome.storage.local.get(['autoplayEnabled'], (r) => {
        const next = !(r.autoplayEnabled || false);
        isAutoplayOn = next;
        chrome.storage.local.set({ autoplayEnabled: next }, () => {
          updateAutoplayUI(next);
          broadcast({ action: 'toggleAutoplay', state: next });
        });
      });
    });
  }

  if (autoplaySpeedSelect) {
    autoplaySpeedSelect.addEventListener('change', () => {
      const spd = autoplaySpeedSelect.value;
      chrome.storage.local.set({ autoplaySpeed: spd }, () => {
        broadcast({ action: 'setAutoplaySpeed', speed: spd });
      });
    });
  }

  saveDeck.addEventListener('click', () => {
    const deckText = deckInput.value.trim();
    chrome.storage.local.set({ playerDeck: deckText }, () => {
      deckStatus.style.display = 'inline';
      setTimeout(() => deckStatus.style.display = 'none', 2000);
      broadcast({ action: 'updateDeck', deck: deckText });
      updateDeckCount();
    });
  });

  toggleBtn.addEventListener('click', () => {
    chrome.storage.local.get(['syncEnabled'], (r) => {
      const next = !(r.syncEnabled || false);
      isSyncOn = next;
      chrome.storage.local.set({ syncEnabled: next }, () => {
        updateUI(next);
        checkServerHealth();
        broadcast({ action: 'toggleSync', state: next });
      });
    });
  });

  function broadcast(msg) {
    chrome.tabs.query({}, (tabs) => {
      tabs.forEach(tab => {
        chrome.tabs.sendMessage(tab.id, msg).catch(() => {});
      });
    });
  }

  // ── HAND REVEAL MEMORY handlers ──
  const revealInput   = document.getElementById('revealCardInput');
  const revealBtn     = document.getElementById('revealBtn');
  const revealedList  = document.getElementById('revealedList');
  const revealedCount = document.getElementById('revealedCount');
  const resetRevBtn   = document.getElementById('resetRevealedBtn');
  const cardDatalist  = document.getElementById('cardSuggestions');

  // Populate autocomplete from card DB
  fetch('https://duel-masters-ai-bot.onrender.com/api/cards').then(r => r.json()).then(d => {
    const list = Array.isArray(d) ? d : (d.data || []);
    list.forEach(c => {
      const opt = document.createElement('option');
      opt.value = c.name;
      cardDatalist.appendChild(opt);
    });
  }).catch(() => {});

  // Load persisted revealed hand from storage
  let revealedMemory = {};
  chrome.storage.local.get(['oppRevealedHand'], r => {
    if (r.oppRevealedHand) { revealedMemory = r.oppRevealedHand; renderRevealedList(); }
  });

  function renderRevealedList() {
    const names = Object.keys(revealedMemory);
    revealedCount.textContent = `${names.length} diketahui`;
    revealedList.textContent  = names.length ? names.map(n => `${n} x${revealedMemory[n].count}`).join(' · ') : '';
  }

  revealBtn.addEventListener('click', () => {
    const name = revealInput.value.trim();
    if (!name) return;
    if (!revealedMemory[name]) revealedMemory[name] = { count: 0, source: 'manual', turn: 0 };
    revealedMemory[name].count++;
    chrome.storage.local.set({ oppRevealedHand: revealedMemory });
    renderRevealedList();
    revealInput.value = '';
    // Broadcast to reader.js
    broadcast({ action: 'revealOppCard', cardName: name, source: 'manual' });
  });

  // Allow pressing Enter in the input
  revealInput.addEventListener('keydown', e => { if (e.key === 'Enter') revealBtn.click(); });

  resetRevBtn.addEventListener('click', () => {
    revealedMemory = {};
    chrome.storage.local.set({ oppRevealedHand: {} });
    renderRevealedList();
    broadcast({ action: 'resetRevealedHand' });
  });

  // ── TAB SWITCHING ──
  const tabAdvisor = document.getElementById('tabBtnAdvisor');
  const tabBuilder = document.getElementById('tabBtnBuilder');
  const tabLearning = document.getElementById('tabBtnLearning');
  const paneAdvisor = document.getElementById('paneAdvisor');
  const paneBuilder = document.getElementById('paneBuilder');
  const paneLearning = document.getElementById('paneLearning');

  function switchTab(activeTabBtn, activePane) {
    [tabAdvisor, tabBuilder, tabLearning].forEach(t => t && t.classList.remove('active'));
    [paneAdvisor, paneBuilder, paneLearning].forEach(p => p && p.classList.remove('active'));
    activeTabBtn.classList.add('active');
    activePane.classList.add('active');
  }

  if (tabAdvisor && tabBuilder && tabLearning) {
    tabAdvisor.addEventListener('click', () => switchTab(tabAdvisor, paneAdvisor));
    tabBuilder.addEventListener('click', () => switchTab(tabBuilder, paneBuilder));
    tabLearning.addEventListener('click', () => {
      switchTab(tabLearning, paneLearning);
      fetchLearningStats();
    });
  }

  // ── DECK BUILDER AGENT ──
  const btnBuildDeck = document.getElementById('btnBuildDeck');
  const archetypeSelect = document.getElementById('builderArchetypeSelect');
  const deckResultBox = document.getElementById('deckResultBox');
  const deckResultTitle = document.getElementById('deckResultTitle');
  const deckResultGrade = document.getElementById('deckResultGrade');
  const metricAvgCost = document.getElementById('metricAvgCost');
  const metricTriggers = document.getElementById('metricTriggers');
  const metricFinishers = document.getElementById('metricFinishers');
  const metricRemoval = document.getElementById('metricRemoval');
  const deckTips = document.getElementById('deckTips');
  const deckResultText = document.getElementById('deckResultText');
  const btnCopyDeck = document.getElementById('btnCopyDeck');
  const btnApplyDeck = document.getElementById('btnApplyDeck');
  const btnAnalyzeMyDeck = document.getElementById('btnAnalyzeMyDeck');
  const upgradeBox = document.getElementById('upgradeBox');
  const upgradeContent = document.getElementById('upgradeContent');

  if (btnBuildDeck) {
    btnBuildDeck.addEventListener('click', () => {
      const arch = archetypeSelect.value;
      btnBuildDeck.textContent = '⏳ Merancang Deck Cerdas...';
      btnBuildDeck.disabled = true;

      fetch('https://duel-masters-ai-bot.onrender.com/api/deck/build', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ archetype: arch })
      })
      .then(res => res.json())
      .then(data => {
        btnBuildDeck.textContent = '⚡ Buat Deck Optimal (40 Kartu)';
        btnBuildDeck.disabled = false;
        if (!data.success) {
          alert('Gagal: ' + (data.error || 'Server error'));
          return;
        }

        deckResultBox.style.display = 'block';
        deckResultTitle.textContent = data.archetype_name;
        
        const gr = data.analysis.grade || 'A';
        deckResultGrade.textContent = `GRADE ${gr}`;
        deckResultGrade.className = `badge badge-${gr.toLowerCase()}`;

        metricAvgCost.textContent = data.analysis.average_cost;
        metricTriggers.textContent = `${data.analysis.shield_triggers} (${data.analysis.trigger_percentage}%)`;
        metricFinishers.textContent = data.analysis.finishers;
        metricRemoval.textContent = data.analysis.removal_cards;

        const tipsList = (data.analysis.tips || []).map(t => `• ${t}`).join('<br>');
        deckTips.innerHTML = tipsList || '✅ Komposisi deck sangat seimbang dan optimal untuk turnamen!';

        deckResultText.value = data.decklist_text;
      })
      .catch(err => {
        btnBuildDeck.textContent = '⚡ Buat Deck Optimal (40 Kartu)';
        btnBuildDeck.disabled = false;
        alert('Gagal terhubung ke backend. Pastikan run.py berjalan!');
      });
    });
  }

  if (btnCopyDeck) {
    btnCopyDeck.addEventListener('click', () => {
      if (!deckResultText.value) return;
      navigator.clipboard.writeText(deckResultText.value).then(() => {
        const orig = btnCopyDeck.textContent;
        btnCopyDeck.textContent = '✓ Disalin!';
        setTimeout(() => { btnCopyDeck.textContent = orig; }, 1500);
      });
    });
  }

  if (btnApplyDeck) {
    btnApplyDeck.addEventListener('click', () => {
      const generated = deckResultText.value.trim();
      if (!generated) return;
      deckInput.value = generated;
      updateDeckCount();
      chrome.storage.local.set({ playerDeck: generated }, () => {
        broadcast({ action: 'updateDeck', deck: generated });
        // Switch back to advisor tab
        if (tabAdvisor) tabAdvisor.click();
        deckStatus.style.display = 'inline';
        deckStatus.textContent = '✓ Deck baru dipasang!';
        setTimeout(() => { deckStatus.style.display = 'none'; }, 2500);
      });
    });
  }

  if (btnAnalyzeMyDeck) {
    btnAnalyzeMyDeck.addEventListener('click', () => {
      const currentDeck = deckInput.value.trim();
      if (!currentDeck) {
        alert('Decklist Anda masih kosong. Masukkan decklist di tab Live Advisor lebih dulu!');
        return;
      }
      btnAnalyzeMyDeck.textContent = '⏳ Menganalisa Deck Anda...';
      btnAnalyzeMyDeck.disabled = true;

      fetch('https://duel-masters-ai-bot.onrender.com/api/deck/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ decklist: currentDeck })
      })
      .then(res => res.json())
      .then(data => {
        btnAnalyzeMyDeck.textContent = '🔬 Analisa & Evaluasi Deck Saya';
        btnAnalyzeMyDeck.disabled = false;
        if (!data.success) {
          alert('Gagal: ' + (data.error || 'Server error'));
          return;
        }

        upgradeBox.style.display = 'block';
        const a = data.analysis;
        const u = data.upgrade_suggestions;

        let html = `<div style="margin-bottom:6px;">
          <b>Total:</b> ${data.total_cards} kartu · <b>Avg Cost:</b> ${a.average_cost} · <b>Trigger:</b> ${a.shield_triggers}
        </div>`;

        if (u.improvements && u.improvements.length > 0) {
          html += `<div style="color:#2ecc71; font-weight:bold; margin-top:4px;">💡 Saran Penambahan:</div>`;
          u.improvements.forEach(imp => {
            html += `<div style="margin-bottom:2px; color:#c8e6c9;">➕ <b>${imp.card}</b>: ${imp.reason}</div>`;
          });
        }

        if (u.candidates_to_cut && u.candidates_to_cut.length > 0) {
          html += `<div style="color:#e74c3c; font-weight:bold; margin-top:6px;">✂️ Saran Pengurangan:</div>`;
          u.candidates_to_cut.forEach(cut => {
            html += `<div style="margin-bottom:2px; color:#ffcdd2;">➖ <b>${cut.card}</b>: ${cut.reason}</div>`;
          });
        }

        if ((!u.improvements || !u.improvements.length) && (!u.candidates_to_cut || !u.candidates_to_cut.length)) {
          html += `<div style="color:#2ecc71;">✅ Deck Anda sudah sangat solid dan seimbang!</div>`;
        }

        upgradeContent.innerHTML = html;
      })
      .catch(err => {
        btnAnalyzeMyDeck.textContent = '🔬 Analisa & Evaluasi Deck Saya';
        btnAnalyzeMyDeck.disabled = false;
        alert('Gagal terhubung ke backend. Pastikan run.py berjalan!');
      });
    });
  }

  // ── AI CONTINUOUS LEARNING HANDLERS ──
  const learnAiLevel   = document.getElementById('learnAiLevel');
  const learnXp        = document.getElementById('learnXp');
  const learnWinRate   = document.getElementById('learnWinRate');
  const learnMatches   = document.getElementById('learnMatches');
  const learnCombosList= document.getElementById('learnCombosList');
  const learnCardsList = document.getElementById('learnCardsList');
  const learnMetaList  = document.getElementById('learnMetaList');
  const btnRefreshStats= document.getElementById('btnRefreshLearnStats');
  const btnResetLearn  = document.getElementById('btnResetLearning');

  function fetchLearningStats() {
    fetch('https://duel-masters-ai-bot.onrender.com/api/learn/stats')
      .then(r => r.json())
      .then(res => {
        if (!res.success || !res.data) return;
        const d = res.data;
        if (learnAiLevel) learnAiLevel.textContent = `AI Level ${d.ai_level || 1}`;
        if (learnXp) learnXp.textContent = `${d.experience_points || 0} XP`;
        if (learnWinRate) learnWinRate.textContent = `${d.win_rate || 0}% Win Rate`;
        if (learnMatches) learnMatches.textContent = `${d.total_matches || 0} Duel (${d.wins || 0}W / ${d.losses || 0}L)`;

        // Render Combos
        if (learnCombosList) {
          if (d.learned_combos && d.learned_combos.length > 0) {
            learnCombosList.innerHTML = d.learned_combos.map(c => `
              <div style="margin-bottom:3px; padding:3px 5px; background:rgba(255,255,255,0.03); border-radius:3px; border-left:2px solid #f1c40f;">
                <b>${c.name}</b> <span style="color:#2ecc71;">(${c.win_rate}% Win)</span>
                <div style="color:#aaa; font-size:8px;">${c.cards.join(' + ')} · Muncul ${c.times_seen}x</div>
              </div>
            `).join('');
          } else {
            learnCombosList.innerHTML = '<div style="color:#777; font-style:italic;">Belum ada kombo baru. Selesaikan duel untuk melatih AI!</div>';
          }
        }

        // Render Cards MVP
        if (learnCardsList) {
          if (d.top_performing_cards && d.top_performing_cards.length > 0) {
            learnCardsList.innerHTML = d.top_performing_cards.map(c => `
              <div style="margin-bottom:2px; display:flex; justify-content:space-between;">
                <span>⭐ <b>${c.name}</b> (${c.played}x main)</span>
                <span style="color:#ffd700;">Dampak: ${c.impact_score}/10</span>
              </div>
            `).join('');
          } else {
            learnCardsList.innerHTML = '<div style="color:#777; font-style:italic;">Belum ada data kartu.</div>';
          }
        }

        // Render Meta
        if (learnMetaList) {
          if (d.top_archetypes && d.top_archetypes.length > 0) {
            learnMetaList.innerHTML = d.top_archetypes.map(a => `
              <div style="margin-bottom:2px;">
                🎭 <b>${a.name}</b>: ${a.count}x dihadapi
              </div>
            `).join('');
          } else {
            learnMetaList.innerHTML = '<div style="color:#777; font-style:italic;">Belum ada profil musuh.</div>';
          }
        }
      })
      .catch(() => {});
  }

  if (btnRefreshStats) {
    btnRefreshStats.addEventListener('click', fetchLearningStats);
  }

  if (btnResetLearn) {
    btnResetLearn.addEventListener('click', () => {
      if (confirm('Apakah Anda yakin ingin me-reset memori pembelajaran AI ke awal?')) {
        fetch('https://duel-masters-ai-bot.onrender.com/api/learn/reset', { method: 'POST' })
          .then(r => r.json())
          .then(() => {
            alert('Memori AI berhasil di-reset.');
            fetchLearningStats();
          })
          .catch(() => alert('Gagal reset memori.'));
      }
    });
  }

  function updateUI(on) {
    if (on) {
      statusDot.className   = 'dot on';
      statusLabel.textContent  = 'ON';
      statusDetail.textContent = '🟢 Auto-Sync Aktif';
      statusDetail.style.color = '#2ecc71';
      toggleBtn.textContent = '⏹ Matikan Auto-Sync';
      toggleBtn.className   = 'active';
    } else {
      statusDot.className   = 'dot off';
      statusLabel.textContent  = 'OFF';
      statusDetail.textContent = 'Tidak aktif';
      statusDetail.style.color = '#9a8b73';
      toggleBtn.textContent = '▶ Mulai Auto-Sync';
      toggleBtn.className   = '';
    }
  }
});

