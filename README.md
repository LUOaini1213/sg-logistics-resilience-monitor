# Singapore Logistics Resilience Monitor

Leading indicators of stress in Singapore's logistics sector, built only from public data, with alarms
backtested against documented disruptions from 2020 to 2026, and a tabletop exercise pack that uses the
same triggers.

**Dashboard:** https://luoaini1213.github.io/sg-logistics-resilience-monitor/

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

**Latest computed posture (publication slots through 11 October 2026): Level 3, Activate review.**
Last known alarms:

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
| 2 Alert | Two route indicators, or one route indicator plus a Singapore or regional port indicator. |
| 3 Activate review | Alert, plus a Singapore monthly outcome in alarm. |

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

**Alert-level days.** From 2020 to October 2026 the ladder spent 549 days at Alert or above. 69 of those
days fell outside every labelled event window (`outputs/posture_days_by_year.csv`,
`outputs/posture_first_level_by_event.csv`).

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

## Reproduce

```
pip install -r requirements.txt
python run_all.py            # rebuilds outputs/ and docs/index.html from data/raw (about 1-2 minutes)
python -m pytest -q tests
python tests/mutate.py       # mutation check
```

**Tests.** The suite checks the detector against hand-computed series, the bookkeeping of the backtest
(window boundaries, lags, lead, ladder levels), missing observation/calendar gaps, empty-result reports,
the raw data against the three official MPA/MOT totals, and
that the numbers in this README match `outputs/summary.json`.

**Mutation check.** `tests/mutate.py` plants 31 bugs one at a time, for example:

- a flipped stress sign;
- a persistence rule that is off by one;
- breach values leaking into the baseline;
- an ignored publication lag;
- an 11-month "year-on-year" lag;
- a wrong Cape direction.

Each bug must make the tests fail. Before that, the harness runs a no-op control mutant that must *survive*,
which shows that it can report a surviving bug.

The first full run caught 30 of 31 and exited with an error
([`outputs/mutation_first_run.txt`](outputs/mutation_first_run.txt)). The survivor raised Activate review
from a Singapore outcome alarm alone, without an Alert. It survived because the ladder test never covered a
day with an outcome alarm and no route alarm. That case was added, and the current run catches 31 of 31
([`outputs/mutation_run.txt`](outputs/mutation_run.txt)). CI runs the tests, the mutation check, and a full rebuild
that must reproduce the committed outputs exactly.

## Repository layout

```
data/raw/          downloaded source files (see Data)
data/events.csv    labelled disruptions with sources
src/lsr/           fetch, indicators, detector, backtest, report, dashboard
outputs/           backtest tables, alarm list, daily posture, summary.json
docs/index.html    dashboard (GitHub Pages)
exercise/          tabletop exercise pack
tests/             tests and mutation harness
```
