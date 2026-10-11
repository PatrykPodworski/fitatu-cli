---
name: fitatu
description: Use when the user asks about their Fitatu food diary. Replace this with the questions and data this CLI answers.
---

# fitatu

`fitatu` reads the user's fitatu data and prints JSON. Run it with Bash.

## Commands

```sh
fitatu day [DATE]                    # one day's foods and totals; DATE: today | yesterday | YYYY-MM-DD, default today
fitatu day --from DATE [--to DATE]   # each day in the range, oldest first; --to defaults to today
fitatu login                         # the user runs this, never an agent (see Rules)
```

`fitatu day` prints `{"date", "foods", "totals"}`. Each food has `meal`, `name`,
`quantity`, `measure` and its nutrients: `energy` in kcal; `carbohydrate`, `protein`,
`fat`, `fiber`, `sugars` and `salt` in grams. `totals` sums the nutrients over the day.
A missing nutrient is 0. A day with nothing logged has `foods: []`, every total 0, and
exits 0. `--raw` prints the service's day plan instead.

With `--from`, `fitatu day` prints a JSON array of those day objects, one per day,
oldest first, or of the raw day plans with `--raw`. A range covers at most 31 days,
counting both ends; split a longer period into several calls. Give either a DATE or
`--from`/`--to`, not both.

`fitatu <command> --help` lists every flag.

## Rules

- Never run `fitatu login`, never read `~/.fitatu` or the file in `FITATU_SESSION`, and
  never print `FITATU_APP_UUID`: they hold the user's login. Every command logs in on
  its own when it needs to.
- Start with the summary. Add `--raw` only when the field you need is missing from it:
  raw output is the full service response, many times larger.
- Summary floats are rounded to two decimals. Quote them as printed.

## Output and errors

Results are JSON on stdout. An error is one stderr line,
`fitatu: <What happened.> <What to do.>`.

- `Unexpected error` or `Fitatu sent a response fitatu-cli could not read` (exit 1): a
  bug in the CLI or a change in Fitatu's API. Show the full line to the user and stop.
- Any other exit 1, such as a rate limit or no network: tell the user the second
  sentence and wait for them.
- Exit 2: bad arguments. The message names the fix (`Did you mean 'login'?`);
  correct the call and retry once.

## Privacy

The output is the user's data. Keep it in this conversation; put it in an issue,
commit, PR or any other external place only when the user asks.
