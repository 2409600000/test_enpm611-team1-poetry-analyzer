# ENPM611 Team 1: Poetry Issue Analyzer

A command-line application that analyzes the GitHub issues of the open-source
[Poetry](https://github.com/python-poetry/poetry) project (issue and event data
provided as a JSON file). It answers three questions about how issues are
labeled, who works on them, and how issue activity changes over time, and shows
the results as console output and matplotlib charts.

This repository is a fork of the ENPM611 application template. The design
diagrams from Milestone 1 are in [`docs/`](docs/).

## Setup

**Python version:** Python 3.10 or newer (developed and tested with Python 3.12).

**Dependencies:** `python-dateutil`, `numpy`, `pandas`, `matplotlib`
(listed in `requirements.txt`).

1. Clone this repository.
2. Create and activate a virtual environment in the repository root:
   - macOS / Linux: `python3 -m venv venv && source venv/bin/activate`
   - Windows (PowerShell): `python -m venv venv; venv\Scripts\Activate.ps1`
3. Install the dependencies: `pip install -r requirements.txt`

### Configure the dataset path

Download the issues JSON file from the project assignment in Canvas. Then tell
the application where it is, using **either** way (the environment variable
takes priority and keeps your personal path out of the repository):

- Environment variable (recommended)
  - macOS / Linux: `export ENPM611_PROJECT_DATA_PATH=/path/to/poetry_issues.json`
  - Windows (PowerShell): `$env:ENPM611_PROJECT_DATA_PATH="C:\path\to\poetry_issues.json"`
- or edit `ENPM611_PROJECT_DATA_PATH` in `config.json` (do not commit your personal path).

Do not commit the data file. If the path is missing or wrong, the application
prints a clear error message instead of crashing.

## Running the features

```
python run.py --feature 1                    # label comparison (all labels)
python run.py --feature 1 --label kind/bug   # one label in detail
python run.py --feature 2                    # contributor activity (whole project)
python run.py --feature 2 --user abn         # one contributor vs. the top contributors
python run.py --feature 3                    # activity trends over time
python run.py --feature 0                    # template example analysis
```

`--label` and `--user` are optional and case-insensitive. If the label or user
is not found, the application suggests similar names and exits cleanly.
Charts open in a matplotlib window; close the window to continue (feature 2
shows two charts, one after the other).

## The three analyses

Every analysis prints its **question**, **method** and **finding** to the console.

### Feature 1: Label resolution (`label_resolution_analysis.py`)
- **Question:** Do issue labels (e.g. `kind/bug`, `area/docs`) differ in how long
  issues take to close and in how much discussion they get?
- **Output (no input):** a table of the most common labels (median days to
  close, comments per issue, distinct commenters per issue), a written finding,
  and two bar charts (time to close; discussion per issue).
- **Output (`--label`):** statistics for that label compared with all issues
  (median/mean/90th percentile days to close, comments, top commenters), a
  written finding, and a histogram of days to close with both medians marked.

### Feature 2: Contributor activity (`contributor_activity_analysis.py`)
- **Question:** Who does the work on the project, and do frequent commenters
  also label or close issues?
- **Output (no input):** a table of the top 10 contributors, Spearman rank
  correlations between comments and triage actions, a written finding, a
  grouped bar chart (comments / label actions / closes) and a scatter plot of
  comments vs. triage actions.
- **Output (`--user`):** the contributor's breakdown, rank and share of all
  activity, a finding comparing their share of triage work with the top 10,
  and a bar chart of the user next to the average of the top 10.

### Feature 3: Discussion trends (`discussion_trend_analysis.py`)
- **Question:** How has issue activity changed over time, and how quickly do new
  issues get a first response? (project-level, no input)
- **Output:** a per-year table (issues opened/closed, comments, median first
  response in hours), a written finding, and a three-panel line chart by
  quarter (opened vs. closed, comment volume, median hours to first response).

## Known limitations and assumptions

- **Bots are excluded** (authors ending in `[bot]`) from comment, contributor
  and response-time statistics.
- **Time to close** uses the date of the last `closed` event. Closed issues
  without a closing event in the data (20 of 401 in `poetry_issues.json`) and
  open issues are left out of timing statistics. Reopened issues use their latest close.
- **Triage** (feature 2): labels and closes made by the issue's own reporter are
  not counted, because issue templates attribute automatic labels to the
  reporter and reporters closing their own issue is not triage work.
- **First response** is the first human comment by someone other than the
  issue creator.
- Most issues in the dataset are from 2024, so earlier years have few issues
  and their medians are less reliable (years with fewer than 10 issues are not
  used in the first-vs-last comparison). The final quarter may be incomplete.
- Medians for labels with few resolved issues are unreliable; feature 1 only
  compares labels with at least 5 resolved issues.
- Results depend on the dataset file used.

## Differences from the Milestone 1 design

- `model.py` gained small helpers shared by all analyses (`Event.is_human`,
  `Issue.closed_date`, `Issue.days_to_close()`, `Issue.human_comments()`) instead
  of duplicating this logic in each analysis.
- `data_loader.py` raises a clear error when the data path is not configured;
  `run.py` now has a `main()` function and reports that error cleanly.
- The sequence diagram (feature 2) also prints a written finding after the
  correlations; the component structure is unchanged.

## Team contributions

| Member | Areas of contribution |
|--------|-----------------------|
| [Name 1] | [e.g. Milestone 1 diagrams, feature 1, tests] |
| [Name 2] | [e.g. feature 2, README] |
| [Name 3] | [e.g. feature 3, presentation] |
