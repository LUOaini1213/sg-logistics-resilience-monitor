# Research proposal outline (one page)

**Working title.** Seeing disruptions travel: an open observatory and systems model for maritime
supply-chain resilience.

**Call type.** An industry-research grant on maritime digitalisation and supply-chain resilience;
duration 18 months.

**Problem.** Route disruptions (the Red Sea since late 2023, the Strait of Hormuz in 2026) reach hub
ports through capacity, schedules and costs over weeks to months. Operators see their own slice;
public monitors see traffic counts but not the mechanisms, the costs or the next disruption. Decisions
on routing, port capacity and contingency stocks are taken without a shared picture of the loops that
connect them.

**Aim.** Build and test, with industry partners, an open toolkit that links (i) public indicators and
an activation ladder, (ii) a calibrated system dynamics model of the disruption-capacity-reliability-
congestion chain, (iii) voyage-level economics and (iv) forward scenarios, and measure how much
partner data improves each link.

**Research questions.**
1. Which links in the causal loop diagram can be estimated from public data, which need partner data,
   and how much does each kind of data narrow the uncertainty of the model?
2. How early, and at what false-alarm cost, can an activation ladder detect disruptions that reach a
   hub port, and which indicators (prices, schedule reliability, berth waiting) close its blind spots?
3. Which routing and port-capacity decisions are robust across forward scenarios?
4. Can locally run language models extract causal claims from industry and policy texts reliably
   enough to keep a causal map up to date?

**Starting point.** This repository: a monitor backtested on eight disruptions, a causal loop diagram
with evidence-tagged links, a stock-and-flow model calibrated to 2023-24, a Suez/Cape voyage-cost model,
seeded scenarios read through the ladder, and a small extraction benchmark (`paper/working_paper.pdf`).

**Work packages.**

| WP | Content | Months |
|---|---|---|
| 1 Data | Add bunker-price, schedule-reliability and (with partners) berth-waiting series; same-season detector baseline; data-sharing protocol | 1-6 |
| 2 Model | Route-level calibration across several disruptions; a freight-rate block using licensed data; structural tests and parameter identifiability | 3-12 |
| 3 Engagement | 12-20 interviews and two half-day workshops (`workshop/`); link-by-link elicitation of signs, sizes and delays | 2-10 |
| 4 Scenarios and decisions | Partner-defined scenarios; robustness of routing, buffer and berth-allocation rules; cost of false alarms | 8-16 |
| 5 Text mining | Larger corpus, two independent human labellers, an open benchmark for local models | 6-15 |
| 6 Dissemination | Two journal papers, an open-source release, a practitioner briefing | 12-18 |

**Outputs.** Open code and data (where licences allow), a public dashboard, a reusable workshop pack,
peer-reviewed papers on model calibration and on early warning, and a benchmark of causal extraction.

**Resources.** One researcher full time; partner time for interviews, workshops and data access;
compute for model runs (local hardware is sufficient); licensed freight-rate and schedule data; open-access
publication fees.

**Risks and mitigation.** Partner data arrive late: the public-data pipeline stands alone and every
partner series is optional. Commercially sensitive data: aggregate to ranges, agree a sharing protocol
before collection, never publish identifiable figures. Model over-fit to one episode: hold out
disruptions for validation and report identifiability. Language-model results that do not generalise:
publish the benchmark with the human labels and report intervals.

**Ethics and governance.** Interviews by informed consent with notes kept by role, not name; no
personal data in the repository; third-party texts stored only as hashes and short quotes.
