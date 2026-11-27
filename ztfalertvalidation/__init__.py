"""
ztfalertvalidation compares ZTF avro alerts from the DZA pipeline
and the official IPAC pipeline
"""

from ztfalertvalidation.paths import (
    get_data_dir,
    get_dza_dir,
    get_ipac_dir,
    get_night_dir,
    list_nights,
)
