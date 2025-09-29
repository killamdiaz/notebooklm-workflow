# NotebookLM MVP Workflow Service

This repository contains a FastAPI-based workflow service that automates Google
NotebookLM using Playwright. It also ships with helper scripts to capture login
cookies once, reuse them for automation, and a stub Kindle connector ready for
future expansion.

## Project Layout

```
.
├── app/
│   ├── config.py              # Configuration loader for selectors and timeouts
│   ├── main.py                # FastAPI application
│   └── notebooklm_client.py   # Async Playwright client
├── config.json                # Editable selectors for the NotebookLM UI
├── kindle_connector.py        # EPUB/MOBI extraction stub
├── scripts/
│   ├── run_workflow.py        # Example automation using saved cookies
│   └── save_cookies.py        # Manual login helper
└── README.md
```

## Prerequisites

- Python 3.10+
- [Playwright](https://playwright.dev/python/) with Chromium browser binaries
  installed (`playwright install chromium`)
- FastAPI (install via `pip install -r requirements.txt` once created)
- A valid Google account with access to NotebookLM

## Capturing Login Cookies

1. Install dependencies and Playwright browsers.
2. Run the helper script and log in manually in the spawned browser window:

   ```bash
   python scripts/save_cookies.py
   ```

   The script saves serialized cookies to `cookies.json`. Adjust the path with
   `--output` if needed.

## Running Automation From the CLI

Reuse the saved cookies to upload a document and optionally run a query:

```bash
python scripts/run_workflow.py --upload /path/to/document.pdf --query "Summarize chapter 1" --headless
```

The script prints structured JSON describing the automation results.

## FastAPI Service

Start the service with Uvicorn:

```bash
uvicorn app.main:app --reload
```

Available endpoints:

- `POST /upload` – accepts a multipart file upload and pushes the document to
  NotebookLM. Returns the processing status as JSON.
- `POST /query` – accepts `{ "query": "..." }` and responds with the AI answer
  plus extracted citations.

Configuration is read from `config.json` by default. Override locations and
runtime behaviour using environment variables:

- `NOTEBOOKLM_CONFIG_PATH` – custom path to a configuration file.
- `NOTEBOOKLM_COOKIES_PATH` – path to the saved cookies file.
- `NOTEBOOKLM_HEADLESS` – set to `False` to run the browser with a UI.

### Customising selectors

The automation steps rely on CSS selectors defined under the `upload` and
`query` sections of `config.json`. When NotebookLM ships UI updates, adjust the
following entries:

- `create_notebook_button` – button that opens a fresh notebook immediately
  after login. If the element is missing the client assumes a notebook is
  already active.
- `notebook_ready_marker` – element that becomes visible once the notebook UI
  is ready to accept uploads. This is optional but helps the workflow wait for
  the correct screen before interacting with file inputs.
- `add_source_button`, `file_input`, `processing_indicator`, `processed_marker`
  – selectors used during document upload and processing.
- `prompt_input`, `submit_button`, `response_container`, `citation_selector`
  – selectors used for query submission and answer extraction.

Timeouts for page load, notebook creation, processing and response collection
live under the `timeouts` section of the same file.

## Kindle Connector Stub

`kindle_connector.py` implements `extract_kindle_book(file_path)` which converts
an EPUB or MOBI file into structured JSON:

```python
from kindle_connector import extract_kindle_book

book = extract_kindle_book("/path/to/book.epub")
print(book["title"], book["chapters"][0]["text"][:200])
```

The EPUB extraction uses only the Python standard library. MOBI support is
intentionally naive and should be replaced with a parser such as the
[Kindle API project](https://github.com/Xetera/kindle-api) for production use.

## Next Steps

- Harden the selectors in `config.json` to match the live NotebookLM DOM.
- Persist per-document context (Notebook IDs) to enable targeted queries.
- Replace the MOBI stub with DRM-aware extraction tied to a single device key.
