class FitatuCliError(Exception):
    """An expected failure that `main` reports as `fitatu: <problem> <action>`."""

    def __init__(self, problem: str, action: str) -> None:
        super().__init__(f"{problem} {action}")
