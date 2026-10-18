# TinyFish smoke test

From the repository root, run:

```powershell
backend/.venv/Scripts/python.exe scripts/tinyfish_smoke_test.py
```

The script reads `TINYFISH_API_KEY` from the backend environment/configuration and never prints or writes the key. It searches for Amphan (2020), Fani (2019), Michaung (2023), and Dana (2024), fetches only approved meteorological domains, applies the existing parser and validator, and uses at most two TinyFish Agent runs per cyclone when Fetch yields fewer than nine parsed rows. Raw responses are stored in `tests/fixtures/`; the report is written to `TINYFISH_SMOKE_REPORT.md`.

The script does not call IMD, interpolate records, or run either LSTM. Agent output is model-generated and remains diagnostic evidence; it is never represented as a verified observation or forecast.
