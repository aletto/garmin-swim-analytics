"""Reject tracked files covered by the repository's private-data ignore rules."""

import subprocess


def main() -> int:
    result = subprocess.run(
        ["git", "ls-files", "-ci", "--exclude-per-directory=.gitignore", "-z"],
        check=True,
        stdout=subprocess.PIPE,
    )
    if result.stdout:
        print("Tracked files match private-data or generated-file exclusions. Review the Git index locally.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
