# Activation ladder and triggers

The ladder is computed daily by the monitor (`outputs/posture_daily.csv`). Each day uses only data already
published by then: PortWatch values count from 7 days after the week they describe, MPA monthly figures from
15 days after month end, Changi air cargo from 30 days, and the GSCPI from 5 days.

An indicator is **in alarm** when its robust z-score is at least 2.5 for 3 consecutive days (daily series)
or one month (monthly series). The z-score compares the latest value with the median of the previous year
of normal values; see the README for the method and the backtest.

| Level | Trigger (all automatic) | Who is told, by when | Expected actions |
|---|---|---|---|
| 0 Normal | No indicator in alarm | Weekly dashboard to the team | Routine monitoring |
| 1 Watch | Any one indicator in alarm | Team lead same day | Check the cause against news and operator contacts within 2 working days; note it in the watch log. No external activation. |
| 2 Alert | Two or more route indicators in alarm, **or** one route indicator plus a Singapore or regional port indicator | Agency management and partner agencies within 24 h | Convene the industry and agency contact group within 3 working days; ask operators for the data the dashboard cannot see (berth waiting time, yard utilisation, bookings); brief essential-goods importers on lead-time risk. |
| 3 Activate review | Alert, **plus** a Singapore monthly outcome in alarm (container throughput, TEU per call, vessel arrivals, cargo throughput, air cargo) | Senior management within 24 h | Decide whether to activate the sector plan: coordination cell, information-sharing rhythm (for example twice weekly), review of measures such as berth or yard priority for essential cargo and customs facilitation. |

**Stepping down.** A level steps down when its trigger has been clear for 14 consecutive days and the
contact group agrees. A *sustained* shift (an alarm active for 182 days) is re-baselined by the detector and
stops counting; the team should then decide whether the new normal needs a standing measure rather than a
crisis response.

## Indicator to question map

| Indicator | Source | What a move means | Question to ask partners |
|---|---|---|---|
| Bab el-Mandeb and Suez transits (drop), Cape of Good Hope transits (rise) | IMF PortWatch | Asia–Europe services diverting around Africa: longer voyages, bunched arrivals in Asia | Which services have changed rotation? Expected arrival bunching at Singapore? |
| Strait of Hormuz transits (drop) | IMF PortWatch | Gulf energy and container trade disrupted | Fuel, petrochemical and Gulf transhipment exposure? |
| Malacca Strait transits (drop) | IMF PortWatch | Regional traffic falls; check for incident, weather or data gap | Any navigation restriction or incident? |
| Panama Canal, Taiwan Strait (drop) | IMF PortWatch | Trans-Pacific or intra-Asia disruption; Taiwan Strait drops cluster in typhoon season | Knock-on to Singapore services? |
| Singapore container-ship calls (drop) | IMF PortWatch | Fewer calls; with high TEU per call, a sign of bunching or skipped calls | Berth waiting time? Skipped calls? |
| TEU per container-ship call (rise) | MPA ÷ PortWatch | More boxes handled per call: carriers discharging more at Singapore to recover schedules | Yard utilisation? Dwell time? |
| Port Klang and Tanjung Pelepas calls (drop) | IMF PortWatch | Regional diversion or regional congestion | Are calls moving to or from Singapore? |
| Container throughput, vessel arrivals, cargo (drop) | MPA | Outcome: volume actually lost | Which trades? Temporary or structural? |
| Changi air cargo (drop) | SingStat (CAAS) | Air capacity or demand shock | Sea-air substitution possible? |
| GSCPI (above 1.0) | New York Fed | Global supply chain pressure is high | Context only; never triggers activation alone |

## Known limits of the triggers

- The ladder sees ships and boxes, not berth waiting times, yard occupancy or inventories. Level 2 exists to
  ask operators for those.
- In the 2020–2026 backtest the monitor raised 0.79 false alarms per indicator-year on the holdout period
  (see the README). Watch is meant to be cheap: a check, not a meeting.
- Monthly Singapore outcomes arrive 2–6 weeks after the month they describe, so Level 3 usually confirms a
  disruption rather than anticipating it.
