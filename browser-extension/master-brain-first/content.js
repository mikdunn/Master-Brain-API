(function () {
  let reentryBypass = false;
  let inFlight = false;

  function isEditable(el) {
    if (!el) return false;
    if (el.tagName === "TEXTAREA") return true;
    if (el.isContentEditable) return true;
    return false;
  }

  function detectComposer() {
    const active = document.activeElement;
    if (isEditable(active)) return active;

    const selectors = [
      "textarea",
      "div[contenteditable='true']",
      "[role='textbox'][contenteditable='true']",
    ];

    for (const sel of selectors) {
      const candidate = document.querySelector(sel);
      if (isEditable(candidate)) return candidate;
    }

    return null;
  }

  function getText(el) {
    if (!el) return "";
    if (el.tagName === "TEXTAREA") return el.value || "";
    return el.innerText || el.textContent || "";
  }

  function setText(el, text) {
    if (!el) return;
    if (el.tagName === "TEXTAREA") {
      el.value = text;
      el.dispatchEvent(new Event("input", { bubbles: true }));
      return;
    }

    el.focus();
    if (document.execCommand) {
      document.execCommand("selectAll", false);
      document.execCommand("insertText", false, text);
    } else {
      el.textContent = text;
    }
    el.dispatchEvent(new Event("input", { bubbles: true }));
  }

  function looksLikeSubmitButton(btn) {
    if (!btn) return false;
    const label = `${btn.getAttribute("aria-label") || ""} ${btn.textContent || ""}`.toLowerCase();
    return /(send|submit|ask|go|arrow|up)/.test(label);
  }

  function triggerSubmitWithEnter(el) {
    reentryBypass = true;
    const evt = new KeyboardEvent("keydown", {
      key: "Enter",
      code: "Enter",
      bubbles: true,
      cancelable: true,
    });
    el.dispatchEvent(evt);
    setTimeout(() => {
      reentryBypass = false;
    }, 0);
  }

  async function enrichAndSubmit(el) {
    if (inFlight) return;
    const original = getText(el).trim();
    if (!original) return;

    inFlight = true;
    try {
      const result = await chrome.runtime.sendMessage({
        type: "MB_ENRICH",
        question: original,
      });

      if (!result || !result.ok || !result.prompt) {
        console.warn("Master Brain enrich failed", result?.error || "unknown error");
        triggerSubmitWithEnter(el);
        return;
      }

      setText(el, result.prompt);
      triggerSubmitWithEnter(el);
    } catch (err) {
      console.warn("Master Brain enrich exception", err);
      triggerSubmitWithEnter(el);
    } finally {
      inFlight = false;
    }
  }

  document.addEventListener(
    "keydown",
    (event) => {
      if (reentryBypass) return;
      if (event.key !== "Enter") return;
      if (event.shiftKey || event.altKey || event.ctrlKey || event.metaKey) return;

      const el = detectComposer();
      if (!isEditable(el)) return;

      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();
      enrichAndSubmit(el);
    },
    true
  );

  document.addEventListener(
    "click",
    (event) => {
      if (reentryBypass) return;
      const btn = event.target && event.target.closest ? event.target.closest("button") : null;
      if (!btn || !looksLikeSubmitButton(btn)) return;

      const el = detectComposer();
      if (!isEditable(el)) return;

      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();
      enrichAndSubmit(el);
    },
    true
  );
})();
