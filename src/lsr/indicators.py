"""Turn the raw downloads into an indicator set.

Two frequencies:

* **daily**: IMF PortWatch counts summed over a trailing 7-day window
  (removes the weekday cycle; one new value per day).
* **monthly**: MPA, SingStat and New York Fed series, plus one derived ratio
  (MPA TEU per PortWatch container port call).

Each indicator carries metadata: the direction that counts as stress
("drop" or "rise"), the family it belongs to (external route, regional port,
Singapore), the source, and the publication lag in days used to date an
alarm by when it could have been known.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"


@dataclass(frozen=True)
class Indicator:
    key: str
    label: str
    freq: str          # "D" (7-day rolling sum) or "M"
    direction: str     # "drop" or "rise"
    family: str        # "route", "regional", "singapore", "global"
    source: str
    lag_days: int      # publication lag added to the alarm date
    transform: str = "level"   # daily: level; monthly: "yoy" or "level"
    # sg_teu_per_call was first run on year-on-year change; on the development
    # period that version never fired during the 2020-22 congestion, so it was
    # switched to the level detector. Both versions are reported (see README).


PW_LAG = 7  # PortWatch updates weekly; a value is usually public within a week.

INDICATORS: dict[str, Indicator] = {i.key: i for i in [
    Indicator("cp_suez", "Suez Canal transits", "D", "drop", "route", "IMF PortWatch", PW_LAG),
    Indicator("cp_bab", "Bab el-Mandeb transits", "D", "drop", "route", "IMF PortWatch", PW_LAG),
    Indicator("cp_cape", "Cape of Good Hope transits", "D", "rise", "route", "IMF PortWatch", PW_LAG),
    Indicator("cp_panama", "Panama Canal transits", "D", "drop", "route", "IMF PortWatch", PW_LAG),
    Indicator("cp_hormuz", "Strait of Hormuz transits", "D", "drop", "route", "IMF PortWatch", PW_LAG),
    Indicator("cp_malacca", "Malacca Strait transits", "D", "drop", "route", "IMF PortWatch", PW_LAG),
    Indicator("cp_taiwan", "Taiwan Strait transits", "D", "drop", "route", "IMF PortWatch", PW_LAG),
    Indicator("sg_calls_container", "Singapore container-ship port calls", "D", "drop", "singapore",
              "IMF PortWatch", PW_LAG),
    Indicator("sg_box_volume", "Singapore container trade volume (estimate)", "D", "drop", "singapore",
              "IMF PortWatch", PW_LAG),
    Indicator("klang_calls_container", "Port Klang container-ship port calls", "D", "drop", "regional",
              "IMF PortWatch", PW_LAG),
    Indicator("tpp_calls_container", "Tanjung Pelepas container-ship port calls", "D", "drop", "regional",
              "IMF PortWatch", PW_LAG),
    Indicator("mpa_teu", "Singapore container throughput (TEU)", "M", "drop", "singapore",
              "MPA via data.gov.sg", 15, "yoy"),
    Indicator("mpa_vessel_arrivals", "Singapore vessel arrivals", "M", "drop", "singapore",
              "MPA via data.gov.sg", 15, "yoy"),
    Indicator("mpa_cargo", "Singapore cargo throughput (tonnes)", "M", "drop", "singapore",
              "MPA via data.gov.sg", 15, "yoy"),
    Indicator("changi_air_cargo", "Changi air cargo (tonnes)", "M", "drop", "singapore",
              "SingStat M650031 (CAAS)", 30, "yoy"),
    Indicator("sg_teu_per_call", "Singapore TEU per container-ship call", "M", "rise", "singapore",
              "MPA TEU / PortWatch container calls", 15, "level"),
    Indicator("gscpi", "NY Fed Global Supply Chain Pressure Index", "M", "rise", "global",
              "Federal Reserve Bank of New York", 5, "level"),
]}

CP_COLS = {
    "Suez Canal": "cp_suez", "Bab el-Mandeb Strait": "cp_bab", "Cape of Good Hope": "cp_cape",
    "Panama Canal": "cp_panama", "Strait of Hormuz": "cp_hormuz", "Malacca Strait": "cp_malacca",
    "Taiwan Strait": "cp_taiwan",
}


def _complete_daily(df: pd.DataFrame, col: str) -> pd.Series:
    s = df.set_index("date")[col].astype(float)
    full = pd.date_range(s.index.min(), s.index.max(), freq="D")
    return s.reindex(full)


def rolling7(s: pd.Series) -> pd.Series:
    """Trailing 7-day sum; NaN unless all 7 days are present."""
    return s.rolling(7, min_periods=7).sum()


def load_daily(raw: Path = RAW) -> pd.DataFrame:
    cp = pd.read_csv(raw / "portwatch_chokepoints_daily.csv", parse_dates=["date"])
    pt = pd.read_csv(raw / "portwatch_ports_daily.csv", parse_dates=["date"])
    out = {}
    for name, key in CP_COLS.items():
        out[key] = rolling7(_complete_daily(cp[cp.portname == name], "n_total"))
    sg = pt[pt.portname == "Singapore"].copy()
    sg["box"] = sg["import_container"] + sg["export_container"]
    out["sg_calls_container"] = rolling7(_complete_daily(sg, "portcalls_container"))
    out["sg_box_volume"] = rolling7(_complete_daily(sg, "box"))
    out["klang_calls_container"] = rolling7(_complete_daily(pt[pt.portname == "Port Klang"], "portcalls_container"))
    out["tpp_calls_container"] = rolling7(_complete_daily(pt[pt.portname == "Tanjung Pelepas"],
                                                          "portcalls_container"))
    return pd.DataFrame(out)


def load_portwatch_monthly_calls(raw: Path = RAW) -> pd.Series:
    pt = pd.read_csv(raw / "portwatch_ports_daily.csv", parse_dates=["date"])
    sg = pt[pt.portname == "Singapore"].set_index("date")["portcalls_container"]
    days = sg.resample("MS").count()
    m = sg.resample("MS").sum().astype(float)
    full_days = m.index.days_in_month
    return m.where(days.values == full_days)   # drop incomplete months


def load_monthly(raw: Path = RAW) -> pd.DataFrame:
    def mpa(name: str, col: str) -> pd.Series:
        d = pd.read_csv(raw / f"{name}.csv")
        return pd.Series(d[col].astype(float).values, index=pd.to_datetime(d["month"]), name=col)

    teu = mpa("mpa_container_throughput", "container_throughput")      # thousand TEU
    arr = mpa("mpa_vessel_arrivals", "number_of_vessels")
    cargo = mpa("mpa_cargo_throughput", "cargo_throughput")
    air = pd.read_csv(raw / "singstat_M650031_air_cargo.csv")
    air = air[air.series == "Total Air Cargo Tonnage"]
    air = pd.Series(air["value"].astype(float).values,
                    index=pd.to_datetime(air["month"], format="%Y %b")).sort_index()
    g = pd.read_excel(raw / "gscpi_data.xlsx", sheet_name="GSCPI Monthly Data").iloc[:, :2]
    g.columns = ["date", "gscpi"]
    g = g.dropna()
    g = g[pd.to_numeric(g["gscpi"], errors="coerce").notna()]
    g = pd.Series(g["gscpi"].astype(float).values,
                  index=pd.to_datetime(g["date"], format="%d-%b-%Y").dt.to_period("M").dt.to_timestamp())
    calls = load_portwatch_monthly_calls(raw)
    df = pd.DataFrame({
        "mpa_teu": teu, "mpa_vessel_arrivals": arr, "mpa_cargo": cargo,
        "changi_air_cargo": air, "gscpi": g,
    })
    df["sg_teu_per_call"] = df["mpa_teu"] * 1000.0 / calls.reindex(df.index)
    return df.sort_index()


def log_yoy(s: pd.Series) -> pd.Series:
    """log(x_t / x_{t-12}) on a monthly series indexed by month start."""
    lagged = s.shift(12, freq="MS").reindex(s.index)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.log(s / lagged)
