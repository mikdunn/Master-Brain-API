const DEFAULT_SETTINGS = {
  bridgeUrl: "http://127.0.0.1:8787",
  endpoint: "/v1/copilot-context",
  apiKey: "master-brain-bridge-local",
  projectRoot: "",
  indexPath: "",
  k: 6,
  appendOriginalQuestion: false,
};

async function getSettings() {
  const existing = await chrome.storage.sync.get(DEFAULT_SETTINGS);
  return { ...DEFAULT_SETTINGS, ...existing };
}

async function enrichQuestion(question) {
  const cfg = await getSettings();
  const base = String(cfg.bridgeUrl || "").replace(/\/$/, "");
  const endpoint = String(cfg.endpoint || "").startsWith("/") ? cfg.endpoint : `/${cfg.endpoint}`;
  const url = `${base}${endpoint}`;

  const payload = {
    question,
    k: Number(cfg.k) || 6,
  };
  if (cfg.projectRoot) payload.project_root = cfg.projectRoot;
  if (cfg.indexPath) payload.index_path = cfg.indexPath;

  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-api-key": String(cfg.apiKey || ""),
    },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`Bridge HTTP ${res.status}: ${detail}`);
  }

  const data = await res.json();
  let prompt = "";

  if (endpoint.endsWith("/v1/copilot-context")) {
    prompt = String(data.prompt || "").trim();
  } else if (endpoint.endsWith("/v1/query") || endpoint.endsWith("/v1/synthesize")) {
    prompt = String(data.answer || "").trim();
  } else {
    prompt = JSON.stringify(data, null, 2);
  }

  if (cfg.appendOriginalQuestion) {
    prompt = `${prompt}\n\nUser question:\n${question}`.trim();
  }

  return { prompt, raw: data, endpoint };
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (!message || message.type !== "MB_ENRICH") {
    return false;
  }

  enrichQuestion(String(message.question || ""))
    .then((result) => sendResponse({ ok: true, ...result }))
    .catch((err) => sendResponse({ ok: false, error: String(err?.message || err) }));

  return true;
});
