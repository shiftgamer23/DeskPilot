"""Downloads and extracts the prebuilt retrieval index + raw dataset from a GitHub Release asset.

Local dev never needs this - data/download_raw.py + app/tools/build_index.py already produce these
files directly on disk. This script exists only for deploy-time hosts (see render.yaml) whose
build step starts from a clean checkout and can't afford to re-download 28K Kaggle rows and
re-embed them on every build.

Run: INDEX_DATA_URL=<github release asset .zip url> python scripts/fetch_index_data.py
"""
import os
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_MARKER = ROOT / "data" / "index" / "chroma" / "chroma.sqlite3"


def main() -> None:
    if _MARKER.exists():
        print("Index already present on disk - skipping download")
        return
    url = os.environ.get("INDEX_DATA_URL")
    if not url:
        print("INDEX_DATA_URL not set and no local index found - retrieval will fail to start")
        return
    dest = ROOT / "_index_data.zip"
    print(f"Downloading index/data bundle from {url} ...")
    urllib.request.urlretrieve(url, dest)
    print("Extracting...")
    with zipfile.ZipFile(dest) as zf:
        zf.extractall(ROOT / "data")
    dest.unlink()
    print("Done.")


if __name__ == "__main__":
    main()
