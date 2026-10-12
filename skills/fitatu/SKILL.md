---
name: fitatu
description: Use when the user asks about their Fitatu food diary — what they ate, meals, calories eaten, macros (protein, carbs, fat), fibre, sugar, salt, or per-kg intake (g/kg) — or wants to find a food in Fitatu, its ID, energy or measure.
---

# fitatu

`fitatu` reads the user's Fitatu data, searches Fitatu's foods, and prints plain text. Run it with Bash.

## Commands

```sh
fitatu day view [DATE]                    # one day's foods and totals; DATE: today | yesterday | YYYY-MM-DD, default today
fitatu day list --from DATE [--to DATE]   # each day in the range, oldest first; --to defaults to today
fitatu food search [PHRASE]               # foods matching PHRASE; without it, the foods the user used last
fitatu auth login                         # the user runs this, never an agent (see Rules)
```

`fitatu day view` prints a `date: YYYY-MM-DD` line and a table of the day's foods,
one row per food. The columns are `meal`, `name`, `quantity`, `measure` and the
nutrients, each named with its unit: `energy_kcal`, `carbohydrate_g`, `protein_g`,
`fat_g`, `fiber_g`, `sugars_g` and `salt_g`. The last row, `total`, sums the nutrients
over the day. `-` marks a missing name, quantity or measure; a missing nutrient is 0.
A day with nothing logged prints `no foods logged` under the date line and exits 0.

`fitatu day list` prints one such block per day, oldest first, with a blank line
between blocks. A range covers at most 31 days, counting both ends; split a longer
period into several calls.

`fitatu food search` searches Fitatu's catalog in the account's search language and
prints a table with one row per food: `id`, `type` (`product` or `recipe`), `name`,
`brand`, `energy_kcal`, and `measure`, the one measure the search returns with the
food, as `<measure id> <name> (<grams> g)`. Quote a multi-word phrase. `-` marks a
missing value or a food without a measure. No match prints `no foods found` and exits 0.

`--json` prints the same data as JSON: `{"date", "foods", "totals"}` from
`day view`, an array of those from `day list`, and an array of
`{"id", "type", "name", "brand", "energy", "measure": {"id", "name", "grams"}}`
from `food search`. `--raw` prints the service's response as JSON instead: the day
plan, an array of day plans from `day list`, or the search response from
`food search`.

`fitatu <noun> <verb> --help` lists every flag.

## Rules

- Never run `fitatu auth login` and never read `~/.fitatu` or the file in `FITATU_SESSION`:
  they hold the user's login. Every command logs in on its own when it needs to.
- Read the default text. Add `--json` only when a script parses the output.
- Start with the summary. Add `--raw` only when the field you need is missing from it:
  raw output is the full service response, many times larger.
- Nutrients are rounded to one decimal. Quote them as printed.
- A per-kg value, such as carbs in g/kg, needs the user's body weight: the latest
  weigh-in on or before that day. When the garmin skill is available, get it with
  `garmin weight` over a range that ends on that day, starting a few weeks earlier
  and reaching further back until it holds a weigh-in; otherwise ask the user.

## Output and errors

Results go to stdout: text by default, JSON with `--json` or `--raw`. An error is one
stderr line, `fitatu: <What happened.> <What to do.>`.

- `Unexpected error` or `Fitatu sent a response fitatu-cli could not read` (exit 1): a
  bug in the CLI or a change in Fitatu's API. Show the full line to the user and stop.
- Any other exit 1, such as a rate limit or no network: tell the user the second
  sentence and wait for them.
- Exit 2: bad arguments. The message names the fix (`Did you mean 'view'?`);
  correct the call and retry once.

## Privacy

The output is the user's data. Keep it in this conversation; put it in an issue,
commit, PR or any other external place only when the user asks.
