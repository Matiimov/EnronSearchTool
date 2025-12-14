"""Small helper around SQLite full-text search."""

import sqlite3
from difflib import get_close_matches
from pathlib import Path
from typing import Dict, List


class EmailSearcher:
    """Wrapper that hides raw SQL and gives a simple search results."""

    def __init__(self, db_path: Path, vocab_rows: int = 20000):
        """
        Open one sqlite connection and prepare a \"vocabulary\" list.

        vocab_rows tells us how many rows we scan to collect words. Bigger number
        means better fuzzy matching but slower startup, so we just take a sample.
        """
        self.db_path = Path(db_path)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row  # access columns by name
        self.vocabulary = self._load_vocabulary(vocab_rows)

    def _load_vocabulary(self, max_rows: int) -> List[str]:
        """
        Build a list of common tokens by scanning the email text.

        We keep only alphabetic words of reasonable length so the list stays tidy.
        """
        tokens = set()
        cur = self.conn.execute(
            "SELECT subject, body FROM emails LIMIT ?",
            (max_rows,),
        )
        for subject, body in cur:
            text = f"{subject or ''} {body or ''}"
            for raw in text.lower().split():
                token = ''.join(ch for ch in raw if ch.isalpha())
                if 3 <= len(token) <= 20:
                    tokens.add(token)
                    if len(tokens) >= 80000:
                        return list(tokens)
        return list(tokens)

    def _expand_token(self, token: str) -> List[str]:
        """
        Return token plus close matches (helps with misspellings).

        Uses difflib to guess what the user probably meant.
        """
        token = token.lower()
        choices = get_close_matches(token, self.vocabulary, n=3, cutoff=0.7)
        if token not in choices:
            choices.insert(0, token)
        return choices

    def _build_match_query(self, text: str) -> str:
        """
        Turn user text into a basic boolean (AND/OR) FTS query.

        - Words are AND'ed unless the user writes the word OR between groups.
        - Example: fraud energy OR bankruptcy
          -> (fraud* AND energy*) OR (bankruptcy*)
        - Adding * lets us match prefixes (fraud catches fraud, fraudulent, etc.).
        """
        # split on whitespace, drop empty bits
        tokens = [piece for piece in text.strip().split() if piece]
        if not tokens:
            return '', []

        # groups represent AND chunks; add a new group whenever OR appears
        groups: List[List[str]] = [[]]
        for token in tokens:
            if token.lower() == 'or':
                # start a fresh group so next words are in the OR branch
                if groups[-1]:
                    groups.append([])
                continue
            groups[-1].append(token)

        # remove empty groups (could happen if query ends with OR)
        groups = [g for g in groups if g]
        if not groups:
            return ''

        clauses = []
        for group in groups:
            expanded_terms = []
            for term in group:
                options = self._expand_token(term)
                if len(options) == 1:
                    expanded_terms.append(f"{options[0]}*")
                else:
                    expanded_terms.append(
                        "(" + " OR ".join(f'"{opt}"*' for opt in options) + ")"
                    )
            # AND join all terms inside one group, add * for prefix match
            clauses.append(' AND '.join(expanded_terms))

        if len(clauses) == 1:
            return clauses[0]
        # wrap each clause so sqlite understands our OR groupings
        return ' OR '.join(f'({clause})' for clause in clauses)

    def search(self, query: str, limit: int = 20) -> List[Dict[str, str]]:
        """
        Return a small list of matches with highlighted snippets.

        Limit defaults to 20 so we don't dump hundreds of rows into the UI.
        """
        match_query = self._build_match_query(query)
        if not match_query:
            return []
        sql = (
            # select metadata plus snippet + relevance score from FTS table
            "SELECT e.id, e.subject, e.sender, e.sent_at, e.file_path, e.body, "
            "snippet(email_fts, '[', ']', ' ... ', -1, 10) AS snippet, "
            "bm25(email_fts) AS score "
            "FROM email_fts JOIN emails e ON e.id = email_fts.rowid "
            "WHERE email_fts MATCH ? "
            "ORDER BY score LIMIT ?"
        )
        cur = self.conn.execute(sql, (match_query, limit))
        rows = cur.fetchall()
        return [dict(row) for row in rows]

    def close(self) -> None:
        """Close the SQLite connection when done."""
        self.conn.close()
