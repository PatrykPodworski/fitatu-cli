import re


class FitatuCliError(Exception):
    """An expected failure that `main` reports as `fitatu: <problem> <action>`."""

    def __init__(self, problem: str, action: str) -> None:
        super().__init__(f"{problem} {action}")


ISSUES = "https://github.com/PatrykPodworski/fitatu-cli/issues"


def unreadable() -> FitatuCliError:
    return FitatuCliError(
        "Fitatu sent a response fitatu-cli could not read.",
        "Fitatu may have changed its API; rerun with --debug and report it at "
        f"{ISSUES}.",
    )


def reason(error: BaseException) -> str:
    """`<type>: <message>` for an error line, without secrets and on one line."""
    text = f"{type(error).__name__}: {str(error).partition(chr(10))[0]}"
    text = re.sub(r"\?\S+", "?…", text)
    text = re.sub(r"Bearer \S+", "Bearer …", text)
    return text[:100]
