from pathlib import Path
from typing import Dict, List

from pybt.data.bar import Bar
from pybt.data.loader import DataSpec, load_csv


def load_dir_csvs(dir_path: str) -> Dict[str, List[Bar]]:
    """Load multiple CSVs under a directory into {symbol: bars}.

    Symbol is derived from filename stem.
    """
    base = Path(dir_path)
    out: Dict[str, List[Bar]] = {}
    for p in base.glob("*.csv"):
        sym = p.stem.upper()
        out[sym] = load_csv(DataSpec(path=p))
    return out
