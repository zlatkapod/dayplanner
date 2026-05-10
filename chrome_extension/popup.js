const API = "http://localhost:8384/capture";

const textEl   = document.getElementById("text");
const urlEl    = document.getElementById("url");
const btn      = document.getElementById("capture");
const statusEl = document.getElementById("status");

let sourceUrl = "";

async function getSelectedText(tabId) {
  const results = await chrome.scripting.executeScript({
    target: { tabId },
    func: () => window.getSelection()?.toString() ?? "",
  });
  return results?.[0]?.result ?? "";
}

(async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  sourceUrl = tab.url ?? "";
  urlEl.textContent = sourceUrl;

  try {
    const selected = await getSelectedText(tab.id);
    if (selected.trim()) {
      textEl.value = selected.trim();
      btn.disabled = false;
    }
  } catch {
    // scripting blocked on chrome:// or PDF pages — user can still type manually
  }
})();

textEl.addEventListener("input", () => {
  btn.disabled = !textEl.value.trim();
});

btn.addEventListener("click", async () => {
  btn.disabled = true;
  statusEl.className = "";
  statusEl.textContent = "Saving…";

  const now = new Date();
  const timestamp = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;

  try {
    const res = await fetch(API, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text: textEl.value.trim(),
        source_url: sourceUrl,
        timestamp,
      }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail ?? "Server error");
    }

    statusEl.className = "ok";
    statusEl.textContent = "Saved to today's notes ✓";
    textEl.value = "";
    btn.disabled = true;
  } catch (e) {
    statusEl.className = "err";
    statusEl.textContent = `Error: ${e.message}`;
    btn.disabled = false;
  }
});
