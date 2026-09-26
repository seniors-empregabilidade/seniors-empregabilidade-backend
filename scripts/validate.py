import os
import subprocess

COMMANDS = (
    ("ruff", "format", "--check", "."),
    ("ruff", "check", "."),
    ("mypy",),
    ("pytest",),
)


def main() -> None:
    # The 80% gate counts the PostgreSQL tests, so they must run here too.
    os.environ.setdefault("RUN_DATABASE_INTEGRATION_TESTS", "1")
    for command in COMMANDS:
        subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
