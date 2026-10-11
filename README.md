# fitatu-cli

`fitatu` reads your Fitatu food diary and prints it as plain text, or as JSON with
`--json`.

**Unofficial.** This project is not affiliated with Fitatu. It uses the private API of
the Fitatu web app, so it may break when Fitatu changes that API.

## Install

```sh
uv tool install git+https://github.com/PatrykPodworski/fitatu-cli
```

## Log in

1. Set your Fitatu account email:

   ```sh
   export FITATU_EMAIL=you@example.com
   ```

2. Store your Fitatu password in the macOS Keychain. The command asks for the password:

   ```sh
   security add-generic-password -s fitatu -a you@example.com -w
   ```

3. Log in:

   ```sh
   fitatu auth login
   ```

`fitatu auth login` saves the session to `~/.fitatu/session.json`, or to the file in
`FITATU_SESSION` when that variable is set. A token lasts 1 hour. Other commands
refresh it, or log in again, when they need to.

Without a Keychain (on any system other than macOS), run `fitatu auth login` on a Mac, copy
the session file to the other machine, and set `FITATU_SESSION` to its path if it is
not at `~/.fitatu/session.json`.

## Dates

A `DATE` is `today`, `yesterday` or `YYYY-MM-DD`.

## Commands

### `fitatu day view [DATE]`

Prints the foods logged on one day and the day totals. `DATE` defaults to `today`.

```sh
fitatu day view 2026-10-11
```

```text
date: 2026-10-11
meal       name          quantity  measure  energy_kcal  carbohydrate_g  protein_g  fat_g  fiber_g  sugars_g  salt_g
Breakfast  Oat porridge  1         bowl     320.0        54.2            11.0       6.5    7.1      3.4       0.1
Lunch      Lentil soup   300       g        270.0        38.0            16.5       4.2    9.0      5.1       1.8
total                                       590.0        92.2            27.5       10.7   16.1     8.5       1.9
```

The first line is the date. A table of foods follows, one row per food, with a `total`
row at the end. `-` marks a missing name, quantity or measure. A missing nutrient
counts as 0. A day with nothing logged prints the date line and `no foods logged`.

With `--json`, it prints the same data as JSON:

```json
{
  "date": "2026-10-11",
  "foods": [
    {
      "meal": "Breakfast",
      "name": "Oat porridge",
      "quantity": 1,
      "measure": "bowl",
      "energy": 320,
      "carbohydrate": 54.2,
      "protein": 11.0,
      "fat": 6.5,
      "fiber": 7.1,
      "sugars": 3.4,
      "salt": 0.1
    },
    {
      "meal": "Lunch",
      "name": "Lentil soup",
      "quantity": 300,
      "measure": "g",
      "energy": 270,
      "carbohydrate": 38.0,
      "protein": 16.5,
      "fat": 4.2,
      "fiber": 9.0,
      "sugars": 5.1,
      "salt": 1.8
    }
  ],
  "totals": {
    "energy": 590.0,
    "carbohydrate": 92.2,
    "protein": 27.5,
    "fat": 10.7,
    "fiber": 16.1,
    "sugars": 8.5,
    "salt": 1.9
  }
}
```

A day with nothing logged has `"foods": []` and every total 0.

### `fitatu day list --from DATE --to DATE`

Prints one day block per day, oldest first, with a blank line between blocks. `--to`
defaults to `today`. A range covers at most 31 days, counting both ends.

```sh
fitatu day list --from 2026-10-09 --to 2026-10-10
```

```text
date: 2026-10-09
meal       name          quantity  measure  energy_kcal  carbohydrate_g  protein_g  fat_g  fiber_g  sugars_g  salt_g
Breakfast  Oat porridge  1         bowl     320.0        54.2            11.0       6.5    7.1      3.4       0.1
total                                       320.0        54.2            11.0       6.5    7.1      3.4       0.1

date: 2026-10-10
no foods logged
```

With `--json`, it prints a JSON array of the day objects `fitatu day view --json`
prints.

### `fitatu auth login`

Logs in as `FITATU_EMAIL` with the Keychain password and prints the path of the saved
session.

```sh
fitatu auth login
```

```text
Saved the session to /Users/you/.fitatu/session.json.
```

With `--json`, it prints `{"session": "<path>"}`.

`fitatu <noun> <verb> --help` lists every option.

## Units

- `energy` is in kcal.
- `carbohydrate`, `protein`, `fat`, `fiber`, `sugars` and `salt` are in grams.
- Nutrient values are rounded to one decimal.
- In text output, each nutrient column names its unit: `energy_kcal`,
  `carbohydrate_g` and so on.

There is no sodium output. Fitatu sends sodium per item in milligrams, and many items
do not have it, so a daily sodium sum is too low. Use `salt` instead.

## Raw output

`fitatu day view --raw` prints Fitatu's response for the day unchanged, as JSON. With
`fitatu day list --raw`, it prints an array of those responses. Use it when you need a
field the summary does not have. `--raw` prints JSON without `--json`.

## Output and exit codes

Results are plain text on stdout, or JSON with `--json` or `--raw`, with exit code 0.
An error is one line on stderr, `fitatu: <What happened.> <What to do.>`:

- Exit 1: a Fitatu, login or data error.
- Exit 2: bad arguments.

To see the full traceback of an exit 1 error, put `--debug` before the command, for
example `fitatu --debug day view`.

| Exit | Message |
| --- | --- |
| 1 | `FITATU_EMAIL is not set. Run 'export FITATU_EMAIL=you@example.com' with your Fitatu account email.` |
| 1 | `No Keychain password for account <email> (service 'fitatu'). Add it with 'security add-generic-password -s fitatu -a <email> -w'.` |
| 1 | `Logging in to Fitatu reads the password from the macOS Keychain, which is not available here. Log in on a Mac and copy ~/.fitatu/session.json to this machine, or set FITATU_SESSION to a copied session file.` |
| 1 | `Logging in to Fitatu reads the password from the macOS Keychain, which is not available here. Copy a session file from a Mac that ran 'fitatu auth login' and point FITATU_SESSION at it.` |
| 1 | `Fitatu rejected the login for <email>. Check the Keychain password for service 'fitatu'.` |
| 1 | `Fitatu did not accept a fresh login. Run 'fitatu auth login'; if it keeps failing, the API may have changed — report it at https://github.com/PatrykPodworski/fitatu-cli/issues.` |
| 1 | `Fitatu is rate-limiting requests from this machine. Wait a few minutes and try again.` |
| 1 | `Could not reach Fitatu (<reason>). Check your internet connection and try again.` |
| 1 | `Fitatu sent a response fitatu-cli could not read. Fitatu may have changed its API; rerun with --debug and report it at https://github.com/PatrykPodworski/fitatu-cli/issues.` |
| 1 | `Unexpected error (<reason>). Rerun with --debug and report it at https://github.com/PatrykPodworski/fitatu-cli/issues.` |
| 2 | `No command given. Run 'fitatu <command>', one of: auth, day.` |
| 2 | `No command given. Run 'fitatu <noun> <command>', one of: <verbs>.` |
| 2 | `Unknown command '<name>'. Did you mean '<command>'?` |
| 2 | `Unknown command '<name>'. Run 'fitatu <command>', one of: auth, day.` |
| 2 | `Unknown command '<name>'. Run 'fitatu <noun> <command>', one of: <verbs>.` |
| 2 | `Unknown option '<option>' for 'fitatu <noun> <verb>'. Did you mean '<option>'? Run 'fitatu <noun> <verb> --help' for all options.` |
| 2 | `Unexpected argument '<argument>' for 'fitatu <noun> <verb>'. Run 'fitatu <noun> <verb> --help' for all options.` |
| 2 | `Option '<option>' goes after the command. Run 'fitatu <noun> <verb> <option>'.` |
| 2 | `Option '<option>' needs a value. Run 'fitatu day list --help'.` |
| 2 | `Option '<option>' takes no value. Remove '=<value>'.` |
| 2 | `Invalid date '<value>'. Use today, yesterday or YYYY-MM-DD.` |
| 2 | `Missing --from for 'fitatu day list'. Run 'fitatu day list --help'.` |
| 2 | `--to <date> is before --from <date>. Give a --to on or after --from.` |
| 2 | `The range covers <n> days; the limit is 31. Split it into shorter ranges.` |

Values in angle brackets are filled in from your input or the failure. The
`Did you mean` part of an unknown option appears only when a close match exists.

## How it works

- `fitatu` calls the same API as the Fitatu web app. That API is not documented; the
  requests were copied from the web app.
- The `API-Secret` header value is committed to this repository on purpose
  ([#3](https://github.com/PatrykPodworski/fitatu-cli/issues/3)). It is the web app's
  public client key: the web app sends it to every browser, and two public third-party
  clients already publish it.
- The `APP-UUID` header value is committed for the same reason
  ([#34](https://github.com/PatrykPodworski/fitatu-cli/issues/34)). It identifies the
  web app, not a device: the web app ships it in its public bundle and every browser
  sends it. Fitatu rejects a login with a UUID it does not know.
- Day totals are the sums of the nutrients Fitatu sends for each item. Recipe items
  are not rescaled, because Fitatu already sends their nutrients for the portion eaten.
  The totals match the day total in the app
  ([#5](https://github.com/PatrykPodworski/fitatu-cli/issues/5)).
- If Fitatu changes its API, `fitatu` stops working until the code is updated. To
  update it, capture the web app's requests again in the browser dev tools and compare
  them with the code.

## Use from an agent

Link the skill into your Claude Code skills folder from the repository root:

```sh
ln -s "$PWD/skills/fitatu" ~/.claude/skills/fitatu
```

The skill tells an agent which commands answer which questions, how to read the output
and errors, and that it must never run `fitatu auth login` or read the session file.

## Development

CI runs these checks on every pull request and push to `main`:

```sh
uv sync
uv run mypy
uv run pytest
uv run ruff check
uv run ruff format --check
uv run typos
uv run vulture
uv run deptry src
uv run zizmor .github
uv run mutmut run
```

`pytest` fails when branch coverage of `src/` drops below 90%. CI fails when the
`mutmut` score drops below 80%.
