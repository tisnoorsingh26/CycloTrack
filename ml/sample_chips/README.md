# Sample Chips for CycloTrack

This directory contains synthetic image arrays strictly intended for:
1. Input validation (testing dimensions `(128, 128, 4)` and multi-channel handling).
2. API contract verification (`POST /predict/wind`).
3. End-to-end integration testing without requiring the full private Kaggle dataset.

### `synthetic_chip_128x128x4.npy`
- **Shape**: `(128, 128, 4)`
- **Data type**: `uint8` (values 0–255)
- **Description**: Synthetically generated radial and swirl patterns across 4 simulated channels.
- **Scientific Notice**: This is **not real satellite imagery**. Predictions made on this file demonstrate that the CNN pipeline, channel validation, and tensor preprocessing are working correctly. They **do not represent valid meteorological estimates or real cyclone intensity**.
