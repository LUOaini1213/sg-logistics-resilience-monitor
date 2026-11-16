# Industry interview guide: testing the causal loop diagram

A semi-structured guide for 45-60 minute interviews with people who see the links in the causal loop
diagram ([`outputs/maritime/figures/cld.svg`](../outputs/maritime/figures/cld.svg)) from the inside:
liner operations and network planning, port and terminal operations, freight forwarding, cargo
owners, marine insurance, chartering and bunker supply.

## Why interview

The diagram has 27 links. Seven are estimated from public data, five follow from the voyage-cost
model, eight are reported in a published source but not estimated here, and seven are assumed
([`outputs/maritime/cld_links.csv`](../outputs/maritime/cld_links.csv)). Interviews are the cheapest
way to test the assumed links, to put a sign, a size and a delay on them, and to learn which data an
operator would share when the ladder reaches Alert. They do not replace measurement: a link that
interviewees agree on is still recorded as *assumed* until data support it.

## Ground rules

- Explain the purpose, how notes are kept and who sees them; ask for consent to take notes.
- Record roles, not names or organisations. Do not record commercially sensitive figures unless the
  interviewee offers them for use, and then only as ranges.
- Ask about what the interviewee has seen, with dates, before asking for opinions.
- Use the link codes below (`from -> to`) in the notes so answers can be tallied against the diagram.

## Opening (5 minutes)

1. What is your role, and which decisions during the 2023-24 Red Sea diversions or the 2026
   disruptions did you take part in?
2. Which indicators or reports did you watch at the time, and how early did they tell you something?

## Routing and costs (10 minutes)

Links: `risk -> diversion`, `warrisk -> diversion`, `diversion -> distance`, `distance -> costs`.

3. When a service moved from Suez to the Cape, who decided, and what weighed most: crew safety, war-risk
   cover, schedule, cost or customers?
4. Was there a war-risk premium, as a share of hull value per transit, at which the loop would have
   gone back through Suez? The voyage model puts the break-even near 0.3% for its example ship
   ([`outputs/maritime/summary.json`](../outputs/maritime/summary.json)); how does that compare with
   your experience?
5. Which costs in the voyage model are missing or mis-sized: crew bonuses, cargo insurance, canal
   agency fees, extra ships chartered at short notice?

## Capacity, speed and blank sailings (10 minutes)

Links: `distance -> absorbed`, `absorbed -> capacity`, `rates -> speed`, `speed -> capacity`,
`bunker -> speed`, `rates -> blank`, `blank -> capacity` (loops B2 and B3).

6. How many ships were added to a weekly Asia-Europe loop when it moved to the Cape, and how quickly
   could they be found?
7. Did the network speed up? What bunker price or freight rate would make a carrier slow down again?
8. When rates fall, how soon are sailings blanked, and how much capacity does that remove?

## Reliability and port congestion (10 minutes)

Links: `capacity -> reliability`, `reliability -> bunching`, `bunching -> capacity`,
`bunching -> calls`, `bunching -> teu_call`, `bunching -> port`, `port -> bunching` (loops R1 and B1).

9. How did off-schedule arrivals turn into berth waiting at the hub ports you worked with? Did ships
   discharge more boxes per call to recover schedules?
10. Which measures shortened waits fastest (berths, yard, manpower, schedule coordination)? How long
    did each take to work? The model fits a build-up and recovery time of about 166 days for the
    2024 Singapore episode; does that match what you saw?
11. While ships waited at anchor, how much capacity did your network lose?

## Market and supply (5 minutes)

Links: `capacity -> rates`, `costs -> rates`, `rates -> newbuild`, `newbuild -> capacity`
(loops B4 and R3).

12. How much of the higher operating cost reached freight rates, and how quickly?
13. Did the diversion change ordering or chartering decisions, given the delivery pipeline?

## Cargo owners (5 minutes)

Links: `reliability -> frontload`, `frontload -> capacity` (loop R2).

14. Did unreliable transit times make you order earlier or hold more stock? By how much, and for
    which goods?

## Data and the activation ladder (5 minutes)

15. At Level 2 (Alert) the triggers ask operators for berth waiting times, yard utilisation and
    bookings ([`exercise/triggers.md`](../exercise/triggers.md)). Which of these could you share, how
    often, and under what conditions?
16. Which signal would have warned you earliest that it was not in this monitor?

## Recording sheet

For each link discussed, record one row:

| Link (`from -> to`) | Sign (+/-) | Size (range, unit) | Delay (range) | Evidence the interviewee cites | Confidence (low/medium/high) | Role |
|---|---|---|---|---|---|---|
| | | | | | | |

Tally the rows across interviews before the workshop ([`workshop_agenda.md`](workshop_agenda.md)).
A link moves from *assumed* to *cited* only with a source that can be referenced, and to *estimated*
only with data.
