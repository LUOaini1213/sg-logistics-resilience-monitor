# Half-day workshop: mapping maritime disruption around one causal loop diagram

A 3.5-hour, in-person workshop for 12-24 participants from shipping lines, port and terminal
operations, freight forwarding, cargo owners, insurers, government agencies and research. It is built
around the causal loop diagram ([`outputs/maritime/figures/cld.svg`](../outputs/maritime/figures/cld.svg))
and complements the tabletop exercise in [`exercise/`](../exercise/), which tests the activation
ladder rather than the causal structure.

## Objectives

1. **Check the structure.** Agree, dispute or add links and loops, with a sign and a delay for each.
2. **Size the assumed links.** Turn the seven links marked *assumed* into ranges that can replace the
   author's assumptions, or into a request for data.
3. **Test the scenarios.** Challenge the assumed distributions of the three forward scenarios
   ([`data/inputs/scenario_parameters.csv`](../data/inputs/scenario_parameters.csv)).
4. **Agree on data sharing.** List what each organisation could share when the ladder reaches Alert.

## Before the workshop

- Run the interviews in [`interview_guide.md`](interview_guide.md) (6-10 are enough) and tally the
  recording sheets by link.
- Print the diagram at A1 with a code on each link (from [`outputs/maritime/cld_links.csv`](../outputs/maritime/cld_links.csv)),
  one card per link, and a one-page summary of each scenario's results
  ([`outputs/maritime/scenario_ladder.csv`](../outputs/maritime/scenario_ladder.csv),
  [`outputs/maritime/scenario_costs.csv`](../outputs/maritime/scenario_costs.csv)).

## Agenda

| Time | Session | Format | Output |
|---|---|---|---|
| 0:00 | Welcome, objectives, ground rules (no attribution of statements to organisations) | Plenary | |
| 0:10 | What the data showed in 2023-24: diversion, reliability and the Singapore episode, and how well the model reproduces them ([`figures/sd_fit.svg`](../outputs/maritime/figures/sd_fit.svg)) | Briefing, 15 min + questions | Shared picture of the evidence |
| 0:35 | Gallery walk on the A1 diagram: each participant marks every link agree / disagree / unsure and adds missing links on sticky notes | Individual | Annotated diagram |
| 1:05 | Break | | |
| 1:20 | Breakout 1, loop deep-dives in four groups: R1 congestion spiral with B1 port response; B2 blank sailings with B3 speed-up; B4 fleet supply with R3 cost pass-through; R2 early ordering. Each group fills sign, size range, delay and evidence for its links, starting from the interview tally | Groups of 3-6 | Link cards with ranges |
| 2:05 | Breakout 2, scenario stress test: each group takes one scenario (Gulf escalation, Singapore Strait incident, Red Sea reopening), judges the assumed distributions and the ladder outcome, and proposes changes with reasons | Same groups, rotated | Revised ranges, written reasons |
| 2:45 | Plenary: which assumed links now have support, which need data; what each organisation could share at Alert, how often and how | Plenary | Data-sharing list, open questions |
| 3:15 | Close: next steps, owners, feedback | Plenary | Action list |
| 3:30 | End | | |

## Roles

- **Facilitator**: keeps time, keeps discussion on links and evidence rather than positions.
- **Modeller**: explains how a link or a range would enter the model, and what it would change.
- **Note-taker per group**: fills the link cards and records disagreements as well as agreements.

## After the workshop

- Update `data/inputs/scenario_parameters.csv` and the link statuses in `src/lsr/maritime/cld.py`
  only where a referenceable source or data support the change; record workshop judgements as
  *ASSUMPTION* with the date of the workshop.
- Rerun `python run_all.py` and circulate the changed results with a short note of what moved.
