# Global COVID-19 Explorer — Capstone

**Author:** Runjiu Chen · JHU 140.628.81 Data Science for Public Health in Python

An interactive historical COVID-19 dashboard using the **JHU CSSE COVID-19 time-series archive (January 22, 2020–March 9, 2023)**. It is **not** a live epidemic tracker.

## What to do

1. Add countries in the sidebar (`Compare countries`).
2. Choose **Cases** or **Deaths**, and switch between **Daily change** and **Cumulative total**.
3. Select the date range; optionally enable the 7-day moving average.
4. Explore the time-series comparison, country ranking, recent observations and the data-quality notes.
5. Download the selected country/day data from the **Data & download** tab.

## Run with Python (macOS or Windows)

```bash
cd covid_capstone_project
python3 -m pip install -r requirements.txt
python3 -m streamlit run capstone.py
```

The Python app fetches the two JHU global CSVs from GitHub on its first run and caches their parsed contents. If internet access is restricted, create `data/` and save the following files from the source repository there:

- `time_series_covid19_confirmed_global.csv`
- `time_series_covid19_deaths_global.csv`

For the static GitHub Pages version, `index.html` uses **Stlite**, which runs the same `capstone.py` in the browser with the original datasets loaded as app files. A modern browser and Internet access are required on first load.

## Data processing and interpretation

JHU cumulative source rows are aggregated to country by summing `Province/State` records within a `Country/Region`. The daily series is the *first difference of the country-level cumulative series*. Negative differences are preserved and counted as retrospective revisions, not erased or interpreted as negative infections. The first observation is used as the initial reported daily count. A 7-day mean is calculated from the **signed** daily series. Counts are not normalized for population or testing levels.

JHU stopped collecting global COVID-19 data on March 10, 2023. This archive should not be used to infer current infections or compare country-level infection risks.

Original data: https://github.com/CSSEGISandData/COVID-19/tree/master/csse_covid_19_data/csse_covid_19_time_series

## Submit

CoursePlus requests `capstone.py` (or `capstone.zip`) and a one-page `capstone.docx` with **two real links**: the running application and a presentation of at most five minutes. A slide deck and speaking notes are provided to help record that presentation. Do not submit an unrecorded slide deck as a recorded demo unless the course accepts it.