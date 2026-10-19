# Finalized core dataset

Start with `processed/demand_development.csv`: NESO half-hour `Demand_Outturn` for development through 31 May 2024. The full table is `processed/demand_halfhour.csv`, covering 1 January 2023–31 July 2024. `timestamp_utc` is interval start; demand is MW.

Read [the final data contract](../docs/finalized_dataset.md) before analysis. It defines all fields, held-out periods, weather leakage restrictions, primary-source links, and limitations. Elexon five-minute notebook results are a separate feasibility exercise.

Rebuild from existing snapshots:

```bash
.venv/bin/python src/finalize_data.py
```

Use `--download` for missing raw inputs. Raw and processed files are Git-ignored; URLs and settings are in `configs/data_contract.json`. The build saves input and output hashes in `processed/data_manifest.json`. Keep that manifest with your analysis outputs. Provider snapshots may change, so do not refresh casually.

NESO data: [NESO Open Data Licence](https://www.neso.energy/data-portal). Weather: Open-Meteo / Copernicus ERA5; see [attribution and licence](https://open-meteo.com/en/docs/historical-weather-api). Holidays: GOV.UK. Fixtures: official England Football links in the fixture CSVs; those small metadata inventories are versioned separately from downloaded data.
