// ─── YouTube Content Script ──────────────────────────────────────────────────
// Injects: Quick summarize button + Floating summary panel on YouTube video pages.

const API_BASE = 'http://127.0.0.1:5000';
let panel = null;
let isDragging = false;
let dragOffset = { x: 0, y: 0 };

// ─── Wait for YouTube's dynamic page load ───────────────────────────────────
function waitForElement(selector, timeout = 10000) {
  return new Promise((resolve, reject) => {
    const el = document.querySelector(selector);
    if (el) return resolve(el);

    const observer = new MutationObserver((_, obs) => {
      const found = document.querySelector(selector);
      if (found) {
        obs.disconnect();
        resolve(found);
      }
    });
    observer.observe(document.body, { childList: true, subtree: true });
    setTimeout(() => { observer.disconnect(); reject('Timeout'); }, timeout);
  });
}

// ─── Inject Quick Summarize Button ──────────────────────────────────────────
async function injectQuickButton() {
  // Remove existing if any (SPA navigation)
  const existing = document.getElementById('yts-quick-btn');
  if (existing) existing.remove();

  try {
    // YouTube's owner info area (below the video)
    const target = await waitForElement('#owner, #top-row #upload-info, ytd-watch-metadata #owner');

    const btn = document.createElement('button');
    btn.id = 'yts-quick-btn';
    btn.innerHTML = '✨ Summarize';
    btn.title = 'Summarize this video with AI';
    btn.addEventListener('click', handleQuickSummarize);

    // Insert after the channel info
    target.parentElement.insertBefore(btn, target.nextSibling);
  } catch (e) {
    console.log('[YT Summarizer] Could not inject button:', e);
  }
}

// ─── Handle Quick Summarize Click ───────────────────────────────────────────
async function handleQuickSummarize() {
  const btn = document.getElementById('yts-quick-btn');
  if (!btn) return;

  btn.disabled = true;
  btn.innerHTML = '⏳ Summarizing...';

  try {
    // Check server first
    const healthRes = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(3000) });
    if (!healthRes.ok) throw new Error('Server not running');

    const res = await fetch(`${API_BASE}/api/process`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: window.location.href,
        percentage: 25
      })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.error || 'Processing failed');
    }

    const data = await res.json();
    const title = data.title || document.title.replace(' - YouTube', '');
    const tw = (data.text || '').split(/\s+/).filter(Boolean).length;
    const sw = (data.summary || '').split(/\s+/).filter(Boolean).length;

    showPanel(data.summary, title, tw, sw);

    btn.innerHTML = '✅ Done!';
    btn.disabled = false;
    setTimeout(() => { btn.innerHTML = '✨ Summarize'; }, 2000);

  } catch (err) {
    btn.innerHTML = '❌ ' + err.message;
    btn.disabled = false;
    setTimeout(() => { btn.innerHTML = '✨ Summarize'; }, 3000);
  }
}

// ─── Show Floating Panel ────────────────────────────────────────────────────
function showPanel(summary, title, totalWords, summaryWords) {
  // Remove existing panel
  if (panel) panel.remove();

  panel = document.createElement('div');
  panel.id = 'yt-summarizer-panel';

  const ratio = totalWords > 0 ? ((summaryWords / totalWords) * 100).toFixed(0) : '0';
  const timeSaved = Math.round((totalWords - summaryWords) / 200);

  panel.innerHTML = `
    <div class="yts-header">
      <div class="yts-header-left">
        <span>📝</span>
        <h3>AI Summary</h3>
      </div>
      <div class="yts-header-btns">
        <button id="yts-minimize" title="Minimize">─</button>
        <button id="yts-close" title="Close">✕</button>
      </div>
    </div>
    <div class="yts-body">
      <div class="yts-stats">
        <div class="yts-stat">
          <div class="yts-stat-num">${totalWords.toLocaleString()}</div>
          <div class="yts-stat-label">Original words</div>
        </div>
        <div class="yts-stat">
          <div class="yts-stat-num">${summaryWords.toLocaleString()}</div>
          <div class="yts-stat-label">Summary words</div>
        </div>
        <div class="yts-stat">
          <div class="yts-stat-num">${ratio}%</div>
          <div class="yts-stat-label">Compressed</div>
        </div>
      </div>
      <div class="yts-video-title">${escapeHtml(title)}</div>
      <div class="yts-summary-text">${escapeHtml(summary)}</div>
      <div class="yts-actions">
        <button class="yts-action-btn" id="yts-copy-btn">📋 Copy</button>
        <button class="yts-action-btn" id="yts-save-btn">⭐ Save</button>
      </div>
      <div style="text-align:center;margin-top:8px;font-size:10px;color:#94a3b8;">
        ~${timeSaved} min reading time saved
      </div>
    </div>
  `;

  document.body.appendChild(panel);

  // ── Event listeners ──
  document.getElementById('yts-close').addEventListener('click', () => {
    panel.style.animation = 'none';
    panel.style.transition = 'all 0.3s ease';
    panel.style.opacity = '0';
    panel.style.transform = 'translateX(30px) scale(0.95)';
    setTimeout(() => panel.remove(), 300);
  });

  document.getElementById('yts-minimize').addEventListener('click', () => {
    panel.classList.toggle('minimized');
    if (panel.classList.contains('minimized')) {
      panel.addEventListener('click', expandPanel, { once: true });
    }
  });

  document.getElementById('yts-copy-btn').addEventListener('click', () => {
    navigator.clipboard.writeText(summary).then(() => {
      const btn = document.getElementById('yts-copy-btn');
      btn.textContent = '✅ Copied!';
      setTimeout(() => { btn.textContent = '📋 Copy'; }, 1500);
    });
  });

  document.getElementById('yts-save-btn').addEventListener('click', () => {
    chrome.storage.local.get('favorites', ({ favorites = [] }) => {
      const fav = {
        url: window.location.href,
        title: title,
        summary: summary,
        date: new Date().toISOString().split('T')[0],
        percentage: '25'
      };
      const filtered = favorites.filter(f => f.url !== fav.url);
      filtered.unshift(fav);
      if (filtered.length > 50) filtered.length = 50;
      chrome.storage.local.set({ favorites: filtered });
      const btn = document.getElementById('yts-save-btn');
      btn.textContent = '✅ Saved!';
      setTimeout(() => { btn.textContent = '⭐ Save'; }, 1500);
    });
  });

  // ── Drag functionality ──
  const header = panel.querySelector('.yts-header');
  header.addEventListener('mousedown', (e) => {
    if (e.target.tagName === 'BUTTON') return;
    isDragging = true;
    const rect = panel.getBoundingClientRect();
    dragOffset.x = e.clientX - rect.left;
    dragOffset.y = e.clientY - rect.top;
    panel.style.transition = 'none';
  });

  document.addEventListener('mousemove', (e) => {
    if (!isDragging || !panel) return;
    const x = e.clientX - dragOffset.x;
    const y = e.clientY - dragOffset.y;
    panel.style.left = x + 'px';
    panel.style.top = y + 'px';
    panel.style.right = 'auto';
  });

  document.addEventListener('mouseup', () => {
    isDragging = false;
    if (panel) panel.style.transition = '';
  });
}

// ── Expand from minimized ──
function expandPanel() {
  if (panel && panel.classList.contains('minimized')) {
    panel.classList.remove('minimized');
  }
}

// ── Escape HTML ──
function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str || '';
  return div.innerHTML;
}

// ─── Listen for messages from popup ─────────────────────────────────────────
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.action === 'showSummary') {
    showPanel(msg.summary, msg.title, msg.totalWords, msg.summaryWords);
    sendResponse({ ok: true });
  }
  return true;
});

// ─── YouTube SPA Navigation Support ─────────────────────────────────────────
// YouTube uses AJAX navigation, so we listen for URL changes.
let lastUrl = location.href;

const urlObserver = new MutationObserver(() => {
  if (location.href !== lastUrl) {
    lastUrl = location.href;
    if (location.href.includes('youtube.com/watch')) {
      setTimeout(injectQuickButton, 1500);
    }
  }
});

urlObserver.observe(document.body, { childList: true, subtree: true });

// ─── Initial Injection ──────────────────────────────────────────────────────
if (window.location.href.includes('youtube.com/watch')) {
  // Wait a bit for YouTube's dynamic DOM to be ready
  setTimeout(injectQuickButton, 2000);
}
