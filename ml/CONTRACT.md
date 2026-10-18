# Verified ML contracts

Source of truth: the original Kaggle notebooks in this folder. Training datasets are **not** in this repository.

## CNN — wind speed from 4-channel imagery

- Artifact: `best_cyclone_cnn_huber.keras` (Huber-loss retraining; file size ~3.98 MB).
- Notebook: `cyclone-project-hackathon.ipynb`.
- Input: `(128, 128, 4)` float32. Training code loaded HDF5 `Images` and did `X.astype(np.float32) / 255.0`.
- Output: one scalar named conceptually `predicted_wind_knots` (knots).
- Channel meaning is **not documented** in the notebook. Channel 3 contained non-finite values that were repaired with the per-image median (or zero if the whole channel was invalid). Ordinary 3-channel RGB photos are **not** a valid input.
- Held-out test metrics from the notebook (unseen cyclone IDs): MAE **11.75 knots**, RMSE **16.32 knots**. Earlier MSE CNN: test MAE 14.90, RMSE 19.94. Validation MAE for the Huber run was 12.01 knots (epoch 18).
- Dataset used on Kaggle: `vaukaofworlds/thecycloneimagedataset` (`Cyclone_Images.h5`, `Cyclone_Labels h5.npy`). Labels included `wind_knots`. That dataset is **not present** here, so we cannot replay the original test images.

## LSTM — 24 h and 48 h track displacement

- Artifacts: `cyclone_24h.keras`, `cyclone_48h.keras`, matching `x_scaler_*` / `y_scaler_*` joblib `StandardScaler` pickles.
- Notebook: `cyclone-project-hackathon-path-predictor.ipynb`.
- Dataset: IMD best-track via `imdtrack` (`bt = imd.load().clean(fix_dates=True)`). Not stored in this repo; feature rules were recovered from the notebook.
- Filter: basins BOB and ARB; lat in [-40, 40]; lon in [30, 130].
- Sequence: **8 steps**, **3 hours apart** (hours 0, 3, …, 21). Last input is +21 h from window start.
- Targets: displacement in **degrees** from the last observed `(lat, lon)` to the position **24 h** later (timestamp +45 h from start) and **48 h** later (+69 h). Output order is `(delta_lat, delta_lon)`, then add last observed position.
- Feature order (`feature_cols_v2`):

  `lat`, `lon`, `wind`, `hour_sin`, `hour_cos`, `month_sin`, `month_cos`, `north_kmh`, `east_kmh`, `delta_lat`, `delta_lon`

- Time encodings: `sin/cos(2π hour/24)` and `sin/cos(2π month/12)` using the observation timestamp’s hour and month.
- Motion: `delta_lat` / `delta_lon` from the previous observation in the same storm; `north_kmh = delta_lat * 111.0 / delta_hours`; `east_kmh = delta_lon * 111.0 * cos(radians(lat)) / delta_hours`. First step of a storm has undefined motion and was dropped when building windows.
- Wind: IMD `wind` (knots in that dataset), with median fill during training. Inference requires a numeric wind value.
- Held-out storm test (notebook): 24 h LSTM mean **140.7 km** (baseline 206.5); 48 h LSTM mean **323.5 km** (baseline 448.2). Baseline = persist latest observed velocity.

Do not treat an HTTP 200 as scientific validation. Without the original test sequences we can only check shapes, scaler dimensions, and that a forward pass returns finite numbers.
