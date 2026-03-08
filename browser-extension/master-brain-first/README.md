# Master Brain First Browser Extension (MV3)

Intercepts chat submit in ChatGPT/Perplexity, calls your local Master Brain bridge, rewrites the outgoing message with grounded prompt, then submits.

## Install (developer mode)

1. Open Chromium browser extensions page.
2. Enable **Developer mode**.
3. Click **Load unpacked**.
4. Select this folder: `browser-extension/master-brain-first`.
5. Open extension **Options** and set:
   - Bridge URL: `http://127.0.0.1:8787`
   - Endpoint: `/v1/copilot-context`
   - API key: your `BRIDGE_API_KEY`
   - Optional: `project_root` and/or `index_path`

## Behavior

- Press `Enter` in chat composer (or click send):
  - Extension blocks default submit
  - Calls local bridge
  - Replaces composer content with grounded prompt
  - Re-submits

## Notes

- If bridge call fails, extension falls back to original submit.
- This is a pragmatic heuristic for dynamic chat UIs; selectors may need updates if providers change DOM structure.
