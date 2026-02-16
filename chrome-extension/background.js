// ─── Background Service Worker ──────────────────────────────────────────────
// Handles context menu and extension icon click badge updates.

const API_BASE = 'https://youtube-ai-analyzer.onrender.com';

// ─── On Install ─────────────────────────────────────────────────────────────
chrome.runtime.onInstalled.addListener(() => {
  // Create right-click context menu on YouTube links
  chrome.contextMenus.create({
    id: 'summarize-link',
    title: '✨ Summarize this YouTube video',
    contexts: ['link'],
    targetUrlPatterns: [
      '*://*.youtube.com/watch*',
      '*://youtu.be/*'
    ]
  });

  console.log('[YT Summarizer] Extension installed');
});

// ─── Context Menu Click ─────────────────────────────────────────────────────
chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId === 'summarize-link' && info.linkUrl) {
    // Open the video in a new tab and trigger summarization
    const newTab = await chrome.tabs.create({ url: info.linkUrl });
    
    // Wait for the tab to load, then send message to content script
    chrome.tabs.onUpdated.addListener(function listener(tabId, changeInfo) {
      if (tabId === newTab.id && changeInfo.status === 'complete') {
        chrome.tabs.onUpdated.removeListener(listener);
        // Let content script inject its button, then auto-trigger
        setTimeout(() => {
          chrome.tabs.sendMessage(tabId, { action: 'autoSummarize' }).catch(() => {});
        }, 3000);
      }
    });
  }
});

// ─── Periodic Server Health Check (badge update) ────────────────────────────
async function updateBadge() {
  try {
    const res = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(3000) });
    if (res.ok) {
      chrome.action.setBadgeBackgroundColor({ color: '#10b981' });
      chrome.action.setBadgeText({ text: '✓' });
    } else {
      throw new Error();
    }
  } catch {
    chrome.action.setBadgeBackgroundColor({ color: '#ef4444' });
    chrome.action.setBadgeText({ text: '!' });
  }
}

// Check every 30 seconds
chrome.alarms.create('healthCheck', { periodInMinutes: 0.5 });
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === 'healthCheck') updateBadge();
});

// Initial check
updateBadge();
