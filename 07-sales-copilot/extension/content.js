// TODO: these selectors are PLACEHOLDERS. The CRM's real DOM was not available when this was
// written. Open the inbox, inspect the elements, and replace them. Nothing else needs to change.
const SELECTORS = {
  message: "[data-testid='message']",       // every message bubble in the open thread
  repMessage: "[data-from='rep']",           // a message sent by your team (others = prospect)
  replyBox: "[data-testid='reply-box']",     // textarea or contenteditable
};

function readThread() {
  return [...document.querySelectorAll(SELECTORS.message)]
    .map((el) => ({
      role: el.matches(SELECTORS.repMessage) ? "rep" : "prospect",
      text: (el.innerText || "").trim(),
    }))
    .filter((m) => m.text);
}

function insertIntoReplyBox(text) {
  const box = document.querySelector(SELECTORS.replyBox);
  if (!box) return false;
  if ("value" in box) box.value = text;
  else box.textContent = text;
  box.dispatchEvent(new Event("input", { bubbles: true })); // let the app's framework notice
  box.focus();
  return true;
}

function render(panel, result) {
  panel.replaceChildren(); // clear; text is always set via textContent, never innerHTML
  if (!result.ok) return addNote(panel, `Copilot unavailable: ${result.error}`);

  const { objection, suggestions, note } = result.data;
  if (!suggestions.length) return addNote(panel, note || "No suggestion for this message.");
  if (objection) addNote(panel, `Detected: ${objection.replace(/_/g, " ")}`);

  for (const s of suggestions) {
    const card = document.createElement("div");
    card.className = "sc-card";
    const label = document.createElement("div");
    label.className = "sc-label";
    label.textContent = s.source === "won_deal" ? "From a won deal" : "AI draft";
    const body = document.createElement("div");
    body.textContent = s.text;
    const use = document.createElement("button");
    use.textContent = "Insert";
    use.onclick = () => {
      if (!insertIntoReplyBox(s.text)) addNote(panel, "Could not find the reply box.");
    };
    card.append(label, body, use);
    panel.append(card);
  }
}

function addNote(panel, text) {
  const p = document.createElement("div");
  p.className = "sc-note";
  p.textContent = text;
  panel.append(p);
}

function mount() {
  if (document.getElementById("sc-root")) return;
  const root = document.createElement("div");
  root.id = "sc-root";
  const button = document.createElement("button");
  button.id = "sc-button";
  button.textContent = "Suggest reply";
  const panel = document.createElement("div");
  panel.id = "sc-panel";
  panel.hidden = true;

  button.onclick = () => {
    const messages = readThread();
    panel.hidden = false;
    panel.replaceChildren();
    if (!messages.length) return addNote(panel, "No messages found. Check SELECTORS in content.js.");
    addNote(panel, "Thinking...");
    chrome.runtime.sendMessage({ type: "suggest", messages }, (response) => {
      render(panel, response || { ok: false, error: "no response from extension" });
    });
  };

  root.append(panel, button);
  document.body.append(root);
}

mount();
