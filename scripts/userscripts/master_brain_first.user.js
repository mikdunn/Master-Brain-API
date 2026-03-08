// ==UserScript==
// @name         Master Brain First (Userscript)
// @namespace    https://github.com/mikdunn/Master-Brain-API
// @version      0.1.0
// @description  Intercept submit in ChatGPT/Perplexity, ground via local Master Brain bridge, then submit.
// @author       mikdunn
// @match        https://chatgpt.com/*
// @match        https://chat.openai.com/*
// @match        https://www.perplexity.ai/*
// @match        https://perplexity.ai/*
// @grant        GM_xmlhttpRequest
// @connect      127.0.0.1
// ==/UserScript==

(function () {
  'use strict';

  const cfg = {
    bridgeUrl: 'http://127.0.0.1:8787',
    endpoint: '/v1/copilot-context',
    apiKey: 'master-brain-bridge-local',
    projectRoot: '',
    indexPath: '',
    k: 6,
  };

  let bypass = false;
  let inFlight = false;

  function isEditable(el) {
    return !!el && (el.tagName === 'TEXTAREA' || el.isContentEditable);
  }

  function detectComposer() {
    const active = document.activeElement;
    if (isEditable(active)) return active;
    return document.querySelector('textarea, div[contenteditable="true"], [role="textbox"][contenteditable="true"]');
  }

  function getText(el) {
    return el.tagName === 'TEXTAREA' ? (el.value || '') : (el.innerText || el.textContent || '');
  }

  function setText(el, text) {
    if (el.tagName === 'TEXTAREA') {
      el.value = text;
      el.dispatchEvent(new Event('input', { bubbles: true }));
      return;
    }
    el.focus();
    document.execCommand('selectAll', false);
    document.execCommand('insertText', false, text);
    el.dispatchEvent(new Event('input', { bubbles: true }));
  }

  function bridgeEnrich(question) {
    return new Promise((resolve, reject) => {
      const body = {
        question,
        k: cfg.k,
      };
      if (cfg.projectRoot) body.project_root = cfg.projectRoot;
      if (cfg.indexPath) body.index_path = cfg.indexPath;

      GM_xmlhttpRequest({
        method: 'POST',
        url: `${cfg.bridgeUrl}${cfg.endpoint}`,
        headers: {
          'Content-Type': 'application/json',
          'x-api-key': cfg.apiKey,
        },
        data: JSON.stringify(body),
        onload: (resp) => {
          if (resp.status < 200 || resp.status >= 300) {
            reject(new Error(`Bridge HTTP ${resp.status}: ${resp.responseText}`));
            return;
          }
          try {
            const data = JSON.parse(resp.responseText || '{}');
            resolve((data.prompt || data.answer || '').trim());
          } catch (err) {
            reject(err);
          }
        },
        onerror: (err) => reject(err),
      });
    });
  }

  function submitWithEnter(el) {
    bypass = true;
    el.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', bubbles: true, cancelable: true }));
    setTimeout(() => { bypass = false; }, 0);
  }

  async function enrichAndSubmit(el) {
    if (inFlight) return;
    const question = getText(el).trim();
    if (!question) return;

    inFlight = true;
    try {
      const prompt = await bridgeEnrich(question);
      if (prompt) {
        setText(el, prompt);
      }
    } catch (err) {
      console.warn('[MasterBrain userscript] enrich failed:', err);
    } finally {
      submitWithEnter(el);
      inFlight = false;
    }
  }

  document.addEventListener('keydown', (event) => {
    if (bypass) return;
    if (event.key !== 'Enter') return;
    if (event.shiftKey || event.ctrlKey || event.altKey || event.metaKey) return;

    const el = detectComposer();
    if (!isEditable(el)) return;

    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
    enrichAndSubmit(el);
  }, true);
})();
