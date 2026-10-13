"""Reading the JSON spec file of a command that writes to Fitatu, and the value
checks the specs share. A failure raises `argparse.ArgumentTypeError`, which exits 2
with one line."""

import argparse
import json
import math
from collections.abc import Sequence
from typing import Any, TypeGuard, cast

Json = dict[str, Any]


def spec_error(
    path: str, noun: str, verb: str, problem: str
) -> argparse.ArgumentTypeError:
    return argparse.ArgumentTypeError(
        f"{noun} spec '{path}' {problem} "
        f"Run 'fitatu {noun.lower()} {verb} --help' for the spec's shape."
    )


def load_spec(path: str, noun: str, verb: str) -> Json:
    """The JSON object in the file at `path`."""
    try:
        with open(path) as file:
            spec = json.load(file)
    except OSError as error:
        raise argparse.ArgumentTypeError(
            f"Cannot read {noun.lower()} spec '{path}' ({error.strerror}). "
            "Give the path of a JSON file."
        ) from None
    except json.JSONDecodeError as error:
        raise spec_error(
            path, noun, verb, f"is not valid JSON ({error.msg}, line {error.lineno})."
        ) from None
    if not isinstance(spec, dict):
        raise spec_error(path, noun, verb, "is not a JSON object.")
    return cast(Json, spec)


def check_keys(
    path: str, noun: str, verb: str, spec: Json, allowed: Sequence[str]
) -> None:
    """Rejects the first key of `spec` that is not in `allowed`."""
    for key in spec:
        if key not in allowed:
            names = ", ".join(f'"{name}"' for name in allowed)
            raise spec_error(
                path, noun, verb, f'has an unknown key "{key}". The keys are {names}.'
            )


def finite(value: object) -> TypeGuard[int | float]:
    """Whether `value` is a JSON number other than `NaN` or an infinity, which
    `json.load` accepts."""
    return (
        isinstance(value, int | float)
        and not isinstance(value, bool)
        and math.isfinite(value)
    )
