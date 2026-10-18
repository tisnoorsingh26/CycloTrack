# Cyclotrack

An AI/ML cyclone forecasting and intelligence platform built for a college hackathon. It combines LSTM track forecasting with a TinyFish-powered data acquisition pipeline that finds, retrieves and validates cyclone track data from the open web, with every row traceable to its source.

> **Status:** hackathon prototype. The historical replay feature is the part that has been tested end to end. See [Limitations](#limitations) before drawing conclusions from any numbers.

## What it does

1. **Historical replay (TinyFish-powered).** Enter a North Indian Ocean cyclone name. The backend retrieves NOAA's IBTrACS best-track archive through TinyFish, validates the storm's observations, runs the 24h and 48h LSTMs from many past cutoff times, and compares each forecast with what actually happened and with a constant-velocity baseline. Results are shown on the existing map.
2. **Live IMD forecast (existing).** The original workflow uses the India Meteorological Department's Cyclone Track API. It is unchanged and is not used by the replay.
3. **CNN satellite-image wind estimation (existing).** Upload a satellite image of a cyclone and a CNN estimates its wind speed in knots. The LSTM, by contrast, forecasts the cyclone's future track for 24 and 48 hours.

## How TinyFish is used

| TinyFish API | Role in Cyclotrack |
|---|---|
| **Search** | Discovers authoritative best-track dataset sources. |
| **Agent** | Navigates the NOAA NCEI IBTrACS directory and returns the URLs of the right North Indian CSV and column documentation. It returns URLs only, never track rows. Results are cached, so the Agent is not called per request. |
| **Fetch** | Primary retrieval of the IBTrACS North Indian CSV (about 28 MB of text). A bounded direct HTTP download is the fallback. |
| **Browser** | Not used. |

**What the smoke tests showed.** Searching the open web for tracks of Amphan, Fani, Michaung and Dana returned pages, but our parser accepted zero usable observation rows from them (news, prose and pages without complete tables). The Agent returned empty lists instead of inventing data. That is why the pipeline targets an authoritative dataset instead. Fetch's copy of the IBTrACS table was checked against a direct NOAA download: same row count (62,864) and matching SHA-256 checksums.

## Pipeline

```
Search / cached Agent discovery -> Fetch (IBTrACS NI CSV) -> parse (units row, storm filter)
    -> validate -> build (1, 8, 11) features -> LSTM 24h / 48h -> compare with actual track and baseline
```

Every response carries provenance: source URL, retrieval path (`tinyfish_fetch` or direct), retrieval time, whether the result is live or cached, and which input rows are flagged as interpolated.

## Machine learning

**LSTM track forecasting (unchanged).** Two models, `cyclone_24h.keras` and `cyclone_48h.keras`, each with its own input and output scalers.
- Input: 8 timesteps exactly 3 hours apart, 11 features: `lat, lon, wind, hour_sin, hour_cos, month_sin, month_cos, north_kmh, east_kmh, delta_lat, delta_lon`. Wind is in knots.
- The model predicts displacement from the last observed position. A 9th earlier fix is required to compute the first row's deltas.
- Trained on IMD best-track data (imdtrack package, North Indian Ocean).
- Held-out test set (15 storms), mean error in km:

| Horizon | LSTM | Constant-velocity baseline |
|---|---|---|
| 24 h | 140.7 | 206.5 |
| 48 h | 323.5 | 448.2 |

**CNN (existing).** Analyzes satellite images to estimate cyclone wind speed (in knots). It is a separate model from the LSTM and does not forecast tracks. *[Add input image size, architecture and evaluation results from the existing implementation if you want them listed.]*

## Validation rules

The model is never run on data that fails these checks, and no observations are fabricated:
- Single cyclone identity, no mixed storms.
- Valid UTC timestamps, no duplicates with conflicting values, and the source order recorded.
- Exactly 3-hourly spacing across the 9 required fixes, with wind present.
- Coordinates inside the training domain (lat -40 to 40, lon 30 to 130).
- Interpolated or flagged input rows are counted. More than 2 of the 9 input rows flagged makes that forecast **approximate**, and the UI says so.
- Data types are kept separate: historical, live, official forecast, model prediction. Historical data is never shown as live.

## Example replay results

Diagnostics from live replays, averaged over every valid cutoff for each storm. **These are not an accuracy evaluation.**

| Storm | Cutoffs | 24 h LSTM / baseline (mean km) | 48 h LSTM / baseline (mean km) |
|---|---|---|---|
| Michaung 2023 | 19 (12 approximate input, 7 clean) | 97.7 / 125.7 | 207.3 / 283.2 |
| Amphan 2020 | 21 (all clean input) | 66.5 / 165.3 | 175.4 / 402.2 |

## Limitations

- **Historical only.** Replay does not establish a live-cyclone data path. Live forecasting still uses the IMD route.
- **Possible training overlap.** The training data (imdtrack, 1982-2026 per its documentation) includes these storms, and the exact split is not available to the app unless `ml/test_storms.json` is present. Without it, every replay is labelled `possible_training_overlap`. The replay numbers above can look better than true held-out performance.
- **Interpolation.** IBTrACS provides 3-hourly points, but most agencies report every 6 hours, so many 3-hourly rows are interpolated. The models were trained mostly on native 3-hourly data.
- **Cutoffs are not independent.** Cutoffs from one storm overlap heavily, so the cutoff count is not a sample size.
- **Not every storm can be replayed.** Short, older or sparsely sampled storms fail validation, and the app reports the reason instead of forcing a result.
- **Same agency data.** The IBTrACS North Indian Ocean data originates largely from IMD (RSMC New Delhi). The replay is independent of the IMD *API*, not of IMD as a data source.

## Setup

Requirements: Python (backend), Node.js (frontend).

Environment variables (backend, never exposed to the frontend):
- `TINYFISH_API_KEY`: TinyFish key.
- `IMD_API_TOKEN`: IMD key, needed only for the live IMD workflow.

Backend (PowerShell):
```powershell
cd backend
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Frontend (PowerShell):
```powershell
cd frontend
.\node_modules\.bin\next.cmd dev --webpack --hostname 127.0.0.1 --port 3000
```

Open http://127.0.0.1:3000. `scikit-learn` is pinned to 1.6.1 to match the saved scalers. The first replay after a restart downloads and parses the IBTrACS archive, so it can take up to a minute.

## Project structure

```
backend/app/services/   registry.py, features.py, lstm.py, imd_cyclone.py,
                        tinyfish.py, live_sources.py, ibtracs_replay.py
backend/tests/          test_ibtracs_replay.py
frontend/               api.ts, source-intelligence-panel.tsx
ml/                     models (.keras), scalers (.pkl), optional test_storms.json
scripts/                tinyfish_smoke_test.py, phase1b_ibtracs.py
```

## Testing status

- Run: focused backend tests (replay validation, interpolation flags, overlap labelling), TypeScript check, webpack production build, live TinyFish Fetch replays, Fetch vs direct download integrity check.
- Not run: TinyFish credit accounting, live-cyclone freshness workflow, independent evaluation on held-out storms.

## Acknowledgements

Data: NOAA NCEI IBTrACS v04r01 (public domain). Web retrieval: TinyFish. Training data: imdtrack package (IMD best tracks).
