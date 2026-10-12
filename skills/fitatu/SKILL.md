---
name: fitatu
description: Use when the user asks about their Fitatu food diary — what they ate, meals, calories eaten, macros (protein, carbs, fat), fibre, sugar, salt, or per-kg intake (g/kg) — about their Fitatu recipes: which ones they have, their ingredients or nutrients per portion — wants to find a food in Fitatu, its ID, energy or measure — or asks to log a food or a recipe in their diary.
---

# fitatu

`fitatu` reads the user's Fitatu diary and recipes, searches Fitatu's foods, puts foods into the diary, and prints plain text. Run it with Bash.

## Commands

```sh
fitatu day view [DATE]                    # one day's foods and totals; DATE: today | yesterday | YYYY-MM-DD, default today
fitatu day list --from DATE [--to DATE]   # each day in the range, oldest first; --to defaults to today
fitatu food search [PHRASE]               # foods matching PHRASE; without it, the foods the user used last
fitatu food search PHRASE --locale en_GB  # search the catalog in another locale, here English
fitatu recipe list                        # the user's recipes, most used first
fitatu recipe view ID                     # one recipe: ingredients and nutrients per portion
fitatu entry create DATE MEAL --product ID --quantity N --measure ID  # put a product into a meal; prints the entry ID
fitatu entry create DATE MEAL --recipe ID --quantity N  # put N portions of a recipe into a meal
fitatu auth login                         # the user runs this, never an agent (see Rules)
```

`fitatu day view` prints a `date: YYYY-MM-DD` line and a table of the day's foods,
one row per food. The columns are `id` (the entry ID), `meal`, `name`, `quantity`,
`measure` and the nutrients, each named with its unit: `energy_kcal`, `carbohydrate_g`, `protein_g`,
`fat_g`, `fiber_g`, `sugars_g` and `salt_g`. The last row, `total`, sums the nutrients
over the day. `-` marks a missing ID, name, quantity or measure; a missing nutrient is 0.
A day with nothing logged prints `no foods logged` under the date line and exits 0.

`fitatu day list` prints one such block per day, oldest first, with a blank line
between blocks. A range covers at most 31 days, counting both ends; split a longer
period into several calls.

`fitatu food search` searches Fitatu's catalog in the account's search language and
prints a table with one row per food: `id`, `type` (`product` or `recipe`), `name`,
`brand`, `energy_kcal`, and `measure`, the one measure the search returns with the
food, as `<measure id> <name> (<grams> g)`. Quote a multi-word phrase. `-` marks a
missing value or a food without a measure. No match prints `no foods found` and exits 0.
`--locale` searches in another locale without changing the account setting. Fitatu's
catalog answers for `pl_PL`, `en_GB`, `en_US`, `de_DE`, `cs_CZ`, `es_ES`, `it_IT` and
`fr_FR`; results can still include a few foods in the account's language. A value not
in the `xx_XX` form exits 2; a well-formed locale Fitatu does not know exits 1 with
the list. Without a phrase, `--locale` has no effect.

`fitatu recipe list` prints a table with the columns `id`, `uses` (how many times
the user logged the recipe) and `name`, most used first. It hides deleted recipes.
With no recipes it prints `no recipes`.

`fitatu recipe view ID` prints `id:`, `name:`, `servings:` and `deleted: yes|no`
lines, a table of ingredients (`ingredient`, `quantity`, `measure`), then a
`per portion` line and a one-row table of the nutrients, named as in `day view`.
`-` marks a missing value; a missing nutrient is 0. A recipe without ingredients
prints `no ingredients`. Take the ID from `recipe list`, or from a diary item's `recipeId` in `day view --raw`.

Editing a recipe in Fitatu gives it a new ID and marks the old one deleted. So an ID
can drop out of `recipe list` after an edit, and `recipe view` of an old ID shows
`deleted: yes`: diary entries logged before the edit still point to that version.
Run `recipe list` again for the current ID.

`fitatu entry create DATE MEAL` adds one food to a meal of a day and prints the new
entry ID, the `id` that `day view` shows for it. MEAL is the meal's name as `day view`
shows it, or its key (`breakfast`, `second_breakfast`, `lunch`, `dinner`, `supper`),
in any case. Give `--product` with an ID from `food search`, or `--recipe` with an ID
from `recipe list`. `--quantity` counts the measure: a product needs `--measure`, the
measure ID `food search` prints; a recipe defaults to measure 39, a portion. Each run
adds a new entry, so running it twice logs the food twice.

`--json` prints the same data as JSON: `{"date", "foods", "totals"}` from
`day view`, an array of those from `day list`; an array of
`{"id", "type", "name", "brand", "energy", "measure": {"id", "name", "grams"}}`
from `food search`; an array of `{"id", "name", "uses"}` from `recipe list`;
`{"id", "name", "servings", "deleted", "ingredients", "per_portion"}` from
`recipe view`; `{"id", "date", "meal"}` from `entry create`. Each `day view` food
has its entry ID in `id`. `--raw` prints the service's day plan as JSON instead, or an array of
day plans from `day list`. With `food search` it prints the service's search
response; with `recipe view`, the service's recipe; with `recipe list`, the
service's search rows for every recipe, deleted ones included, unsorted.

`fitatu <noun> <verb> --help` lists every flag.

## Rules

- Never run `fitatu auth login` and never read `~/.fitatu` or the file in `FITATU_SESSION`:
  they hold the user's login. Every command logs in on its own when it needs to.
- `entry create` changes the user's diary. Run it only when the user asks to log a
  food, and confirm the day, meal, food and quantity first when they are unclear.
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
- `Fitatu has no recipe with ID <id>` (exit 1): the ID is wrong. Run `fitatu recipe
  list` and retry with an ID from it.
- `Fitatu did not save the entry (<reason>)` (exit 1): Fitatu refused the food,
  measure or quantity. Check them with `food search` or `recipe view`, then retry once.
- Any other exit 1, such as a rate limit or no network: tell the user the second
  sentence and wait for them.
- Exit 2: bad arguments. The message names the fix (`Did you mean 'view'?`);
  correct the call and retry once. `No meal '<meal>' on <date>` lists the day's
  meals; retry with one of them.

## Privacy

The output is the user's data. Keep it in this conversation; put it in an issue,
commit, PR or any other external place only when the user asks.
