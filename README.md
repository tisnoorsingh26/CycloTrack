# CycloTrack

## Historical IBTrACS replay backend

The backend exposes `POST /replay/ibtracs` with `{ "name": "Amphan", "season": 2020 }`.
It reads the official NOAA/NCEI North Indian Ocean IBTrACS v04r01 archive, uses TinyFish Fetch
as the preferred retrieval path, and falls back to a bounded direct download. Parsed storm tables
are cached under `backend/cache/ibtracs`. TinyFish Agent URL discovery is a maintenance action
that refreshes at most once per day; replay requests do not run the Agent. Set
`TINYFISH_API_KEY` only in the backend environment to enable Fetch and discovery. The replay
path does not call IMD; `imd_cross_check` is an explicit opt-in field and is reported separately.

The replay uses the existing feature builder, validator, 24-hour and 48-hour LSTMs, and scalers.
It only evaluates cutoffs with nine consecutive three-hourly inputs and exact +24-hour/+48-hour
verification fixes. No missing rows are interpolated. Published flagged rows and rows without
native New Delhi wind are marked in provenance; more than two flagged inputs produces an
`approximate_input` quality warning. Results are historical replay, not live forecasts.

## Backend setup and focused tests

From the repository root in PowerShell:

```powershell
python -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
backend/.venv/Scripts/python.exe -m pytest --basetemp=backend/.pytest-run backend/tests/test_ibtracs_replay.py -q
```

The backend pins `scikit-learn==1.6.1` because the existing serialized scalers were created
with scikit-learn 1.6.1. An environment reporting another version (the inspected workspace
virtual environment reported 1.7.2 before the requirements were aligned) can warn or fail when
loading those scaler artifacts; install the pinned requirements before running the API.
