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
    compare_depth,
    compare_photometry,
    compare_quadrants,
    compare_volume,
    fraction_within,
    get_quadrant_depth,
    list_asymmetric_failures,
)
from ztfalertvalidation.checks.photometry import PRIMARY_MAG_COLUMN
from ztfalertvalidation.checks.quadrants import N_QUADRANTS
from ztfalertvalidation.crossmatch import (
    MAX_SEPARATION_ARCSEC,
    get_matched_dza_table,
    get_matched_ipac_table,
)
from ztfalertvalidation.tables import get_dza_table, get_ipac_table

logger = logging.getLogger(__name__)

N_WORST = 10
MVP_MATCH_FRACTION = 0.99
MVP_SEPARATION_ARCSEC = 0.5
MVP_FLUX_FRACTION = 0.05
PHOTOMETRY_TITLES = {
    "magpsf": "PSF photometry",
    "magap": "Aperture photometry",
}


@dataclass
class Section:
    """
    One check, as it appears in the report
    """

    title: str
    text: str
    table: pd.DataFrame
    summary: dict[str, str]
    message: str


def verdict(passed: bool) -> str:
    """
    Say whether a requirement is met

    :param passed: Whether the requirement is met
    :return: Word to use in a message
    """
    return "is met" if passed else "is not met"


def get_programids(night: str, data_dir: Path | None = None) -> list[int]:
    """
    List the observing programs the alerts of a night come from

    :param night: Night, as a 'YYYYMMDD' string
    :param data_dir: Path to data directory
    :return: Program ids, of either pipeline
    """
    programs = set()
    for table in [get_ipac_table(night, data_dir), get_dza_table(night, data_dir)]:
        programs |= set(table["programid"].unique())

    return sorted(int(x) for x in programs)


def volume_section(night: str, data_dir: Path | None = None) -> Section:
    """
    Report the number of alerts and the volume of data of each pipeline

    :param night: Night, as a 'YYYYMMDD' string
    :param data_dir: Path to data directory
    :return: Section of the report
    """
    df = compare_volume(night, data_dir)

    alerts = df["n_alerts"]
    volume = df["volume_gb"]
    by_count = alerts["dza"] / alerts["ipac"] - 1

    text = (
        "The number of avro files each pipeline wrote for the night, their "
        "total size on disk, and the mean size of one alert."
    )

    message = (
        f"DZA produced {abs(by_count):.2%} "
        f"{'more' if by_count > 0 else 'fewer'} alerts than IPAC."
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
        "Alerts (DZA / IPAC)": f"{alerts['dza']:,} / {alerts['ipac']:,}",
        "Data volume (DZA / IPAC)": (
            f"{volume['dza']:.1f} GB / {volume['ipac']:.1f} GB"
        ),
    }

    return Section("Alert volume", text, table, summary, message)


def quadrant_section(night: str, data_dir: Path | None = None) -> Section:
    """
    Report how the two pipelines agree on each exposure quadrant

    :param night: Night, as a 'YYYYMMDD' string
    :param data_dir: Path to data directory
    :return: Section of the report
    """
    df = compare_quadrants(night, data_dir)

    # a quadrant neither pipeline produced alerts for counts NA, not zero, and
    # a comparison against NA is NA, which .all() would otherwise skip over
    read_out = df.dropna()
    both = read_out[(read_out > 0).all(axis="columns")]

    counts = {
        "quadrants in the night": len(df),
        "with no alerts from either pipeline": len(df) - len(read_out),
        "with alerts from both pipelines": len(both),
        "with alerts from IPAC only": int((df["n_dza"] == 0).sum()),
        "with alerts from DZA only": int((df["n_ipac"] == 0).sum()),
    }
    identical = int((both["n_dza"] == both["n_ipac"]).sum())
    counts["of those from both, with identical counts"] = identical
    counts["of those from both, with differing counts"] = len(both) - identical

    shares = [x / len(df) for x in list(counts.values())[:5]] + [
        identical / len(both),
        (len(both) - identical) / len(both),
    ]

    table = pd.DataFrame(
        {
            "quadrants": list(counts.values()),
            "share": [f"{x:.1%}" for x in shares],
        },
        index=list(counts),
    )

    difference = (both["n_dza"] - both["n_ipac"]).abs()
    differing = len(both) - identical

    text = (
        "Both pipelines see the same raw images. Alerts of one exposure share "
        "a Julian date, and each quadrant read out for that exposure has its "
        "own rcid, so a quadrant is one detector readout. The share of the "
        "first five rows is of all the night's quadrants, and of the last two "
        "is of the quadrants both pipelines processed."
    )

    message = (
        f"{identical / len(both):.1%} of the quadrants both pipelines "
        f"processed yield an identical number of alerts. Of the {differing} "
        f"that differ, {int((difference == 1).sum())} differ by one alert and "
        f"{int((difference > 1).sum())} by more, the largest difference being "
        f"{int(difference.max())} alerts. "
        f"{(difference <= 1).mean():.2%} of shared quadrants agree to within "
        "one alert."
    )

    summary = {
        "Exposures": f"{df.index.levshape[0]:,}",
        "Quadrants processed by both": (
            f"{len(both):,} ({len(both) / len(df):.1%} of the night)"
        ),
    }

    return Section("Quadrant coverage", text, table, summary, message)


def failure_section(night: str, data_dir: Path | None = None) -> Section:
    """
    Report the quadrants only one pipeline processed

    :param night: Night, as a 'YYYYMMDD' string
    :param data_dir: Path to data directory
    :return: Section of the report
    """
    df = list_asymmetric_failures(night, data_dir)
    quadrants = compare_quadrants(night, data_dir)

    ipac_only = int(df["n_dza"].eq(0).sum())
    dza_only = int(df["n_ipac"].eq(0).sum())
    n_exposures = quadrants.index.levshape[0]
    affected = df.index.get_level_values("jd").nunique()

    per_exposure = (
        df.assign(ipac_only=df["n_dza"] == 0, dza_only=df["n_ipac"] == 0)
        .groupby(level="jd")[["ipac_only", "dza_only"]]
        .sum()
    )
    table = (
        per_exposure.assign(total=per_exposure.sum(axis="columns"))
        .nlargest(N_WORST, "total")
        .sort_index()
        .rename(
            columns={
                "ipac_only": "quadrants IPAC only",
                "dza_only": "quadrants DZA only",
                "total": "quadrants affected",
            }
        )
    )
    table.index = [f"{x:.6f}" for x in table.index]

    text = (
        "One row per exposure, counting the quadrants of that exposure that "
        "only one pipeline produced alerts for. The "
        f"{N_WORST} exposures with the most affected quadrants are listed, by "
        "Julian date; the rest are in the table on disk."
    )

    message = (
        f"{affected / n_exposures:.1%} of exposures have at least one quadrant "
        f"(out of {N_QUADRANTS}) which was only processed successfully by one "
        f"of the two pipelines. Of the night's quadrants, "
        f"{ipac_only / len(quadrants):.1%} were processed by IPAC alone and "
        f"{dza_only / len(quadrants):.1%} by DZA alone."
    )

    summary = {
        "Quadrants only IPAC processed": (
            f"{ipac_only:,} ({ipac_only / len(quadrants):.1%})"
        ),
        "Quadrants only DZA processed": (
            f"{dza_only:,} ({dza_only / len(quadrants):.1%})"
        ),
    }

    return Section("Asymmetric processing failures", text, table, summary, message)


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

    counts = {}
    for name, df, column in [("IPAC", ipac, "DZAname"), ("DZA", dza, "IPACname")]:
        counts[name] = [
            len(df),
            int(df[column].notna().sum()),
            int(df[column].isna().sum()),
            int(quadrants[f"n_{name.lower()}"].sum()),
            int(df[column].isna().sum() - quadrants[f"n_{name.lower()}"].sum()),
        ]

    table = pd.DataFrame(
        counts,
        index=[
            "alerts",
            f'matched (within {MAX_SEPARATION_ARCSEC:.0f}")',
            "unmatched",
            "unmatched on a one-sided quadrant",
            "unmatched on a shared quadrant",
        ],
    )
    table["IPAC share"] = [f"{x / len(ipac):.2%}" for x in counts["IPAC"]]

    matched = counts["IPAC"][1] / len(ipac)
    text = (
        "Sources are matched by position within one quadrant of one "
        "exposure, since the two pipelines name the same source differently. "
        f"A source counts as matched when its counterpart lies within "
        f'{MAX_SEPARATION_ARCSEC:.0f}". The last row counts alerts on a '
        "quadrant both pipelines processed that have no counterpart within "
        "that radius. The shares are of IPAC alerts."
    )

    message = (
        f"{matched:.2%} of IPAC alerts have a DZA match. The MVP requires more "
        f"than {MVP_MATCH_FRACTION:.0%} of IPAC alerts to be matched, so this "
        f"requirement {verdict(matched > MVP_MATCH_FRACTION)}."
    )

    summary = {
        f'Sources matched (within {MAX_SEPARATION_ARCSEC:.0f}")': (
            f"{counts['IPAC'][1]:,} ({matched:.2%} of IPAC alerts)"
        ),
    }

    return Section("Source crossmatch", text, table, summary, message)


def astrometry_section(night: str, data_dir: Path | None = None) -> Section:
    """
    Report how closely the two pipelines agree on where a source is

    :param night: Night, as a 'YYYYMMDD' string
    :param data_dir: Path to data directory
    :return: Section of the report
    """
    separations = get_matched_ipac_table(night, data_dir)["DZAdist"].dropna()

    quantiles = {
        "median": separations.median(),
        "90th percentile": separations.quantile(0.9),
        "99th percentile": separations.quantile(0.99),
        "maximum": separations.max(),
    }
    table = pd.DataFrame(
        {"separation (arcsec)": [f"{x:.4f}" for x in quantiles.values()]},
        index=list(quantiles),
    )

    beyond = int((separations >= MVP_SEPARATION_ARCSEC).sum())
    text = (
        "The separation of the two pipelines' positions, over every matched "
        "pair. These are separations between the two pipelines, not absolute "
        "astrometry."
    )

    message = (
        f"The 99th percentile separation is "
        f'{quantiles["99th percentile"]:.4f}", within the '
        f'{MVP_SEPARATION_ARCSEC}" the MVP requires. {beyond} of '
        f"{len(separations):,} matched pairs lie beyond "
        f'{MVP_SEPARATION_ARCSEC}", the furthest at {quantiles["maximum"]:.4f}".'
    )

    return Section("Astrometric precision", text, table, {}, message)


def depth_section(night: str, data_dir: Path | None = None) -> Section:
    """
    Report how deep each pipeline reaches in each quadrant

    :param night: Night, as a 'YYYYMMDD' string
    :param data_dir: Path to data directory
    :return: Section of the report
    """
    df = compare_depth(night, data_dir)
    quadrants = len(get_quadrant_depth(night, data_dir))

    table = pd.DataFrame(
        {"limiting magnitude difference": [f"{x:.6f}" for x in df.iloc[:, 0]]},
        index=df.index,
    )

    text = (
        "The difference between the limiting magnitudes the two pipelines "
        "report for a quadrant, over the quadrants both processed. Every "
        "alert of a quadrant carries the same limiting magnitude."
    )

    message = (
        f"Over {quadrants:,} quadrants, the limiting magnitudes agree to "
        f"within {df.iloc[-1, 0]:.6f} magnitudes at the 99th percentile."
    )

    return Section("Limiting magnitude", text, table, {}, message)


def photometry_section(
    night: str, column: str, data_dir: Path | None = None
) -> Section:
    """
    Report how closely the two pipelines agree on one magnitude of a source

    :param night: Night, as a 'YYYYMMDD' string
    :param column: Magnitude to compare, such as 'magpsf'
    :param data_dir: Path to data directory
    :return: Section of the report
    """
    df = compare_photometry(night, column, data_dir)
    agreeing, pairs = fraction_within(night, MVP_FLUX_FRACTION, column, data_dir)

    table = pd.DataFrame(
        {
            "flux difference": [f"{x:.4%}" for x in df["flux difference"]],
            "magnitude difference": [f"{x:.6f}" for x in df["magnitude difference"]],
        },
        index=df.index,
    )

    text = (
        f"The difference between the {column} the two pipelines measure for "
        "one matched source, as a fraction of the flux and as a magnitude."
    )

    message = (
        f"{agreeing:,} of {pairs:,} matched pairs agree to within "
        f"{MVP_FLUX_FRACTION:.0%} in flux, which the MVP requires, leaving "
        f"{pairs - agreeing} that do not."
    )

    summary = (
        {
            f"Sources within {MVP_FLUX_FRACTION:.0%} in flux": (
                f"{agreeing / pairs:.3%} of matched pairs"
            )
        }
        if column == PRIMARY_MAG_COLUMN
        else {}
    )

    return Section(PHOTOMETRY_TITLES[column], text, table, summary, message)


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
        astrometry_section(night, data_dir),
        depth_section(night, data_dir),
        photometry_section(night, PRIMARY_MAG_COLUMN, data_dir),
        photometry_section(night, "magap", data_dir),
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


TEMPLATE = Template("""<!doctype html>
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
  --accent: #2f6f9f;
}
@media (prefers-color-scheme: dark) {
  :root {
    --ink: #e6e8ec;
    --faint: #9aa1ad;
    --rule: #2e333c;
    --panel: #1a1d23;
    --page: #11131a;
    --accent: #6fa8d0;
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
.message {
  border-left: 3px solid var(--accent);
  background: var(--panel);
  padding: 0.75rem 1rem;
  margin: 1.4rem 0 0;
  font-size: 0.95rem;
}
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
IPAC pipeline &middot; programid {{ programids }} &middot;
generated {{ generated }}</p>

<div class="summary">
{{ summary }}
</div>

{% for section in sections %}
<h2>{{ section.title }}</h2>
<p>{{ section.text }}</p>
{{ section.html }}
<p class="message">{{ section.message }}</p>
{% endfor %}

<footer>
Each check reads the cached alert tables of the night. The full tables are on
disk beside the alerts, as parquet.
</footer>

</main>
</body>
</html>
""")


def render_html(sections: list[Section], night: str, programids: list[int]) -> str:
    """
    Render the sections of a night as one self-contained html page

    :param sections: Sections of the report
    :param night: Night, as a 'YYYYMMDD' string
    :param programids: Observing programs the alerts come from
    :return: The page
    """
    return TEMPLATE.render(
        night=night,
        programids=", ".join(str(x) for x in programids),
        generated=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        summary=build_summary(sections, night).to_html(border=0, header=False),
        sections=[
            {
                "title": x.title,
                "text": x.text,
                "html": x.table.to_html(border=0),
                "message": x.message,
            }
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
    sections = build_sections(night, data_dir)
    programids = get_programids(night, data_dir)

    path.write_text(render_html(sections, night, programids))

    logger.info(f"Wrote report to {path}")
