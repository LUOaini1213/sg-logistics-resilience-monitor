# Codebook: cause-effect links in maritime disruption texts

Version 1 (2026-11-15). Used both to label the reference set (`reference_links.csv`) and, word for word,
in the prompt of the local language model (`scripts/run_llm_extraction.py`). The variables follow the
causal loop diagram (`outputs/maritime/figures/cld.svg`).

**Who labelled the reference set.** The reference labels were produced with this codebook by the
repository author's tooling (an AI coding assistant working for the author), not by independent human
annotators. There is one labeller, so no inter-annotator agreement can be reported. Precision and recall
against this set measure agreement with one careful reading, not accuracy against ground truth.

## Variables

| Variable | Covers | Higher means |
|---|---|---|
| `red_sea_disruption` | Attacks or security threats in the Red Sea; disruptions to the Red Sea, Suez Canal or Panama Canal routes, or to "shipping routes" in general | more disruption |
| `diversion` | Ships rerouted or diverted, around the Cape of Good Hope or onto other longer routes | more diversion |
| `distance_time` | Sailing distance, transit or voyage time, ton-miles, "longer routes" | longer |
| `capacity_demand` | Demand for ships or shipping capacity, including capacity needed because routes are longer | more demand |
| `shipping_capacity` | Available or effective shipping capacity; excess capacity or overcapacity | more capacity available |
| `schedule_reliability` | Ships arriving on schedule. Off-schedule arrivals or disrupted arrival schedules mean *lower* reliability | more reliable |
| `port_congestion` | Port congestion, bottlenecks, vessel bunching, berth waiting time, time ships spend in port | more congestion |
| `port_capacity` | Port handling capacity: berths, yards, cranes, manpower, reactivated terminals | more capacity |
| `container_volume` | Containers handled at a port; demand on container handling at a port | more volume |
| `containers_per_call` | Containers handled per vessel or per call | more per call |
| `freight_rates` | Freight rates, container shipping rates, shipping charges paid by cargo owners | higher |
| `charter_rates` | Time-charter rates for ships; the charter market | higher |
| `operating_costs` | Carriers' costs: fuel, crew wages, chartering, insurance | higher |
| `vessel_speed` | Ship sailing speed | faster |
| `fuel_emissions` | Fuel consumption and carbon emissions | more |
| `front_loading` | Shippers bringing forward export schedules or orders | more |
| `consumer_prices` | Consumer prices | higher |

## Rules

1. A link needs causal language in the passage that connects a cause to an effect: for example
   *caused, led to, resulted in, due to, as a result, driven by, prompted, contributed to, translate
   into, adds, meant that, compounded by*. Two facts reported side by side, a date sequence or a number
   alone are not links.
2. Both ends must map to a variable above. If either end does not (for example ship demolitions or
   real GDP), there is no link.
3. Direction runs from cause to effect as the passage states it.
4. Polarity is `+` when the effect moves in the same direction as the cause, `-` when it moves the
   opposite way, judged with the "Higher means" column (more off-schedule arrivals is *lower*
   `schedule_reliability`).
5. A chain "A caused B, which caused C" gives A -> B and B -> C, not A -> C, unless the passage also
   states A -> C.
6. A cause written as two variables joined by "and" gives one link from each.
7. Expected or possible effects (*could lead to, are likely to, to help alleviate*) count as links.
8. No link from a variable to itself. Each cause-effect pair counts once per passage.
9. If the passage gives no direction for the effect (*affected, altered, impacted*), there is no link.
10. Evidence: the shortest verbatim span that shows the link, at most 14 words; two verbatim
    fragments may be joined with " ... ".

## Scoring

A predicted link is a true positive when the same directed (cause, effect) pair is in the reference set
for the same passage. Precision = true positives / predicted links; recall = true positives /
reference links. Polarity agreement is reported separately, over the true positives. Links with a
variable outside the codebook count as false positives.
