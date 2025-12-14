# Enron Email Search Tool

Search the Enron CSV with SQLite full text search and a Streamlit UI.

## Architecture

- `emails.csv` → `scripts/build_index.py` → `data/enron.db` (SQLite + FTS5 index)
- `search/repository.py` Talks to SQLite and handles AND/OR + fuzzy matching
- `streamlit_app.py` Simple UI that calls the repository

## Files

- `scripts/inspect_csv.py` – Inspect first few rows to see the raw message format (RFC-822 headers + body).
- `scripts/build_index.py` – streams the CSV, parses each email, and stores fields + cleaned body text into SQLite and an FTS5 table.
- `search/repository.py` – Wraps SQLite queries, builds boolean search strings, does basic fuzzy matching.
- `streamlit_app.py` – Streamlit page with one text box and expandable result cards.

## How to run things

1. **Inspect the CSV (optional)**
   ```
   python3 scripts/inspect_csv.py
   ```
2. **Build or rebuild the SQLite database**
   ```
   python3 scripts/build_index.py data/raw/emails.csv data/enron.db --limit 30000
   ```
   - Drop the `--limit` flag to load everything (takes longer).
   - Remove `data/enron.db` first if you want a clean rebuild.
3. **Start the Streamlit UI**
   ```
   streamlit run streamlit_app.py
   ```
   - Open the shown localhost URL, type a query (use `OR` between groups), and press Search.

## Design choices & trade-offs

- **Storage/indexing:** SQLite + FTS5 keeps everything in one file, no extra services. FTS5 gives ranking, and fast keyword search.
- **Memory handling:** CSV ingestion is streamed row by row with commits every 1000 inserts. Oversized rows (>1 MB) are skipped to stay under tight memory budgets; we can raise the cap later.
- **Text parsing:** Python’s `email` module handles multipart/HTML emails so only storing the readable text and ignore attachments.
- **Query logic:** The repository turns user text into AND/OR FTS queries, adds fuzzy spellings via a vocabulary built at startup, and appends `*` so partial words match.
- **UI:** Streamlit gives the single-textbox search. Each result shows subject, sender, and the full body (trimmed).

## Future improvements / scaling ideas

- Save the vocabulary during ingestion (JSON) so startup is instant and fuzzy matching has richer data.
- Add “related emails” suggestions (same subject thread or sender/recipient pair).
- Swap SQLite for a search service (OpenSearch, Tantivy, etc.) once the data outgrows a single file; keep raw emails in cloud storage and index them via a batch job.
- Use a better tokenizer (keep hyphenated words etc).
