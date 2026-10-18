# TinyFish live-data smoke report

Generated: 2026-10-17T20:41:13.576513+00:00

This diagnostic performs TinyFish Search, Fetch, the existing `parse_observations` parser, and a capped Agent fallback only when fetched tables have fewer than nine usable rows. It does not call IMD, interpolate observations, or run an LSTM. Search snippets and Agent output are not treated as verified observations.

## Amphan 2020

### Search queries

- `"Amphan" 2020 cyclone historical track best track latitude longitude observation time wind speed` — 10 results; status: ok; fixture: `tests/fixtures/amphan_2020_search_1.json`
- `"Amphan" 2020 cyclone track positions 3-hourly latitude longitude wind speed` — 10 results; status: ok; fixture: `tests/fixtures/amphan_2020_search_2.json`

### Candidates and Fetch

- [cyclone warning in india - standard operation procedure - IMD](https://mausam.imd.gov.in/imd_latest/contents/pdf/cyclone_sop.pdf) — approved for Fetch: True; fetched: True; snippet unverified: `(a) INSAT imagery of cyclone 'AMPHAN' on 18th May showing eye of cyclone. (b) 10m wind distribution during cyclone Amphan at 0000 UTC/17th May, 2020. 1.2.5 ...`
- [Dynamics of Amphan Cyclone and associated changes in ...](http://mausamjournal.imd.gov.in/index.php/MAUSAM/article/download/145/110) — approved for Fetch: False; fetched: False; snippet unverified: `by A CHAUHAN · 2021 · Cited by 18 — On 20 May, 2020, tropical cyclone Amphan hit the Indian coast at ... The strong wind and heavy rainfall were observed as Amphan Cyclone pass ove`
- [Key factors behind super cyclone Gonu (1-7 June 2007) over ...](http://mausamjournal.imd.gov.in/index.php/MAUSAM/article/download/7095/5850) — approved for Fetch: False; fetched: False; snippet unverified: `Recent studies on North. Indian Ocean cyclones, including Tauktae (May 2021),. Amphan (May 2020), Asani (May 2022), and Dana. (October 2024), provide ...`
- [Frequently Asked Questions on Tropical Cyclones and Marine ...](https://rsmcnewdelhi.imd.gov.in/images/pdf/faq.pdf) — approved for Fetch: True; fetched: True; snippet unverified: `Information of position, intensity and track of the tropical cyclone, radius of maximum winds is prepared by ... Moh-rar Phethai Pay-ti Amphan Um-pun. 145. How ...`
- [Performance of moored real time ocean observations ...](https://repository.library.noaa.gov/view/noaa/71427/noaa_71427_DS1.pdf) — approved for Fetch: True; fetched: True; snippet unverified: `by S Ranganathan · 2024 · Cited by 4 — Buoys(CB) . The 10-meter wind field is from 1 m/s to 24 m/s. The black stars in the Bay of. 102. Bengal show the track of cyclone Amphan, sta`
- [Precursors of hazard due to super cyclone AMPHAN for ...](https://mausamjournal.imd.gov.in/index.php/MAUSAM/article/download/6259/5706/28684) — approved for Fetch: True; fetched: True; snippet unverified: `In this article, we have focused on precursors of super cyclone AMPHAN and its associated hazards from a surface observational point of view with respect to.`
- [Recent advancements in prediction of tropical cyclone ...](https://mausamjournal.imd.gov.in/index.php/MAUSAM/article/download/167/120/503) — approved for Fetch: True; fetched: True; snippet unverified: `... Amphan and extremely severe cyclonic storm Phailin. Article. Full-text ... Results were validated with IMD best-fit track observations, Doppler ...`
- [CYCLONE WARNING IN INDIA - IMD](https://mausam.imd.gov.in/thiruvananthapuram/mcdata/cyclone_warning_sop.pdf) — approved for Fetch: True; fetched: True; snippet unverified: `Track prediction of TC, Vardah by EPS. Fig.5.14. A typical example of observed and forecast track of SuCS Amphan. Unlike National Hurricane ...`
- [NWP_REPORT_2022.pdf - Numerical Weather Prediction](https://nwp.imd.gov.in/NWP_REPORT_2022.pdf) — approved for Fetch: True; fetched: True; snippet unverified: `In case of Super cyclone “Amphan” it indicated the genesis of the system in ... The best estimate of the track and intensity of the cyclone as provided ...`
- [D. R. Pattanaik](https://severeweather.wmo.int/TCFW/NewDelhi_Training2022/3_DRPattanaik_ERF_06April2022.pdf) — approved for Fetch: True; fetched: True; snippet unverified: `the vortex center position i.e., Latitude & Longitude and track the storm for the duration ... ❖ ERF forecast for AMPHAN & GULAB also very ...`
- [Cyclone Warning for West Bengal and - RSMC](https://rsmcnewdelhi.imd.gov.in/uploads/archive/1/1_6e7cde_34.National%20Bulletin%2020200520_0300UTC.pdf) — approved for Fetch: True; fetched: True; snippet unverified: `The Super Cyclonic Storm 'AMPHAN' (pronounced as UM-PUN) over Northwest Bay of Bengal ... • Gale wind speed reaching 165-175 gusting to 195 kmph ...`
- [Measurement of Total Ozone, D-UV ... - MAUSAM Journal](https://mausamjournal.imd.gov.in/index.php/MAUSAM/article/download/126/98) — approved for Fetch: True; fetched: True; snippet unverified: `by SS GANESH · 2021 · Cited by 6 — Finally, real-time probabilistic forecasts of cyclogenesis, evolution and track from the prediction system is analysed for two recent tropical cy`
- [Comparative performance of HWRF model coupled with POM ...](http://mausamjournal.imd.gov.in/index.php/MAUSAM/article/download/127/94) — approved for Fetch: False; fetched: False; snippet unverified: `by AK DAS · 2021 · Cited by 8 — AMPHAN over BoB was a classic case super cyclone with clockwise recurving track and rapid intensification which made a landfall over. Indian-Banglad`
- [Super Cyclonic Storm “AMPHAN” over the southeast Bay of ...](https://internal.imd.gov.in/press_release/20200614_pr_840.pdf) — approved for Fetch: True; fetched: False; snippet unverified: `The six hourly average translational speed during the life cycle of SuCS Amphan is presented in Fig. 3a. The six hourly maximum sustained wind ...`
- Fetch status: ok; cache: `tests/fixtures/amphan_2020_fetch.json`; per-URL errors: [{"url": "https://nwp.imd.gov.in/NWP_REPORT_2022.pdf", "error": "timeout"}]

### Rows, spacing, validator, and training domain

- **https://mausam.imd.gov.in/imd_latest/contents/pdf/cyclone_sop.pdf**: Fetch status fetched; parser rows 0; spacing **not enough rows**; 9 consecutive 3-hour rows: **False**; validator pass: **False**; training-domain pass: **False**; spacing-only 6h interpolation possibility: **False**.
- **https://rsmcnewdelhi.imd.gov.in/images/pdf/faq.pdf**: Fetch status fetched; parser rows 0; spacing **not enough rows**; 9 consecutive 3-hour rows: **False**; validator pass: **False**; training-domain pass: **False**; spacing-only 6h interpolation possibility: **False**.
- **https://repository.library.noaa.gov/view/noaa/71427/noaa_71427_DS1.pdf**: Fetch status fetched; parser rows 0; spacing **not enough rows**; 9 consecutive 3-hour rows: **False**; validator pass: **False**; training-domain pass: **False**; spacing-only 6h interpolation possibility: **False**.
- **https://mausamjournal.imd.gov.in/index.php/MAUSAM/article/download/6259/5706/28684**: Fetch status fetched; parser rows 0; spacing **not enough rows**; 9 consecutive 3-hour rows: **False**; validator pass: **False**; training-domain pass: **False**; spacing-only 6h interpolation possibility: **False**.
- **https://mausamjournal.imd.gov.in/index.php/MAUSAM/article/download/167/120/503**: Fetch status fetched; parser rows 0; spacing **not enough rows**; 9 consecutive 3-hour rows: **False**; validator pass: **False**; training-domain pass: **False**; spacing-only 6h interpolation possibility: **False**.
- **https://mausam.imd.gov.in/thiruvananthapuram/mcdata/cyclone_warning_sop.pdf**: Fetch status fetched; parser rows 0; spacing **not enough rows**; 9 consecutive 3-hour rows: **False**; validator pass: **False**; training-domain pass: **False**; spacing-only 6h interpolation possibility: **False**.
- **https://nwp.imd.gov.in/NWP_REPORT_2022.pdf**: Fetch status not returned; parser rows 0; spacing **not enough rows**; 9 consecutive 3-hour rows: **False**; validator pass: **False**; training-domain pass: **False**; spacing-only 6h interpolation possibility: **False**.
- **https://severeweather.wmo.int/TCFW/NewDelhi_Training2022/3_DRPattanaik_ERF_06April2022.pdf**: Fetch status fetched; parser rows 0; spacing **not enough rows**; 9 consecutive 3-hour rows: **False**; validator pass: **False**; training-domain pass: **False**; spacing-only 6h interpolation possibility: **False**.
- **https://rsmcnewdelhi.imd.gov.in/uploads/archive/1/1_6e7cde_34.National%20Bulletin%2020200520_0300UTC.pdf**: Fetch status fetched; parser rows 0; spacing **not enough rows**; 9 consecutive 3-hour rows: **False**; validator pass: **False**; training-domain pass: **False**; spacing-only 6h interpolation possibility: **False**.
- **https://mausamjournal.imd.gov.in/index.php/MAUSAM/article/download/126/98**: Fetch status fetched; parser rows 0; spacing **not enough rows**; 9 consecutive 3-hour rows: **False**; validator pass: **False**; training-domain pass: **False**; spacing-only 6h interpolation possibility: **False**.

### Agent fallback

- Ran: **True**; max runs per cyclone: 2; exact credit amount: not exposed by the run response.
- https://mausam.imd.gov.in/imd_latest/contents/pdf/cyclone_sop.pdf: status ok; structured rows 0; rows accepted for validation 0; fixture `tests/fixtures/amphan_2020_agent_1.json`; run ID `d0bbaf8e-06db-49a7-97b3-3ba1eae805b4`.
  - Spacing not enough rows; 9 consecutive 3h: False; validator pass: False; domain pass: False; spacing-only interpolation possibility: False.
- https://rsmcnewdelhi.imd.gov.in/images/pdf/faq.pdf: status ok; structured rows 0; rows accepted for validation 0; fixture `tests/fixtures/amphan_2020_agent_2.json`; run ID `1f394db4-3d8b-41b0-a9ac-2b0e8d3e3027`.
  - Spacing not enough rows; 9 consecutive 3h: False; validator pass: False; domain pass: False; spacing-only interpolation possibility: False.

### Provenance and limits

Agent JSON is model-generated evidence and only diagnostics are reported; smoke test never runs the LSTM.
This script does not query usage endpoints or wallet balances. Search and Fetch are within their documented daily free allowances when quota remains; Agent execution may consume credits. Check the TinyFish dashboard for exact wallet debits.

## Fani 2019

### Search queries

- `"Fani" 2019 cyclone historical track best track latitude longitude observation time wind speed` — 10 results; status: ok; fixture: `tests/fixtures/fani_2019_search_1.json`
- `"Fani" 2019 cyclone track positions 3-hourly latitude longitude wind speed` — 10 results; status: ok; fixture: `tests/fixtures/fani_2019_search_2.json`

### Candidates and Fetch

- [Hurricane FAQ](https://www.aoml.noaa.gov/hrd-faq/) — approved for Fetch: True; fetched: True; snippet unverified: `The Best Track has a center position and maximum wind speed value for ... 2019 Extremely Severe Cyclonic Storm Fani hits Odisha, India and kills 89 ...`
- [Extremely Severe Cyclonic Storm “FANI” over ... - RSMC](https://rsmcnewdelhi.imd.gov.in/uploads/archive/60/60_a53fa0_fani.pdf) — approved for Fetch: True; fetched: True; snippet unverified: `... and 2.8. X106 knots3 respectively. Fig.1: Observed track of ESCS FANI over east EIO and adjoining southeast. BoB (26 April-04 May, 2019). Fig.2 ...`
- [Cyclone Prediction System (CPS) for the North Indian Ocean](https://severeweather.wmo.int/TCFW/NewDelhi_Training2022/3_CPS-RSMC-2022-SDKOTAL.pdf) — approved for Fetch: True; fetched: True; snippet unverified: `Mean GPP forecasts forecasts based on 00 UTC of 25.04.2019 (FANI) ... All Track forecasts by MME vs Observed Track (FANI). (Bay of Bengal ...`
- [Area of responsibility of RSMC New Delhi](https://rsmcnewdelhi.imd.gov.in/images/pdf/Souvenir_RSMC_17Aug.pdf) — approved for Fetch: True; fetched: True; snippet unverified: `In 2019, COU was further reduced based on average track forecast errors during 2014-18 from cyclone FANI. Page 37. 29. Chapter 7. Operational ...`
- [Precursors of hazard due to super cyclone AMPHAN for ...](https://mausamjournal.imd.gov.in/index.php/MAUSAM/article/download/6259/5706/28684) — approved for Fetch: True; fetched: True; snippet unverified: `In the year 2020, Super Cyclone AMPHAN caused havoc and devastation as it crossed the West. Bengal coast. FANI in 2019, HUDHUD in 2014, LEHAR in 2013, PHAILIN ...`
- [Edition 2019 - RSMC - India Meteorological Department](https://rsmcnewdelhi.imd.gov.in/uploads/report/28/28_8f1ffa_tcp-21-2019.pdf) — approved for Fetch: True; fetched: True; snippet unverified: `(prior to recurvature) and (ii) Observed and forecast track of cyclone FANI with COU effective from (A) 2014 and (B) 2019. 2.5.2 Quadrant wind forecast: (i) ...`
- [STATE OF THE CLIMATE IN 2019](https://repository.library.noaa.gov/view/noaa/61416/noaa_61416_DS1.pdf) — approved for Fetch: True; fetched: True; snippet unverified: `... cyclone season, Cyclone Fani (27 April–3. May), developed unusually close to the equa- tor, at 2.7°N, just west of Sumatra. Strong vertical wind ...`
- [D. R. Pattanaik](https://severeweather.wmo.int/TCFW/NewDelhi_Training2022/3_DRPattanaik_ERF_06April2022.pdf) — approved for Fetch: True; fetched: True; snippet unverified: `the vortex center position i.e., Latitude & Longitude and track the storm for the duration ... FANI Cyclone, 26 April- 05 May 2019. Page 48. IMD ...`
- [Very Severe Cyclonic Storm YAAS over the Bay of Bengal ( ...](https://internal.imd.gov.in/press_release/20210611_pr_1133.pdf) — approved for Fetch: True; fetched: True; snippet unverified: `... Fani, May 2019, 100 kt) in the month of. May. YAAS was the 4 th very severe category cyclonic storm (75 kt) crossing Odisha coast in the ...`
- [mausam - METNET - India Meteorological Department](https://metnet.imd.gov.in/docs/mausamdocs/17616_F.pdf) — approved for Fetch: True; fetched: True; snippet unverified: `by UC MOHANTY · Cited by 5 — VSCS Fani (2019; Mohanty et al., 2020) that struck. Odisha's triplet cities ... Quasi-operational forecast guidance of extremely severe cyclonic storm `
- [cyclone warning in india - standard operation procedure - IMD](https://mausam.imd.gov.in/imd_latest/contents/pdf/cyclone_sop.pdf) — approved for Fetch: True; fetched: False; snippet unverified: `(reduction in COU values based on average track forecast errors during 2009-13) and #FANI. (reduction in COU values based on average track forecast errors ...`
- [CYCLONE WARNING IN INDIA - IMD](https://mausam.imd.gov.in/thiruvananthapuram/mcdata/cyclone_warning_sop.pdf) — approved for Fetch: True; fetched: False; snippet unverified: `2009-13) and #FANI (reduction in COU values based on average track forecast errors during 2009-13 (about 30% further reduction in COU values ...`
- Fetch status: ok; cache: `tests/fixtures/fani_2019_fetch.json`; per-URL errors: [{"url": "https://repository.library.noaa.gov/view/noaa/61416/noaa_61416_DS1.pdf", "error": "target_unreachable"}]

### Rows, spacing, validator, and training domain

- **https://www.aoml.noaa.gov/hrd-faq/**: Fetch status fetched; parser rows 0; spacing **not enough rows**; 9 consecutive 3-hour rows: **False**; validator pass: **False**; training-domain pass: **False**; spacing-only 6h interpolation possibility: **False**.
- **https://rsmcnewdelhi.imd.gov.in/uploads/archive/60/60_a53fa0_fani.pdf**: Fetch status fetched; parser rows 0; spacing **not enough rows**; 9 consecutive 3-hour rows: **False**; validator pass: **False**; training-domain pass: **False**; spacing-only 6h interpolation possibility: **False**.
- **https://severeweather.wmo.int/TCFW/NewDelhi_Training2022/3_CPS-RSMC-2022-SDKOTAL.pdf**: Fetch status fetched; parser rows 0; spacing **not enough rows**; 9 consecutive 3-hour rows: **False**; validator pass: **False**; training-domain pass: **False**; spacing-only 6h interpolation possibility: **False**.
- **https://rsmcnewdelhi.imd.gov.in/images/pdf/Souvenir_RSMC_17Aug.pdf**: Fetch status fetched; parser rows 0; spacing **not enough rows**; 9 consecutive 3-hour rows: **False**; validator pass: **False**; training-domain pass: **False**; spacing-only 6h interpolation possibility: **False**.
- **https://mausamjournal.imd.gov.in/index.php/MAUSAM/article/download/6259/5706/28684**: Fetch status fetched; parser rows 0; spacing **not enough rows**; 9 consecutive 3-hour rows: **False**; validator pass: **False**; training-domain pass: **False**; spacing-only 6h interpolation possibility: **False**.
- **https://rsmcnewdelhi.imd.gov.in/uploads/report/28/28_8f1ffa_tcp-21-2019.pdf**: Fetch status fetched; parser rows 0; spacing **not enough rows**; 9 consecutive 3-hour rows: **False**; validator pass: **False**; training-domain pass: **False**; spacing-only 6h interpolation possibility: **False**.
- **https://repository.library.noaa.gov/view/noaa/61416/noaa_61416_DS1.pdf**: Fetch status not returned; parser rows 0; spacing **not enough rows**; 9 consecutive 3-hour rows: **False**; validator pass: **False**; training-domain pass: **False**; spacing-only 6h interpolation possibility: **False**.
- **https://severeweather.wmo.int/TCFW/NewDelhi_Training2022/3_DRPattanaik_ERF_06April2022.pdf**: Fetch status fetched; parser rows 0; spacing **not enough rows**; 9 consecutive 3-hour rows: **False**; validator pass: **False**; training-domain pass: **False**; spacing-only 6h interpolation possibility: **False**.
- **https://internal.imd.gov.in/press_release/20210611_pr_1133.pdf**: Fetch status fetched; parser rows 0; spacing **not enough rows**; 9 consecutive 3-hour rows: **False**; validator pass: **False**; training-domain pass: **False**; spacing-only 6h interpolation possibility: **False**.
- **https://metnet.imd.gov.in/docs/mausamdocs/17616_F.pdf**: Fetch status fetched; parser rows 0; spacing **not enough rows**; 9 consecutive 3-hour rows: **False**; validator pass: **False**; training-domain pass: **False**; spacing-only 6h interpolation possibility: **False**.

### Agent fallback

- Ran: **True**; max runs per cyclone: 2; exact credit amount: not exposed by the run response.
- https://www.aoml.noaa.gov/hrd-faq/: status ok; structured rows 0; rows accepted for validation 0; fixture `tests/fixtures/fani_2019_agent_1.json`; run ID `9e865b71-a15b-4b59-85e9-c6e744368353`.
  - Spacing not enough rows; 9 consecutive 3h: False; validator pass: False; domain pass: False; spacing-only interpolation possibility: False.
- https://rsmcnewdelhi.imd.gov.in/uploads/archive/60/60_a53fa0_fani.pdf: status error; structured rows 0; rows accepted for validation 0; fixture `tests/fixtures/fani_2019_agent_2.json`; run ID `None`.`n  - Agent failure (timeout): The read operation timed out
  - Spacing not enough rows; 9 consecutive 3h: False; validator pass: False; domain pass: False; spacing-only interpolation possibility: False.

### Provenance and limits

Agent JSON is model-generated evidence and only diagnostics are reported; smoke test never runs the LSTM.
This script does not query usage endpoints or wallet balances. Search and Fetch are within their documented daily free allowances when quota remains; Agent execution may consume credits. Check the TinyFish dashboard for exact wallet debits.

## Michaung 2023

### Search queries

- `"Michaung" 2023 cyclone historical track best track latitude longitude observation time wind speed` — 4 results; status: ok; fixture: `tests/fixtures/michaung_2023_search_1.json`
- `"Michaung" 2023 cyclone track positions 3-hourly latitude longitude wind speed` — 4 results; status: ok; fixture: `tests/fixtures/michaung_2023_search_2.json`

### Candidates and Fetch

- [State of the Climate in 2023: The Tropics](https://repository.library.noaa.gov/view/noaa/69273/noaa_69273_DS1.pdf) — approved for Fetch: True; fetched: True; snippet unverified: `by HJ Diamond · 2024 · Cited by 6 — numerous fatalities and extensive damage. (Aon 2024). Late in the year, Cyclone Midhili and Cyclone Michaung caused flooding and damages ...`
- [प्रेस विज्ञप्ति](https://internal.imd.gov.in/pages/press_release_mausam.php) — approved for Fetch: True; fetched: True; snippet unverified: `... 2023 SEVERE CYCLONIC STORM “MICHAUNG” OVER WESTCENTRAL BAY OF BENGAL ALONG & OFF SOUTH ANDHRA PRADESH COAST, View (pdf) (0 KB). 2138, 2674, 05 Dec 2023, PRESS ...`
- [Monthly Climate Reports | Tropical Cyclones Report](https://www.ncei.noaa.gov/access/monitoring/monthly-report/tropical-cyclones/202312) — approved for Fetch: True; fetched: True; snippet unverified: `Cyclonic Storm Michaung caused heavy rain and strong winds in southeastern India. This activity was typical for the North Indian Ocean. Tropical Storm Jelawat ...`
- [cyclone warning in india - standard operation procedure - IMD](https://mausam.imd.gov.in/imd_latest/contents/pdf/cyclone_sop.pdf) — approved for Fetch: True; fetched: True; snippet unverified: `Typical DWR products used for cyclone monitoring during SCS Michaung. Page ... ✓ Information about forecast track, maximum sustained wind speed and gust, speed ...`
- [FORECASTERS' COMPETENCY FOR WEATHER ... - IMD](https://mausam.imd.gov.in/newdelhi/mcdata/press_release_hi.pdf) — approved for Fetch: True; fetched: True; snippet unverified: `Date and Time of Observation (UTC). 05:00 UTC. 3. Name of the Cyclone. MICHAUNG. 4. Information about the eye of the Cyclone a. Is the Eye Visible. Yes b. Shape ...`
- Fetch status: ok; cache: `tests/fixtures/michaung_2023_fetch.json`; per-URL errors: [{"url": "https://mausam.imd.gov.in/newdelhi/mcdata/press_release_hi.pdf", "error": "target_unreachable"}]

### Rows, spacing, validator, and training domain

- **https://repository.library.noaa.gov/view/noaa/69273/noaa_69273_DS1.pdf**: Fetch status fetched; parser rows 0; spacing **not enough rows**; 9 consecutive 3-hour rows: **False**; validator pass: **False**; training-domain pass: **False**; spacing-only 6h interpolation possibility: **False**.
- **https://internal.imd.gov.in/pages/press_release_mausam.php**: Fetch status fetched; parser rows 0; spacing **not enough rows**; 9 consecutive 3-hour rows: **False**; validator pass: **False**; training-domain pass: **False**; spacing-only 6h interpolation possibility: **False**.
- **https://www.ncei.noaa.gov/access/monitoring/monthly-report/tropical-cyclones/202312**: Fetch status fetched; parser rows 0; spacing **not enough rows**; 9 consecutive 3-hour rows: **False**; validator pass: **False**; training-domain pass: **False**; spacing-only 6h interpolation possibility: **False**.
- **https://mausam.imd.gov.in/imd_latest/contents/pdf/cyclone_sop.pdf**: Fetch status fetched; parser rows 0; spacing **not enough rows**; 9 consecutive 3-hour rows: **False**; validator pass: **False**; training-domain pass: **False**; spacing-only 6h interpolation possibility: **False**.
- **https://mausam.imd.gov.in/newdelhi/mcdata/press_release_hi.pdf**: Fetch status not returned; parser rows 0; spacing **not enough rows**; 9 consecutive 3-hour rows: **False**; validator pass: **False**; training-domain pass: **False**; spacing-only 6h interpolation possibility: **False**.

### Agent fallback

- Ran: **True**; max runs per cyclone: 2; exact credit amount: not exposed by the run response.
- https://repository.library.noaa.gov/view/noaa/69273/noaa_69273_DS1.pdf: status ok; structured rows 0; rows accepted for validation 0; fixture `tests/fixtures/michaung_2023_agent_1.json`; run ID `8783b4c6-2c7f-4ea9-ba05-b0ffd84ac873`.
  - Spacing not enough rows; 9 consecutive 3h: False; validator pass: False; domain pass: False; spacing-only interpolation possibility: False.
- https://internal.imd.gov.in/pages/press_release_mausam.php: status ok; structured rows 0; rows accepted for validation 0; fixture `tests/fixtures/michaung_2023_agent_2.json`; run ID `b3d5a874-f59f-481f-962f-da3cc04b8558`.
  - Spacing not enough rows; 9 consecutive 3h: False; validator pass: False; domain pass: False; spacing-only interpolation possibility: False.

### Provenance and limits

Agent JSON is model-generated evidence and only diagnostics are reported; smoke test never runs the LSTM.
This script does not query usage endpoints or wallet balances. Search and Fetch are within their documented daily free allowances when quota remains; Agent execution may consume credits. Check the TinyFish dashboard for exact wallet debits.

## Dana 2024

### Search queries

- `"Dana" 2024 cyclone historical track best track latitude longitude observation time wind speed` — 10 results; status: ok; fixture: `tests/fixtures/dana_2024_search_1.json`
- `"Dana" 2024 cyclone track positions 3-hourly latitude longitude wind speed` — 10 results; status: ok; fixture: `tests/fixtures/dana_2024_search_2.json`

### Candidates and Fetch

- [Hurricane Hilary](https://www.nhc.noaa.gov/data/tcr/EP092023_Hilary.pdf) — approved for Fetch: True; fetched: True; snippet unverified: `Dana Point Light 3 (XDPT). (33.45N 117.69W). 21/0559. 35. 38. Mission Bay ... Selected wind observations and best track maximum sustained ...`
- [NCEI Geoportal - NOAA](https://www.ncei.noaa.gov/metadata/geoportal/index.html?from=0&size=10&sort=title.sort%3Aasc&esdsl=%7B%22query%22%3A%7B%22bool%22%3A%7B%22must%22%3A%5B%7B%22query_string%22%3A%7B%22analyze_wildcard%22%3Atrue%2C%22query%22%3A%22-metadata_not_published%22%7D%7D%2C%7B%22query_string%22%3A%7B%22analyze_wildcard%22%3Atrue%2C%22query%22%3A%22-src_source_name_s%3ANCCOS-library%22%7D%7D%2C%7B%22query_string%22%3A%7B%22analyze_wildcard%22%3Atrue%2C%22query%22%3A%22-src_source_name_s%3ANCCOS-InPort%22%7D%7D%2C%7B%22query_string%22%3A%7B%22analyze_wildcard%22%3Atrue%2C%22query%22%3A%22-src_source_name_s%3ANCCOS-Services%22%7D%7D%2C%7B%22query_string%22%3A%7B%22analyze_wildcard%22%3Atrue%2C%22query%22%3A%22climate%22%7D%7D%5D%7D%7D%7D) — approved for Fetch: True; fetched: True; snippet unverified: `DANA (16). DANAIDE (4). DANILEVSKY (4). DANMARK (6). DANT (6). DAPHNE (4). DARBY ... Hurricane database (HURDAT) and best track information, from the Joint ...`
- [Key factors behind super cyclone Gonu (1-7 June 2007) over ...](http://mausamjournal.imd.gov.in/index.php/MAUSAM/article/download/7095/5850) — approved for Fetch: False; fetched: False; snippet unverified: `Amphan (May 2020), Asani (May 2022), and Dana. (October 2024), provide ... provides historical records of track position, intensity, and duration over ...`
- [State of the Global Climate 2024](https://wmo.int/sites/default/files/2025-03/WMO-1368-2024_en.pdf) — approved for Fetch: True; fetched: True; snippet unverified: `by T CLIMA · 2025 · Cited by 1 — the end of 2023 and back to neutral or mild La Niña conditions at the end of 2024. ... 49 https://www.lamoncloa.gob.es/info-dana/Paginas/2024/ ...`
- [NGS Weekly - NGS News - National Geodetic Survey](https://geodesy.noaa.gov/web/news/) — approved for Fetch: True; fetched: True; snippet unverified: `May 3, 2024. New webpages for the NOAA Continuously Operating ... For more information, contact: Dana Caccamise or Dan Roman. NGS Does ...`
- [cyclone warning in india - standard operation procedure - IMD](https://mausam.imd.gov.in/imd_latest/contents/pdf/cyclone_sop.pdf) — approved for Fetch: True; fetched: True; snippet unverified: `Dana. Lulu. Lulu. Mouj. Mouj. Saudi. Arabia. Jawad Jowad. Fengal. Feinjal Ghazeer ... ✓ Information about forecast track, maximum sustained wind speed and gust, ...`
- [Weather Log - Voluntary Observing Ship Program - NOAA](https://www.vos.noaa.gov/MWL/201808/201808.pdf) — approved for Fetch: True; fetched: True; snippet unverified: `The color scale is for the wind barbs and cross-track time lines of ... DANA CRUZ. WDF4762. Anchorage. 0. 0. 0. 0. 5. 14. 10. 29. DARLING RIVER.`
- [वार्षिक प्रर्िवेदन - annual report 2025 - METNET](https://metnet.imd.gov.in/docs/imdnews/ANNUAL_REPORT2025English.pdf) — approved for Fetch: True; fetched: True; snippet unverified: `50: Comparative COU wef April 2019 and Oct. 2025 alongwith forecast track during cyclone DANA. Considering the variation in the estimate by.`
- [Dr. Diane's Flight with the NOAA Hurricane Hunters](https://www.fisheries.noaa.gov/s3/2024-07/tas-book2.pdf) — approved for Fetch: True; fetched: True; snippet unverified: `Kathy Seiler, Tom Shepherd, Patricia and Raymond Stanitski, Dana. Tomlinson ... Tropical Depression – A tropical cyclone in which the maximum sustained surface ...`
- [Takeaway Points from the State of the Climate](https://www.ncei.noaa.gov/sites/default/files/2026-01/SoC-in-2024-ExecSummary.pdf) — approved for Fetch: True; fetched: True; snippet unverified: `TRACK OF SEVERE CYCLONIC STORM REMAL (24–28 MAY). 2. TRACK OF CYCLONIC STORM ASNA (25 AUG–2 SEP). 3. TRACK OF SEVERE CYCLONIC STORM DANA (22–25 OCT). 4. TRACK ...`
- [SPARK Tool - NOAA Weather Program Office](https://wpo.noaa.gov/spark/) — approved for Fetch: True; fetched: True; snippet unverified: `Dana Tobin, Heather Reeves, Kim Klockow-McCain, James Correia, Kirstin ... track, wind speed, and precipitation forecast precision. David Letson ...`
- [NOAA/NESDIS Commercial Data Program (CDP) Industry ...](https://www.nesdis.noaa.gov/s3/2024-03/Industry-Day_11.16.2023_NESDIS-Commercial-Data-Program-%28CDP%29-Overview-2023nov20-dmg.pdf) — approved for Fetch: True; fetched: False; snippet unverified: `○ Dana Burns (SES Contract, CDP). ○ Suzanna Espinoza, Contracting ... ocean wind speed products previously developed by NOAA and investigate the ...`
- [Mitigation Efforts to Address Rapid Refresh Forecast ...](https://repository.library.noaa.gov/view/noaa/56514/noaa_56514_DS1.pdf) — approved for Fetch: True; fetched: False; snippet unverified: `by J Carley · 2023 · Cited by 16 — We also thank our respective leadership for their support throughout this process, including DaNa Carlis, Brian Gross,. Jennifer Mahoney, David N`
- [NOAA Science Seminar Series Past 2025 Seminars](https://www.star.nesdis.noaa.gov/star/NOAAScienceSeminars_2025.php) — approved for Fetch: True; fetched: False; snippet unverified: `Dana Wright, NOAA/NMFS Alaska Fisheries Science Center. Date & Time: 25 February 2025 1:00 pm - 2:00 pm ET. Location: Webinar. Description: Expand. NOAA Science ...`
- [प्रेस विज्ञप्ति](https://internal.imd.gov.in/pages/press_release_mausam.php) — approved for Fetch: True; fetched: False; snippet unverified: `PRESS RELEASE DATED: 25TH APRIL 2026 HEAT WAVE CONDITIONS LIKELY OVER NORTHWEST & CENTRAL INDIA DURING NEXT 3 DAYS AND ABATE THEREAFTER. ... DANA” WEAKENED INTO A ...`
- Fetch status: ok; cache: `tests/fixtures/dana_2024_fetch.json`; per-URL errors: [{"url": "https://wpo.noaa.gov/spark/", "error": "bot_blocked"}]

### Rows, spacing, validator, and training domain

- **https://www.nhc.noaa.gov/data/tcr/EP092023_Hilary.pdf**: Fetch status fetched; parser rows 0; spacing **not enough rows**; 9 consecutive 3-hour rows: **False**; validator pass: **False**; training-domain pass: **False**; spacing-only 6h interpolation possibility: **False**.
- **https://www.ncei.noaa.gov/metadata/geoportal/index.html?from=0&size=10&sort=title.sort%3Aasc&esdsl=%7B%22query%22%3A%7B%22bool%22%3A%7B%22must%22%3A%5B%7B%22query_string%22%3A%7B%22analyze_wildcard%22%3Atrue%2C%22query%22%3A%22-metadata_not_published%22%7D%7D%2C%7B%22query_string%22%3A%7B%22analyze_wildcard%22%3Atrue%2C%22query%22%3A%22-src_source_name_s%3ANCCOS-library%22%7D%7D%2C%7B%22query_string%22%3A%7B%22analyze_wildcard%22%3Atrue%2C%22query%22%3A%22-src_source_name_s%3ANCCOS-InPort%22%7D%7D%2C%7B%22query_string%22%3A%7B%22analyze_wildcard%22%3Atrue%2C%22query%22%3A%22-src_source_name_s%3ANCCOS-Services%22%7D%7D%2C%7B%22query_string%22%3A%7B%22analyze_wildcard%22%3Atrue%2C%22query%22%3A%22climate%22%7D%7D%5D%7D%7D%7D**: Fetch status fetched; parser rows 0; spacing **not enough rows**; 9 consecutive 3-hour rows: **False**; validator pass: **False**; training-domain pass: **False**; spacing-only 6h interpolation possibility: **False**.
- **https://wmo.int/sites/default/files/2025-03/WMO-1368-2024_en.pdf**: Fetch status fetched; parser rows 0; spacing **not enough rows**; 9 consecutive 3-hour rows: **False**; validator pass: **False**; training-domain pass: **False**; spacing-only 6h interpolation possibility: **False**.
- **https://geodesy.noaa.gov/web/news/**: Fetch status fetched; parser rows 0; spacing **not enough rows**; 9 consecutive 3-hour rows: **False**; validator pass: **False**; training-domain pass: **False**; spacing-only 6h interpolation possibility: **False**.
- **https://mausam.imd.gov.in/imd_latest/contents/pdf/cyclone_sop.pdf**: Fetch status fetched; parser rows 0; spacing **not enough rows**; 9 consecutive 3-hour rows: **False**; validator pass: **False**; training-domain pass: **False**; spacing-only 6h interpolation possibility: **False**.
- **https://www.vos.noaa.gov/MWL/201808/201808.pdf**: Fetch status fetched; parser rows 0; spacing **not enough rows**; 9 consecutive 3-hour rows: **False**; validator pass: **False**; training-domain pass: **False**; spacing-only 6h interpolation possibility: **False**.
- **https://metnet.imd.gov.in/docs/imdnews/ANNUAL_REPORT2025English.pdf**: Fetch status fetched; parser rows 0; spacing **not enough rows**; 9 consecutive 3-hour rows: **False**; validator pass: **False**; training-domain pass: **False**; spacing-only 6h interpolation possibility: **False**.
- **https://www.fisheries.noaa.gov/s3/2024-07/tas-book2.pdf**: Fetch status fetched; parser rows 0; spacing **not enough rows**; 9 consecutive 3-hour rows: **False**; validator pass: **False**; training-domain pass: **False**; spacing-only 6h interpolation possibility: **False**.
- **https://www.ncei.noaa.gov/sites/default/files/2026-01/SoC-in-2024-ExecSummary.pdf**: Fetch status fetched; parser rows 0; spacing **not enough rows**; 9 consecutive 3-hour rows: **False**; validator pass: **False**; training-domain pass: **False**; spacing-only 6h interpolation possibility: **False**.
- **https://wpo.noaa.gov/spark/**: Fetch status not returned; parser rows 0; spacing **not enough rows**; 9 consecutive 3-hour rows: **False**; validator pass: **False**; training-domain pass: **False**; spacing-only 6h interpolation possibility: **False**.

### Agent fallback

- Ran: **True**; max runs per cyclone: 2; exact credit amount: not exposed by the run response.
- https://www.nhc.noaa.gov/data/tcr/EP092023_Hilary.pdf: status ok; structured rows 0; rows accepted for validation 0; fixture `tests/fixtures/dana_2024_agent_1.json`; run ID `950f78ff-a3c6-42e7-a86d-cf7716139253`.
  - Spacing not enough rows; 9 consecutive 3h: False; validator pass: False; domain pass: False; spacing-only interpolation possibility: False.
- https://www.ncei.noaa.gov/metadata/geoportal/index.html?from=0&size=10&sort=title.sort%3Aasc&esdsl=%7B%22query%22%3A%7B%22bool%22%3A%7B%22must%22%3A%5B%7B%22query_string%22%3A%7B%22analyze_wildcard%22%3Atrue%2C%22query%22%3A%22-metadata_not_published%22%7D%7D%2C%7B%22query_string%22%3A%7B%22analyze_wildcard%22%3Atrue%2C%22query%22%3A%22-src_source_name_s%3ANCCOS-library%22%7D%7D%2C%7B%22query_string%22%3A%7B%22analyze_wildcard%22%3Atrue%2C%22query%22%3A%22-src_source_name_s%3ANCCOS-InPort%22%7D%7D%2C%7B%22query_string%22%3A%7B%22analyze_wildcard%22%3Atrue%2C%22query%22%3A%22-src_source_name_s%3ANCCOS-Services%22%7D%7D%2C%7B%22query_string%22%3A%7B%22analyze_wildcard%22%3Atrue%2C%22query%22%3A%22climate%22%7D%7D%5D%7D%7D%7D: status error; structured rows 0; rows accepted for validation 0; fixture `tests/fixtures/dana_2024_agent_2.json`; run ID `None`.`n  - Agent failure (timeout): The read operation timed out
  - Spacing not enough rows; 9 consecutive 3h: False; validator pass: False; domain pass: False; spacing-only interpolation possibility: False.

### Provenance and limits

Agent JSON is model-generated evidence and only diagnostics are reported; smoke test never runs the LSTM.
This script does not query usage endpoints or wallet balances. Search and Fetch are within their documented daily free allowances when quota remains; Agent execution may consume credits. Check the TinyFish dashboard for exact wallet debits.

## Usage

Run with `backend/.venv/Scripts/python.exe scripts/tinyfish_smoke_test.py`. Raw HTTP response bodies (with no API-key headers) and request metadata are cached under `tests/fixtures/`.

## Phase 1b — saved-fixture diagnosis and IBTrACS dataset evaluation

No IMD API or route was called. Step A used saved Phase 1 fixtures only. Search/Fetch/Agent results are preserved in `tests/fixtures/phase1b_*`; direct downloaded row records are preserved with source provenance. URLs and rows here came from real responses/files, not generated storm data.

### A. Classification of every fetched Phase 1 URL (offline fixtures)

`lat/lon-like` counts lines matching decimal coordinate pairs or degree-letter pairs. TinyFish returned extracted Markdown/text and did not provide source HTTP MIME for most pages; the source file extension and response format are distinguished below. Coordinate-like snippets are not verified observations. The existing parser returned 0 because no page supplied its required complete, explicitly labeled timestamp + latitude + longitude + supported wind-unit observation table; flattened prose/figures and aggregate tables failed that contract. Fetch errors had no body for the parser.

| URL | Domain | Content type | Page content | Lat/lon-like lines | Parser rows / reason |
|---|---|---|---|---:|---|
| https://geodesy.noaa.gov/web/news/ | geodesy.noaa.gov | HTML page (TinyFish returned Markdown/text) | news/press content (158494 chars; 0 table-like lines) | 1 | 0 — No parser-compatible complete observation rows (timestamps + coordinates + wind/unit) |
  - Coordinate-like excerpt: `NGS has posted satellite imagery from the areas affected by the Eaton, Hurst, and Palisades wildfires in California. The imagery is available through `
| https://internal.imd.gov.in/pages/press_release_mausam.php | internal.imd.gov.in | HTML page (TinyFish returned Markdown/text) | news/press content (600798 chars; 6846 table-like lines) | 2 | 0 — No parser-compatible complete observation rows (timestamps + coordinates + wind/unit) |
  - Coordinate-like excerpt: ` /  1128  /  4079  /  22 Jun 2025  /  PRESS RELEASE DATED 22.06.2025:HEAVY TO VERY HEAVY RAINFALL LIKELY OVER NORTHWEST INDIA, MADHYA PRADESH, GUJARAT AND KON`
  - Coordinate-like excerpt: ` /  3246  /  1074  /  20 Apr 2021  /  WET SPELL OVER NORTHWEST INDIA DURING 20TH TO 22ND APRIL, 2021 WITH ISOLATED HEAVY SPELLS OVER WESTERN HIMALAYAN REGION `
| https://internal.imd.gov.in/press_release/20210611_pr_1133.pdf | internal.imd.gov.in | PDF (TinyFish returned extracted Markdown/text) | report/article prose or figures (41802 chars; 0 table-like lines) | 41 | 0 — No parser-compatible complete observation rows (timestamps + coordinates + wind/unit) |
  - Coordinate-like excerpt: `xii. The track forecast errors for 24, 48 and 72 hrs lead period were 24.1, 53.1 and 81.6 km `
  - Coordinate-like excerpt: `xiii. The landfall point forecast errors for 12, 24, 48 and 60 hrs lead period were 7.8, 7.8, 7.8 and `
| https://mausam.imd.gov.in/imd_latest/contents/pdf/cyclone_sop.pdf | mausam.imd.gov.in | PDF (TinyFish returned extracted Markdown/text) | table-like content (405934 chars; 136 table-like lines) | 236 | 0 — No parser-compatible complete observation rows (timestamps + coordinates + wind/unit) |
  - Coordinate-like excerpt: `probable maximum precipitation over coast are presented in Fig 1.1 2, 1.14, 1.16.1.17 & `
  - Coordinate-like excerpt: `coasts near 18.80N/84.50E during early hours of `
| https://mausam.imd.gov.in/newdelhi/mcdata/press_release_hi.pdf | mausam.imd.gov.in | not returned | target_unreachable (0 chars; 0 table-like lines) | 0 | 0 — Fetch failure; no body |
| https://mausam.imd.gov.in/thiruvananthapuram/mcdata/cyclone_warning_sop.pdf | mausam.imd.gov.in | PDF (TinyFish returned extracted Markdown/text) | table-like content (377235 chars; 134 table-like lines) | 188 | 0 — No parser-compatible complete observation rows (timestamps + coordinates + wind/unit) |
  - Coordinate-like excerpt: `during a year including about 6.5 D, 1.8 CS, 0.9 SCS, 1.1 VSCS, 0.8 ESCS and 0.1 SuCS. `
  - Coordinate-like excerpt: `13.9, 13.6 and 13.0 kmph respectively.  The average speed is higher over the BOB than `
| https://mausamjournal.imd.gov.in/index.php/MAUSAM/article/download/126/98 | mausamjournal.imd.gov.in | HTML page (TinyFish returned Markdown/text) | table-like content (55457 chars; 14 table-like lines) | 14 | 0 — No parser-compatible complete observation rows (timestamps + coordinates + wind/unit) |
  - Coordinate-like excerpt: `1. Nisarga Pre-monsoon AS 01 Jun, 2020 4 SCS 13 N / 71.4 E `
  - Coordinate-like excerpt: `2. Amphan Pre-monsoon BoB 16 May, 2020 6 SuCS 10.4 N/ 87 E `
| https://mausamjournal.imd.gov.in/index.php/MAUSAM/article/download/167/120/503 | mausamjournal.imd.gov.in | HTML page (TinyFish returned Markdown/text) | report/article prose or figures (54417 chars; 0 table-like lines) | 2 | 0 — No parser-compatible complete observation rows (timestamps + coordinates + wind/unit) |
  - Coordinate-like excerpt: `37.5 /42.6 km at 12 hours to, 286.2/260.9 km at 120 hour `
  - Coordinate-like excerpt: `varied from 3.69/4.5 ms -1 at 12 hours to 11.6/12.7 ms -1 at `
| https://mausamjournal.imd.gov.in/index.php/MAUSAM/article/download/6259/5706/28684 | mausamjournal.imd.gov.in | HTML page (TinyFish returned Markdown/text) | table-like content (33970 chars; 1 table-like lines) | 6 | 0 — No parser-compatible complete observation rows (timestamps + coordinates + wind/unit) |
  - Coordinate-like excerpt: `Proposed Scheme 0.5 7.9 `
  - Coordinate-like excerpt: `IMD-SCIP 6.1 8.1 `
| https://metnet.imd.gov.in/docs/imdnews/ANNUAL_REPORT2025English.pdf | metnet.imd.gov.in | PDF (TinyFish returned extracted Markdown/text) | table-like content (537601 chars; 1 table-like lines) | 53 | 0 — No parser-compatible complete observation rows (timestamps + coordinates + wind/unit) |
  - Coordinate-like excerpt: `Probability of detection  0.6  0.76  `
  - Coordinate-like excerpt: `False alarm  0.1  0.1`
| https://metnet.imd.gov.in/docs/mausamdocs/17616_F.pdf | metnet.imd.gov.in | PDF (TinyFish returned extracted Markdown/text) | report/article prose or figures (112700 chars; 0 table-like lines) | 1 | 0 — No parser-compatible complete observation rows (timestamps + coordinates + wind/unit) |
  - Coordinate-like excerpt: `and 8 km (Infrared) for the INSAT 2 series. INSAT -2E `
| https://nwp.imd.gov.in/NWP_REPORT_2022.pdf | nwp.imd.gov.in | not returned | timeout (0 chars; 0 table-like lines) | 0 | 0 — Fetch failure; no body |
| https://repository.library.noaa.gov/view/noaa/61416/noaa_61416_DS1.pdf | repository.library.noaa.gov | not returned | target_unreachable (0 chars; 0 table-like lines) | 0 | 0 — Fetch failure; no body |
| https://repository.library.noaa.gov/view/noaa/69273/noaa_69273_DS1.pdf | repository.library.noaa.gov | PDF (TinyFish returned extracted Markdown/text) | table-like content (199480 chars; 63 table-like lines) | 5 | 0 — No parser-compatible complete observation rows (timestamps + coordinates + wind/unit) |
  - Coordinate-like excerpt: `the beginning of 2023, with the enhanced convective phase crossing the Pacific (Figs. 4.7 , 4.9a). `
  - Coordinate-like excerpt: `Kelvin waves (red). Contours are drawn at Â±12 W mâˆ’2 and Â±4 Ã— 106 m2 sâˆ’1 with the enhanced (suppressed) convective phase `
| https://repository.library.noaa.gov/view/noaa/71427/noaa_71427_DS1.pdf | repository.library.noaa.gov | PDF (TinyFish returned extracted Markdown/text) | report/article prose or figures (49068 chars; 0 table-like lines) | 0 | 0 — No parser-compatible complete observation rows (timestamps + coordinates + wind/unit) |
| https://rsmcnewdelhi.imd.gov.in/images/pdf/Souvenir_RSMC_17Aug.pdf | rsmcnewdelhi.imd.gov.in | PDF (TinyFish returned extracted Markdown/text) | report/article prose or figures (53658 chars; 0 table-like lines) | 3 | 0 — No parser-compatible complete observation rows (timestamps + coordinates + wind/unit) |
  - Coordinate-like excerpt: `and Arabian Sea, cover ing the area of latitude 50 N to 350 N and longitude 600 E to 100 0 `
  - Coordinate-like excerpt: `longitude 600â€“1000 E to latitude 00â€“350 N & longitude 450â€“1000 E in 2005 and to latitude `
| https://rsmcnewdelhi.imd.gov.in/images/pdf/faq.pdf | rsmcnewdelhi.imd.gov.in | PDF (TinyFish returned extracted Markdown/text) | wiki/FAQ/general prose (158674 chars; 0 table-like lines) | 13 | 0 — No parser-compatible complete observation rows (timestamps + coordinates + wind/unit) |
  - Coordinate-like excerpt: `T2.0 DD 30 55.6 4.5 28-33 50-61 `
  - Coordinate-like excerpt: `T2.5 CS 35 64.9 6.1 34-47 62-88 `
| https://rsmcnewdelhi.imd.gov.in/uploads/archive/1/1_6e7cde_34.National%20Bulletin%2020200520_0300UTC.pdf | rsmcnewdelhi.imd.gov.in | PDF (TinyFish returned extracted Markdown/text) | table-like content (13108 chars; 2 table-like lines) | 8 | 0 — No parser-compatible complete observation rows (timestamps + coordinates + wind/unit) |
  - Coordinate-like excerpt: `(Lat. 0N/ long. 0E) `
  - Coordinate-like excerpt: `20.05.20/0830 19.8/87.7 165-175 gusting to 195 Extremely Severe Cyclonic Storm `
| https://rsmcnewdelhi.imd.gov.in/uploads/archive/60/60_a53fa0_fani.pdf | rsmcnewdelhi.imd.gov.in | PDF (TinyFish returned extracted Markdown/text) | table-like content (33573 chars; 1 table-like lines) | 70 | 0 — No parser-compatible complete observation rows (timestamps + coordinates + wind/unit) |
  - Coordinate-like excerpt: `i. It developed near the equator (near 2.7 0N and 88.7 0E). Genesis of the cyclonic `
  - Coordinate-like excerpt: `0300 2.7 89.7 1.5 25 998 4 D `
| https://rsmcnewdelhi.imd.gov.in/uploads/report/28/28_8f1ffa_tcp-21-2019.pdf | rsmcnewdelhi.imd.gov.in | PDF (TinyFish returned extracted Markdown/text) | table-like content (304431 chars; 19 table-like lines) | 102 | 0 — No parser-compatible complete observation rows (timestamps + coordinates + wind/unit) |
  - Coordinate-like excerpt: `e.g. "12.2S, 168.4E" `
  - Coordinate-like excerpt: `AS OFF OMAN COAST. IT IS LESS THAN 50 KJ/CM 2 TO THE NORTH OF 17.00 N AND WEST OF 60.00E.  `
| https://severeweather.wmo.int/TCFW/NewDelhi_Training2022/3_CPS-RSMC-2022-SDKOTAL.pdf | severeweather.wmo.int | PDF (TinyFish returned extracted Markdown/text) | report/article prose or figures (27780 chars; 0 table-like lines) | 32 | 0 — No parser-compatible complete observation rows (timestamps + coordinates + wind/unit) |
  - Coordinate-like excerpt: `T.No. ïƒ  1.0 1.5 2.0 2.5 3.0`
  - Coordinate-like excerpt: `Developing 11.1 12.3 13.3 13.5 13.6`
| https://severeweather.wmo.int/TCFW/NewDelhi_Training2022/3_DRPattanaik_ERF_06April2022.pdf | severeweather.wmo.int | PDF (TinyFish returned extracted Markdown/text) | report/article prose or figures (15845 chars; 0 table-like lines) | 17 | 0 — No parser-compatible complete observation rows (timestamps + coordinates + wind/unit) |
  - Coordinate-like excerpt: `1 5.80 -2.28 0.01 0.05 1.58 -0.92 2.51`
  - Coordinate-like excerpt: `2 -1.12 1.22 0.04 -0.18 1.68 -1.21 2.89`
| https://wmo.int/sites/default/files/2025-03/WMO-1368-2024_en.pdf | wmo.int | PDF (TinyFish returned extracted Markdown/text) | report/article prose or figures (94512 chars; 0 table-like lines) | 8 | 0 — No parser-compatible complete observation rows (timestamps + coordinates + wind/unit) |
  - Coordinate-like excerpt: `â€“5.0      â€“3.0      â€“2.0      â€“1.0      â€“0.5      â€“0.25       0         0.25      0.5         1.0        2.0        3.0        5.0   Â°C`
  - Coordinate-like excerpt: `HadCRUT5 1.52 0.83 0.63 1.17`
| https://wpo.noaa.gov/spark/ | wpo.noaa.gov | not returned | bot_blocked (0 chars; 0 table-like lines) | 0 | 0 — Fetch failure; no body |
| https://www.aoml.noaa.gov/hrd-faq/ | www.aoml.noaa.gov | HTML page (TinyFish returned Markdown/text) | wiki/FAQ/general prose (256253 chars; 759 table-like lines) | 1 | 0 — No parser-compatible complete observation rows (timestamps + coordinates + wind/unit) |
  - Coordinate-like excerpt: `Internally a number of parallel SLOSH runs with same intensity, forward speed, storm trajectory, and initial tide level are performed for the basin. T`
| https://www.fisheries.noaa.gov/s3/2024-07/tas-book2.pdf | www.fisheries.noaa.gov | PDF (TinyFish returned extracted Markdown/text) | report/article prose or figures (61247 chars; 0 table-like lines) | 0 | 0 — No parser-compatible complete observation rows (timestamps + coordinates + wind/unit) |
| https://www.ncei.noaa.gov/access/monitoring/monthly-report/tropical-cyclones/202312 | www.ncei.noaa.gov | HTML page (TinyFish returned Markdown/text) | report/article prose or figures (286 chars; 0 table-like lines) | 0 | 0 — No parser-compatible complete observation rows (timestamps + coordinates + wind/unit) |
| https://www.ncei.noaa.gov/metadata/geoportal/index.html?from=0&size=10&sort=title.sort%3Aasc&esdsl=%7B%22query%22%3A%7B%22bool%22%3A%7B%22must%22%3A%5B%7B%22query_string%22%3A%7B%22analyze_wildcard%22%3Atrue%2C%22query%22%3A%22-metadata_not_published%22%7D%7D%2C%7B%22query_string%22%3A%7B%22analyze_wildcard%22%3Atrue%2C%22query%22%3A%22-src_source_name_s%3ANCCOS-library%22%7D%7D%2C%7B%22query_string%22%3A%7B%22analyze_wildcard%22%3Atrue%2C%22query%22%3A%22-src_source_name_s%3ANCCOS-InPort%22%7D%7D%2C%7B%22query_string%22%3A%7B%22analyze_wildcard%22%3Atrue%2C%22query%22%3A%22-src_source_name_s%3ANCCOS-Services%22%7D%7D%2C%7B%22query_string%22%3A%7B%22analyze_wildcard%22%3Atrue%2C%22query%22%3A%22climate%22%7D%7D%5D%7D%7D%7D | www.ncei.noaa.gov | HTML page (TinyFish returned Markdown/text) | report/article prose or figures (5019 chars; 0 table-like lines) | 0 | 0 — No parser-compatible complete observation rows (timestamps + coordinates + wind/unit) |
| https://www.ncei.noaa.gov/sites/default/files/2026-01/SoC-in-2024-ExecSummary.pdf | www.ncei.noaa.gov | PDF (TinyFish returned extracted Markdown/text) | report/article prose or figures (43360 chars; 0 table-like lines) | 1 | 0 — No parser-compatible complete observation rows (timestamps + coordinates + wind/unit) |
  - Coordinate-like excerpt: `âˆ’4 âˆ’2 âˆ’1 âˆ’0.5 4 2 1 0.5 0.1âˆ’0.1`
| https://www.nhc.noaa.gov/data/tcr/EP092023_Hilary.pdf | www.nhc.noaa.gov | PDF (TinyFish returned extracted Markdown/text) | table-like content (57555 chars; 43 table-like lines) | 111 | 0 — No parser-compatible complete observation rows (timestamps + coordinates + wind/unit) |
  - Coordinate-like excerpt: `16 / 0600 11.9 100.8 1003 30 tropical depression `
  - Coordinate-like excerpt: `16 / 1200 12.6 102.3 1002 35 tropical storm `
| https://www.vos.noaa.gov/MWL/201808/201808.pdf | www.vos.noaa.gov | PDF (TinyFish returned extracted Markdown/text) | table-like content (196662 chars; 129 table-like lines) | 129 | 0 — No parser-compatible complete observation rows (timestamps + coordinates + wind/unit) |
  - Coordinate-like excerpt: `1200 UTC 01 Jan W Atlc 30N W of 77W 35 kt 18 hr Front `
  - Coordinate-like excerpt: `1200 UTC 02 Jan W Atlc N of 27N W of 77W 55 kt 72 hr (6 hr) Low/Front `

### B. NOAA NCEI IBTrACS v04r01

Official [column documentation](https://www.ncei.noaa.gov/sites/default/files/2025-09/IBTrACS_v04r01_column_documentation.pdf) names `SID`, `SEASON`, `BASIN`, `SUBBASIN`, `NAME`, `ISO_TIME`, `LAT`, `LON`, `NEWDELHI_LAT`, `NEWDELHI_LON`, `NEWDELHI_WIND`, and `IFLAG`. It specifies `ISO_TIME` in UTC, `LAT` in degrees north, `LON` in degrees east; `NEWDELHI_WIND` is in knots with 3-minute averaging. The 15-character IFLAG assigns New Delhi the 6th agency slot: `O` means the original agency report; `P`/`I`/`V` indicate interpolation or filling. IBTrACS notes most points are 6-hourly, while New Delhi supplies some 3-hour points. See also the [NCEI dataset page](https://www.ncei.noaa.gov/products/international-best-track-archive) and [v04r01 CSV directory](https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-stewardship-ibtracs/v04r01/access/csv/).

- TinyFish Search: 1 query, `NOAA NCEI IBTrACS v04r01 CSV North Indian basin best track dataset`; status `ok`, 6 results. The first result is the official NCEI IBTrACS product page. Fixture: `tests/fixtures/phase1b_ibtracs_search.json`.
- TinyFish Fetch directory: `ok`; returned the CSV index and listed NI, since1980, and last3years files. Fixture: `tests/fixtures/phase1b_ibtracs_fetch_directory.json`.
- TinyFish Fetch NI CSV: `ok`; 27,886,424 text characters; CSV-looking: True; truncation marker: False; errors: `[]`. This is usable CSV text (TinyFish Fetch returned the entire 27,886,424-character content observed in this run). Fixture: `tests/fixtures/phase1b_ibtracs_fetch_ni.csv.json`.
- TinyFish Agent: 1 run (cap 2); URL-only response supplied NI and since1980 CSV URLs, but no column-doc URL. Agent credit debit amount is not exposed in API response. Fixture: `tests/fixtures/phase1b_ibtracs_agent_1.json`.
- Direct NOAA bounded download: `cached`, 27,886,424 bytes, content type `text/csv (observed in initial direct download response)`, 40 MiB max guard; `tests\fixtures\ibtracs.NI.list.v04r01.csv`.
- Initial download attempt stopped at a local 25 MiB safety limit because the official NI file's directory size was 27,886,424 bytes; after increasing the explicit guard to 40 MiB, the direct download completed. This was a local size guard, not a NOAA/network error.
- Directory sizes show the NI basin subset (27,886,424 bytes) is the smallest sufficient offered file for all four requested seasons; the `since1980` global subset is 145,059,983 bytes and `last3years` is 11,540,942 bytes but does not cover all target seasons.
- CSV's second row was inspected as units, then skipped by pandas while preserving row 1 as headers. Unit-row values: `SEASON=Year`, `LAT=degrees_north`, `LON=degrees_east`, `NEWDELHI_LAT=degrees_north`, `NEWDELHI_LON=degrees_east`, `NEWDELHI_WIND=kts`; the other listed fields have blank unit cells.
- Storm filter: exact `NAME + SEASON + BASIN=NI`. Native RSMC New Delhi wind means `NEWDELHI_WIND` nonblank and IFLAG character 6=`O`. A row is marked `interpolated=true` if New Delhi wind or position is blank, or that IFLAG is not `O`; no wind or position values were imputed/substituted. The model input used only rows with original New Delhi wind and position. Domain is checked on the selected position against lat −40..40/lon 30..130.

| Storm | Rows | Spacing | Native New Delhi wind | Blank/flagged rows | 9 consecutive 3h native fixes | Validator / feature builder | Domain |
|---|---:|---|---:|---:|---|---|---|
| Amphan 2020 | 51 | 3h | 44 | 7 | True | passed / passed (existing 1x8x11 contract) | all rows pass: True (0 outside) |
  - Provenance records: `tests\fixtures\phase1b_amphan_2020_ibtracs_rows.json`; every row includes acquisition `tinyfish_agent_discovery + direct_http_download` and source URL.
| Fani 2019 | 71 | 3h | 62 | 9 | True | passed / passed (existing 1x8x11 contract) | all rows pass: True (0 outside) |
  - Provenance records: `tests\fixtures\phase1b_fani_2019_ibtracs_rows.json`; every row includes acquisition `tinyfish_agent_discovery + direct_http_download` and source URL.
| Michaung 2023 | 49 | 3h | 34 | 15 | True | passed / passed (existing 1x8x11 contract) | all rows pass: True (0 outside) |
  - Provenance records: `tests\fixtures\phase1b_michaung_2023_ibtracs_rows.json`; every row includes acquisition `tinyfish_agent_discovery + direct_http_download` and source URL.
| Dana 2024 | 39 | 3h | 27 | 12 | True | passed / passed (existing 1x8x11 contract) | all rows pass: True (0 outside) |
  - Provenance records: `tests\fixtures\phase1b_dana_2024_ibtracs_rows.json`; every row includes acquisition `tinyfish_agent_discovery + direct_http_download` and source URL.

### C. Historical replay

The existing 24h and 48h LSTMs and scalers were loaded without modifying model artifacts. Input windows used the exact existing 1×8×11 feature builder and 9 native 3-hourly New Delhi fixes. Cutoff is the final input timestamp; actual comparison coordinates are exact +24h/+48h IBTrACS `LAT/LON` composite rows. Constant-velocity baseline extrapolates the last observed 3-hour displacement. Errors are haversine kilometers.

#### Exact model inputs (9 timestamps per storm)

- **Amphan 2020** — cutoff `2020-05-19T12:00:00Z`: `2020-05-18T12:00:00Z, 2020-05-18T15:00:00Z, 2020-05-18T18:00:00Z, 2020-05-18T21:00:00Z, 2020-05-19T00:00:00Z, 2020-05-19T03:00:00Z, 2020-05-19T06:00:00Z, 2020-05-19T09:00:00Z, 2020-05-19T12:00:00Z`
- **Fani 2019** — cutoff `2019-05-02T12:00:00Z`: `2019-05-01T12:00:00Z, 2019-05-01T15:00:00Z, 2019-05-01T18:00:00Z, 2019-05-01T21:00:00Z, 2019-05-02T00:00:00Z, 2019-05-02T03:00:00Z, 2019-05-02T06:00:00Z, 2019-05-02T09:00:00Z, 2019-05-02T12:00:00Z`
- **Michaung 2023** — cutoff `2023-12-04T06:00:00Z`: `2023-12-03T06:00:00Z, 2023-12-03T09:00:00Z, 2023-12-03T12:00:00Z, 2023-12-03T15:00:00Z, 2023-12-03T18:00:00Z, 2023-12-03T21:00:00Z, 2023-12-04T00:00:00Z, 2023-12-04T03:00:00Z, 2023-12-04T06:00:00Z`
- **Dana 2024** — cutoff `2024-10-24T00:00:00Z`: `2024-10-23T00:00:00Z, 2024-10-23T03:00:00Z, 2024-10-23T06:00:00Z, 2024-10-23T09:00:00Z, 2024-10-23T12:00:00Z, 2024-10-23T15:00:00Z, 2024-10-23T18:00:00Z, 2024-10-23T21:00:00Z, 2024-10-24T00:00:00Z`

| Storm | Cutoff UTC | Verification time | LSTM error km | Constant-velocity error km |
|---|---|---|---:|---:|
| Amphan 2020 | 2020-05-19T12:00:00Z | 2020-05-20T12:00:00Z (24h) | 163.1 | 178.0 |
| Amphan 2020 | 2020-05-19T12:00:00Z | 2020-05-21T12:00:00Z (48h) | 158.3 | 204.6 |
| Fani 2019 | 2019-05-02T12:00:00Z | 2019-05-03T12:00:00Z (24h) | 122.9 | 185.1 |
| Fani 2019 | 2019-05-02T12:00:00Z | 2019-05-04T12:00:00Z (48h) | 419.8 | 613.9 |
| Michaung 2023 | 2023-12-04T06:00:00Z | 2023-12-05T06:00:00Z (24h) | 107.0 | 120.8 |
| Michaung 2023 | 2023-12-04T06:00:00Z | 2023-12-06T06:00:00Z (48h) | 339.2 | 411.6 |
| Dana 2024 | 2024-10-24T00:00:00Z | 2024-10-25T00:00:00Z (24h) | 52.2 | 53.1 |
| Dana 2024 | 2024-10-24T00:00:00Z | 2024-10-26T00:00:00Z (48h) | 9.3 | 245.5 |

The [imdtrack package documentation](https://imdtrack.readthedocs.io/en/stable/examples/quickstart.html) describes the IMD best-track record as spanning 1982–2026 (one 3-hourly fix per row). Thus Fani 2019, Amphan 2020, Michaung 2023, and Dana 2024 fall within the source year span; exact training/test storm IDs and leakage cannot be established because the training data/split are absent. Replay is a diagnostic, not an independent accuracy evaluation.

The TensorFlow forward passes succeeded. The runtime emitted scikit-learn `StandardScaler` version warning: the serialized scaler was created with 1.6.1 and this environment runs 1.7.2; numerical predictions were produced, but that version mismatch is a reproducibility caveat.

### Tested / Not tested

**Tested:** offline diagnosis of all 31 saved Phase 1 fetched URLs; one live Search; TinyFish Fetch of the official directory and NI CSV; one URL-only Agent discovery; direct NOAA NI CSV download; pandas parsing and second-row units handling; all four name/season/basin filters; validation/domain/feature builder; existing 24h and 48h model forward passes; historical replay against actual +24h/+48h rows.

**Not tested:** IMD cross-check (explicitly prohibited here); live/ongoing cyclone freshness behavior; frontend rendering or real user workflow; exact TinyFish credits charged; independent model generalization or training leakage (training data and split are absent). No TinyFish-extracted track rows were used.

**Agent credits:** one Agent run; API response did not expose a numeric debit, so the amount is unknown.

**Recommendation:** viable for historical replay and obtaining model-contract-compatible archived fixes. Use TinyFish for discovery and source selection, and direct bounded HTTP for the large official CSV payload. This does not validate an operational live-cyclone path; that still needs a separate, freshness-checked live source. The four replay errors are not an accuracy evaluation because the storms fall within the documented 1982–2026 imdtrack source span.

Step A used no network. Step B used one TinyFish Search, one directory Fetch, one CSV Fetch, and one Agent run. No IMD calls were made.
