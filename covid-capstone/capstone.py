"""COVID-19 Global Explorer: historical JHU CSSE COVID-19 dashboard.

Author: Runjiu Chen | 140.628 Data Science for Public Health in Python, 2026.
Launch: streamlit run capstone.py
Source data are archived (last observation 2023-03-09); NOT a live tracker.
"""

from datetime import date
from pathlib import Path
import io

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


SOURCE = (
    "https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/"
    "csse_covid_19_data/csse_covid_19_time_series/"
)
DATA_FILES = {
    "Cases": "time_series_covid19_confirmed_global.csv",
    "Deaths": "time_series_covid19_deaths_global.csv",
}
COLORS = [
    "#42B8A5", "#EC8C66", "#698BEB", "#E8BD69", "#AF8FE4",
    "#6AA9C7", "#DB7796", "#8DAB75", "#B2A3DF", "#D4A76F",
]
ALIASES = {
    "US": "United States",
    "Korea, South": "South Korea",
    "Taiwan*": "Taiwan",
    "Burma": "Myanmar",
}


def parse_jhu_time_series(raw: pd.DataFrame) -> pd.DataFrame:
    """Aggregate all province rows to one country-level cumulative time series.

    Index: dates. Columns: source Country/Region labels. No clipping of
    negative day-to-day revisions or filling gaps with invented trends.
    """
    if "Country/Region" not in raw.columns:
        raise ValueError("JHU CSV must include 'Country/Region'.")
    metadata = {"Province/State", "Country/Region", "Lat", "Long"}
    date_columns = []
    dates = []
    for column in raw.columns:
        if column in metadata:
            continue
        parsed = pd.to_datetime(column, format="%m/%d/%y", errors="coerce")
        if pd.notna(parsed):
            date_columns.append(column)
            dates.append(parsed)
    if not date_columns:
        raise ValueError("No recognizable date columns found in JHU CSV.")

    numeric = raw[date_columns].apply(pd.to_numeric, errors="coerce")
    # These source files report cumulative counts, not rates or incident cases.
    country = raw["Country/Region"].fillna("Unknown").astype(str).str.strip()
    numeric.insert(0, "Country/Region", country)
    grouped = numeric.groupby("Country/Region", sort=True)[date_columns].sum(min_count=1)
    wide = grouped.T
    wide.index = pd.DatetimeIndex(dates, name="date")
    wide = wide.sort_index()
    # Numeric NAs remain NA: avoid silently turning missing reports into zero.
    return wide


def daily_from_cumulative(cumulative: pd.DataFrame) -> pd.DataFrame:
    """Use first differences; retain negative values caused by source revisions."""
    daily = cumulative.diff()
    if not daily.empty:
        # Earliest source cumulative count serves as an initial baseline report.
        daily.iloc[0] = cumulative.iloc[0]
    return daily


def tidy_export(cumulative, countries, start, end, metric):
    """Tidy long data with both daily and cumulative values for selected countries."""
    subset = cumulative.loc[start:end, countries]
    incident = daily_from_cumulative(cumulative).loc[start:end, countries]
    records = []
    for country in countries:
        for dt in subset.index:
            records.append({
                "date": dt.date().isoformat(),
                "country": country,
                "metric": metric.lower(),
                "cumulative_count": subset.at[dt, country],
                "daily_reported_change": incident.at[dt, country],
                "is_negative_revision": bool(pd.notna(incident.at[dt, country]) and incident.at[dt, country] < 0),
            })
    return pd.DataFrame.from_records(records)


@st.cache_data(show_spinner="Loading the Johns Hopkins historical time series...")
def load_series(metric: str) -> pd.DataFrame:
    filename = DATA_FILES[metric]
    local_path = Path(__file__).resolve().parent / "data" / filename
    try:
        if local_path.exists():
            raw = pd.read_csv(local_path, low_memory=False)
        else:
            raw = pd.read_csv(SOURCE + filename, low_memory=False)
    except Exception as exc:
        raise RuntimeError(
            "Could not load the public JHU data. Check your internet connection "
            "or put the source CSV in the data/ folder."
        ) from exc
    return parse_jhu_time_series(raw)


def format_country(country):
    return ALIASES.get(country, country)


def fmt_count(value):
    if pd.isna(value):
        return "Not available"
    return f"{value:,.0f}"


def line_chart(cumulative, countries, metric, mode, smoothing, start, end):
    daily = daily_from_cumulative(cumulative)
    fig = go.Figure()
    series_all = daily if mode == "Daily change" else cumulative
    if mode == "Daily change" and smoothing:
        # Smooth the signed report revisions; no negative values are discarded.
        series_all = series_all.rolling(7, min_periods=1).mean()
    series = series_all.loc[start:end, countries]
    for idx, country in enumerate(countries):
        color = COLORS[idx % len(COLORS)]
        name = format_country(country)
        y = series[country]
        fig.add_trace(go.Scatter(
            x=series.index, y=y, name=name,
            mode="lines", line={"color": color, "width": 2.8},
            hovertemplate=("<b>" + name + "</b><br>%{x|%d %b %Y}"
                           + "<br>%{y:,.0f}<extra></extra>"),
        ))
        # A raw, unsmoothed daily series can have negative correction days.
        if mode == "Daily change" and not smoothing:
            corrections = daily.loc[start:end, country]
            corrections = corrections[corrections < 0]
            if not corrections.empty:
                fig.add_trace(go.Scatter(
                    x=corrections.index, y=corrections,
                    mode="markers", name=f"{name} revisions",
                    marker={"color": "#D45D64", "size": 8, "symbol": "x"},
                    hovertemplate="Retrospective correction<br>%{x|%d %b %Y}<br>%{y:,.0f}<extra></extra>",
                    showlegend=False,
                ))
    label = f"{metric.lower()} • {'7-day average of daily changes' if (mode == 'Daily change' and smoothing) else mode.lower()}"
    fig.update_layout(
        title={"text": label.capitalize(), "font": {"size": 18}},
        height=430, margin={"l": 10, "r": 10, "t": 56, "b": 10},
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Arial", "size": 12},
        hovermode="x unified", legend={"orientation": "h", "y": -0.16, "x": 0},
        xaxis={"title": "Report date", "showgrid": False},
        yaxis={"title": "Reported count", "gridcolor": "#DFE7ED", "zerolinecolor": "#AAB9C4"},
    )
    return fig


def ranking_chart(cumulative, countries, end):
    vals = cumulative.loc[end, countries].dropna().sort_values()
    fig = go.Figure(go.Bar(
        x=vals.values, y=[format_country(x) for x in vals.index],
        orientation="h", marker={"color": "#479B9F"},
        text=[fmt_count(v) for v in vals.values], textposition="outside",
        hovertemplate="%{y}<br>%{x:,.0f}<extra></extra>",
    ))
    fig.update_layout(
        title={"text": "Cumulative total at the end of the selected period", "font": {"size": 16}},
        height=max(260, 82 + len(vals) * 45),
        margin={"l": 10, "r": 70, "t": 55, "b": 15},
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis={"title": "Reported cumulative count", "showgrid": True, "gridcolor": "#E8EDF1"},
        yaxis={"title": ""},
    )
    return fig


def app():
    st.set_page_config(
        page_title="Global COVID-19 Explorer | JHU historical data",
        page_icon="🌐", layout="wide", initial_sidebar_state="expanded",
    )
    st.markdown("""<style>
    .block-container {max-width: 1270px; padding-top: 1.4rem; padding-bottom: 2.5rem;}
    .stMetric {border: 1px solid #DBE8EB; border-radius: 11px; padding: 12px 16px;
      background: #F8FBFB;}
    [data-testid='stSidebar'] {background-color:#F5FAFA;}
    h1 {letter-spacing: -.045em;}
    h2, h3 {letter-spacing: -.018em;}
    </style>""", unsafe_allow_html=True)

    st.markdown("<small style='letter-spacing:.15em;color:#2E8A8B;font-weight:700'>JHU CSSE · HISTORICAL DATA EXPLORER</small>", unsafe_allow_html=True)
    st.title("Global COVID-19 Explorer")
    st.caption("An interactive view of reported COVID-19 cases and deaths across countries | January 2020 – March 2023")

    try:
        # Cases are loaded first so options and available dates are coherent.
        cases = load_series("Cases")
    except RuntimeError as exc:
        st.error(str(exc))
        st.stop()

    with st.sidebar:
        st.markdown("### Explore the data")
        metric = st.selectbox("What to measure", ["Cases", "Deaths"], index=0)
        mode = st.radio("How to display", ["Daily change", "Cumulative total"], index=0)
        if metric == "Cases":
            frame = cases
        else:
            try:
                frame = load_series("Deaths")
            except RuntimeError as exc:
                st.error(str(exc))
                st.stop()
        options = sorted(frame.columns, key=lambda x: format_country(x).lower())
        defaults = [v for v in ("US", "India", "Brazil") if v in options]
        countries = st.multiselect(
            "Compare countries", options=options, default=defaults,
            format_func=format_country,
            help="Add or remove countries to compare their trends on the same timeline.",
        )
        start_date, final_date = frame.index.min().date(), frame.index.max().date()
        suggested_start = max(start_date, date(2020, 3, 1))
        date_range = st.slider(
            "Date range", min_value=start_date, max_value=final_date,
            value=(suggested_start, final_date), format="MMM YYYY",
        )
        smoothing = st.checkbox(
            "Use a 7-day moving average", value=True,
            disabled=mode != "Daily change",
            help="A rolling average of signed daily differences. It does not erase retrospective corrections.",
        )
        st.markdown("---")
        st.info(
            "**Archived dataset.** JHU stopped collecting global data on March 10, 2023. "
            "This app does not show current COVID-19 activity.", icon="ℹ️",
        )
        st.markdown("[Original JHU CSSE repository](https://github.com/CSSEGISandData/COVID-19)")

    if not countries:
        st.warning("Choose at least one country in the sidebar to begin.")
        st.stop()

    start = pd.Timestamp(date_range[0]); end = pd.Timestamp(date_range[1])
    subset = frame.loc[start:end, countries]
    if subset.empty:
        st.warning("No data are available in the selected date range.")
        st.stop()
    last = subset.index[-1]
    raw_daily = daily_from_cumulative(frame)
    last_daily = raw_daily.loc[last, countries]
    period_change = raw_daily.loc[start:end, countries].sum(axis=0, min_count=1)

    st.markdown("<div style='background:#EAF5F5;border-left:4px solid #3CA39A;padding:10px 15px;border-radius:6px;color:#245E5F;margin:10px 0 20px'>"
                "<b>Historical series only:</b> use the sidebar to add countries, switch between daily/cumulative counts, "
                "or change the observation window.</div>", unsafe_allow_html=True)

    a, b, c, d = st.columns(4)
    a.metric("Countries compared", f"{len(countries)}")
    b.metric(f"Reported cumulative {metric.lower()}", fmt_count(subset.loc[last].sum(min_count=1)))
    c.metric(f"Latest daily change · {metric.lower()}", fmt_count(last_daily.sum(min_count=1)))
    d.metric("Data shown through", last.strftime("%d %b %Y"))
    st.caption("Totals above sum only the countries currently selected; they are not worldwide totals.")

    tab_trends, tab_table, tab_method = st.tabs(["📈 Trends & comparison", "📋 Data & download", "🔎 Methods & quality"])
    with tab_trends:
        st.plotly_chart(line_chart(frame, countries, metric, mode, smoothing, start, end), use_container_width=True)
        st.markdown("---")
        left, right = st.columns([1.1, 0.9], gap="large")
        with left:
            st.plotly_chart(ranking_chart(frame, countries, last), use_container_width=True)
        with right:
            st.markdown("#### Change over your selected window")
            rows = pd.DataFrame({
                "Country": [format_country(c) for c in countries],
                "Reported change": [period_change[c] for c in countries],
                "Cumulative at end": [frame.at[last, c] for c in countries],
            })
            st.dataframe(rows, hide_index=True, use_container_width=True)
            st.caption(
                "The period change is the sum of the daily differences in the selected interval, "
                "including retrospective revisions. It is not a person-level incidence rate."
            )
    with tab_table:
        st.markdown("#### Country-day dataset")
        export = tidy_export(frame, countries, start, end, metric)
        st.dataframe(export.tail(60).iloc[::-1], use_container_width=True, hide_index=True)
        st.download_button(
            "Download selected data (CSV)", export.to_csv(index=False).encode("utf-8"),
            file_name=f"jhu_{metric.lower()}_{start.date()}_{end.date()}.csv", mime="text/csv",
        )
        st.caption("Displays the 60 most recent rows; CSV includes the full selected time window.")
    with tab_method:
        st.markdown("#### How the data are handled")
        st.markdown(
            """1. **Source:** JHU CSSE worldwide confirmed-case and death time-series CSVs, archived in March 2023.
2. **Geographic aggregation:** Province/state rows are summed within each source `Country/Region` to get country-level **cumulative** counts. The country names follow the archive's naming scheme.
3. **Daily change:** `today's cumulative − yesterday's cumulative`; the first observed date uses its original cumulative count as the initial report.
4. **Corrections:** Negative daily differences are retained because they indicate retrospective reporting adjustments, not negative infections. The 7-day mean smooths the **signed** differences.
5. **Interpretation:** Counts are reported confirmed events, not a standardized infection risk. Cross-country comparability depends on testing practices and reporting quality.
"""
        )
        revisions = raw_daily.loc[start:end, countries].lt(0).sum()
        qa = pd.DataFrame({
            "Country": [format_country(c) for c in countries],
            "Days with negative correction": [int(revisions[c]) for c in countries],
            "Missing cumulative days": [int(frame.loc[start:end,c].isna().sum()) for c in countries],
        })
        st.markdown("#### Quality checks for selected countries")
        st.dataframe(qa, hide_index=True, use_container_width=True)
        st.caption(
            f"Source coverage: {frame.index.min():%d %b %Y} to {frame.index.max():%d %b %Y}. "
            "Not updated after the JHU archive closed."
        )
        st.markdown("**References**")
        st.markdown(
            "- [JHU CSSE COVID-19 data repository](https://github.com/CSSEGISandData/COVID-19)\n"
            "- [Johns Hopkins Coronavirus Resource Center](https://coronavirus.jhu.edu/)"
        )

    st.markdown("---")
    st.caption("Academic visualization for JHU Data Science for Public Health in Python · Source: JHU CSSE · Runjiu Chen")


if __name__ == "__main__":
    app()
