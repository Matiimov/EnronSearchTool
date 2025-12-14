"""Simple Streamlit UI for the Enron search tool."""

from pathlib import Path

import streamlit as st

from search.repository import EmailSearcher

DB_PATH = Path("data/enron.db")

st.set_page_config(page_title="Enron Search", layout="wide")
st.title("Enron Email Search")

if not DB_PATH.exists():
    st.error("Database not found. Please run scripts/build_index.py first.")
    st.stop()

searcher = EmailSearcher(DB_PATH)

query = st.text_input("Search terms", "")
limit = st.slider("Max results", min_value=5, max_value=50, value=20, step=5)

if st.button("Search") and query.strip():
    with st.spinner("Searching..."):
        results = searcher.search(query, limit=limit)
    if not results:
        st.info("No matches found.")
    for idx, row in enumerate(results, start=1):
        with st.expander(f"{idx}. {row['subject'] or '(no subject)'}"):
            st.markdown(f"**From:** {row['sender']}")
            st.markdown(f"**Date:** {row['sent_at']}")
            st.markdown(f"**File:** `{row['file_path']}`")
            st.markdown("**Full body:**")
            st.text(row['body'][:2000] + ("..." if len(row['body']) > 2000 else ""))

searcher.close()
