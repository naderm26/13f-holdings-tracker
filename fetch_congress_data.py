name: Fetch Congress Trading Data

on:
  workflow_dispatch:

jobs:
  fetch:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    permissions:
      contents: write

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: pip install pdfplumber requests beautifulsoup4

      - name: Run fetch
        run: python fetch_congress_data.py

      - name: Commit results
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add pelosi_trades.json || true
          git add _ptr_cache/ || true
          git diff --cached --quiet || git commit -m "Update congressional trading data"
          git push
