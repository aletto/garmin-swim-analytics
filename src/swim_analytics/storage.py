import hashlib
import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path

from .connectors.base import FitActivity


@contextmanager
def archive(root: Path) -> Iterator[sqlite3.Connection]:
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if root.stat().st_mode & 0o077:
        raise ValueError("Choose a private storage directory (permissions 0700).")
    with closing(sqlite3.connect(root / "raw.sqlite3")) as db, db:
        db.execute("PRAGMA foreign_keys = ON")
        db.execute("CREATE TABLE IF NOT EXISTS raw (digest TEXT PRIMARY KEY, fit BLOB NOT NULL)")
        db.execute("""
            CREATE TABLE IF NOT EXISTS origins (
                source TEXT NOT NULL,
                external_id TEXT NOT NULL,
                digest TEXT NOT NULL REFERENCES raw(digest),
                PRIMARY KEY (source, external_id, digest)
            )
        """)
        yield db


def archived_activity_ids(root: Path, source: str) -> frozenset[str]:
    with archive(root) as db:
        rows = db.execute("SELECT DISTINCT external_id FROM origins WHERE source = ?", (source,))
        return frozenset(row[0] for row in rows)


def preserve(db: sqlite3.Connection, source: str, activity: FitActivity) -> bool:
    """Atomically add original bytes and their provenance; keep changed file versions."""
    digest = hashlib.sha256(activity.payload).hexdigest()
    with db:
        insert = db.execute(
            "INSERT OR IGNORE INTO raw VALUES (?, ?)", (digest, activity.payload)
        )
        db.execute(
            "INSERT OR IGNORE INTO origins VALUES (?, ?, ?)",
            (source, activity.external_id or "", digest),
        )
    return insert.rowcount == 1


def archived_payloads(root: Path) -> Iterator[bytes]:
    path = root / "raw.sqlite3"
    if not path.is_file():
        return
    with closing(sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)) as db:
        for (payload,) in db.execute("SELECT fit FROM raw"):
            yield bytes(payload)
