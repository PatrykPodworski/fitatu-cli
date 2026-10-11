---
name: fitatu
description: Use when the user asks about their Fitatu food diary. Replace this with the questions and data this CLI answers.
---

# fitatu

`fitatu` reads the user's fitatu data and prints JSON. Run it with Bash.

## Commands

```sh
fitatu login         # the user runs this, never an agent (see Rules)
```

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

- `Unexpected error` (exit 1): a bug in the CLI. Show the full line to the user and stop.
- Any other exit 1: tell the user the second sentence and wait for them.
- Exit 2: bad arguments. The message names the fix (`Did you mean 'login'?`);
  correct the call and retry once.

## Privacy

The output is the user's data. Keep it in this conversation; put it in an issue,
commit, PR or any other external place only when the user asks.
