# Math Logic Agent

A hybrid local+cloud math logic sidecar for VS Code Copilot workflows.

## What this MVP does

- Ingests math documents from folders (`.pdf`, `.pptx`, `.txt`, `.md`)
- Chunks content with source/page metadata
- Builds a hybrid retriever (lexical + semantic proxy) with optional cloud embedding rerank
- Adds theorem-aware ranking boosts (definition/theorem/proof/exercise + domain tags)
- Routes user queries by mode: explanation, symbolic, coding, exam
- Performs symbolic operations (solve/simplify/diff/integrate/verify) with SymPy
- Supports incremental re-indexing with file change detection
- Includes benchmark harness for mode accuracy and retrieval hit rate
- Adds OCR fallback hooks for low-quality/scanned PDF pages (optional extras)
- Extracts page-level equation candidates into document metadata
- Reports answer confidence score and label (`low`/`medium`/`high`)
- Exposes a CLI bridge for context generation before prompting Copilot

## Quick start

1. Create and activate a virtual environment
2. Install package in editable mode with dev extras
3. Put your API key in `.env` (optional for cloud reranking)
4. Build index from your folders
5. Ask queries through the CLI

## Example project paths

- `<your-project>/Math`
- `<your-project>/SVD_stuffs`

## CLI flow

- `mla build-index --input-dir <path> --index-path data/index.pkl --incremental --ocr-fallback`
- `mla watch-index --input-dir <path> --index-path data/index.pkl --interval-seconds 60 --ocr-fallback`
- `mla ask "What is SVD and why does it help least squares?" --index-path data/index.pkl`
- `mla ask "solve x^2-4=0 for x" --index-path data/index.pkl`
- `mla copilot-context "Explain eigendecomposition vs SVD" --index-path data/index.pkl`
- `mla benchmark --dataset-path benchmarks/sample_benchmark.jsonl --index-path data/index.pkl`

## Multi-module brain flow

- `mla list-modules --module-config config/modules.toml`
- `mla build-brain --module-config config/modules.toml --index-path data/brain_index.pkl --incremental --quarantine-path data/quarantine.json --checkpoint-path data/build_checkpoint.json --checkpoint-every 200`
- `mla ask "Compare SVD in imaging and bioinformatics workflows" --index-path data/brain_index.pkl`
- `mla quarantine-list --quarantine-path data/quarantine.json`
- `mla quarantine-clear --quarantine-path data/quarantine.json --module-id microscopy_core`

By default, module mappings live in `config/modules.toml`, where each module ID maps to one or more folder paths.

### Resumable and fail-fast builds

- Problematic files are quarantined so future runs can skip repeated failures.
- Progress checkpoints are written during long builds and at completion.
- Use `--checkpoint-every` to control checkpoint frequency for large corpora.
- Use `quarantine-list` to inspect failures and `quarantine-clear` after fixing files.

## Master Brain flow

- `mla init-master-structure --master-root "<your-project>/Master Brain" --module-config config/master_brain.toml`
- `mla build-master-brain --master-root "<your-project>/Master Brain" --module-config config/master_brain.toml --index-path data/master_brain_index.pkl --incremental --quarantine-path data/master_brain_quarantine.json --checkpoint-path data/master_brain_checkpoint.json --checkpoint-every 200 --respect-quarantine`
- `mla ask "Connect optimization, control theory, and econometrics" --index-path data/master_brain_index.pkl`

## Bridge API + Windows background service

Use this to bridge Master Brain context into Copilot/ChatGPT-style workflows.

- Start API locally:
  - `python -m uvicorn math_logic_agent.api:app --host 127.0.0.1 --port 8787`
- Health check:
  - `GET http://127.0.0.1:8787/health`
- Query endpoint:
  - `POST http://127.0.0.1:8787/v1/query`
  - body: `{"question":"Explain SVD for denoising","k":6,"project_root":"<your-project>"}`
  - optional header alternative: `x-project-root: <your-project>`
  - header (if `BRIDGE_API_KEY` set): `x-api-key: <key>`
- Copilot context endpoint:
  - `POST http://127.0.0.1:8787/v1/copilot-context`
- Indexed file listing endpoint:
  - `GET http://127.0.0.1:8787/v1/indexed-files?project_root=<your-project>`
  - optional header alternative: `x-project-root: <your-project>`
- Dropbox connectivity endpoint:
  - `GET http://127.0.0.1:8787/v1/dropbox-health`
  - header: `x-api-key: <key>`

Windows service scripts:

- Install + start service:
  - `powershell -ExecutionPolicy Bypass -File scripts/install-masterbrain-service.ps1`
- Stop service (without uninstall):
  - `powershell -ExecutionPolicy Bypass -File scripts/stop-masterbrain-service.ps1`
- Uninstall service:
  - `powershell -ExecutionPolicy Bypass -File scripts/uninstall-masterbrain-service.ps1`

Service behavior:

- Starts automatically at Windows startup.
- Restarts automatically if the API process exits unexpectedly.
- Continues running until you explicitly stop or uninstall the service.

Bridge environment variables (`.env`):

- `PERPLEXITY_API_KEY` (optional, for Perplexity-backed features)
- `BRIDGE_API_KEY` (recommended for any non-local use)
- `BRIDGE_HOST` (default `127.0.0.1`)
- `BRIDGE_PORT` (default `8787`)
- `BRIDGE_DEFAULT_INDEX_PATH` (default `data/master_brain_index.pkl`)
- `BRIDGE_WORKSPACE_ROOT` (optional base folder used when resolving relative index paths)
- `MASTER_BRAIN_ROOT` (optional default root for `init-master-structure`/`build-master-brain`)

If `BRIDGE_API_KEY` is missing/placeholder, the API enforces a built-in fallback key: `master-brain-bridge-local`.

## Optional OCR support

- Install OCR extras: `pip install -e .[ocr]`
- For scanned PDFs, you may also need system tools:
  - Tesseract OCR installed and on PATH
  - Poppler installed and on PATH (for `pdf2image`)

## Update behavior for new files

- New files are **not** ingested automatically unless you:
  - run `build-index --incremental`, or
  - run `watch-index` continuously.
- With incremental indexing, unchanged files are reused and only changed/new files are ingested.
