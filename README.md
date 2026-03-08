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
- Synthesis endpoint (grounded answer + citations; recommended for sharing):
  - `POST http://127.0.0.1:8787/v1/synthesize`
  - body: `{"question":"Explain SVD for denoising","k":6,"project_root":"<your-project>"}`
  - header (if `BRIDGE_API_KEY` set): `x-api-key: <key>`
  - requires: `PERPLEXITY_API_KEY`
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
- `PERPLEXITY_BASE_URL` (default `https://api.perplexity.ai`)
- `PERPLEXITY_MODEL` (default `sonar-pro`)
- `BRIDGE_API_KEY` (recommended for any non-local use)
- `BRIDGE_HOST` (default `127.0.0.1`)
- `BRIDGE_PORT` (default `8787`)
- `BRIDGE_DEFAULT_INDEX_PATH` (default `data/master_brain_index.pkl`)
- `BRIDGE_WORKSPACE_ROOT` (optional base folder used when resolving relative index paths)
- `MASTER_BRAIN_ROOT` (optional default root for `init-master-structure`/`build-master-brain`)

### Master Brain-first prompt workflow (VS Code + browser chats)

This repo now includes local prompt-preprocessing infrastructure so your chat prompt is grounded by Master Brain **before** submission.

#### 1) Local preprocessor script

- File: `scripts/master_brain_preprocess.py`
- Purpose: calls Bridge API and emits a grounded prompt suitable for VS Code/Copilot/ChatGPT/Perplexity input.

Examples:

- Print grounded prompt from question:
  - `python scripts/master_brain_preprocess.py --question "Explain SVD denoising" --project-root "<your-project>"`
- Read question from stdin:
  - `echo Explain SVD denoising | python scripts/master_brain_preprocess.py --stdin --project-root "<your-project>"`
- Raw JSON output:
  - `python scripts/master_brain_preprocess.py --question "Explain SVD denoising" --output json`

Environment variables supported by the preprocessor:

- `MASTER_BRAIN_BRIDGE_URL` (default `http://127.0.0.1:8787`)
- `MASTER_BRAIN_BRIDGE_ENDPOINT` (default `/v1/copilot-context`)
- `MASTER_BRAIN_PROJECT_ROOT` (default current directory)
- `MASTER_BRAIN_INDEX_PATH` (optional)
- `MASTER_BRAIN_K` (default `6`)
- `MASTER_BRAIN_TIMEOUT_SECONDS` (default `30`)
- `MASTER_BRAIN_APPEND_ORIGINAL_QUESTION` (`1`/`0`)

#### 2) VS Code one-hotkey flow

Workspace files:

- `.vscode/tasks.json`
  - `master-brain: prompt->clipboard` (asks for question, grounds it, copies result to clipboard)
  - `master-brain: prompt->terminal` (same, but prints in terminal)
- `.vscode/keybindings.json`
  - `Ctrl+Alt+M` runs `master-brain: prompt->clipboard`

Usage:

1. Press `Ctrl+Alt+M`
2. Enter your question in the prompt box
3. Paste grounded prompt into your chat/composer

#### 3) Browser submit interception (extension/userscript)

- Extension (recommended): `browser-extension/master-brain-first/`
  - Intercepts Enter/click submit in ChatGPT/Perplexity
  - Calls local bridge
  - Rewrites composer text with grounded prompt
  - Re-submits
- Userscript alternative: `scripts/userscripts/master_brain_first.user.js`

For extension setup, see:

- `browser-extension/master-brain-first/README.md`

BigQuery telemetry environment variables:

- `BQ_TELEMETRY_ENABLED` (default `0`)
- `BQ_PROJECT_ID` (required when telemetry enabled)
- `BQ_DATASET_ID` (default `master_brain_analytics`)
- `BQ_QUERY_TABLE` (default `query_telemetry`)
- `BQ_RETRIEVAL_HITS_TABLE` (default `retrieval_hits`)
- `BQ_BUILD_RUNS_TABLE` (default `build_runs`)
- `BQ_FILE_INVENTORY_TABLE` (default `file_inventory_snapshot`)
- `BQ_CHUNK_METADATA_TABLE` (default `chunk_metadata_catalog`)
- `BQ_TIMELINE_EVENTS_TABLE` (default `timeline_events`)
- `BQ_INSERT_TIMEOUT_SECONDS` (default `1`)
- `BQ_FLUSH_BATCH_SIZE` (default `50`)
- `BQ_FLUSH_INTERVAL_SECONDS` (default `2`)
- `BQ_QUEUE_MAXSIZE` (default `2000`)
- `BQ_INCLUDE_QUESTION_TEXT` (default `0`; keep disabled for safer logging)

Interdisciplinary retrieval tuning:

- `INTERDISCIPLINARY_MIN_PER_BRAIN` (default `1`; minimum seed hits attempted per selected brain during fusion)
- `INTERDISCIPLINARY_SEED_SCORE_RATIO` (default `0.70`; per-brain seed must score at least this fraction of top score)

Public/shared deployment safety switches:

- `BRIDGE_PUBLIC_MODE=1` enables a hardened mode intended for safe sharing.
  - ignores caller-provided `project_root` and `index_path` overrides
  - clamps `k` to `BRIDGE_PUBLIC_MAX_K`
  - forces `cloud_rerank=false`
  - disables endpoints that can leak raw chunk text by default
- `BRIDGE_PUBLIC_MAX_K` (default `10`)
- `BRIDGE_PUBLIC_ALLOW_ADMIN_ENDPOINTS=1` to allow `/v1/config` and `/v1/indexed-files` in public mode (off by default)
- `BRIDGE_PUBLIC_RETURN_CONTEXT=1` to allow raw-context endpoints in public mode (off by default; not recommended)

Best-effort rate limiting (in-process):

- `BRIDGE_RATE_LIMIT_RPM` (default `60`)
- `BRIDGE_RATE_LIMIT_BURST` (default `20`)

If `BRIDGE_API_KEY` is missing/placeholder, the API enforces a built-in fallback key: `master-brain-bridge-local`.

Important: if you enable `BRIDGE_PUBLIC_MODE=1`, you must set a real `BRIDGE_API_KEY` (the server will refuse to run in public mode with the fallback key).

## BigQuery schema bootstrap (Phase 2.5)

Telemetry emits to multiple BigQuery tables. Bootstrap them once before enabling telemetry:

1. Edit defaults at the top of `scripts/bigquery_schema.sql` (`project_id`, `dataset_id`, and `dataset_location`).

1. Run the schema script: `bq query --use_legacy_sql=false < scripts/bigquery_schema.sql`.

1. Set matching values in `.env`: `BQ_TELEMETRY_ENABLED=1`, `BQ_PROJECT_ID=<your-project-id>`, and `BQ_DATASET_ID=<your-dataset>`.

1. Restart the API process/service.

The schema script creates these tables if they do not already exist:

- `query_telemetry`
- `retrieval_hits`
- `build_runs`
- `file_inventory_snapshot`
- `timeline_events`
- `chunk_metadata_catalog` (reserved for chunk catalog emission in next phases)

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
