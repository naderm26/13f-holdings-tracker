name: Fix PRN Positions (one-time)

on:
  workflow_dispatch:

permissions:
  contents: write

jobs:
  fix:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repo
        uses: actions/checkout@v4
        with:
          token: ${{ secrets.GITHUB_TOKEN }}

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Run PRN cleanup
        run: python fix_prn_positions.py

      - name: Commit results
        run: |
          git config user.name  "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data/
          git diff --cached --quiet && echo "No changes" && exit 0
          git commit -m "fix: remove PRN debt positions from fund JSONs"
          git push
