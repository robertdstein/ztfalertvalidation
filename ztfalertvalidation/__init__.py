"""
ztfalertvalidation compares ZTF avro alerts from the DZA pipeline
and the official IPAC pipeline
"""

from ztfalertvalidation.avro import load_alerts, load_avro, unpack_record
from ztfalertvalidation.checks import (
    compare_quadrants,
    compare_volume,
    list_asymmetric_failures,
)
from ztfalertvalidation.crossmatch import (
    add_nearest,
    get_matched_dza_table,
    get_matched_ipac_table,
)
from ztfalertvalidation.paths import (
    get_data_dir,
    get_dza_dir,
    get_ipac_dir,
    get_night_dir,
    list_nights,
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
