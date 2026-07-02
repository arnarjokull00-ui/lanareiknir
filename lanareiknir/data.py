"""
lanareiknir.data — CPI and rate data
=====================================

Live sources
------------
* CPI: Hagstofa Íslands PX-Web API (vísitala neysluverðs, monthly).
* Rates: Seðlabanki Íslands gagnatorg (policy rate; bank mortgage rates).

`fetch_cpi()` / `fetch_policy_rate()` hit the live APIs and cache to
data/*.csv. If the network is unavailable, the module falls back to the
approximate annual series below (reconstructed from published annual
averages) — good enough for scenario work, replace with the live pull
before publishing backtest numbers.
"""

from __future__ import annotations

import json
import os
import urllib.request

import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

# Approximate annual CPI inflation, Iceland (year -> avg %). Fallback only.
CPI_ANNUAL_FALLBACK = {
    2015: 0.016, 2016: 0.017, 2017: 0.018, 2018: 0.027, 2019: 0.030,
    2020: 0.028, 2021: 0.044, 2022: 0.083, 2023: 0.088, 2024: 0.059,
    2025: 0.040,
}

# Approximate Seðlabanki policy-rate path (year -> avg %, key change-points).
POLICY_RATE_FALLBACK = {
    2015: 0.0575, 2016: 0.0575, 2017: 0.0475, 2018: 0.0435, 2019: 0.0350,
    2020: 0.0100, 2021: 0.0150, 2022: 0.0500, 2023: 0.0875, 2024: 0.0900,
    2025: 0.0775,
}

HAGSTOFA_CPI_URL = (
    "https://px.hagstofa.is:443/pxis/api/v1/is/Efnahagur/visitolur/"
    "1_vnv/1_vnv/VIS01000.px"
)
CPI_QUERY = {
    "query": [{"code": "Vísitala", "selection": {"filter": "item", "values": ["CPI"]}}],
    "response": {"format": "json"},
}


def fetch_cpi(cache: str = "cpi_monthly.csv") -> pd.DataFrame:
    """Monthly CPI index from Hagstofa PX-Web; cached to data/."""
    path = os.path.join(DATA_DIR, cache)
    if os.path.exists(path):
        return pd.read_csv(path, parse_dates=["month"])
    req = urllib.request.Request(
        HAGSTOFA_CPI_URL,
        data=json.dumps(CPI_QUERY).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = json.load(resp)
    rows = [
        (item["key"][-1], float(item["values"][0]))
        for item in raw["data"] if item["values"][0] not in (".", "..")
    ]
    df = pd.DataFrame(rows, columns=["month", "cpi"])
    df["month"] = pd.to_datetime(df["month"].str.replace("M", "-"), format="%Y-%m")
    os.makedirs(DATA_DIR, exist_ok=True)
    df.to_csv(path, index=False)
    return df


def annual_inflation_series(start_year: int = 2015, end_year: int = 2025) -> list[float]:
    """Annual inflation series, live if possible, fallback otherwise."""
    try:
        df = fetch_cpi()
        df["year"] = df.month.dt.year
        annual = df.groupby("year").cpi.mean()
        return [float(annual[y] / annual[y - 1] - 1)
                for y in range(start_year, end_year + 1) if y - 1 in annual.index]
    except Exception:
        return [CPI_ANNUAL_FALLBACK[y]
                for y in range(start_year, end_year + 1) if y in CPI_ANNUAL_FALLBACK]


def variable_rate_series(spread: float = 0.025,
                         start_year: int = 2015, end_year: int = 2025) -> list[float]:
    """Approximate breytilegir óverðtryggðir vextir: policy rate + spread."""
    return [POLICY_RATE_FALLBACK[y] + spread
            for y in range(start_year, end_year + 1) if y in POLICY_RATE_FALLBACK]
