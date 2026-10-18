# Phase 1b IBTrACS check

From the repository root, install the CSV parser dependency and run:

```powershell
backend\.venv\Scripts\python.exe -m pip install -r scripts\requirements-phase1b.txt
backend\.venv\Scripts\python.exe scripts\phase1b_ibtracs.py
```

The script reads `TINYFISH_API_KEY` only through backend settings (`backend/.env` or the server environment). It never prints or stores request headers. It caches raw API responses and downloaded CSVs under `tests/fixtures/`, enforces a 40 MiB download limit and HTTP timeout, and does not call IMD. The Agent task returns URLs only and is limited to one run (maximum two). A fresh execution makes one Search, two Fetch requests (directory and selected CSV), and one Agent call; rerunning the command may repeat them and consume credits.

`--resume-file-check` continues from the cached Agent and Fetch fixtures without repeating Search, directory Fetch, file Fetch, or Agent calls:

```powershell
backend\.venv\Scripts\python.exe scripts\phase1b_ibtracs.py --resume-file-check
```

Run the resume form only after a prior complete run has written `tests/fixtures/phase1b_ibtracs_agent_1.json`. If `TINYFISH_API_KEY` is absent, the script still writes Step A from saved fixtures and records that live checks were not run.
