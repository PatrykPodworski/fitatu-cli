# fitatu-cli

`fitatu` reads your Fitatu food diary, searches Fitatu's foods, and puts foods into
your diary and removes them. It prints plain text, or JSON with `--json`.

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
id                                    meal       name          quantity  measure  energy_kcal  carbohydrate_g  protein_g  fat_g  fiber_g  sugars_g  salt_g
3f5e8a10-9a4b-11f1-8000-0b1c2d3e4f50  Breakfast  Oat porridge  1         bowl     320.0        54.2            11.0       6.5    7.1      3.4       0.1
41c7d2e0-9a4b-11f1-8000-0b1c2d3e4f50  Lunch      Lentil soup   300       g        270.0        38.0            16.5       4.2    9.0      5.1       1.8
total                                                                             590.0        92.2            27.5       10.7   16.1     8.5       1.9
```

The first line is the date. A table of foods follows, one row per food, with a `total`
row at the end. The `id` column is the entry ID, which names one food on the day. `-`
marks a missing ID, name, quantity or measure. A missing nutrient
counts as 0. A day with nothing logged prints the date line and `no foods logged`.

With `--json`, it prints the same data as JSON:

```json
{
  "date": "2026-10-11",
  "foods": [
    {
      "id": "3f5e8a10-9a4b-11f1-8000-0b1c2d3e4f50",
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
      "id": "41c7d2e0-9a4b-11f1-8000-0b1c2d3e4f50",
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
id                                    meal       name          quantity  measure  energy_kcal  carbohydrate_g  protein_g  fat_g  fiber_g  sugars_g  salt_g
3f5e8a10-9a4b-11f1-8000-0b1c2d3e4f50  Breakfast  Oat porridge  1         bowl     320.0        54.2            11.0       6.5    7.1      3.4       0.1
total                                                                             320.0        54.2            11.0       6.5    7.1      3.4       0.1

date: 2026-10-10
no foods logged
```

With `--json`, it prints a JSON array of the day objects `fitatu day view --json`
prints.

### `fitatu food search [PHRASE]`

Finds foods matching `PHRASE` in Fitatu's catalog, in your account's search language.
Without a phrase, it lists the foods you used last. Each row gives the food's ID, its
type (`product` or `recipe`), name, brand, energy, and the one measure Fitatu's search
returns with it: the measure's ID, name and weight in grams.

```sh
fitatu food search "rye bread"
```

```text
id    type     name       brand   energy_kcal  measure
501   product  Rye bread  Bakery  240.3        7 slice (32.5 g)
9001  recipe   Stew       -       410.0        39 portion (350 g)
```

`-` marks a missing value or a food without a measure. No match prints
`no foods found`.

To search in another locale without changing your account setting, add `--locale`.
Fitatu's catalog answers for `pl_PL`, `en_GB`, `en_US`, `de_DE`, `cs_CZ`, `es_ES`,
`it_IT` and `fr_FR`.

```sh
fitatu food search "rye bread" --locale en_GB
```

With `--json`, it prints a JSON array:

```json
[
  {
    "id": 501,
    "type": "product",
    "name": "Rye bread",
    "brand": "Bakery",
    "energy": 240.3,
    "measure": {"id": 7, "name": "slice", "grams": 32.5}
  }
]
```

### `fitatu recipe list`

Prints your recipes, most used first: the recipe ID, how many times you logged it, and
its name. Deleted recipes are hidden. With no recipes, it prints `no recipes`.

```sh
fitatu recipe list
```

```text
id         uses  name
100000002  14    Lentil soup
100000001  3     Oat porridge
```

With `--json`, it prints an array of `{"id", "name", "uses"}`.

### `fitatu recipe view ID`

Prints one recipe: its fields, a table of its ingredients, and its nutrients per
portion.

```sh
fitatu recipe view 100000002
```

```text
id: 100000002
name: Lentil soup
servings: 4
deleted: no

ingredient       quantity  measure
Red lentils      200       g
Carrot           2         piece
Vegetable stock  1         l

per portion
energy_kcal  carbohydrate_g  protein_g  fat_g  fiber_g  sugars_g  salt_g
270.0        38.0            16.5       4.2    9.0      5.1       1.8
```

`-` marks a missing name, servings, quantity or measure. A missing nutrient counts as
0. A recipe without ingredients prints `no ingredients`.

Editing a recipe's ingredients or their quantities in Fitatu gives it a new ID and
marks the old one deleted; other edits keep the ID. `recipe view` still shows a
deleted recipe, with `deleted: yes`, because diary entries logged before the edit
point to it. `recipe list` shows only the latest version.

With `--json`, it prints `{"id", "name", "servings", "deleted", "ingredients",
"per_portion"}`. Each ingredient is `{"name", "quantity", "measure"}`, and
`per_portion` has the seven nutrients.

### `fitatu product list`

Prints your own products, most used first: the product ID, how many times you logged
it, its brand and its name. It lists only products you created, not catalog foods you
ate. Deleted products are hidden. `-` marks a product without a brand. With no
products, it prints `no products`.

```sh
fitatu product list
```

```text
id         uses  brand   name
100000012  21    -       Granola
100000011  4     Bakery  Rye bread
```

With `--json`, it prints an array of `{"id", "uses", "brand", "name"}`, with `brand`
null when the product has none.

### `fitatu product view ID`

Prints one product: its fields, a table of its measures with the grams in one unit of
each, and its nutrients per 100 g.

```sh
fitatu product view 100000011
```

```text
id: 100000011
name: Rye bread
brand: Bakery
mine: yes
deleted: no

measure_id  measure  grams
7           slice    32.5
1           g        1

per 100 g
energy_kcal  carbohydrate_g  protein_g  fat_g  fiber_g  sugars_g  salt_g
240.3        45.1            7.8        1.6    6.2      2.9       1.2
```

Fitatu stores nutrients per 100 g, even for a product entered from a per-portion
label. `mine: yes` marks one of your own products. Any product ID from `fitatu food
search` works too, with `mine: no`. `-` marks a missing name, brand or measure field.
A missing nutrient counts as 0. A product without measures prints `no measures`.

With `--json`, it prints `{"id", "name", "brand", "mine", "deleted", "measures",
"per_100g"}`. Each measure is `{"id", "name", "grams"}`, and `per_100g` has the seven
nutrients.

### `fitatu product create SPEC`

Creates a private product from the values on a food label, and prints its ID. `SPEC`
is a JSON file:

```json
{"name": "Bean stew", "brand": "Bistro", "energy": 129, "protein": 7.8, "fat": 3.4,
 "carbohydrate": 10.9, "fiber": 1.2, "sugars": 2.3, "salt": 0.9, "per": 100}
```

```sh
fitatu product create stew.json
```

```text
100000031
```

- `brand`, `fiber`, `sugars`, `salt` and `per` are optional. Any other key is an
  error.
- `energy` is in kcal, the other nutrients in grams. Each is a number of 0 or more.
- With `"per": 100`, the default, the values are per 100 g. The product gets one
  measure, `g`.
- With `"per": {"measure": "portion", "grams": 450}`, the values are per portion of
  450 g, entered as printed on the label. Fitatu stores them per 100 g and gives the
  product a `portion` measure, ID 39, of that weight.

The product shows up in `fitatu food search` and `fitatu product view`. Log it with
`fitatu entry create DATE MEAL --product ID --measure 1 --quantity GRAMS`, or with
`--measure 39 --quantity PORTIONS` when it has a portion.

With `--json`, it prints `{"id"}`.

### `fitatu product edit ID SPEC`

Changes one of your products, and prints its ID. `SPEC` is a JSON file with any of the
keys of a `fitatu product create` spec, at least one, checked the same way:

```json
{"name": "Bean stew", "energy": 600, "per": {"measure": "portion", "grams": 450}}
```

```sh
fitatu product edit 100000031 stew.json
```

```text
100000032
```

- Each key given replaces that value.
- Nutrients are per 100 g, or per portion with `"per": {"measure": "portion",
  "grams": 450}`, which also sets the product's portion to that weight. Without it,
  the product keeps its portion.
- Any edit, even of the name alone, can give the product a new ID, so use the
  printed ID. The old one stays, marked deleted, and diary entries keep using it.
- A deleted product, or one that is not yours, is an error, and nothing is sent.

With `--json`, it prints `{"id"}`.

### `fitatu product delete ID`

Deletes one of your products and prints its ID and name. There is no confirmation
prompt.

```sh
fitatu product delete 100000031
```

```text
deleted product 100000031: Bean stew
```

Fitatu keeps the product marked deleted: it leaves `fitatu product list`, `fitatu
product view` shows `deleted: yes`, and diary entries that use it keep their name and
values. A catalog product, one with `mine: no`, cannot be deleted. `-` marks a product
without a name.

With `--json`, it prints `{"id", "name"}`.

### `fitatu entry create DATE MEAL (--product ID | --recipe ID) --quantity N [--measure ID]`

Puts one product or recipe into a meal on a day, and prints the new entry ID.

```sh
fitatu entry create 2026-10-11 breakfast --product 501 --quantity 2 --measure 7
fitatu entry create 2026-10-11 Lunch --recipe 100000002 --quantity 1
```

```text
3f5e8a10-9a4b-11f1-8000-0b1c2d3e4f50
```

- `MEAL` is the meal's name as the app shows it, or its key: `breakfast`,
  `second_breakfast`, `lunch`, `dinner` or `supper`. Case does not matter. A meal
  name comes before a key, since you can rename meals in the app.
- `--product` takes an ID from `fitatu food search`, and `--recipe` an ID from
  `fitatu recipe list`.
- `--quantity` counts the measure. A product needs `--measure`, a measure ID that
  `fitatu food search` prints. A recipe defaults to measure 39, a portion.

Each run adds a new entry; running it twice logs the food twice. `fitatu day view`
shows the entry in its `id` column.

With `--json`, it prints `{"id", "date", "meal"}`, where `meal` is the meal's name.

### `fitatu entry delete DATE ENTRY_ID`

Removes one entry from a day. There is no confirmation prompt. `ENTRY_ID` is the
entry's ID from the `id` column of `fitatu day view`.

```sh
fitatu entry delete 2026-10-11 3f5e8a10-9a4b-11f1-8000-0b1c2d3e4f50
```

```text
deleted entry 3f5e8a10-9a4b-11f1-8000-0b1c2d3e4f50 from Breakfast: Rice
```

Fitatu applies the change after it answers, so a `fitatu day view` right after can
still show the entry.

With `--json`, it prints `{"id", "date", "meal", "name"}`.

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
`fitatu day list --raw`, it prints an array of those responses. `fitatu food search
--raw` prints Fitatu's search response. Use it when you need a
field the summary does not have. `--raw` prints JSON without `--json`.

`fitatu recipe view --raw` prints Fitatu's response for the recipe unchanged.
`fitatu recipe list --raw` prints Fitatu's search rows for your recipes, in the
service's order, deleted recipes included.

`fitatu product view --raw` prints Fitatu's response for the product unchanged.
`fitatu product list --raw` prints Fitatu's search rows for your products, in the
service's order, deleted products included. `fitatu product create --raw` prints
Fitatu's response to the new product, and `fitatu product edit --raw` its response to
the edit.

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
| 1 | `Fitatu has no recipe with ID <id>. Run 'fitatu recipe list' to see your recipes' IDs.` |
| 1 | `Fitatu has no product with ID <id>. Run 'fitatu product list' to see your products' IDs.` |
| 1 | `Fitatu rejected the product (HTTP <code>). Check the spec with 'fitatu product create --help'.` |
| 1 | `Product <id> is deleted. An edit can give a product a new ID; run 'fitatu product list' for its current ID.` |
| 1 | `Product <id> is not one of yours. You can edit only your own products; run 'fitatu product list' to see them.` |
| 1 | `Fitatu did not edit product <id> (HTTP <code>). You can edit only your own products; run 'fitatu product list' to see them.` |
| 1 | `Product <id> is already deleted. Run 'fitatu product list' to see your products' IDs.` |
| 1 | `Product <id> is not one of yours. You can delete only your own products; run 'fitatu product list' to see them.` |
| 1 | `Fitatu did not delete product <id> (HTTP <code>). You can delete only your own products; run 'fitatu product list' to see them.` |
| 1 | `Fitatu did not save the entry (<reason>). Check the food ID, the measure ID and the quantity.` |
| 1 | `Fitatu's answer did not arrive (<reason>), so the entry may be saved. Wait a minute and check 'fitatu day view <date>' before you run this again.` |
| 1 | `No entry '<id>' on <date>. Run 'fitatu day view <date>' to see the day's entry IDs.` |
| 1 | `Fitatu did not delete the entry (<reason>). Rerun with --debug and report it at https://github.com/PatrykPodworski/fitatu-cli/issues.` |
| 1 | `Unexpected error (<reason>). Rerun with --debug and report it at https://github.com/PatrykPodworski/fitatu-cli/issues.` |
| 2 | `No command given. Run 'fitatu <command>', one of: auth, day, entry, food, recipe, product.` |
| 2 | `No command given. Run 'fitatu <noun> <command>', one of: <verbs>.` |
| 2 | `Unknown command '<name>'. Did you mean '<command>'?` |
| 2 | `Unknown command '<name>'. Run 'fitatu <command>', one of: auth, day, entry, food, recipe, product.` |
| 2 | `Unknown command '<name>'. Run 'fitatu <noun> <command>', one of: <verbs>.` |
| 2 | `Unknown option '<option>' for 'fitatu <noun> <verb>'. Did you mean '<option>'? Run 'fitatu <noun> <verb> --help' for all options.` |
| 2 | `Unexpected argument '<argument>' for 'fitatu <noun> <verb>'. Run 'fitatu <noun> <verb> --help' for all options.` |
| 2 | `Option '<option>' goes after the command. Run 'fitatu <noun> <verb> <option>'.` |
| 2 | `Option '<option>' needs a value. Run 'fitatu day list --help'.` |
| 2 | `Option '<option>' takes no value. Remove '=<value>'.` |
| 2 | `Invalid date '<value>'. Use today, yesterday or YYYY-MM-DD.` |
| 2 | `Invalid recipe ID '<value>'. Give the number from 'fitatu recipe list'.` |
| 2 | `Invalid product ID '<value>'. Give the number from 'fitatu food search'.` |
| 2 | `Invalid product ID '<value>'. Give the number from 'fitatu product list'.` |
| 2 | `Invalid measure ID '<value>'. Give the number from 'fitatu food search'.` |
| 2 | `Invalid quantity '<value>'. Give a number greater than 0.` |
| 2 | `One of the arguments --product --recipe is required. Run 'fitatu entry create --help'.` |
| 2 | `Argument --recipe: not allowed with argument --product. Run 'fitatu entry create --help'.` |
| 2 | `--product needs --measure. Give the measure ID from 'fitatu food search'.` |
| 2 | `No meal '<meal>' on <date>. Use one of: <meals>.` |
| 2 | `Cannot read product spec '<path>' (<reason>). Give the path of a JSON file.` |
| 2 | `Product spec '<path>' <problem> Run 'fitatu product create --help' for the spec's shape.` |
| 2 | `Product spec '<path>' <problem> Run 'fitatu product edit --help' for the spec's shape.` |
| 2 | `Missing --from for 'fitatu day list'. Run 'fitatu day list --help'.` |
| 2 | `--from <date> is in the future. Give a --from on or before today.` |
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
- `fitatu entry create` sends only the new item, as the web app does, so the day's
  other entries stay as they are. Fitatu adds or updates an item by its entry ID. A
  write also sets the day's note and tags to what it holds, so the command resends
  them, and the toilet items, from the day it read. The
  entry ID is a UUID v1, like the web app's, built from random bits instead of your
  machine's network address.
- `fitatu entry delete` removes an entry as the web app does: it sends the entry again
  with `deletedAt` set, and with the day's note, tags and toilet items, like `entry
  create`. The day's read then no longer lists it.
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
