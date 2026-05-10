const API = "http://localhost:8384/capture";

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "capture-highlight",
    title: "Capture to today's notes",
    contexts: ["selection"],
  });
});

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId !== "capture-highlight") return;

  const now = new Date();
  const timestamp = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;

  try {
    const res = await fetch(API, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text: info.selectionText,
        source_url: tab.url,
        timestamp,
      }),
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    chrome.notifications.create({
      type: "basic",
      iconUrl: "icons/icon48.png",
      title: "Saved to today's notes",
      message: info.selectionText.length > 80
        ? info.selectionText.slice(0, 77) + "…"
        : info.selectionText,
    });
  } catch (e) {
    chrome.notifications.create({
      type: "basic",
      iconUrl: "icons/icon48.png",
      title: "Capture failed",
      message: e.message,
    });
  }
});
