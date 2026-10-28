// The service worker makes the network call, not the page. Content scripts run under the host
// page's rules (CSP, CORS), while the worker uses this extension's own host_permissions.
const API = "http://127.0.0.1:8787/suggest";

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.type !== "suggest") return false;

  fetch(API, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ messages: message.messages }),
  })
    .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`API returned ${r.status}`))))
    .then((data) => sendResponse({ ok: true, data }))
    .catch((err) => sendResponse({ ok: false, error: String(err.message || err) }));

  return true; // keep the message channel open for the async response
});
