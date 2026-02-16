// ─── Config ─────────────────────────────────────────────────────────────────
const API_BASE = 'http://127.0.0.1:5000';

// ─── DOM refs ───────────────────────────────────────────────────────────────
const $ = (id) => document.getElementById(id);

const statusDot    = $('statusDot');
const statusText   = $('statusText');
const notYoutube   = $('notYoutube');
const mainContent  = $('mainContent');
const videoTitle   = $('videoTitle');
const videoUrl     = $('videoUrl');
const sliderVal    = $('sliderVal');
const slider       = $('percentage');
const btnSummarize = $('btnSummarize');
const progressBar  = $('progressBar');
const progressFill = $('progressFill');
const errorBox     = $('errorBox');
const results      = $('results');
const summaryText  = $('summaryText');
const btnCopy      = $('btnCopy');
const btnFav       = $('btnFav');
const btnPanel     = $('btnPanel');

let currentUrl = '';
let currentTitle = '';
let currentSummary = '';
let currentText = '';

// ─── Init ───────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  checkServer();
  setupSlider();
  setupTabs();

  // Check if we're on a YouTube video page
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

  if (tab && tab.url && tab.url.includes('youtube.com/watch')) {
    currentUrl = tab.url;
    mainContent.style.display = 'block';
    notYoutube.style.display = 'none';
    videoUrl.textContent = tab.url;
    videoTitle.textContent = tab.title ? tab.title.replace(' - YouTube', '') : 'YouTube Video';
    currentTitle = videoTitle.textContent;
  } else {
    mainContent.style.display = 'none';
    notYoutube.style.display = 'block';
    loadFavorites('favListAlt');
  }

  loadFavorites('favList');
});

// ─── Server Health Check ────────────────────────────────────────────────────
async function checkServer() {
  try {
    const res = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(3000) });
    if (res.ok) {
      statusDot.className = 'status-dot connected';
      statusText.textContent = 'Server connected';
    } else {
      throw new Error('Server error');
    }
  } catch (e) {
    statusDot.className = 'status-dot';
    statusText.textContent = 'Server offline — start python main.py';
  }
}

// ─── Slider ─────────────────────────────────────────────────────────────────
function setupSlider() {
  slider.addEventListener('input', () => {
    sliderVal.textContent = slider.value + '%';
  });
}

// ─── Tabs ───────────────────────────────────────────────────────────────────
function setupTabs() {
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
      btn.classList.add('active');
      document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
      if (btn.dataset.tab === 'favorites') loadFavorites('favList');
    });
  });
}

// ─── Summarize ──────────────────────────────────────────────────────────────
btnSummarize.addEventListener('click', async () => {
  if (!currentUrl) return;

  // Reset UI
  btnSummarize.disabled = true;
  btnSummarize.textContent = '⏳ Summarizing...';
  progressBar.style.display = 'block';
  progressFill.style.width = '15%';
  errorBox.style.display = 'none';
  results.style.display = 'none';

  // Animate progress
  let progress = 15;
  const interval = setInterval(() => {
    if (progress < 85) {
      progress += Math.random() * 8;
      progressFill.style.width = Math.min(progress, 85) + '%';
    }
  }, 600);

  try {
    const res = await fetch(`${API_BASE}/api/process`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: currentUrl,
        percentage: parseInt(slider.value)
      })
    });

    clearInterval(interval);

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.error || 'Server error');
    }

    const data = await res.json();

    // Complete progress
    progressFill.style.width = '100%';
    setTimeout(() => { progressBar.style.display = 'none'; }, 400);

    // Show results
    currentSummary = data.summary || '';
    currentText = data.text || '';
    if (data.title) {
      currentTitle = data.title;
      videoTitle.textContent = data.title;
    }

    summaryText.textContent = currentSummary;

    const tw = (currentText || '').split(/\s+/).filter(Boolean).length;
    const sw = (currentSummary || '').split(/\s+/).filter(Boolean).length;
    $('statWords').textContent = tw.toLocaleString();
    $('statSummary').textContent = sw.toLocaleString();
    $('statRatio').textContent = tw > 0 ? ((sw / tw) * 100).toFixed(0) + '%' : '0%';

    results.style.display = 'block';
    btnSummarize.textContent = '✅ Done! Summarize Again?';
    btnSummarize.disabled = false;

    // Also send summary to content script for floating panel
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab) {
      chrome.tabs.sendMessage(tab.id, {
        action: 'showSummary',
        summary: currentSummary,
        title: currentTitle,
        totalWords: tw,
        summaryWords: sw
      }).catch(() => {}); // content script might not be ready
    }

  } catch (err) {
    clearInterval(interval);
    progressBar.style.display = 'none';
    errorBox.textContent = '❌ ' + err.message;
    errorBox.style.display = 'block';
    btnSummarize.textContent = '⚡ Retry Summarize';
    btnSummarize.disabled = false;
  }
});

// ─── Copy ───────────────────────────────────────────────────────────────────
btnCopy.addEventListener('click', () => {
  navigator.clipboard.writeText(currentSummary).then(() => {
    btnCopy.textContent = '✅ Copied!';
    btnCopy.classList.add('active');
    setTimeout(() => {
      btnCopy.textContent = '📋 Copy';
      btnCopy.classList.remove('active');
    }, 1500);
  });
});

// ─── Save to Favorites ──────────────────────────────────────────────────────
btnFav.addEventListener('click', async () => {
  const fav = {
    url: currentUrl,
    title: currentTitle,
    summary: currentSummary,
    date: new Date().toISOString().split('T')[0],
    percentage: slider.value
  };

  const { favorites = [] } = await chrome.storage.local.get('favorites');

  // Avoid duplicates by URL
  const filtered = favorites.filter(f => f.url !== fav.url);
  filtered.unshift(fav);

  // Keep max 50
  if (filtered.length > 50) filtered.length = 50;

  await chrome.storage.local.set({ favorites: filtered });
  btnFav.textContent = '✅ Saved!';
  btnFav.classList.add('active');
  setTimeout(() => {
    btnFav.textContent = '⭐ Save';
    btnFav.classList.remove('active');
  }, 1500);
});

// ─── Show Panel on Page (via content script) ────────────────────────────────
btnPanel.addEventListener('click', async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (tab && currentSummary) {
    chrome.tabs.sendMessage(tab.id, {
      action: 'showSummary',
      summary: currentSummary,
      title: currentTitle,
      totalWords: parseInt($('statWords').textContent.replace(/,/g, '')) || 0,
      summaryWords: parseInt($('statSummary').textContent.replace(/,/g, '')) || 0
    }).catch(() => {});
    btnPanel.textContent = '✅ Panel Shown!';
    setTimeout(() => { btnPanel.textContent = '📌 Panel'; }, 1500);
  }
});

// ─── Load Favorites ─────────────────────────────────────────────────────────
async function loadFavorites(containerId) {
  const container = document.getElementById(containerId);
  if (!container) return;

  const { favorites = [] } = await chrome.storage.local.get('favorites');

  if (favorites.length === 0) {
    container.innerHTML = '<div class="empty-fav">No favorites saved yet.<br>Summarize a video and click ⭐ Save!</div>';
    return;
  }

  container.innerHTML = favorites.map((fav, i) => `
    <div class="fav-item" data-index="${i}">
      <div class="fav-title" title="${fav.title || fav.url}">${fav.title || fav.url}</div>
      <div class="fav-date">${fav.date}</div>
      <button class="fav-remove" data-index="${i}" title="Remove">✕</button>
    </div>
  `).join('');

  // Click to open URL
  container.querySelectorAll('.fav-item').forEach(item => {
    item.addEventListener('click', (e) => {
      if (e.target.classList.contains('fav-remove')) return;
      const idx = parseInt(item.dataset.index);
      const fav = favorites[idx];
      if (fav && fav.url) chrome.tabs.create({ url: fav.url });
    });
  });

  // Remove button
  container.querySelectorAll('.fav-remove').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      const idx = parseInt(btn.dataset.index);
      const { favorites: favs = [] } = await chrome.storage.local.get('favorites');
      favs.splice(idx, 1);
      await chrome.storage.local.set({ favorites: favs });
      loadFavorites(containerId);
    });
  });
}
