const DEFAULTS = {
  bridgeUrl: "http://127.0.0.1:8787",
  endpoint: "/v1/copilot-context",
  apiKey: "master-brain-bridge-local",
  projectRoot: "",
  indexPath: "",
  k: 6,
  appendOriginalQuestion: false,
};

function setStatus(message) {
  const status = document.getElementById("status");
  status.textContent = message;
  setTimeout(() => {
    status.textContent = "";
  }, 1500);
}

async function load() {
  const cfg = await chrome.storage.sync.get(DEFAULTS);
  document.getElementById("bridgeUrl").value = cfg.bridgeUrl || DEFAULTS.bridgeUrl;
  document.getElementById("endpoint").value = cfg.endpoint || DEFAULTS.endpoint;
  document.getElementById("apiKey").value = cfg.apiKey || DEFAULTS.apiKey;
  document.getElementById("projectRoot").value = cfg.projectRoot || "";
  document.getElementById("indexPath").value = cfg.indexPath || "";
  document.getElementById("k").value = Number(cfg.k || DEFAULTS.k);
  document.getElementById("appendOriginalQuestion").value = cfg.appendOriginalQuestion ? 1 : 0;
}

async function save() {
  const cfg = {
    bridgeUrl: document.getElementById("bridgeUrl").value.trim(),
    endpoint: document.getElementById("endpoint").value,
    apiKey: document.getElementById("apiKey").value.trim(),
    projectRoot: document.getElementById("projectRoot").value.trim(),
    indexPath: document.getElementById("indexPath").value.trim(),
    k: Math.max(1, Math.min(30, Number(document.getElementById("k").value) || 6)),
    appendOriginalQuestion: Number(document.getElementById("appendOriginalQuestion").value) === 1,
  };
  await chrome.storage.sync.set(cfg);
  setStatus("Saved");
}

document.getElementById("save").addEventListener("click", save);
load();
