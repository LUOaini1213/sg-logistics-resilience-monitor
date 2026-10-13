# Scenario and injects

**The scenario is fictional.** Dates are given as exercise days (D+0, D+7, …). The magnitudes are taken
from the 2023–24 Red Sea episode in this repository's data, so players can compare them with the
dashboard; the figures marked "real" come from the cited source.

## Starting picture (D+0)

- The dashboard is at Level 0 (Normal).
- Bab el-Mandeb: about 520 transits a week. Real: 522 in the 7 days to 10 Dec 2023 (IMF PortWatch).
- Cape of Good Hope: about 320 a week. Real: 318 in the same week.
- Singapore container-ship calls: about 310 a week. Real: 313.
- MPA container throughput: about 3.4 million TEU a month. Real: 3.42 million in December 2023 (MPA).

## Move 1: the Red Sea route closes (D+0 to D+21)

| Inject | Time | Content |
|---|---|---|
| 1.1 | D+0 | Attacks on merchant ships in the southern Red Sea. Two of the largest container lines announce they are pausing Red Sea transits. (Real precedent: Maersk and Hapag-Lloyd paused on 15 Dec 2023, Argus.) |
| 1.2 | D+8 | Dashboard: Bab el-Mandeb in alarm, Level 1 Watch. In the real 2023 run the Bab el-Mandeb alarm was readable 15 days after the pause. |
| 1.3 | D+14 | Bab el-Mandeb 307 a week, Suez 347, Cape of Good Hope 508 (real values for the week to 14 Jan 2024). Suez and Cape now in alarm. Dashboard: **Level 2 Alert**. |
| 1.4 | D+18 | A food importer calls: two Europe-origin consignments of dairy and infant formula are now 2–3 weeks late. |

**Decisions**

1. Does the team accept Level 2? Who convenes the contact group, and by when?
2. What do you ask carriers and the port for that the dashboard cannot show?
3. Which essential-goods categories depend most on the Asia–Europe route? Who holds the inventory-cover numbers?

**Facilitator notes for empty tables (assumed for the exercise, not measured here).** Carriers: most Asia–Europe services move to the Cape routing, adding
about 10–14 days per voyage; arrival windows in Asia become less reliable. Shippers: cover for most chilled
products is 2–4 weeks.

## Move 2: congestion arrives in Singapore (D+60 to D+170)

| Inject | Time | Content |
|---|---|---|
| 2.1 | D+90 | Singapore container-ship calls fall to about 265 a week while monthly throughput keeps rising. Dashboard: Singapore container calls in alarm. (Real: the alarm was readable on 28 Mar 2024.) |
| 2.2 | D+120 | TEU handled per call reaches 3,200, up from 2,700 before the diversions (real: 2,710 in Dec 2023 and 3,176 in May 2024). |
| 2.3 | D+165 | Port authority statement: average waiting time for container vessels is two to three days where arrivals cannot be rescheduled; containers handled per vessel have increased. (Real: MPA media statement, 30 May 2024.) |
| 2.4 | D+170 | A forwarder reports that a feeder line will skip the next two calls to recover its schedule; transhipment boxes for Indonesian ports roll over by a week. |

**Decisions**

1. When the TEU-per-call alarm lands (Level 3 Activate review), does the team activate the sector plan?
   What would make you say no?
2. Which measures are within reach in weeks, not months? For example: yard and berth priority for essential
   cargo, extended gate hours, temporary storage outside the port, customs facilitation.
3. What information-sharing rhythm do operators accept (daily, twice weekly), and who consolidates it?

**Facilitator notes.** Real context: the Minister for Transport reported that about 90% of container vessels
were arriving off-schedule, against about 77% for 2023 (MOT written reply, 2 Jul 2024). MPA reported the
average wait fell below one day in July 2024 after more berth and yard capacity was brought into use and
schedules were coordinated with carriers (MPA, 4 Sep 2024).

## Move 3: collision in the Singapore Strait (D+175 to D+190)

| Inject | Time | Content |
|---|---|---|
| 3.1 | D+175 | Fictional: a container ship and a product tanker collide in the eastbound lane of the Singapore Strait traffic separation scheme. Oil is leaking; nobody is hurt. |
| 3.2 | D+175 +4 h | Fictional: the port authority restricts traffic in part of the eastbound lane for an expected 72 hours while spill response craft work. Two berths near the incident are closed. (Real precedent of a smaller incident: on 14 June 2024 a dredger struck a bunker tanker at a container terminal berth; MPA reported no disruption to navigation in the traffic separation scheme.) |
| 3.3 | D+177 | Fictional: 40 vessels are waiting at the eastern approaches. Two carriers ask to swap their Singapore calls to Tanjung Pelepas. |
| 3.4 | D+182 | Dashboard: Malacca transits in alarm (fictional reading 1,350 a week against a 2025 median of 1,644). Level stays at 3. |
| 3.5 | D+186 | A pharmaceutical distributor needs one temperature-controlled container released within 48 hours for hospital supply. |

**Decisions**

1. Two disruptions now overlap. Is it one coordination cell or two? Who leads communications to industry?
2. Which cargo gets priority when berths reopen? Who decides, and how is it communicated?
3. Would air cargo or sea-air through Changi relieve the most urgent flows? What capacity is there?

## Stand-down (D+190)

For each level, players agree what must be true to step down (see `triggers.md`: trigger clear for 14 days
plus agreement of the contact group), and who signs off.

## Sources for the real figures

- IMF PortWatch daily chokepoint and port data (this repository, `data/raw/`).
- MPA monthly container throughput via data.gov.sg (this repository, `data/raw/`).
- Argus, 15 Dec 2023: https://www.argusmedia.com/en/news-and-insights/latest-market-news/2519660-maersk-hapag-lloyd-pause-shipments-through-the-red-sea
- MPA, 30 May 2024: https://www.mpa.gov.sg/media-centre/details/in-response-to-media-queries-on--vessels--extended-waiting-times-for-berths-in-the-port-of-singapore
- MOT, 2 Jul 2024: https://www.mot.gov.sg/news-resources/newsroom/written-reply-to-parliamentary-question-on-adequacy-of-singapore-s-seaports-to-anticipate-and-manage-severe-cargo-congestion/
- MPA, 4 Sep 2024: https://mpa.gov.sg/media-centre/details/mpa-to-permit-night-movement-of-line-towed-container-barges-at-pasir-panjang-terminal
- 14 June 2024 incident (Ship & Bunker, citing MPA): https://shipandbunker.com/news/apac/590855-fuel-spill-reported-in-singapore-after-dredger-hits-bunker-vessel
