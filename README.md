# Singapore Logistics Resilience Monitor

**Built:** 17 leading indicators of stress in Singapore's logistics sector from public data only, one
robust z-score detector with alarms dated by publication lag, a three-level activation ladder, a backtest
against 8 labelled disruptions (2020–2026), a static dashboard and a tabletop exercise pack.
**Found:** the setting tuned on 2020–2022 caught **11 of 11** event-indicator pairs there and **8 of 8** in the
2023–2026 holdout (alarms firing at random at each indicator's own false-alarm rate would catch about 1.9
and 2.5), at **0.79 false alarms per indicator-year**; the Bab el-Mandeb alarm was readable **152 days**
before MPA's 30 May 2024 congestion statement.
**Limits:** 8 events are too few for tight recall intervals; public data cannot see berth waits, yards or
rates; this is a reproducible snapshot of data fetched 13 October 2026, not a live feed.

**Dashboard:** https://luoaini1213.github.io/sg-logistics-resilience-monitor/

**Maritime scenarios.** A causal loop diagram, a stock-and-flow model calibrated to the 2023-24 Red Sea
diversion, a Suez-versus-Cape voyage-cost model, seeded forward scenarios read through the activation
ladder, a small language-model extraction benchmark and a working paper: see
[Maritime scenarios](#maritime-scenarios-loops-costs-and-forward-scenarios).

What it covers:

- **17 indicators.** Shipping routes, Singapore's port and airport, two Malaysian ports and one global
  pressure index, as daily 7-day sums or monthly values.
- **One detector.** Each indicator gets a robust, one-sided z-score against its own recent normal, with a
  persistence rule. Alarms are dated by when the data was actually published.
- **An activation ladder.** Watch, Alert and Activate review, with written triggers.
- **A backtest.** 8 labelled events, tuned on 2020–2022 and tested on 2023–2026, reporting detection lag,
  lead time and every false alarm.
- **A tabletop exercise pack** in [`exercise/`](exercise/): scenario, injects, decisions, triggers and an
  after-action template.

## Headline results

Selected setting, tuned on 2020–2022 only: **z ≥ 2.5 for 3 consecutive days** (daily series) or one month
(monthly series).

- **Detection.** Every expected indicator fired for every labelled event: **11 of 11** event-indicator pairs
  in the development period and **8 of 8** in the holdout (2023–2026).
  - Chance baseline: alarms firing at random, at each indicator's own false-alarm rate in that period, would
    be expected to hit about 1.9 of the 11 and 2.5 of the 8 windows (`outputs/chance_baseline.csv`). The
    windows are long (up to 758 days), so this is not zero: Cape of Good Hope alone has a 0.84 chance of a
    random alarm inside the Red Sea 2023 window.
  - Holdout recall does not separate settings: 10 of the 16 grid settings also reach 8 of 8 there. They
    differ in false alarms (`outputs/tuning_grid.csv`).
- **Route alarms came quickly.** For route indicators, the median time from documented onset to a readable
  alarm was **18 days**, publication lag included. Examples:
  - Ever Given, Suez: 11 days.
  - Red Sea 2023, Bab el-Mandeb: 15 days.
  - Hormuz 2026: 14 days.
  - Panama drought: 106 days. The canal cut transit slots in steps, so traffic fell gradually.
- **Lead over Singapore's 2024 congestion.** MPA said on 30 May 2024 that container ships were waiting two to
  three days for berths where arrivals could not be rescheduled.
  - The Bab el-Mandeb alarm was readable **152 days** earlier.
  - The Singapore container-call alarm was readable **63 days** earlier.
  - The TEU-per-call alarm came 16 days *after* the statement. The first month to breach was May 2024,
    and MPA publishes about two weeks after the month ends.
- **False alarms are the cost.** The holdout produced **50 false alarms** across 63.0 indicator-years,
  i.e. **0.79 per indicator-year**, or about 13 a year across all 17 indicators.
  - Most fall on a few series: Cape of Good Hope (11), Taiwan Strait (11) and Tanjung Pelepas (8).
  - The development period had 42 (0.82 per indicator-year).
- **The data match official figures.** The MPA monthly series reproduces three published totals exactly:
  - 13.36 million TEU for January–April 2024 (MPA, 30 May 2024);
  - 16.9 million TEU for January–May 2024, up 7.7% on 15.7 million (MOT, 2 July 2024);
  - 23.82 million TEU for January–July 2024 (MPA, 4 September 2024).

  These checks are in the test suite.

**Posture at the data cut-off (data fetched 13 October 2026, publication slots through 11 October 2026):
Level 3, Activate review.** This is a snapshot: nothing refreshes the data or the dashboard automatically
(`python run_all.py --fetch` does it by hand). Last known alarms:

- Bab el-Mandeb transits, falling since the Red Sea restrictions of 20 July 2026.
- TEU per container-ship call: 3,581 in August 2026, the highest value in the series.
- The GSCPI at 1.28 (September 2026).
- Singapore container-ship calls: the alarm remains active at the last available observation, 2 October.

PortWatch route data extend to 4 October, but port data stop on 2 October. The missing port observations
are marked unavailable; retaining the last known alarm does not establish current stress or recovery.
We found no official statement on berth waiting times in Singapore in 2026, so this reading is a flag
for follow-up with operators, not a finding of congestion.

## Data

| Source | Series | Coverage | Access |
|---|---|---|---|
| [IMF PortWatch](https://portwatch.imf.org/) | Daily transits for Suez, Bab el-Mandeb, Cape of Good Hope, Panama, Hormuz, Malacca, Taiwan Strait. Daily port calls and container trade-volume estimates for Singapore, Port Klang, Tanjung Pelepas | 1 Jan 2019 – 4 Oct 2026 (ports to 2 Oct) | ArcGIS feature services `Daily_Chokepoints_Data`, `Daily_Ports_Data` |
| MPA via [data.gov.sg](https://data.gov.sg/) | Container throughput (`d_da030f7028200d19ffcbe4a2d71af39c`), vessel arrivals (`d_d48c5a038904f6da3c603cd854b6c191`), cargo throughput (`d_042dd8b935eab998f389adaf559c80de`), monthly | Jan 1995 – Aug 2026 | datastore API |
| [SingStat Table Builder](https://tablebuilder.singstat.gov.sg/table/TS/M650031) M650031 (CAAS) | Changi total air cargo, monthly | Jan 2000 – Aug 2026 | Table Builder API |
| [Federal Reserve Bank of New York](https://www.newyorkfed.org/research/policy/gscpi) | Global Supply Chain Pressure Index, monthly | Jan 1998 – Sep 2026 | xlsx download |

Raw files are committed in `data/raw/` (fetched 13 October 2026), so every result rebuilds offline.
`python run_all.py --fetch` downloads fresh copies.

No freight-rate index is included. The common container-rate indices (SCFI, Drewry WCI, FBX) do not offer a
free historical download that can be redistributed in a public repository.

## Method

**Indicators** (`src/lsr/indicators.py`):

- Daily PortWatch counts are summed over trailing 7-day windows. This removes the weekday cycle and still
  gives one new value per day.
- Monthly MPA and Changi series are used as year-on-year log changes, which removes seasonality.
- Singapore TEU per container-ship call is MPA throughput divided by PortWatch container-ship calls. It is
  used as a level (see "Design decisions" below). MPA's 30 May 2024 statement noted that "the number of
  containers handled per vessel has also increased"; this indicator measures exactly that.
- Each indicator has a stress direction. Transits and calls are stressed when they **drop**. Cape of Good
  Hope transits (diversions) and TEU per call (bunching) are stressed when they **rise**.

**Detector** (`src/lsr/detect.py`):

- The baseline for each new daily value is the median of the previous 364 *clean* values, ending 28 days
  earlier. Monthly series use the previous 36 clean months (24 for the TEU-per-call level).
- The scale is 1.4826 × MAD, with a floor (5% of the median for daily counts).
- Values that breach the threshold never enter the baseline, so a disruption cannot redefine "normal"
  while it is still going on.
- An alarm that stays active for 182 days (12 months for monthly series) is declared a sustained shift and
  re-baselined on the new level. Without this, the 2023 Red Sea alarm would have stayed open into 2026 and
  hidden the second Red Sea shock in July 2026. With it, that shock raised a fresh alarm 24 days after the
  20 July restrictions.
- The GSCPI is already in standard-deviation units; it alarms at ≥ 1.0 for two consecutive months.

**Missing observations.** Daily and monthly calendars retain missing dates. A non-finite detector input
resets consecutive confirmation, recovery and sustained-shift counts; it cannot help confirm an alarm or
re-baselining. An existing alarm retains its last known state until observed recovery. Detector frames
include `observed`; daily posture and the dashboard identify `unavailable` inputs after publication lag.
This marks missing input at the latest published slot, not a guarantee of source freshness. In particular,
two high GSCPI months separated by an unobserved month do not satisfy the two-consecutive-month rule.

**Publication lag.** Every alarm is dated by when it could have been read:

| Source | Lag added |
|---|---|
| PortWatch | 7 days (weekly updates) |
| MPA | 15 days after month end |
| Changi air cargo | 30 days after month end |
| GSCPI | 5 days after month end |

**Activation ladder** (`backtest.posture`, details in [`exercise/triggers.md`](exercise/triggers.md)):

| Level | Trigger |
|---|---|
| 1 Watch | Any indicator in alarm. |
| 2 Alert | Two route indicators, or one route indicator plus a Singapore or regional port indicator (daily port calls or container volume; the monthly outcomes do not count here). |
| 3 Activate review | Alert, plus a Singapore monthly outcome in alarm. |

The level is recomputed every day. The 14-day step-down hold in the exercise pack is a team procedure and is
not applied to the daily series or to the day counts below.

## Backtest protocol

`data/events.csv` lists 8 disruptions. Each has:

- a documented onset, with its source;
- an assessment window;
- a development or holdout split;
- the indicators expected to move. These lists were written from the event descriptions, before tuning.

| Event | Onset | Split | Expected indicators |
|---|---|---|---|
| COVID-19, Wuhan lockdown | 23 Jan 2020 | dev | Malacca, Taiwan Strait, SG calls, SG volume, MPA TEU, Changi cargo |
| Pandemic-era congestion | Oct 2020 (approx.) | dev | GSCPI, TEU per call, SG calls |
| Ever Given, Suez | 23 Mar 2021 | dev | Suez, Bab el-Mandeb |
| Panama drought slot caps | 30 Jul 2023 | holdout | Panama |
| Red Sea, carriers pause | 15 Dec 2023 | holdout | Bab el-Mandeb, Suez, Cape |
| Singapore berth congestion | Mar 2024 (MPA statement 30 May) | holdout | TEU per call, SG calls |
| Strait of Hormuz collapse | 28 Feb 2026 | holdout | Hormuz |
| Red Sea restrictions | 20 Jul 2026 | holdout | Bab el-Mandeb |

How alarms are scored:

- An alarm is **true** if its indicator is expected for an event and it was raised between 28 days before
  onset and the end of that event's window.
- **Every other alarm is false.** That includes alarms during a real event on an indicator that was not
  expected to move, such as GSCPI in 2026.
- Alarms raised before 2020 are not scored. The monthly series need their long history as a baseline,
  but the period before PortWatch has no labels.

Tuning:

- The grid was z ∈ {2.5, 3, 3.5, 4} × persistence ∈ {1, 3, 5, 7} days.
- The rule, fixed before the grid was run: highest development recall, then fewest development false alarms
  per indicator-year, then the stricter setting.
- The full grid is in `outputs/tuning_grid.csv`.
- The rule chose the most sensitive setting that still caught all 11 development pairs.
- A stricter setting (z ≥ 3, 7 days) would have done better on the holdout: 8 of 8 detected with 7 false
  alarms. It caught only 7 of 11 in development, so the rule did not pick it. We report the setting the rule
  chose.

Quiet runs and empty event sets produce tables with the same columns as nonempty results. Scores always
retain `pairs` and `indicator_years`: `recall_defined` and `false_alarm_rate_defined` are false when their
denominators are zero. The corresponding numeric `0.0` is a finite placeholder, **not** measured zero
recall or false-alarm rate. No detected route events gives a null median lag.

## Findings in more detail

**Alert-level days.** From 2020 to October 2026 the ladder spent 475 days at Alert or above, 206 of them at
Activate review. 38 of the 475 days fell outside every labelled event window (`outputs/posture_days_by_year.csv`,
`outputs/posture_first_level_by_event.csv`). With the exercise pack's 14-day step-down hold, episodes would
run longer than these counts.

The first Alert near the Red Sea event came on 29 December 2023. It was set by a Panama alarm plus a Taiwan
Strait false alarm, one day before the Bab el-Mandeb alarm became readable; the Red Sea route alarms alone
reached Alert by 5 January 2024.

**Where the false alarms come from** (`outputs/false_alarms_by_indicator.csv`, `outputs/alarms.csv`):

- **Cape of Good Hope.** 10 of the 11 holdout false alarms were raised between June and September. Cape
  traffic is seasonally higher then, and a trailing median does not model seasonality.
- **Taiwan Strait.** 11 of its 17 false alarms (2020–2026) fall in July–October, the typhoon season. Weather
  events are not labelled here.
- **Port Klang.** The series has deep, short dips in 2020–21 (11 development false alarms) that match no
  closure we could find. They are treated as unexplained.
- **Mid-2026.** Several alarms coincide with the 2026 Hormuz crisis on indicators that were not expected to
  move (GSCPI, Malacca, Tanjung Pelepas) and so count as false.

**One design change after looking at results.** TEU per call was first run as a year-on-year change, like
the other monthly series.

- That version alarmed 257 days after the pandemic-congestion onset and missed the 2024 Singapore
  congestion entirely.
- The level version alarmed after 14 days and 106 days respectively, with one false alarm.
- The switch was made after both periods had been seen, so the holdout result for this one indicator is not
  a clean out-of-sample test. Both versions are in `outputs/teu_per_call_transform_check.csv`.

## Limits

- **Public data only.** The monitor sees ships and boxes, not berth waiting times, yard utilisation,
  inventories or freight rates. Level 2 is designed to prompt a request to operators for those.
- **PortWatch counts are AIS-based estimates.** Ships that switch off their transponders are missed, and
  recent days can be revised. The Malacca series also steps up in late 2021 (2022 averaged 34% above January–October 2021), so long
  comparisons across that date should be read with care.
- **Small event set.** 8 events and 19 event-indicator pairs are enough to measure lag and false alarms. They
  are not enough to give tight confidence intervals for recall.
- **Monthly confirmation is slow.** Singapore monthly outcomes are published two to six weeks after the
  month, so Level 3 usually confirms a disruption rather than anticipating it.
- **No seasonal model.** The trailing median makes no seasonal adjustment, which accounts for most of the
  Cape and part of the Taiwan Strait false alarms. A same-season baseline is the obvious next step.

## Tabletop exercise pack

[`exercise/`](exercise/) holds a 2.5-hour, three-move tabletop called "Two Straits". The Red Sea route
closes, congestion reaches Singapore, and then a collision restricts the Singapore Strait. It contains:

- objectives, player tables and running order ([`README`](exercise/README.md));
- injects and decision points, with magnitudes drawn from the 2023–24 data and cited
  ([`scenario_and_injects.md`](exercise/scenario_and_injects.md));
- the activation ladder, with an indicator-to-question map for partners ([`triggers.md`](exercise/triggers.md));
- a two-page [after-action template](exercise/after_action_template.md).

## Maritime scenarios: loops, costs and forward scenarios

A second layer asks how the 2023-24 Red Sea diversion travelled to Singapore, what the long way round
costs a carrier, and what the ladder would show for the next disruption. It rebuilds offline with the
rest (`python run_all.py`, outputs in [`outputs/maritime/`](outputs/maritime/)) and is written up in a
working paper ([`paper/working_paper.pdf`](paper/working_paper.pdf)).

- **Causal loop diagram** ([`cld.svg`](outputs/maritime/figures/cld.svg), `src/lsr/maritime/cld.py`).
  27 signed links between 18 variables, each tagged by its evidence: 7 estimated by the stock-and-flow
  fit, 5 implied by the voyage-cost model, 8 cited from published sources but not estimated here, and
  7 assumed. Seven feedback loops; only the port-response loop (B1) is estimated end to end.
- **Stock-and-flow model** (`sd.py`, `calibrate.py`, with the package's own RK4 integrator). Seven
  stocks, calibrated block by block to PortWatch container transits of Bab el-Mandeb and the Cape and
  Singapore container calls (weekly), Sea-Intelligence global schedule reliability and MPA TEU per call
  (monthly), July 2023 to December 2024 ([`sd_fit.svg`](outputs/maritime/figures/sd_fit.svg)).
  - Fit (R²): Bab el-Mandeb 0.96, Cape 0.91, schedule reliability 0.93, Singapore calls 0.66,
    TEU per call 0.82.
  - The profiled onset is 14 December 2023 (95% range 30 November to 16 December); the event list
    documents 15 December. 74% of the pre-crisis Bab el-Mandeb container traffic diverted, and the
    diverted ships reached the Cape about 13 days later.
  - Reliability fell with no measurable delay: the capacity-absorption delay sits at the bottom of its
    search range and the profile rejects more than 10 days. Singapore's bunching built and faded with a
    time constant of 166 days (95% interval 131 to 201). The smooth model reaches a 13.3% fall in calls
    where the data show 22.2%.
  - Estimates, intervals and which parameters are assumed: [`sd_parameters.csv`](outputs/maritime/sd_parameters.csv).
- **Voyage economics** (`voyage.py`). A 14,000 TEU ship on a Shanghai-Singapore-Rotterdam-Hamburg-Antwerp
  loop: the Cape round voyage takes 78.51 days against 66.75 via Suez, needs 1.68 more ships for a weekly
  service and burns 1,902 t more fuel. Suez is cheaper only below a war-risk premium of
  **0.302% of hull value per transit**; at the 1% reported for the southern Red Sea in July 2026 the
  Cape is cheaper by 99.68 USD per TEU. The bunker price, the length of the Cape detour and the Cape
  speed move the break-even most ([`voyage_tornado.svg`](outputs/maritime/figures/voyage_tornado.svg)).
- **Forward scenarios** (`scenarios.py`): 2,000 seeded draws each over 26 weeks from 5 October 2026,
  through the selected detector and the ladder, with the same noise as a noise-only control so that
  increments are attributable ([`scenario_ladder.csv`](outputs/maritime/scenario_ladder.csv)).
  - Singapore Strait incident: an Alert caused by the incident in 41% of draws, a median 11 days after
    it; waiting ships cost a median 48 million USD.
  - Gulf escalation with a second fuel shock: a median 99 USD per TEU more on the Cape loop (5-95%:
    61 to 138), but an Alert caused by it in only 1.4% of draws, because the monitor has no price
    indicator.
  - Red Sea reopening: no alarm caused by it (the route detectors look one way); Suez is cheaper than
    the Cape in 37% of draws.
  - Noise alone reaches Alert in 41% of draws, and the noise model's per-indicator false-alarm rates
    differ from the real ones ([`scenario_noise_check.csv`](outputs/maritime/scenario_noise_check.csv)).
- **Language-model extraction** (`extraction.py`, `scripts/run_llm_extraction.py`). 19 passages
  from UNCTAD's *Review of Maritime Transport 2024*, two MPA statements and an MOT parliamentary reply, a
  17-variable codebook ([`codebook.md`](data/corpus/codebook.md)) and 45 reference links.
  The reference labels were produced with the codebook by the author's tooling, not by independent human
  annotators, so the scores measure agreement with one reading. Run locally through Ollama
  (temperature 0, fixed seed, JSON-schema output), `qwen3.5:4b` reached precision 0.60
  (95% interval 0.45-0.70) and recall 0.56 (0.42-0.67); `llama3.2:3b`
  0.16 and 0.33; `gemma3:4b` 0.53 and 0.44
  ([`extraction_scores.csv`](outputs/maritime/extraction_scores.csv)). Two runs of `qwen3.5:4b` with the same
  settings shared 41 of 43 distinct links, so the runs are close to but not exactly
  repeatable. The models are not called by the build or CI; their outputs are committed. The texts' terms do not allow
  republishing them, so the repository keeps only hashes, anchor phrases and quotes of at most 14 words.
- **Workshop pack** ([`workshop/`](workshop/)): an industry interview guide and a half-day workshop
  agenda built around the diagram. A one-page research-proposal outline is in
  [`paper/research_proposal_outline.md`](paper/research_proposal_outline.md).

**Provenance.** Every hand-entered input is labelled REAL (with URL and access date), ASSUMPTION,
ILLUSTRATIVE or SYNTHETIC: 70 REAL and 52 ASSUMPTION rows across 10 files, none ILLUSTRATIVE or SYNTHETIC ([`data/PROVENANCE.md`](data/PROVENANCE.md), which also lists
what could not be verified, such as a dated charter rate for this ship size, its net tonnage and hull
value, and the Suez tiers-on-deck surcharge).

## Reproduce

Python 3.11 (the CI version). The pinned numpy 1.24.3 and pandas 2.0.3 publish no wheels for Python 3.12 or
later, so `pip install` fails there.

```
pip install -r requirements.txt
python run_all.py            # rebuilds outputs/, docs/index.html and paper/working_paper.md (about 3-5 minutes)
python -m pytest -q tests
python tests/mutate.py       # mutation check of the monitor
python tests/mutate_maritime.py   # mutation check of the maritime modules
```

Optional steps that need extra tools or the network (`pip install -r requirements-extra.txt`):

```
python scripts/compute_distances.py      # sea distances with searoute (offline)
python scripts/fetch_corpus.py           # downloads the corpus texts into a git-ignored cache
python scripts/run_llm_extraction.py qwen3.5:4b llama3.2:3b gemma3:4b   # needs Ollama on localhost
python scripts/build_paper.py            # paper PDF with pandoc and headless Chromium
```

**Tests.** The suite checks the detector against hand-computed series, the bookkeeping of the backtest
(window boundaries, lags, lead, ladder levels), missing observation/calendar gaps, empty-result reports,
the raw data against the three official MPA/MOT totals, and
that the numbers in this README match `outputs/summary.json` and the output tables.

**Mutation check.** `tests/mutate.py` plants 32 bugs one at a time, for example:

- a flipped stress sign;
- a persistence rule that is off by one;
- breach values leaking into the baseline;
- an ignored publication lag;
- an 11-month "year-on-year" lag;
- a wrong Cape direction;
- a Singapore monthly outcome counted as the Alert's port indicator.

Each bug must make the tests fail. Before that, the harness runs a no-op control mutant that must *survive*,
which shows that it can report a surviving bug.

The first full run caught 30 of 31 and exited with an error
([`outputs/mutation_first_run.txt`](outputs/mutation_first_run.txt)). The survivor raised Activate review
from a Singapore outcome alarm alone, without an Alert. It survived because the ladder test never covered a
day with an outcome alarm and no route alarm. That case was added, and the current run catches 32 of 32
([`outputs/mutation_run.txt`](outputs/mutation_run.txt)). CI runs the tests, the mutation check, and a full rebuild
that must reproduce every committed file in `outputs/` and `docs/index.html` exactly.

## Repository layout

```
data/raw/          downloaded source files (see Data)
data/events.csv    labelled disruptions with sources
data/inputs/       hand-entered, provenance-labelled inputs of the maritime layer
data/corpus/       extraction corpus metadata, codebook, reference links, model runs (no passage text)
data/PROVENANCE.md labels and what could not be verified
src/lsr/           fetch, indicators, detector, backtest, report, dashboard
src/lsr/maritime/  causal loop diagram, stock-and-flow model, voyage costs, scenarios, extraction scoring
scripts/           distances, corpus download, local-model extraction, paper PDF (not run by CI)
outputs/           backtest tables, alarm list, daily posture, summary.json
outputs/maritime/  maritime results, figures and summary.json
paper/             working paper (template, generated Markdown, PDF) and proposal outline
docs/index.html    dashboard (GitHub Pages)
exercise/          tabletop exercise pack
workshop/          industry interview guide and half-day workshop agenda
tests/             tests and mutation harnesses
```
