"""Download the raw public series into data/raw/.

Run once with network access: ``python -m lsr.fetch``. Everything downstream
reads only the files written here, so tests and CI run offline.

Sources
-------
* IMF PortWatch (daily chokepoint transits; daily port calls and trade-volume
  estimates), ArcGIS feature services published by the IMF PortWatch team.
* data.gov.sg, Maritime and Port Authority of Singapore (MPA): monthly
  container throughput, vessel arrivals and cargo throughput.
* SingStat Table Builder M650031 (Civil Aviation Authority of Singapore):
  monthly Changi air cargo tonnage.
* Federal Reserve Bank of New York: Global Supply Chain Pressure Index.
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"

PW = "https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services"

CHOKEPOINTS = {
    "chokepoint1": "Suez Canal",
    "chokepoint2": "Panama Canal",
    "chokepoint4": "Bab el-Mandeb Strait",
    "chokepoint5": "Malacca Strait",
    "chokepoint6": "Strait of Hormuz",
    "chokepoint7": "Cape of Good Hope",
    "chokepoint11": "Taiwan Strait",
}
PORTS = {
    "port1201": "Singapore",
    "port960": "Port Klang",
    "port1269": "Tanjung Pelepas",
}
DATAGOV = {
    "mpa_container_throughput": "d_da030f7028200d19ffcbe4a2d71af39c",
    "mpa_vessel_arrivals": "d_d48c5a038904f6da3c603cd854b6c191",
    "mpa_cargo_throughput": "d_042dd8b935eab998f389adaf559c80de",
}
UA = {"User-Agent": "Mozilla/5.0", "Accept": "*/*"}


def _get(url: str, retries: int = 4) -> bytes:
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except Exception:  # pragma: no cover - network
            if i == retries - 1:
                raise
            time.sleep(3 * (i + 1))
    raise RuntimeError("unreachable")


def _arcgis_all(service: str, where: str, fields: str) -> pd.DataFrame:
    rows, offset = [], 0
    while True:
        q = urllib.parse.urlencode({
            "where": where, "outFields": fields, "returnGeometry": "false",
            "orderByFields": "ObjectId", "resultOffset": offset,
            "resultRecordCount": 1000, "f": "json",
        })
        for attempt in range(4):
            d = json.loads(_get(f"{PW}/{service}/FeatureServer/0/query?{q}"))
            if "error" not in d:
                break
            time.sleep(5 * (attempt + 1))
        else:  # pragma: no cover - network
            raise RuntimeError(f"ArcGIS error: {d['error']}")
        feats = d.get("features", [])
        rows += [f["attributes"] for f in feats]
        if not d.get("exceededTransferLimit") and len(feats) < 1000:
            break
        offset += len(feats)
    return pd.DataFrame(rows)


def fetch_portwatch() -> None:
    cp = pd.concat([_arcgis_all("Daily_Chokepoints_Data", f"portid='{k}'",
                                "date,portid,portname,n_container,n_tanker,n_cargo,n_total,"
                                "capacity_container,capacity") for k in CHOKEPOINTS])
    cp.sort_values(["portid", "date"]).to_csv(RAW / "portwatch_chokepoints_daily.csv", index=False)
    pt = pd.concat([_arcgis_all("Daily_Ports_Data", f"portid='{k}'",
                                "date,portid,portname,portcalls_container,portcalls_tanker,portcalls_cargo,"
                                "portcalls,import_container,export_container,import,export") for k in PORTS])
    pt.sort_values(["portid", "date"]).to_csv(RAW / "portwatch_ports_daily.csv", index=False)


def fetch_datagov() -> None:
    for name, rid in DATAGOV.items():
        d = json.loads(_get(f"https://data.gov.sg/api/action/datastore_search?resource_id={rid}&limit=5000"))
        df = pd.DataFrame(d["result"]["records"]).drop(columns="_id")
        df.to_csv(RAW / f"{name}.csv", index=False)


def fetch_singstat_air() -> None:
    d = json.loads(_get("https://tablebuilder.singstat.gov.sg/api/table/tabledata/M650031?limit=3000"
                        "&seriesNoORrowNo=4"))["Data"]
    rows = []
    for r in d["row"]:
        if r["seriesNo"] in ("4", "4.1", "4.2"):
            for c in r["columns"]:
                rows.append({"series": r["rowText"], "month": c["key"], "value": c["value"]})
    pd.DataFrame(rows).to_csv(RAW / "singstat_M650031_air_cargo.csv", index=False)


def fetch_gscpi() -> None:
    (RAW / "gscpi_data.xlsx").write_bytes(_get(
        "https://www.newyorkfed.org/medialibrary/research/interactives/gscpi/downloads/gscpi_data.xlsx"))


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    fetch_portwatch()
    fetch_datagov()
    fetch_singstat_air()
    fetch_gscpi()
    stamp = {"fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    (RAW / "FETCHED.json").write_text(json.dumps(stamp, indent=1))
    print("ok", stamp)


if __name__ == "__main__":
    main()
