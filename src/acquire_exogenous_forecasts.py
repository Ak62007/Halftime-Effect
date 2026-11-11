"""Acquire archived ex-ante weather and embedded-generation forecast vintages."""
from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd
import requests


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "configs/forecast_data_contract.json").read_text())
RAW = ROOT / "data/raw/forecast_exogenous"
WEATHER_OUT = RAW / "weather/jma_temperature_previous_runs.json"
EMBEDDED_OUT = RAW / "neso_embedded"
OPEN_METEO = "https://previous-runs-api.open-meteo.com/v1/forecast"
CKAN = "https://api.neso.energy/api/3/action"
PAGE_SIZE = 16_000


def get_json(url: str, params: dict | None = None, timeout: int = 120) -> dict | list:
    last_error: requests.RequestException | None = None
    for attempt in range(5):
        try:
            response = requests.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as error:
            last_error = error
            if attempt == 4:
                break
            time.sleep(2**attempt)
    raise RuntimeError(f"Request failed after retries: {url}") from last_error


def acquire_weather() -> dict:
    weather = CONFIG["weather"]
    weather_start = (
        pd.Timestamp(CONFIG["source_start_date"]) - pd.Timedelta(days=1)
    ).strftime("%Y-%m-%d")
    weather_end = (
        pd.Timestamp(CONFIG["final_test_end_inclusive"]) + pd.Timedelta(days=1)
    ).strftime("%Y-%m-%d")
    params = {
        "latitude": ",".join(str(x["latitude"]) for x in weather["locations"]),
        "longitude": ",".join(str(x["longitude"]) for x in weather["locations"]),
        # Pad both boundaries because London settlement days do not always align
        # with UTC dates and half-hour interpolation needs the following hour.
        "start_date": weather_start,
        "end_date": weather_end,
        "hourly": (
            "temperature_2m_previous_day1,temperature_2m_previous_day2"
        ),
        "models": weather["model"],
        "timezone": "UTC",
    }
    payload = get_json(OPEN_METEO, params=params)
    if not isinstance(payload, list) or len(payload) != len(weather["locations"]):
        raise ValueError("Unexpected multi-location Open-Meteo response")
    expected_hours = len(
        pd.date_range(
            weather_start,
            pd.Timestamp(weather_end) + pd.Timedelta(hours=23),
            freq="h",
        )
    )
    for location, response in zip(weather["locations"], payload):
        response["requested_location_name"] = location["name"]
        hourly = response["hourly"]
        if len(hourly["time"]) != expected_hours:
            raise ValueError(f"Unexpected weather length for {location['name']}")
        for variable in [
            "temperature_2m_previous_day1",
            "temperature_2m_previous_day2",
        ]:
            if len(hourly[variable]) != expected_hours or any(
                value is None for value in hourly[variable]
            ):
                raise ValueError(f"Incomplete {variable} for {location['name']}")
    WEATHER_OUT.parent.mkdir(parents=True, exist_ok=True)
    WEATHER_OUT.write_text(json.dumps(payload) + "\n")
    return {
        "locations": len(payload),
        "hours_per_location": expected_hours,
        "missing_values": 0,
    }


def archive_resources() -> tuple[dict, dict[int, str]]:
    package = get_json(
        f"{CKAN}/datapackage_show",
        params={"id": CONFIG["neso_embedded_archive_package"]},
    )
    if not package.get("success"):
        raise ValueError(package.get("error", "NESO package request failed"))
    resources = {}
    for resource in package["result"]["resources"]:
        title = resource.get("title", "")
        for year in range(2021, 2027):
            if title.endswith(str(year)) and resource.get("datastore_active"):
                resources[year] = resource["id"]
    expected = set(range(2021, 2027))
    if set(resources) != expected:
        raise ValueError(f"Missing NESO archive resources: {expected - set(resources)}")
    return package, resources


def acquire_embedded_year(year: int, resource_id: str) -> dict:
    output_path = EMBEDDED_OUT / f"embedded_cutoff_candidates_{year}.csv"
    if output_path.exists():
        existing = pd.read_csv(output_path)
        required = {
            "SETTLEMENT_DATE",
            "SETTLEMENT_PERIOD",
            "EMBEDDED_WIND_FORECAST",
            "EMBEDDED_SOLAR_FORECAST",
            "Forecast_Datetime",
        }
        if not existing.empty and required.issubset(existing.columns):
            return {
                "resource_id": resource_id,
                "candidate_rows": int(len(existing)),
                "first_issue": existing["Forecast_Datetime"].min(),
                "last_issue": existing["Forecast_Datetime"].max(),
                "resumed_from_existing_file": True,
            }
    start_hour, end_hour = CONFIG["embedded_issue_query_utc_hours"]
    relation = (
        f'"Forecast_Datetime" >= "SETTLEMENT_DATE" - INTERVAL \'1 day\' '
        f"+ INTERVAL '{start_hour} hours' AND "
        f'"Forecast_Datetime" < "SETTLEMENT_DATE" - INTERVAL \'1 day\' '
        f"+ INTERVAL '{end_hour} hours'"
    )
    columns = ", ".join(
        f'"{column}"'
        for column in [
            "SETTLEMENT_DATE",
            "SETTLEMENT_PERIOD",
            "EMBEDDED_WIND_FORECAST",
            "EMBEDDED_WIND_CAPACITY",
            "EMBEDDED_SOLAR_FORECAST",
            "EMBEDDED_SOLAR_CAPACITY",
            "Forecast_Datetime",
        ]
    )
    records: list[dict] = []
    offset = 0
    while True:
        sql = (
            f'SELECT {columns} FROM "{resource_id}" WHERE {relation} '
            f'ORDER BY "SETTLEMENT_DATE", "SETTLEMENT_PERIOD", '
            f'"Forecast_Datetime" LIMIT {PAGE_SIZE} OFFSET {offset}'
        )
        payload = get_json(
            f"{CKAN}/datastore_search_sql", params={"sql": sql}, timeout=180
        )
        if not payload.get("success"):
            raise ValueError(payload.get("error", f"NESO query failed for {year}"))
        page = payload["result"]["records"]
        records.extend(page)
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    frame = pd.DataFrame.from_records(records)
    if frame.empty:
        raise ValueError(f"No embedded forecast rows for {year}")
    EMBEDDED_OUT.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output_path, index=False)
    return {
        "resource_id": resource_id,
        "candidate_rows": int(len(frame)),
        "first_issue": frame["Forecast_Datetime"].min(),
        "last_issue": frame["Forecast_Datetime"].max(),
    }


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    weather_audit = acquire_weather()
    package, resources = archive_resources()
    (RAW / "neso_embedded_package.json").write_text(json.dumps(package) + "\n")
    embedded_audit = {
        str(year): acquire_embedded_year(year, resource_id)
        for year, resource_id in sorted(resources.items())
    }
    audit = {
        "weather": weather_audit,
        "embedded": embedded_audit,
        "final_test_data_opened": False,
    }
    (RAW / "acquisition_audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
