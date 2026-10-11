---
name: fitatu
description: Use when the user asks about their Fitatu food diary — what they ate, meals, calories eaten, macros (protein, carbs, fat), fibre, sugar, salt, or per-kg intake (g/kg).
---

# fitatu

`fitatu` reads the user's Fitatu data and prints JSON. Run it with Bash.

## Commands

```sh
fitatu day view [DATE]                    # one day's foods and totals; DATE: today | yesterday | YYYY-MM-DD, default today
fitatu day list --from DATE [--to DATE]   # each day in the range, oldest first; --to defaults to today
fitatu auth login                         # the user runs this, never an agent (see Rules)
```

`fitatu day view` prints `{"date", "foods", "totals"}`. Each food has `meal`, `name`,
`quantity`, `measure` and its nutrients: `energy` in kcal; `carbohydrate`, `protein`,
`fat`, `fiber`, `sugars` and `salt` in grams. `totals` sums the nutrients over the day.
A missing nutrient is 0. A day with nothing logged has `foods: []`, every total 0, and
exits 0. `--raw` prints the service's day plan instead.

`fitatu day list` prints a JSON array of those day objects, one per day, oldest
first, or of the raw day plans with `--raw`. A range covers at most 31 days, counting
both ends; split a longer period into several calls.

`fitatu <noun> <verb> --help` lists every flag.

## Rules

- Never run `fitatu auth login` and never read `~/.fitatu` or the file in `FITATU_SESSION`:
  they hold the user's login. Every command logs in on its own when it needs to.
- Start with the summary. Add `--raw` only when the field you need is missing from it:
  raw output is the full service response, many times larger.
- Summary floats are rounded to two decimals. Quote them as printed.
- A per-kg value, such as carbs in g/kg, needs the user's body weight: the latest
  weigh-in on or before that day. When the garmin skill is available, get it with
  `garmin weight` over a range that ends on that day, starting a few weeks earlier
  and reaching further back until it holds a weigh-in; otherwise ask the user.

## Output and errors

Results are JSON on stdout. An error is one stderr line,
`fitatu: <What happened.> <What to do.>`.

- `Unexpected error` or `Fitatu sent a response fitatu-cli could not read` (exit 1): a
  bug in the CLI or a change in Fitatu's API. Show the full line to the user and stop.
- Any other exit 1, such as a rate limit or no network: tell the user the second
  sentence and wait for them.
- Exit 2: bad arguments. The message names the fix (`Did you mean 'view'?`);
  correct the call and retry once.

## Privacy

The output is the user's data. Keep it in this conversation; put it in an issue,
commit, PR or any other external place only when the user asks.
