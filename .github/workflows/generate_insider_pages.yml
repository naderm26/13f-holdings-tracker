name: Generate Insider Pages

on:
  workflow_dispatch:
  workflow_run:
    workflows: ["Generate Insider Index"]
    types: [completed]

jobs:
  generate:
    runs-on: ubuntu-latest
    if: ${{ github.event_name == 'workflow_dispatch' || github.event.workflow_run.conclusion == 'success' }}

    permissions:
      contents: write

    steps:
      - name: Checkout repo
        uses: actions/checkout@v4
        with:
          ref: main
          token: ${{ secrets.GITHUB_TOKEN }}

      - name: Pull latest changes
        run: git pull origin main

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Generate insider pages
        run: python generate_insider_pages.py

      - name: Commit results
        run: |
          git config user.name  "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add insiders/
          git diff --cached --quiet && echo "No changes" && exit 0
          git commit -m "chore: regenerate insider trading pages"
          git push
