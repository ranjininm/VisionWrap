"""Optional printable ArUco markers (one per product in data/products.csv).
The app can build a ZIP of them for you (sidebar button), so you never need to run this by hand.
You can still run it directly:  python generate_markers.py"""
import io
import zipfile
from pathlib import Path
import cv2
import pandas as pd

CSV = Path(__file__).parent / "data" / "products.csv"


def marker_images():
    """Yields (filename, png_bytes) for every product."""
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    df = pd.read_csv(CSV, sep=None, engine="python", encoding="utf-8-sig")
    df.columns = df.columns.str.strip().str.lower()
    df["marker_id"] = pd.to_numeric(df["marker_id"], errors="coerce")
    df = df.dropna(subset=["marker_id"]).drop_duplicates("marker_id")
    for _, row in df.iterrows():
        mid = int(row["marker_id"])
        if hasattr(cv2.aruco, "generateImageMarker"):
            img = cv2.aruco.generateImageMarker(dictionary, mid, 400)
        else:
            img = cv2.aruco.drawMarker(dictionary, mid, 400)
        img = cv2.copyMakeBorder(img, 50, 110, 50, 50, cv2.BORDER_CONSTANT, value=255)
        cv2.putText(img, f"ID {mid}: {row['name']}", (50, img.shape[0] - 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, 0, 2)
        ok, buf = cv2.imencode(".png", img)
        yield f"marker_{mid:02d}.png", buf.tobytes()


def markers_zip_bytes():
    mem = io.BytesIO()
    with zipfile.ZipFile(mem, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in marker_images():
            z.writestr(name, data)
    return mem.getvalue()


if __name__ == "__main__":
    out = Path("markers"); out.mkdir(exist_ok=True)
    for name, data in marker_images():
        (out / name).write_bytes(data)
    print("Markers saved in the 'markers' folder.")
