# fitatu-cli

`fitatu` reads your Fitatu food diary and prints it as JSON.

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

3. Set `FITATU_APP_UUID`. Fitatu accepts a login only from a device UUID it already
   knows for your account. Open the Fitatu web app, open the browser dev tools, and
   copy the `APP-UUID` request header from any request in the Network tab:

   ```sh
   export FITATU_APP_UUID=<value>
   ```

4. Log in:

   ```sh
   fitatu login
   ```

`fitatu login` saves the session to `~/.fitatu/session.json`, or to the file in
`FITATU_SESSION` when that variable is set. A token lasts 1 hour. Other commands
refresh it, or log in again, when they need to.

Without a Keychain (on any system other than macOS), run `fitatu login` on a Mac, copy
the session file to the other machine, and set `FITATU_SESSION` to its path if it is
not at `~/.fitatu/session.json`.

## Dates

A `DATE` is `today`, `yesterday` or `YYYY-MM-DD`.

## Commands

### `fitatu day [DATE]`

Prints the foods logged on one day and the day totals. `DATE` defaults to `today`.

```sh
fitatu day 2026-10-11
```

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

A missing nutrient counts as 0. A day with nothing logged has `"foods": []` and every
total 0.

### `fitatu day --from DATE --to DATE`

Prints a JSON array with one day object per day, oldest first. `--to` defaults to
`today`. A range covers at most 31 days, counting both ends. Give either a `DATE` or
`--from`/`--to`, not both.

```sh
fitatu day --from 2026-10-09 --to 2026-10-10
```

```json
[
  {
    "date": "2026-10-09",
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
      }
    ],
    "totals": {
      "energy": 320.0,
      "carbohydrate": 54.2,
      "protein": 11.0,
      "fat": 6.5,
      "fiber": 7.1,
      "sugars": 3.4,
      "salt": 0.1
    }
  },
  {
    "date": "2026-10-10",
    "foods": [
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
      "energy": 270.0,
      "carbohydrate": 38.0,
      "protein": 16.5,
      "fat": 4.2,
      "fiber": 9.0,
      "sugars": 5.1,
      "salt": 1.8
    }
  }
]
```

### `fitatu login`

Logs in as `FITATU_EMAIL` with the Keychain password and prints the path of the saved
session.

```sh
fitatu login
```

```json
{
  "session": "/Users/you/.fitatu/session.json"
}
```

`fitatu <command> --help` lists every option.

## Units

- `energy` is in kcal.
- `carbohydrate`, `protein`, `fat`, `fiber`, `sugars` and `salt` are in grams.
- Nutrient values are rounded to one decimal.

There is no sodium output. Fitatu sends sodium per item in milligrams, and many items
do not have it, so a daily sodium sum is too low. Use `salt` instead.

## Raw output

`fitatu day --raw` prints Fitatu's response for the day unchanged. With `--from`, it
prints an array of those responses. Use it when you need a field the summary does not
have.

## Output and exit codes

Results are JSON on stdout, with exit code 0. An error is one line on stderr,
`fitatu: <What happened.> <What to do.>`:

- Exit 1: a Fitatu, login or data error.
- Exit 2: bad arguments.

To see the full traceback of an exit 1 error, put `--debug` before the command, for
example `fitatu --debug day`.

| Exit | Message |
| --- | --- |
| 1 | `FITATU_EMAIL is not set. Run 'export FITATU_EMAIL=you@example.com' with your Fitatu account email.` |
| 1 | `FITATU_APP_UUID is not set. Copy the APP-UUID request header from the Fitatu web app (browser dev tools, Network tab) and run 'export FITATU_APP_UUID=<value>'.` |
| 1 | `No Keychain password for account <email> (service 'fitatu'). Add it with 'security add-generic-password -s fitatu -a <email> -w'.` |
| 1 | `Logging in to Fitatu reads the password from the macOS Keychain, which is not available here. Log in on a Mac and copy ~/.fitatu/session.json to this machine, or set FITATU_SESSION to a copied session file.` |
| 1 | `Logging in to Fitatu reads the password from the macOS Keychain, which is not available here. Copy a session file from a Mac that ran 'fitatu login' and point FITATU_SESSION at it.` |
| 1 | `Fitatu rejected the login for <email>. Check the Keychain password for service 'fitatu' and FITATU_APP_UUID.` |
| 1 | `Fitatu did not accept a fresh login. Run 'fitatu login'; if it keeps failing, the API may have changed — report it at https://github.com/PatrykPodworski/fitatu-cli/issues.` |
| 1 | `Fitatu is rate-limiting requests from this machine. Wait a few minutes and try again.` |
| 1 | `Could not reach Fitatu (<reason>). Check your internet connection and try again.` |
| 1 | `Fitatu sent a response fitatu-cli could not read. Fitatu may have changed its API; rerun with --debug and report it at https://github.com/PatrykPodworski/fitatu-cli/issues.` |
| 1 | `Unexpected error (<reason>). Rerun with --debug and report it at https://github.com/PatrykPodworski/fitatu-cli/issues.` |
| 2 | `No command given. Run 'fitatu <command>', one of: login, day.` |
| 2 | `Unknown command '<name>'. Did you mean '<command>'?` |
| 2 | `Unknown command '<name>'. Run 'fitatu <command>', one of: login, day.` |
| 2 | `Unknown option '<option>' for 'fitatu <command>'. Did you mean '<option>'? Run 'fitatu <command> --help' for all options.` |
| 2 | `Unexpected argument '<argument>' for 'fitatu <command>'. Run 'fitatu <command> --help' for all options.` |
| 2 | `Option '<option>' goes after the command. Run 'fitatu <command> <option>'.` |
| 2 | `Option '<option>' needs a value. Run 'fitatu day --help'.` |
| 2 | `Option '<option>' takes no value. Remove '=<value>'.` |
| 2 | `Invalid date '<value>'. Use today, yesterday or YYYY-MM-DD.` |
| 2 | `Give either a date or --from/--to, not both. Run 'fitatu day --help'.` |
| 2 | `Missing --from for 'fitatu day'. Run 'fitatu day --help'.` |
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
- Day totals are the sums of the nutrients Fitatu sends for each item. Recipe items
  are not rescaled, because Fitatu already sends their nutrients for the portion eaten.
  The totals match the day total in the app
  ([#5](https://github.com/PatrykPodworski/fitatu-cli/issues/5)).
- A login works only with a device UUID that Fitatu already knows for the account,
  which is why `FITATU_APP_UUID` is required.
- If Fitatu changes its API, `fitatu` stops working until the code is updated. To
  update it, capture the web app's requests again in the browser dev tools and compare
  them with the code.

## Use from an agent

Link the skill into your Claude Code skills folder from the repository root:

```sh
ln -s "$PWD/skills/fitatu" ~/.claude/skills/fitatu
```

The skill tells an agent which commands answer which questions, how to read the output
and errors, and that it must never run `fitatu login` or read the session file.

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
