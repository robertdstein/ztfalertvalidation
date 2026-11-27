# ztfalertvalidation

Compare ZTF avro alerts from the DZA pipeline and the official IPAC pipeline.

## Installation

```bash
pip install -e ".[dev]"
```

## Configuration

Copy `example.env` to `.env`, and set the parent directory holding the alerts:

```bash
ZTFALERTVALIDATION_DATA_DIR=/path/to/DZAZTF
```

The alerts are expected to be laid out as one directory per night, each
containing one subdirectory per pipeline:

```
$ZTFALERTVALIDATION_DATA_DIR/
    <night>/
        dza/                      # DZA pipeline alerts
        ztf_public_<YYYYMMDD>/    # Official IPAC pipeline alerts
```

## Usage

```python
from ztfalertvalidation import get_dza_dir, get_ipac_dir, list_nights

list_nights()
# ['2026112']

get_dza_dir("2026112")
get_ipac_dir("2026112")
```
