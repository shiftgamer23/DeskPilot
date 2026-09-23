"""Download the Kaggle dataset and write the untouched 16-column variant to data/raw/support_tickets.jsonl.

Run once: python data/download_raw.py
"""
import sys
from pathlib import Path

import kagglehub
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import config

# Kaggle ships several CSVs with different column sets - only this one has the 16 columns we rely on.
EXPECTED_FILE = "aa_dataset-tickets-multi-lang-5-2-50-version.csv"
EXPECTED_ROWS, EXPECTED_COLS = 28587, 16


def main() -> None:
    path = Path(kagglehub.dataset_download("tobiasbueck/multilingual-customer-support-tickets"))
    df = pd.read_csv(path / EXPECTED_FILE)
    assert df.shape == (EXPECTED_ROWS, EXPECTED_COLS), f"Unexpected shape {df.shape}"
    config.RAW_TICKETS.parent.mkdir(parents=True, exist_ok=True)
    df.to_json(config.RAW_TICKETS, orient="records", lines=True, force_ascii=False)
    print(f"Wrote {len(df)} rows -> {config.RAW_TICKETS}")


if __name__ == "__main__":
    main()
