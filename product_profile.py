"""Loads product records and maps detections to products."""
from pathlib import Path
import pandas as pd

PRODUCTS_CSV = Path(__file__).parent / "data" / "products.csv"


def load_products() -> pd.DataFrame:
    df = pd.read_csv(PRODUCTS_CSV, sep=None, engine="python", encoding="utf-8-sig")
    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")
    if "name" not in df.columns:
        raise ValueError(f"products.csv is missing a 'name' column. Found: {list(df.columns)}")

    # drop repeated header rows and duplicate products
    df["marker_id"] = pd.to_numeric(df["marker_id"], errors="coerce")
    df = df.dropna(subset=["marker_id"])
    df["marker_id"] = df["marker_id"].astype(int)
    df = df.drop_duplicates(subset="marker_id").reset_index(drop=True)
    return df

def get_product_by_marker(marker_id: int):
    """Returns a product as a dict, or None if the marker is unknown."""
    df = load_products()
    row = df[df["marker_id"] == marker_id]
    return None if row.empty else row.iloc[0].to_dict()


def get_product_by_name(name: str):
    df = load_products()
    row = df[df["name"] == name]
    return None if row.empty else row.iloc[0].to_dict()
