---
title: "The long way round: Red Sea diversions, Singapore's port and a systems view built from public data"
subtitle: "Working paper, 15 November 2026"
author: "Repository author (GitHub: LUOaini1213)"
---

**Abstract.** When container lines left the Suez route in December 2023, the effect reached
Singapore through the capacity that longer voyages absorb and through ships arriving off schedule.
This paper links four parts built only from public data and dated sources. A causal loop diagram
names {{cld.links}} links and {{cld.links_by_status.estimated}} of them are estimated. A stock-and-flow
model, calibrated to 2023-24 transits, schedule reliability and Singapore port data, explains
{{sd.r2.bab|.0%}} of the variance of Bab el-Mandeb container transits and {{sd.r2.calls|.0%}} of that of
Singapore container calls. A voyage-cost model of an Asia-North Europe loop puts the war-risk premium at
which Suez and the Cape cost the same at {{voyage.breakeven_war_risk_pct|.2f}}% of hull value per
transit, against 1-2% reported in July 2026. Seeded Monte Carlo scenarios, read through the
repository's own alarm detector and activation ladder, show which future disruptions the ladder would
see. A small local language model extracted cause-effect links from {{extraction.passages}} public
passages; its agreement with a reference set made by the author's tooling is reported with
intervals.

# 1. Question

The repository this paper extends is a monitor: {{main.n_indicators}} public indicators, a robust
alarm detector and a three-level activation ladder, backtested on {{main.n_events}} labelled
disruptions. It answers *whether* something is moving. This paper asks *how* the 2023-24 Red Sea
diversion moved through the network, what it costs, and what the monitor would show next time:

1. Which feedback loops connect the diversion to congestion in Singapore and to freight markets,
   and which of those links can public data estimate?
2. How quickly did routing, schedule reliability and Singapore's port respond, and how well does a
   small stock-and-flow model reproduce them?
3. What does the long way round cost a carrier, and at what war-risk premium does Suez become cheaper?
4. Which forward disruptions would reach the monitor's Alert level, how fast, and at what cost?
5. Can a 4-billion-parameter model running on a laptop help map causal claims in public texts?

# 2. Data

All results rebuild offline from files in the repository (`python run_all.py`); network access is
needed only to refresh them. Every hand-entered input carries one of four labels: REAL (with a URL
and access date), ASSUMPTION, ILLUSTRATIVE or SYNTHETIC ({{provenance.REAL}} REAL rows,
{{provenance.ASSUMPTION}} ASSUMPTION rows across {{provenance.files}} files; `data/PROVENANCE.md`
lists what could not be verified).

- **Monitor data** (IMF PortWatch daily chokepoint transits and port calls; MPA monthly container
  throughput via data.gov.sg), fetched 13 October 2026. Container-ship transits of Bab el-Mandeb and
  the Cape of Good Hope and Singapore container-ship calls are used as non-overlapping weekly sums,
  and TEU per call as MPA throughput divided by PortWatch calls.
- **Schedule reliability.** Eighteen monthly values of Sea-Intelligence's global schedule
  reliability, June 2023 to December 2024 (April 2024 is missing), each taken from its press release.
- **Voyage inputs.** Fuel use from a published 14,000 TEU reference design (MAN Energy Solutions),
  Suez Canal Authority containership toll bands from January 2024 with the 2026 surcharge, the IMF SDR
  rate, the Singapore VLSFO price of early November 2026 (ENGINE), the EEX auction price of an EU
  allowance on 12 November 2026, the ECB euro rate, and war-risk premiums reported by Reuters. The
  charter rate, the ship's net tonnage and hull value, auxiliary fuel and port times are assumptions.
- **Text corpus.** {{extraction.passages}} passages from UNCTAD's *Review of Maritime Transport 2024*
  (chapters II and III, CC BY 3.0 IGO), two MPA statements and an MOT parliamentary reply. Their terms
  do not allow republication, so only hashes, anchor phrases and quotes of at most 14 words are kept.

# 3. Methods

**Causal loop diagram.** Eighteen variables and {{cld.links}} signed links, each tagged by its
evidence: *estimated* by the stock-and-flow calibration, implied by the voyage *model*, *cited* from a
published source without being estimated here, or *assumed*. Feedback loops are all simple cycles of
the link graph; a loop reinforces when the product of its signs is positive.

**Stock-and-flow model.** Seven stocks integrated daily with the package's own fourth-order
Runge-Kutta scheme (tested against analytic step responses): the diverted share *D* of pre-crisis
Bab el-Mandeb container transits, which approaches *d*~max~ after the onset with time constant
*τ*~d~; a Cape pipeline that follows *D* with delay *τ*~c~; the capacity absorbed by longer routes, *A*,
which follows *D* with delay *τ*~a~; schedule unreliability *U = u*~0~ + *βA* (with response time
*τ*~u~ fixed at one day); Singapore bunching *Q*, which builds from *U − u*~0~ and is removed by an
adaptation stock *K* (berths, yards, schedule coordination) with a common time constant *τ*~q~; and a
network-position stock used only in scenarios. Observations are Bab el-Mandeb transits *B*~0~(1 − *D*),
Cape transits *C*~0~ + *κB*~0~*D*~c~, reliability 1 − *U*, Singapore calls *C*~b~(1 − *θ*~c~*Q*) and TEU per
call *T*~b~(1 + *θ*~t~*Q*). Baselines are pre-crisis means. Calibration runs block by block in causal
order (routing, reliability, Singapore), solving linear parameters in closed form and the others by
bounded Nelder-Mead or golden-section search; the onset day is profiled. Standard errors come from
the Gauss-Newton covariance with one residual variance per series, inflated by (1 + *ρ*)/(1 − *ρ*) for
lag-1 residual autocorrelation *ρ*. A model with known parameters, plus noise, is recovered by the
same code in the test suite.

**Voyage economics.** A Shanghai-Ningbo-Yantian-Singapore-Rotterdam-Hamburg-Antwerp-Singapore loop
for a {{voyage.ship_teu|,}} TEU ship, with sea distances from `searoute` (within 2% of UNCTAD's
Shenzhen-Rotterdam figures, but 27% short of the Cape detour given by Notteboom et al., 2024, which the
sensitivity analysis carries). Costs per round voyage: main-engine fuel scaled from the reference
point by (speed ratio)^3^ and by calorific value, auxiliary fuel, charter hire for the voyage days,
Suez tolls (two laden transits), the war-risk premium on hull value (two transits of the high-risk
area) and EU allowances for 50% of the emissions of voyages to or from the EU and 100% within and
between EU ports (European Commission, 2026). Suez is costed at 16 knots and the Cape at 17, following
Notteboom et al. (2024). The premium enters linearly, so the break-even premium is exact; each other
input is moved alone to its low and high value for the tornado.

**Scenarios.** 2,000 seeded draws per scenario over 26 weeks from 5 October 2026: a Gulf escalation
with a second fuel shock, a Singapore Strait incident, and a Red Sea reopening driven through the
calibrated model. Each indicator starts at the detector's baseline at the data cut-off, with
detrended 2025 noise resampled in 28-day blocks; every scenario uses the same noise as a noise-only
control, so its increment over the control on the same draw is attributable to its shock. Paths go
through the selected detector (z ≥ {{main.selected.k}} for {{main.selected.persist_days}} days, against
the cut-off baseline), the publication lags and the ladder. Re-running the repository's own detector on
real history plus simulated paths agrees on {{scenarios.exact_check_min_agreement|.1%}} or more of
breach days.

**Language-model extraction.** A 17-variable codebook (`data/corpus/codebook.md`) defines when a
sentence states a link and how to sign it. The reference set ({{extraction.reference_links}} links) was
labelled with the codebook by the author's tooling, not by independent human annotators. The models
ran locally through Ollama with temperature 0, a fixed seed and JSON-schema output, prompted with the
codebook verbatim. A prediction counts when the same directed pair is in the reference set for the
same passage; intervals come from 2,000 bootstrap resamples of passages.

# 4. Results

## 4.1 Structure

![Causal loop diagram. Line style shows the evidence for each link.](../outputs/maritime/figures/cld.svg)

Of the {{cld.links}} links, {{cld.links_by_status.estimated}} are estimated, {{cld.links_by_status.model}}
follow from the voyage model, {{cld.links_by_status.cited}} are cited and {{cld.links_by_status.assumed}}
are assumed. Of the seven loops, only the port-response loop (B1) is estimated end to end. The
congestion spiral (R1) rests on two estimated links and one cited link; the freight-market loops (B2,
B3, B4, R3) contain assumed links because the repository has no freight-rate series, which is where
interviews and a workshop can add most (`workshop/`).

## 4.2 Calibration

{{table:sd_fit}}

{{table:sd_parameters}}

![The model against the 2023-24 observations.](../outputs/maritime/figures/sd_fit.svg)

The profiled onset is {{sd.onset}} (95% range {{sd.onset_ci95.0}} to {{sd.onset_ci95.1}}); the
carriers' pause documented in the event list began on 15 December 2023. Routing changed within days
and settled with {{sd.params.d_max|.0%}} of the pre-crisis Bab el-Mandeb container traffic diverted;
{{sd.params.kappa|.2f}} Cape transits appeared for each lost Bab el-Mandeb transit, about
{{sd.params.tau_c|.0f}} days later. Global reliability fell with no measurable delay: the absorption
delay sits at the bottom of its search range, and the profile rejects delays above about
{{sd.tau_a_profile_max_days|.0f}} days. Holding it at one Asia-Europe voyage (30 days) worsens the
reliability fit (RMSE {{sd.tau_a_held.glp_rmse|.2f}} against {{sd.glp_rmse_fitted|.2f}} percentage
points). This is consistent with reliability falling as soon as ships were out of position, rather
than gradually as absorbed capacity built up; the data cannot separate the two delays, so the model
reports them as one. Singapore's response took longer: bunching built and faded with a time constant of
{{sd.params.tau_q|.0f}} days (95% interval {{sd.ci95.tau_q.0|.0f}} to {{sd.ci95.tau_q.1|.0f}}). The
smooth model under-states the peaks: it lowers calls by at most {{sd.peak_calls_drop_pct}}% and raises
TEU per call by at most {{sd.peak_tpc_rise_pct}}%, against {{sd.obs_calls_drop_pct}}% and
{{sd.obs_tpc_rise_pct}}% at the observed extremes. Residuals are autocorrelated (*ρ* up to
{{sd.rho.reliability|.2f}}), and the intervals are inflated for it.

## 4.3 Voyage economics

{{table:voyage}}

![Tornado chart of the break-even war-risk premium.](../outputs/maritime/figures/voyage_tornado.svg)

The Cape loop takes {{voyage.cape_days|.1f}} days against {{voyage.suez_days|.1f}}, needs
{{voyage.extra_ships_weekly|.1f}} more ships for a weekly service (Notteboom et al., 2024, report at least
two for a typical loop) and burns {{voyage.extra_fuel_t|,}} t more fuel per round voyage. Suez saves that
fuel, charter time and some EU allowances but pays {{voyage.suez_toll_usd_per_transit|,}} USD per
transit in tolls and the war-risk premium twice. Suez is cheaper only below
{{voyage.breakeven_war_risk_pct|.2f}}% of hull value per transit ({{voyage.breakeven_war_risk_usd_per_transit|,}}
USD on a 150 million USD hull). At the 1% reported for the southern Red Sea at the end of July 2026
(Reuters via Insurance Journal, 2026) the Cape is cheaper by {{voyage.cape_saving_usd_per_teu|.0f}} USD
per TEU carried. The break-even is most sensitive to the bunker price
({{voyage.tornado_top_range_pct.0.0|.2f}}-{{voyage.tornado_top_range_pct.0.1|.2f}}%), the length of the
Cape detour ({{voyage.tornado_top_range_pct.1.0|.2f}}-{{voyage.tornado_top_range_pct.1.1|.2f}}%) and the
speed on the Cape route ({{voyage.tornado_top_range_pct.2.0|.2f}}-{{voyage.tornado_top_range_pct.2.1|.2f}}%).
Costs that arise only on the Suez routing and are outside the model, such as crew bonuses for the
high-risk area or war-risk cover on cargo (not verified here), would lower the break-even further, and
crew safety is not priced at all.

## 4.4 Scenarios

{{table:scenarios}}

![Ladder outcomes within 26 weeks.](../outputs/maritime/figures/scenario_ladder.svg)

Noise alone reaches Alert in {{scenarios.ladder.control.p_level2|.0%}} of draws, which is why the
attributable column matters. A Singapore Strait incident is the disruption the ladder is built for: it
adds an Alert in {{scenarios.ladder.strait.p_level2_attributable|.0%}} of draws, a median
{{scenarios.ladder.strait.days_to_level2_p50|.0f}} days after the incident, because Malacca transits and
Singapore calls fall together; waiting ships cost a median {{scenarios.strait_waiting_cost_usd_m.1|.0f}}
million USD (5-95%: {{scenarios.strait_waiting_cost_usd_m.0|.0f}}-{{scenarios.strait_waiting_cost_usd_m.2|.0f}}).
A second Gulf fuel shock adds a median {{scenarios.gulf_cape_cost_change_usd_per_teu.1|.0f}} USD per TEU to
the Cape loop (5-95%: {{scenarios.gulf_cape_cost_change_usd_per_teu.0|.0f}}-{{scenarios.gulf_cape_cost_change_usd_per_teu.2|.0f}})
but adds an Alert in only {{scenarios.ladder.gulf.p_level2_attributable|.1%}} of draws: the monitor has no
price indicator, and Hormuz traffic, already re-baselined after its 2026 collapse, cannot fall far. A
Red Sea reopening adds no alarms at all, because the route detectors only look for falls in
Bab el-Mandeb and Suez traffic and rises at the Cape; the calibrated model predicts relief in Singapore,
and Suez is cheaper than the Cape in {{scenarios.reopen_p_suez_cheaper|.0%}} of draws. The noise model
over-alarms on Suez and Bab el-Mandeb and never alarms on Malacca or the port indicators
(`outputs/maritime/scenario_noise_check.csv`), so the absolute shares carry that bias.

## 4.5 Language-model extraction

{{table:extraction}}

The reference set has {{extraction.reference_links}} links in {{extraction.passages}} passages.
`qwen3.5:4b` proposed {{extraction.models.qwen3_5_4b.predicted_links}} links, of which
{{extraction.models.qwen3_5_4b.tp}} match the reference: precision {{extraction.models.qwen3_5_4b.precision|.2f}}
(95% interval {{extraction.models.qwen3_5_4b.precision_ci95}}) and recall {{extraction.models.qwen3_5_4b.recall|.2f}}
({{extraction.models.qwen3_5_4b.recall_ci95}}), with the reference's sign on
{{extraction.models.qwen3_5_4b.polarity_agreement|.0%}} of the matched links and
{{extraction.models.qwen3_5_4b.quote_verbatim_share|.0%}} of its evidence quotes found verbatim in the passage.
`gemma3:4b` reached {{extraction.models.gemma3_4b.precision|.2f}} and {{extraction.models.gemma3_4b.recall|.2f}}.
`llama3.2:3b` reached only {{extraction.models.llama3_2_3b.precision|.2f}} and
{{extraction.models.llama3_2_3b.recall|.2f}}: it listed {{extraction.models.llama3_2_3b.predicted_links}} links,
and on {{extraction.models.llama3_2_3b.failed_passages}} passages its output ran into the 1,024-token cap twice
and was scored as no links. Temperature 0 and a fixed seed did not make the runs exactly repeatable: two
runs of `qwen3.5:4b` shared {{extraction.repeat.qwen3_5_4b.shared}} of {{extraction.repeat.qwen3_5_4b.union}}
distinct links (`outputs/maritime/extraction_repeat.csv`). The intervals are wide because there are only
{{extraction.passages}} passages. The disagreements are of two kinds (`outputs/maritime/extraction_errors.csv`):
links the codebook requires but a model missed, most often the effect of off-schedule arrivals and of
port capacity on berth waiting; and readings the single reference labeller did not choose but that are
defensible, such as freight rates driving consumer prices where the reference attributes the rise in
prices to the disruption itself. The second kind is a reason to add an independent human labeller
before these figures are used as a benchmark.

# 5. Limitations

- **One episode.** The model is calibrated to one diversion. Its Singapore block is linear and
  symmetric, so the predicted relief on reopening is an extrapolation, and the re-routing friction is an
  assumption, not an estimate.
- **Global, not route-level, reliability.** The reliability index covers all trades; the model treats
  its 2024 fall as caused by the Red Sea alone.
- **No freight rates.** Free historical freight-rate indices cannot be redistributed, so every link
  into or out of rates is cited or assumed.
- **Representative costs.** One ship, one loop, one bunker price; the charter rate, net tonnage and
  hull value are assumptions, and costs outside the carrier's voyage account are left out.
- **Scenario design.** Scenarios start from a quiet baseline rather than from the Level 3 posture at the
  cut-off, the noise model reproduces per-indicator false-alarm rates only roughly, and every
  distribution is an assumption with stated anchors.
- **One labeller.** The extraction reference set is one reading by the author's tooling; agreement with
  it is not accuracy, and 19 passages give wide intervals.

# 6. Conclusion

Public data identify the first half of the chain well (routing, the Cape pipeline and the fall in
schedule reliability) and the Singapore episode adequately, and they show that reliability fell at once
while Singapore took months to bunch and recover. They say nothing direct about freight rates, which is
where the diagram rests on citations and assumptions. On costs, the Cape stays cheaper while war-risk
premiums exceed about {{voyage.breakeven_war_risk_pct|.1f}}% of hull value per transit. On monitoring,
the activation ladder is well suited to sudden local losses of throughput, blind to price shocks, and
by design silent about recoveries; a bunker-price indicator and a schedule-reliability series would
close the first gap. The next steps are a same-season baseline for the detector, the interview and
workshop programme in `workshop/`, and a second labeller for the extraction set.

# References

European Central Bank (2026). Euro foreign exchange reference rates, 13 November 2026. https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml (accessed 15 Nov 2026).

European Commission (2026). Reducing emissions from the shipping sector (page last updated 6 May 2026). https://climate.ec.europa.eu/eu-action/transport-decarbonisation/reducing-emissions-shipping-sector_en (accessed 15 Nov 2026).

EEX (2026). EU ETS primary market auction report 2026 (workbook). https://public.eex-group.com/eex/eua-auction-report/emission-spot-primary-market-auction-report-2026-data.xlsx (accessed 15 Nov 2026).

ENGINE (2026). Singapore's VLSFO price falls below $900/mt to around $890/mt, 4 November 2026. https://engine.online/news/singapores-vlsfo-price-falls-below-usd900-mt-to-around-usd890-mt-839c (accessed 15 Nov 2026).

ENGINE via Hellenic Shipping News (2026). Suez Canal Authority suspends container ship rebate, 8 April 2026. https://www.hellenicshippingnews.com/suez-canal-authority-suspends-container-ship-rebate/ (accessed 15 Nov 2026).

Halili, G. (2025). searoute 1.6.0 (Python package). https://pypi.org/project/searoute/1.6.0/ (accessed 15 Nov 2026).

IMF (2026). SDR valuation, rates as of 13 November 2026. https://www.imf.org/external/np/fin/data/rms_sdrv.aspx (accessed 15 Nov 2026).

IMF PortWatch (2026). Daily chokepoint transit and port call data. https://portwatch.imf.org/ (fetched 13 Oct 2026).

IMO (2022). Resolution MEPC.364(79), 2022 Guidelines on the method of calculation of the attained EEDI for new ships. https://wwwcdn.imo.org/localresources/en/KnowledgeCentre/IndexofIMOResolutions/MEPCDocuments/MEPC.364(79).pdf (accessed 15 Nov 2026).

Leth Agencies (2026). Newsletter, 10 June 2026. https://lethagencies.com/1203 (accessed 15 Nov 2026).

Lloyd's List via Kuehne+Nagel (2025). Suez Canal Authority extends container ship rebate, 5 August 2025. https://mykn.kuehne-nagel.com/news/article/suez-canal-authority-extends (accessed 15 Nov 2026).

MAN Energy Solutions (n.d.). Propulsion of 14,000 teu container vessels. https://www.man-es.com/docs/default-source/marine/tools/propulsion-of-14-000-teu-new-panamax-container-vessel.pdf?sfvrsn=58b2c2_14 (accessed 15 Nov 2026).

Maritime and Port Authority of Singapore (2024a). Media statement on vessels' extended waiting times for berths in the Port of Singapore, 30 May 2024 (accessed 15 Nov 2026).

Maritime and Port Authority of Singapore (2024b). MPA to permit night movement of line-towed container barges at Pasir Panjang Terminal, 4 September 2024 (accessed 15 Nov 2026).

Ministry of Transport, Singapore (2024). Written reply to Parliamentary Question on adequacy of Singapore's seaports to anticipate and manage severe cargo congestion, 2 July 2024 (accessed 15 Nov 2026).

Notteboom, T., Haralambides, H. and Cullinane, K. (2024). The Red Sea Crisis: ramifications for vessel operations, shipping networks, and maritime supply chains. *Maritime Economics & Logistics* 26, 1-20. https://doi.org/10.1057/s41278-024-00287-z

Reuters via Insurance Journal (2026). Houthis' Red Sea attacks prompt London insurers to widen high-risk zone, 30 July 2026. https://amp.insurancejournal.com/news/international/2026/07/30/879653.htm (accessed 15 Nov 2026).

Sea-Intelligence (2023-2025). Global Liner Performance press releases, July 2023 to January 2025; one URL per month in `data/inputs/schedule_reliability_glp.csv` (accessed 15 Nov 2026).

Suez Canal Authority (2023). "Transit Dues Rates" schedules applicable from the 15th of January 2024 (copy hosted by ISS). https://www.iss-shipping.com/wp-content/uploads/2023/10/Transit-Dues-Rates-Schedules.pdf (accessed 15 Nov 2026).

UNCTAD (2024). *Review of Maritime Transport 2024: Navigating maritime chokepoints*, chapters II and III. United Nations, Geneva. https://unctad.org/publication/review-maritime-transport-2024 (accessed 15 Nov 2026).

Veson Nautical via Hellenic Shipping News (2026). Bunkering at $1,000/MT: what I'm telling clients right now, 14 April 2026 (accessed 15 Nov 2026).

VesselsValue via Hellenic Shipping News (2026). Weekly vessel valuations report, 20 January 2026 (accessed 15 Nov 2026).
