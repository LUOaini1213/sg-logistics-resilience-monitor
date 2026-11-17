# Provenance of the inputs

Every number that enters a result comes from one of three places: the raw downloads in `data/raw/`
(unchanged from the original monitor), the hand-entered tables in `data/inputs/` and `data/corpus/`,
or a calculation in `src/` on those files. This file explains the labels on the hand-entered tables
and lists what could not be verified. The build writes a count of rows per file and label to
`outputs/maritime/provenance_summary.csv`; a test fails if any row lacks a valid label or if a `REAL`
row lacks a URL and an access date.

## Labels

| Label | Meaning | Required fields |
|---|---|---|
| `REAL` | Taken from a public source. Where the value is computed from that source (for example a distance from `searoute` or a percentage change in the PortWatch data), the `source` column says so. | `url`, `accessed` (YYYY-MM-DD) |
| `ASSUMPTION` | Chosen by the author. The `note` gives the reasoning; `source` cites anything that informed the choice (an anchor is not a measurement of the value used). | `note` |
| `ILLUSTRATIVE` | A placeholder that shows how a mechanism works. Not evidence. | `note` |
| `SYNTHETIC` | Generated data, such as the Monte Carlo noise or test fixtures. | `note` |

No input in this release is labelled `ILLUSTRATIVE` or `SYNTHETIC`. Monte Carlo draws are generated at
run time from `data/inputs/scenario_parameters.csv` with a fixed seed and are not stored as inputs;
everything in `outputs/maritime/scenario_*.csv` is therefore simulated (synthetic) output, not
observation, and the synthetic series in the tests exist only inside the test run.

## Files

| File | What it holds |
|---|---|
| `data/raw/*` | IMF PortWatch, MPA (data.gov.sg), SingStat and New York Fed downloads, fetched 13 Oct 2026 (`data/raw/FETCHED.json`); sources in the README's Data section |
| `data/events.csv` | Labelled disruptions with their sources (unchanged) |
| `data/inputs/voyage_parameters.csv` | Ship, fuel, prices, tolls, war-risk premium, EU ETS rules |
| `data/inputs/suez_toll_schedule.csv` | Suez Canal Authority containership transit-dues bands from 15 Jan 2024 |
| `data/inputs/ports.csv`, `voyage_legs.csv` | Port positions (assumed) and the `searoute` distances computed from them |
| `data/inputs/distance_checks_*.csv` | `searoute` distances against published figures |
| `data/inputs/schedule_reliability_glp.csv` | Sea-Intelligence global schedule reliability, Jun 2023 - Dec 2024, from its press releases |
| `data/inputs/sd_parameters.csv` | Assumptions and the one cited scale of the stock-and-flow model |
| `data/inputs/scenario_parameters.csv` | Distributions of the Monte Carlo scenarios and their anchors |
| `data/corpus/sources.csv` | The public texts of the extraction corpus and their terms of use |
| `data/corpus/passages.csv` | Anchor phrases, word counts and SHA-256 hashes of the 19 passages (no text) |
| `data/corpus/reference_links.csv` | Reference cause-effect links with short evidence quotes |
| `data/corpus/llm_runs/*` | Links extracted by local models, with run metadata |
| `data/corpus/llm_repeat/*` | An earlier run of `qwen3.5:4b` with the same prompt, temperature and seed (before the 1,024-token output cap was added; no output of the later run reached the cap), kept to measure repeatability |

## Third-party texts

The UNCTAD *Review of Maritime Transport 2024* is open access under CC BY 3.0 IGO. The MPA and MOT
pages may be viewed, downloaded and printed for personal non-commercial use, and their terms do not
allow republication; the MPA terms also ask for permission before hyperlinking. The repository
therefore keeps no passage text: `scripts/fetch_corpus.py` downloads the pages into a git-ignored
cache and re-cuts the passages, and `passages.csv` holds hashes to check that the same text was used.
Quotes kept in the repository are at most 14 words. The citations to MPA pages, which the original
monitor already carried, were not cleared with MPA (not verified whether its permission is needed).

## Access notes

- `imf.org` refused automated requests (HTTP 403); the SDR valuation page was read through the
  `r.jina.ai` reader. The Springer page of Notteboom, Haralambides and Cullinane (2024) redirects
  automated requests to a login service and was read the same way.
- The Suez Canal Authority's transit-dues schedule was read from a copy hosted by a shipping agent
  (ISS); the SCA website renders its circulars with JavaScript and could not be read.
- EU allowance prices come from the EEX 2026 primary-auction workbook (listed as updated 13 Nov 2026).

## Not verified

These enter the results as assumptions or are left out, and are flagged where they are used:

- A dated time-charter rate for a 14,000 TEU ship (the charter rate is an assumption, 40,000-90,000
  USD/day in the sensitivity analysis).
- The Suez Canal Net Tonnage and the insured hull value of a specific ship of that size.
- The SCA tiers-on-deck surcharge (left out) and the start date of the 12% surcharge (15 July 2026 per
  Leth Agencies, 15 June 2026 per ISS); whether the container-ship rebate was reinstated after April
  2026.
- War-risk premiums after September 2026.
- The current EU MRV emission-factor table (Delegated Regulation (EU) 2023/2776 publishes it as an
  image); the factors used are those of IMO MEPC.364(79) and Regulation (EU) 2016/2071.
- The validity of the cubic speed-fuel law at slow-steaming speeds for this ship (an exponent from 2.5
  to 3.5 is tested).
- Whether the EU list of neighbouring container transhipment ports changed after 2023 (the loop calls
  at none of them).
- The April 2024 global schedule reliability level (the release gives only the monthly change).
- Why Notteboom et al. (2024) give a Cape detour 38% longer than `searoute` does.
- Auxiliary fuel, days per port call and per canal transit, and slot utilisation (assumptions).
- The reference labels of the extraction corpus come from one labeller, the author's tooling, not
  from independent human annotators.
