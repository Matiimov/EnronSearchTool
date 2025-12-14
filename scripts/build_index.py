"""Create a small SQLite database with full text search from the emails CSV."""

# argparse -> easy way to read script parameters
# csv -> stream the csv file line by line
# sqlite3 -> small local database that keeps things searchable
# email.* -> parses the raw RFC-822 message into headers/body
# Path -> nicer handling of file paths (Path objects instead of raw strings)
# sys -> bump csv field size limit so long messages don't crash
import argparse
import csv
import sqlite3
from email import policy
from email.parser import Parser
from pathlib import Path
import sys

# allow up to ~1 MB per field; bigger emails will be skipped
csv.field_size_limit(1_000_000)

# set up simple CLI: python build_index.py <csv> <db> [--limit N]
parser = argparse.ArgumentParser(description="Build SQLite index from emails.csv")
parser.add_argument("csv_path", type=Path, help="Path to emails.csv")
parser.add_argument("db_path", type=Path, help="Where to store the SQLite database")
parser.add_argument("--limit", type=int, default=0, help="Only load this many rows (0 means all)")
args = parser.parse_args()

# parser understands the raw email text (headers + body)
EMAIL_PARSER = Parser(policy=policy.default)


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Set up the normal table plus the full text search table (FTS)."""
    conn.executescript(
        """
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT,
            message_id TEXT,
            sent_at TEXT,
            sender TEXT,
            recipients TEXT,
            subject TEXT,
            body TEXT
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS email_fts USING fts5(
            subject, body, content='emails', content_rowid='id'
        );
        """
    )


def extract_body(msg) -> str:
    """
    Try to pull the plain text body.

    emails sometimes come as multi-part (text + html). we just grab the first text/plain part.
    this also ignores attachments or html tags, keeping only the readable message.
    """
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                try:
                    return part.get_content().strip()  # best case: parser already decoded it
                except Exception:
                    return part.get_payload(decode=True).decode(errors="ignore").strip()
        return ""
    try:
        return msg.get_content().strip()  # single-part email, plain text
    except Exception:
        payload = msg.get_payload(decode=True)  # fall back to manual decode
        if payload:
            return payload.decode(errors="ignore").strip()
        return msg.get_payload().strip() if isinstance(msg.get_payload(), str) else ""


def insert_email(conn: sqlite3.Connection, data: dict) -> None:
    """Insert one email into both normal table and the FTS index."""
    cur = conn.execute(
        """
        INSERT INTO emails (file_path, message_id, sent_at, sender, recipients, subject, body)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data.get("file_path"),
            data.get("message_id"),
            data.get("sent_at"),
            data.get("sender"),
            data.get("recipients"),
            data.get("subject"),
            data.get("body"),
        ),
    )
    conn.execute(
        "INSERT INTO email_fts(rowid, subject, body) VALUES (?, ?, ?)",
        (cur.lastrowid, data.get("subject"), data.get("body")),
    )

# open or create the sqlite db file (stored at db_path)
conn = sqlite3.connect(args.db_path)
ensure_schema(conn)


with args.csv_path.open(newline='', encoding='utf-8', errors='ignore') as csv_file:
    reader = csv.DictReader(csv_file)  # gives dicts with keys: file, message
    skipped_big_rows = 0
    idx = 0
    while True:
        try:
            row = next(reader)
        except StopIteration:
            break
        except csv.Error as err:
            skipped_big_rows += 1
            print(f"Skipping row because it's too large: {err}")
            continue
        idx += 1
        msg = EMAIL_PARSER.parsestr(row["message"])  # turn raw string into EmailMessage object
        body = extract_body(msg)
        entry = {   # build a dict with all fields to be stored
            "file_path": row["file"],
            "message_id": msg.get("Message-ID"),
            "sent_at": msg.get("Date"),
            "sender": msg.get("From"),
            "recipients": msg.get("To"),
            "subject": msg.get("Subject"),
            "body": body,
        }
        insert_email(conn, entry)
        if idx % 1000 == 0:
            conn.commit()
            print(f"Imported {idx} rows")  # small progress log so we know it is still working
        if args.limit and idx >= args.limit:
            break  # useful for quick tests

conn.commit()
if skipped_big_rows:
    print(f"Skipped {skipped_big_rows} oversized rows (over 1 MB).")
print("Done")
