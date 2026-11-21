# Verification report — fresh v1.0 prototype

## Checks run in this environment
- `python -m compileall -q app.py run.py` — pass
- `node --check static/app.js` — pass
- `pytest -q` — 7 tests pass
- HTML parser structure check — seven page sections; no duplicate IDs
- Chromium mocked UI smoke test — query report rendered, one claim and one source card rendered, all page navigation exercised
- Desktop viewport 1440px — no horizontal document overflow
- Mobile viewport 390px — no horizontal overflow; drawer opens and closes; stability test renders four condition cards
- Desktop and mobile screenshots are included for visual reference

## Not verified
- Live API requests to any real AI provider (no real provider credentials used)
- Live Tavily search
- Windows-specific launcher installation/startup on a real Windows machine
- Long-running stability runs, model rate limits, or actual research accuracy

The UI smoke test uses mock responses. It does not represent model performance or external integration success.
