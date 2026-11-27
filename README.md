# ztfalertvalidation

Compare ZTF avro alerts from the DZA pipeline and the official IPAC pipeline.

## Installation

```bash
pip install -e ".[dev]"
```

## Configuration

Copy `example.env` to `.env`, and set the parent directory holding the alerts:

```bash
ZTF_DATA_DIR=/path/to/DZAZTF
```

The alerts are expected to be laid out as one directory per night, each
containing one subdirectory per pipeline:

```
$ZTF_DATA_DIR/
    <YYYYMMDD>/
        dza/                      # DZA pipeline alerts
        ztf_public_<YYYYMMDD>/    # Official IPAC pipeline alerts
```

## Usage

```python
from ztfalertvalidation import get_dza_dir, get_ipac_dir, list_nights, load_alerts

list_nights()
# ['20261112']

df = load_alerts(get_ipac_dir("20261112"))
```

`load_alerts` returns one row per alert, with the `candidate` fields raised to
the top level. The cutouts, the previous candidates and the forced photometry
history are left out.
