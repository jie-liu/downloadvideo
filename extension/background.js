const SERVER_URL = "http://localhost:8765";

async function checkServer() {
  try {
    const resp = await fetch(`${SERVER_URL}/api/ping`, { signal: AbortSignal.timeout(2000) });
    return resp.ok;
  } catch {
    return false;
  }
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "CHECK_SERVER") {
    checkServer().then((online) => sendResponse({ online }));
    return true;
  }
});
