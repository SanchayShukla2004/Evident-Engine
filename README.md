# EVIDENT ENGINE — Fresh Research Prototype

An evidence-aware AI response review prototype: query → draft → claim decomposition → source inspection → counter-challenge → calibrated final decision. This is a research prototype, not a certified fact-checking system.


## Requirements
- Windows 10/11
- Python 3.10 or newer (Python launcher `py`)
- Internet access for dependency installation and configured model/search providers

## Start
1. Extract the folder to a normal writable location (e.g., Desktop).
2. Double-click `START_EVIDENT.bat`. On first run, it creates `.venv`, installs requirements, creates `.env` and starts the app.
3. Browser opens at `http://127.0.0.1:8765`. If it doesn't, open that address manually.
4. Open **Configuration** and add your provider's OpenAI-compatible API base URL, API key and model ID, save, then use **Test connection** to check the endpoint.
5. Optional: configure Tavily search API key in `.env` as `TAVILY_API_KEY` and restart the app.

Stop the server by closing its terminal window or pressing Ctrl+C.

## Provider configuration
- `AI_BASE_URL`: endpoint base URL ending in `/v1` (example `https://api.openai.com/v1`)
- `AI_API_KEY`: provider key
- `AI_MODEL`: model ID supported by the provider
- `TAVILY_API_KEY`: optional external search API key
- `APP_HOST`, `APP_PORT`: local bind address and port

Provider key entered in Configuration is stored locally in `evident.db`; it is not returned to the browser. The database is not encrypted. Keep this folder private and don't share it with API credentials.


## Pages
- Overview: local activity counts and pipeline summary (workflow, not telemetry)
- Intelligence Workspace: live query review, language choice, depth, evidence budget, optional search
- Verification Room: claim assessments, challenge and revision view from the latest report
- Evidence Explorer: source links and snippets from latest run
- Stability Lab: runs four live model-response conditions (baseline, paraphrase, evidence-constrained, hypothetical contradiction), saves experiment history, and reports a lexical-overlap metric. **This is not an accuracy or semantic-stability score; no ground truth is included.**
- Audit History: saved queries and report previews
- Configuration: model connection (including test button), language defaults, depth and evidence-budget settings


## Cost and research limits
- A Quick review uses 2 model calls, Balanced uses 3, and Deep uses 4. Stability Lab uses 4 additional calls per experiment. Provider API usage may cost money.
- Stability Lab uses hypothetical prompt perturbations and no ground-truth labels. Its lexical-overlap metric is only a surface proxy.

## Verification output limitations
- Provider-generated claims and confidence labels are not ground truth.
- Search snippets alone are not sufficient evidence. Verify source content independently.
- No source retrieval means the answer is not externally verified.
- The stability experiment uses synthetic prompt conditions; the lexical overlap metric is only a surface proxy, not semantic stability or accuracy. No empirical accuracy claims are made.
- Research claims must be supported by real tests, data and comparisons. Do not treat sample/demo output as results.

## Local data
SQLite database: `evident.db` (created at first launch). Query history and settings are stored locally. No database file is included in the distribution.
