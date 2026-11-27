"""
Scripts for reporting the result of each check
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from jinja2 import Template

from ztfalertvalidation.checks import (
    compare_quadrants,
    compare_volume,
    list_asymmetric_failures,
)
from ztfalertvalidation.crossmatch import (
    MAX_SEPARATION_ARCSEC,
    get_matched_dza_table,
    get_matched_ipac_table,
)

logger = logging.getLogger(__name__)

N_WORST = 10


@dataclass
class Section:
    """
    One check, as it appears in the report
    """

    title: str
    text: str
    table: pd.DataFrame
    summary: dict[str, str]


def volume_section(night: str, data_dir: Path | None = None) -> Section:
    """
    Report the number of alerts and the volume of data of each pipeline

    :param night: Night, as a 'YYYYMMDD' string
    :param data_dir: Path to data directory
    :return: Section of the report
    """
    df = compare_volume(night, data_dir)

    ratio = df.loc["dza", "n_alerts"] / df.loc["ipac", "n_alerts"] - 1
    text = (
        "Counts every avro file each pipeline wrote for the night, and the "
        "space it takes. A pipeline that silently dropped part of the night "
        "shows up here first, before anything is read. DZA wrote "
        f"{abs(ratio):.2%} {'more' if ratio > 0 else 'fewer'} alerts than IPAC."
    )

    table = df.round(2).rename(
        index={"dza": "DZA", "ipac": "IPAC"},
        columns={
            "n_alerts": "alerts",
            "volume_gb": "volume (GB)",
            "mean_alert_kb": "mean alert (kB)",
        },
    )

    summary = {
        "Alerts (DZA / IPAC)": (
            f"{table.loc['DZA', 'alerts']:,} / {table.loc['IPAC', 'alerts']:,}"
        ),
        "Data volume (DZA / IPAC)": (
            f"{table.loc['DZA', 'volume (GB)']:.1f} GB / "
            f"{table.loc['IPAC', 'volume (GB)']:.1f} GB"
        ),
    }

    return Section("Alert volume", text, table, summary)


def quadrant_section(night: str, data_dir: Path | None = None) -> Section:
    """
    Report how the two pipelines agree on each exposure quadrant

    :param night: Night, as a 'YYYYMMDD' string
    :param data_dir: Path to data directory
    :return: Section of the report
    """
    df = compare_quadrants(night, data_dir)

    read_out = df.dropna(how="all")
    both = read_out[(read_out > 0).all(axis="columns")]
    diff = both["n_dza"] - both["n_ipac"]

    summary = pd.DataFrame(
        {
            "quadrants": [
                len(df),
                len(read_out),
                len(both),
                int((diff == 0).sum()),
                int((diff != 0).sum()),
            ]
        },
        index=[
            "in the night",
            "with alerts from either pipeline",
            "with alerts from both",
            "with identical counts",
            "with differing counts",
        ],
    )

    text = (
        "Alerts of one exposure share a Julian date, and each quadrant read "
        "out for that exposure has its own rcid, so a quadrant is one "
        "detector readout. Both pipelines see the same sky, so a quadrant "
        "they both processed should hold the same number of alerts. "
        f"Of the quadrants both processed, {(diff == 0).mean():.1%} agree "
        "exactly. Quadrants no pipeline produced alerts for are left out: "
        "the night's dead channels sit there and say nothing about either "
        "pipeline."
    )

    headline = {
        "Quadrants processed by both": f"{len(both):,}",
        "Quadrants with differing counts": f"{int((diff != 0).sum()):,}",
    }

    return Section("Quadrant coverage", text, summary, headline)


def failure_section(night: str, data_dir: Path | None = None) -> Section:
    """
    Report the quadrants only one pipeline processed

    :param night: Night, as a 'YYYYMMDD' string
    :param data_dir: Path to data directory
    :return: Section of the report
    """
    df = list_asymmetric_failures(night, data_dir)

    per_exposure = (
        df.assign(
            ipac_only=df["n_dza"] == 0,
            dza_only=df["n_ipac"] == 0,
        )
        .groupby(level="jd")[["ipac_only", "dza_only"]]
        .sum()
    )
    worst = (
        per_exposure.assign(quadrants=per_exposure.sum(axis="columns"))
        .nlargest(N_WORST, "quadrants")
        .rename(columns={"ipac_only": "IPAC only", "dza_only": "DZA only"})
    )
    worst.index = [f"{x:.6f}" for x in worst.index]

    text = (
        "A quadrant one pipeline produced alerts for and the other did not "
        "at all. This is the failure that matters: it is not a detection "
        "difference but a readout missing from one side, so every source on "
        f"it is lost. {int(df['n_dza'].eq(0).sum())} quadrants are IPAC only "
        f"and {int(df['n_ipac'].eq(0).sum())} are DZA only, spread over "
        f"{df.index.get_level_values('jd').nunique()} exposures. The "
        f"{N_WORST} worst exposures are listed; the rest are in the table on "
        "disk."
    )

    headline = {
        "Quadrants only one pipeline processed": f"{len(df):,}",
        "Exposures affected": f"{df.index.get_level_values('jd').nunique():,}",
    }

    return Section("Asymmetric processing failures", text, worst, headline)


def crossmatch_section(night: str, data_dir: Path | None = None) -> Section:
    """
    Report how the sources of the two pipelines map onto each other

    :param night: Night, as a 'YYYYMMDD' string
    :param data_dir: Path to data directory
    :return: Section of the report
    """
    ipac = get_matched_ipac_table(night, data_dir)
    dza = get_matched_dza_table(night, data_dir)

    quadrants = list_asymmetric_failures(night, data_dir)
    lost = {"ipac": quadrants["n_ipac"].sum(), "dza": quadrants["n_dza"].sum()}

    summary = pd.DataFrame(
        {
            "ipac": [
                len(ipac),
                int(ipac["DZAname"].notna().sum()),
                int(ipac["DZAname"].isna().sum()),
                int(lost["ipac"]),
                int(ipac["DZAname"].isna().sum() - lost["ipac"]),
            ],
            "dza": [
                len(dza),
                int(dza["IPACname"].notna().sum()),
                int(dza["IPACname"].isna().sum()),
                int(lost["dza"]),
                int(dza["IPACname"].isna().sum() - lost["dza"]),
            ],
        },
        index=[
            "alerts",
            "matched",
            "unmatched",
            "unmatched on a one-sided quadrant",
            "unmatched on a shared quadrant",
        ],
    ).rename(columns={"ipac": "IPAC", "dza": "DZA"})

    separations = ipac["DZAdist"].dropna()
    text = (
        "The two pipelines name the same source differently, so sources are "
        "matched by position within one quadrant of one exposure. A source "
        f"counts as matched within {MAX_SEPARATION_ARCSEC:.0f} arcsecond. "
        f"The median separation of a matched pair is "
        f"{separations.median():.4f} arcseconds, so where both pipelines "
        "find a source they agree on where it is. The last row is the one to "
        "watch: an alert on a quadrant both pipelines processed that still "
        "has no counterpart is a genuine difference in what they detected, "
        "not a readout they disagreed about."
    )

    headline = {
        "Sources matched": f"{summary.loc['matched', 'IPAC']:,}",
        "Sources unmatched on a shared quadrant": (
            f"{summary.loc['unmatched on a shared quadrant', 'IPAC']:,} IPAC / "
            f"{summary.loc['unmatched on a shared quadrant', 'DZA']:,} DZA"
        ),
    }

    return Section("Source crossmatch", text, summary, headline)


def build_sections(night: str, data_dir: Path | None = None) -> list[Section]:
    """
    Run every check and report it

    :param night: Night, as a 'YYYYMMDD' string
    :param data_dir: Path to data directory
    :return: Sections of the report
    """
    return [
        volume_section(night, data_dir),
        quadrant_section(night, data_dir),
        failure_section(night, data_dir),
        crossmatch_section(night, data_dir),
    ]


def build_summary(sections: list[Section], night: str) -> pd.DataFrame:
    """
    Collect the headline numbers the sections offer

    :param sections: Sections of the report
    :param night: Night, as a 'YYYYMMDD' string
    :return: Table of one row per headline number
    """
    rows = {"Night": night}
    for section in sections:
        rows |= section.summary

    return pd.DataFrame({"value": list(rows.values())}, index=list(rows))


TEMPLATE = Template(
    """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>ZTF alert validation &mdash; {{ night }}</title>
<style>
:root {
  --ink: #16181d;
  --faint: #6b7280;
  --rule: #e2e5ea;
  --panel: #f7f8fa;
  --page: #ffffff;
}
@media (prefers-color-scheme: dark) {
  :root {
    --ink: #e6e8ec;
    --faint: #9aa1ad;
    --rule: #2e333c;
    --panel: #1a1d23;
    --page: #11131a;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0;
  padding: 3rem 1.5rem 6rem;
  background: var(--page);
  color: var(--ink);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica,
    Arial, sans-serif;
  font-size: 16px;
  line-height: 1.65;
}
main { max-width: 46rem; margin: 0 auto; }
h1 {
  font-size: 1.6rem;
  font-weight: 600;
  letter-spacing: -0.01em;
  margin: 0 0 0.3rem;
}
h2 {
  font-size: 1.05rem;
  font-weight: 600;
  margin: 3rem 0 0.6rem;
  padding-top: 1.5rem;
  border-top: 1px solid var(--rule);
}
.sub { color: var(--faint); font-size: 0.9rem; margin: 0 0 2.5rem; }
p { margin: 0 0 1.1rem; }
.summary {
  background: var(--panel);
  border: 1px solid var(--rule);
  border-radius: 6px;
  padding: 0.4rem 1.2rem;
}
table {
  border-collapse: collapse;
  width: 100%;
  font-size: 0.9rem;
  margin: 0.4rem 0 0;
}
th, td {
  text-align: right;
  padding: 0.42rem 0.6rem;
  border-bottom: 1px solid var(--rule);
}
th:first-child, td:first-child { text-align: left; }
thead th {
  color: var(--faint);
  font-weight: 500;
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
tbody tr:last-child td { border-bottom: none; }
td { font-variant-numeric: tabular-nums; }
.summary table { font-size: 0.95rem; }
.summary thead { display: none; }
.summary td:last-child { font-weight: 600; }
footer {
  color: var(--faint);
  font-size: 0.8rem;
  margin-top: 4rem;
}
</style>
</head>
<body>
<main>

<h1>ZTF alert validation</h1>
<p class="sub">Night {{ night }} &middot; DZA pipeline against the official
IPAC pipeline
&middot; generated {{ generated }}</p>

<div class="summary">
{{ summary }}
</div>

{% for section in sections %}
<h2>{{ section.title }}</h2>
<p>{{ section.text }}</p>
{{ section.html }}
{% endfor %}

<footer>
Each check reads the cached alert tables of the night. The full tables are on
disk beside the alerts, as parquet.
</footer>

</main>
</body>
</html>
"""
)


def render_html(sections: list[Section], night: str) -> str:
    """
    Render the sections of a night as one self-contained html page

    :param sections: Sections of the report
    :param night: Night, as a 'YYYYMMDD' string
    :return: The page
    """
    return TEMPLATE.render(
        night=night,
        generated=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        summary=build_summary(sections, night).to_html(border=0, header=False),
        sections=[
            {"title": x.title, "text": x.text, "html": x.table.to_html(border=0)}
            for x in sections
        ],
    )


def write_html_report(night: str, path: Path, data_dir: Path | None = None) -> None:
    """
    Run every check of a night and write the report as an html page

    :param night: Night, as a 'YYYYMMDD' string
    :param path: Path of the html file to write
    :param data_dir: Path to data directory
    :return: None
    """
    path.write_text(render_html(build_sections(night, data_dir), night))

    logger.info(f"Wrote report to {path}")
