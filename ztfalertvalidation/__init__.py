"""
ztfalertvalidation compares ZTF avro alerts from the DZA pipeline
and the official IPAC pipeline
"""

from ztfalertvalidation.avro import load_alerts, load_avro, unpack_record
from ztfalertvalidation.checks import (
    compare_depth,
    compare_photometry,
    compare_quadrants,
    compare_sources,
    compare_volume,
    fraction_within,
    get_quadrant_depth,
    list_asymmetric_failures,
)
from ztfalertvalidation.crossmatch import (
    add_matches,
    get_ipac_matches,
    get_matched_dza_table,
    get_matched_ipac_table,
    match_tables,
)
from ztfalertvalidation.download import (
    download_ipac_alerts,
    get_ipac_url,
    unpack_alerts,
)
from ztfalertvalidation.paths import (
    get_data_dir,
    get_dza_dir,
    get_ipac_dir,
    get_night_dir,
    list_nights,
)
from ztfalertvalidation.plots import (
    find_matched_pair,
    plot_alert_pair,
)
from ztfalertvalidation.report import (
    Section,
    build_sections,
    build_summary,
    get_programids,
    render_html,
    write_html_report,
)
from ztfalertvalidation.tables import (
    get_dza_table,
    get_ipac_table,
    load_cached_table,
)
