"""Loads the raw dataset and applies the Phase 1 cleaning rules. The raw file itself is never modified."""
import pandas as pd

from app import config

KEEP = ["ticket_id", "subject", "body", "answer", "type", "queue", "priority", "tag_1", "tag_2"]


def _clean(s: pd.Series) -> pd.Series:
    # The dataset stores newlines as a literal backslash + "n"; restore real newlines.
    return s.str.replace("\\n", "\n", regex=False).str.strip()


def load_tickets() -> pd.DataFrame:
    """English tickets that have a resolution.

    - ticket_id is stable: derived from the row's position in the raw file (e.g. T00042).
    - text is the retrieval / agent input: "subject\\n\\nbody", or body alone when subject is null (~16% of rows).
    - version and tag_3..tag_8 are dropped (unused / too sparse).
    """
    df = pd.read_json(config.RAW_TICKETS, lines=True)
    df.insert(0, "ticket_id", [f"T{i:05d}" for i in range(len(df))])
    df = df[df["language"] == "en"]
    df = df[df["answer"].notna()].copy()
    for col in ("subject", "body", "answer"):
        df[col] = _clean(df[col])
    df["text"] = df["body"].where(df["subject"].isna(), df["subject"] + "\n\n" + df["body"])
    return df[KEEP + ["text"]].reset_index(drop=True)


if __name__ == "__main__":
    t = load_tickets()
    print(f"{len(t)} English tickets with an answer; {t['subject'].isna().sum()} without subject")
    print(t.iloc[0].to_dict())
