"""
VisionWrap core helpers.

Pure Python (no Streamlit), so everything here can be tested on its own.

Contains:
  * product / packaging normalisation
  * downloadable packing sheet (TXT + printable HTML)
  * virtual warehouse layout, A* routing, pick-order optimisation,
    random / dynamic obstacles and an HTML grid renderer
"""

import heapq
import html
import itertools
import json
import random
from datetime import datetime

# =========================================================
# CONSTANTS
# =========================================================

CATEGORIES = [
    "electronics",
    "electronics_accessory",
    "fragile_item",
    "clothing",
    "book",
    "household_item",
    "cosmetic",
    "food_container",
    "toy",
    "other",
]

CONFIDENCE_OPTIONS = ["high", "medium", "low"]
FRAGILITY_OPTIONS = ["potentially_fragile", "potentially_durable", "unknown"]
SIZE_OPTIONS = ["small", "medium", "large", "unknown"]

STORAGE_ZONES = [
    "A - Fragile Goods",
    "B - Electronics",
    "C - General Storage",
    "D - Lightweight Goods",
    "E - Large Items",
    "F - Restricted / Special Handling",
]

SIZE_GUIDE = {
    "small": "Small - compact mailer or small corrugated box",
    "medium": "Medium - standard corrugated shipping box",
    "large": "Large - large corrugated box (double-wall if heavy)",
    "unknown": "Unknown - measure the item before choosing a box",
}

# =========================================================
# TEXT / PRODUCT HELPERS
# =========================================================


def safe_text(value, default="Not available"):
    if value is None:
        return default
    if isinstance(value, str):
        value = value.strip()
        return value if value else default
    return str(value)


def pretty_label(value, default="Not available"):
    text = safe_text(value, "")
    return text.replace("_", " ").title() if text else default


def as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str):
        return [value] if value.strip() else []
    return [value]


def split_lines(value):
    if isinstance(value, list):
        return [str(i).strip() for i in value if str(i).strip()]
    if not value:
        return []
    return [line.strip() for line in str(value).splitlines() if line.strip()]


def parse_json_value(value):
    if isinstance(value, (dict, list)):
        return value
    if not value:
        return None
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None


def format_dimensions(dimensions):
    dimensions = parse_json_value(dimensions) if isinstance(dimensions, str) else dimensions
    if not dimensions:
        return ""
    if isinstance(dimensions, dict):
        return " x ".join(f"{k}: {v}" for k, v in dimensions.items()) + " cm"
    if isinstance(dimensions, (list, tuple)):
        return " x ".join(str(v) for v in dimensions) + " cm"
    return str(dimensions)


def normalize_packaging(packaging):
    if not isinstance(packaging, dict):
        packaging = {}

    def text(key, *fallbacks):
        for name in (key, *fallbacks):
            value = packaging.get(name)
            if value not in (None, ""):
                return str(value)
        return ""

    return {
        "recommended_box": text("recommended_box"),
        "outer_material": text("outer_material"),
        "cushioning": text("cushioning"),
        "void_fill": text("void_fill"),
        "orientation": text("orientation"),
        "protection_features": as_list(packaging.get("protection_features")),
        "reasoning": text("reasoning", "packaging_reasoning"),
        "sustainability_tip": text("sustainability_tip"),
    }


def product_from_record(record):
    """Convert a database record into the product dictionary used by the app."""
    if not record:
        return None

    packaging = record.get("finalized_packaging") or {}
    if not isinstance(packaging, dict) or not packaging:
        packaging = {
            "recommended_box": record.get("recommended_box", ""),
            "outer_material": record.get("outer_material", ""),
            "cushioning": record.get("cushioning", ""),
            "void_fill": record.get("void_fill", ""),
            "orientation": record.get("orientation", ""),
            "protection_features": record.get("protection_features", []),
            "reasoning": record.get("packaging_reasoning", ""),
            "sustainability_tip": record.get("sustainability_tip", ""),
        }

    return {
        "product_name": record.get("product_name", ""),
        "product_category": record.get("product_category", "other"),
        "description": record.get("description", ""),
        "visible_material": record.get("visible_material", "unknown"),
        "confidence": record.get("confidence", "low"),
        "fragility": record.get("fragility", "unknown"),
        "estimated_size_class": record.get("estimated_size_class", "unknown"),
        "dimensions_cm": parse_json_value(record.get("dimensions_cm")),
        "weight_g": record.get("weight_g"),
        "packaging": normalize_packaging(packaging),
        "risk_factors": as_list(record.get("risk_factors")),
        "packing_steps": as_list(record.get("packing_steps")),
        "warnings": as_list(record.get("warnings")),
        "confirmed": True,
    }


def choose_storage_zone(product):
    """Automated decision: pick a warehouse zone from the product assessment."""
    fragility = str(product.get("fragility", "unknown")).lower()
    category = str(product.get("product_category", "other")).lower()
    size = str(product.get("estimated_size_class", "unknown")).lower()

    if fragility == "potentially_fragile":
        return STORAGE_ZONES[0]
    if "electronic" in category:
        return STORAGE_ZONES[1]
    if size == "large":
        return STORAGE_ZONES[4]
    if category == "clothing":
        return STORAGE_ZONES[3]
    return STORAGE_ZONES[2]


def package_size_text(product):
    size = str(product.get("estimated_size_class", "unknown")).lower()
    text = SIZE_GUIDE.get(size, SIZE_GUIDE["unknown"])
    measured = format_dimensions(product.get("dimensions_cm"))
    if measured:
        text += f" (item dimensions: {measured})"
    return text


# =========================================================
# DOWNLOADABLE PACKING SHEET
# =========================================================


def _sheet_data(product, record_id=None):
    pk = normalize_packaging(product.get("packaging"))
    return {
        "title": "VisionWrap Packing Sheet",
        "meta": [
            ("Generated", datetime.now().strftime("%Y-%m-%d %H:%M")),
            ("Record ID", str(record_id) if record_id is not None else "Not saved yet"),
            ("AI engine", safe_text(product.get("ai_provider"), "Not recorded")),
        ],
        "identification": [
            ("Product", safe_text(product.get("product_name"))),
            ("Category", pretty_label(product.get("product_category"))),
            ("Confidence", pretty_label(product.get("confidence"))),
        ],
        "description": safe_text(product.get("description")),
        "details": [
            ("Visible material", pretty_label(product.get("visible_material"))),
            ("Fragility", pretty_label(product.get("fragility"))),
            ("Size class", pretty_label(product.get("estimated_size_class"))),
        ],
        "packaging": [
            ("Packaging material", safe_text(pk["outer_material"])),
            ("Package size", package_size_text(product)),
            ("Box type", safe_text(pk["recommended_box"])),
            ("Cushioning", safe_text(pk["cushioning"])),
            ("Void fill", safe_text(pk["void_fill"])),
            ("Orientation", safe_text(pk["orientation"])),
            ("Reasoning", safe_text(pk["reasoning"])),
        ],
        "protection": [str(i) for i in as_list(pk["protection_features"])],
        "steps": [str(i) for i in as_list(product.get("packing_steps"))],
        "risks": [str(i) for i in as_list(product.get("risk_factors"))],
        "warnings": [str(i) for i in as_list(product.get("warnings"))],
        "sustainability": safe_text(pk["sustainability_tip"], ""),
    }


def build_packing_sheet_text(product, record_id=None):
    d = _sheet_data(product, record_id)
    out = [d["title"].upper(), "=" * len(d["title"])]
    out += [f"{k}: {v}" for k, v in d["meta"]]

    def block(title, rows=None, items=None, text=None, numbered=False):
        out.append("")
        out.append(title.upper())
        out.append("-" * len(title))
        if rows:
            out.extend(f"{k}: {v}" for k, v in rows)
        if text:
            out.append(text)
        if items is not None:
            if not items:
                out.append("None listed.")
            for n, item in enumerate(items, 1):
                out.append(f"{n}. {item}" if numbered else f"- {item}")

    block("Product identification", rows=d["identification"])
    block("Product description", text=d["description"])
    block("Product details", rows=d["details"])
    block("Packaging recommendation", rows=d["packaging"])
    block("Protection features", items=d["protection"])
    block("Packing instructions", items=d["steps"], numbered=True)
    block("Shipping risks", items=d["risks"])
    block("Important warnings", items=d["warnings"])
    if d["sustainability"]:
        block("Sustainability tip", text=d["sustainability"])
    out += ["", "AI recommendations must be reviewed by a person before shipping."]
    return "\n".join(out)


def build_packing_sheet_html(product, record_id=None):
    d = _sheet_data(product, record_id)
    e = html.escape

    def rows(pairs):
        return "".join(
            f"<tr><th>{e(k)}</th><td>{e(v)}</td></tr>" for k, v in pairs
        )

    def items(values, ordered=False):
        if not values:
            return "<p class='muted'>None listed.</p>"
        tag = "ol" if ordered else "ul"
        return f"<{tag}>" + "".join(f"<li>{e(v)}</li>" for v in values) + f"</{tag}>"

    warnings_html = (
        "<ul class='warn'>" + "".join(f"<li>{e(w)}</li>" for w in d["warnings"]) + "</ul>"
        if d["warnings"]
        else "<p class='muted'>None listed.</p>"
    )
    sustain = (
        f"<h2>Sustainability tip</h2><p>{e(d['sustainability'])}</p>"
        if d["sustainability"]
        else ""
    )

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>{e(d['title'])}</title>
<style>
body{{font-family:Arial,Helvetica,sans-serif;color:#172b4d;max-width:780px;margin:32px auto;padding:0 20px;line-height:1.5}}
h1{{color:#1d4ed8;margin-bottom:4px}} h2{{border-bottom:2px solid #dbeafe;padding-bottom:4px;margin-top:28px;font-size:18px}}
table{{border-collapse:collapse;width:100%}} th{{text-align:left;width:32%;color:#526985;font-weight:600;vertical-align:top}}
th,td{{padding:6px 8px;border-bottom:1px solid #e3eaf4}} .muted{{color:#718096}}
.warn li{{color:#92400e}} .meta{{color:#718096;font-size:13px}} .foot{{margin-top:30px;color:#718096;font-size:12px}}
@media print{{body{{margin:0}}}}
</style></head><body>
<h1>{e(d['title'])}</h1>
<div class="meta">{' &middot; '.join(e(k) + ': ' + e(v) for k, v in d['meta'])}</div>
<h2>Product identification</h2><table>{rows(d['identification'])}</table>
<h2>Product description</h2><p>{e(d['description'])}</p><table>{rows(d['details'])}</table>
<h2>Packaging recommendation</h2><table>{rows(d['packaging'])}</table>
<h2>Protection features</h2>{items(d['protection'])}
<h2>Packing instructions</h2>{items(d['steps'], ordered=True)}
<h2>Shipping risks</h2>{items(d['risks'])}
<h2>Important warnings</h2>{warnings_html}
{sustain}
<div class="foot">AI recommendations must be reviewed by a person before shipping.
Use your browser's Print &rarr; Save as PDF to create a PDF copy.</div>
</body></html>"""


def build_product_json(product, record_id=None):
    clean = {k: v for k, v in product.items() if not str(k).startswith("_")}
    clean["record_id"] = record_id
    clean["package_size_guidance"] = package_size_text(product)
    return json.dumps(clean, indent=2, ensure_ascii=False, default=str)


# =========================================================
# VIRTUAL WAREHOUSE LAYOUT
# =========================================================

GRID_ROWS = 12
GRID_COLS = 16
DOCK = (11, 0)  # receiving dock where the robot starts

# Shelf blocks are static obstacles. The pickup cell is the aisle cell
# directly in front of each block.
ZONE_LAYOUT = {
    "A": {"rows": (1, 3), "cols": (2, 5), "pickup": (4, 3), "color": "#fecaca"},
    "B": {"rows": (1, 3), "cols": (7, 10), "pickup": (4, 8), "color": "#bfdbfe"},
    "C": {"rows": (1, 3), "cols": (12, 14), "pickup": (4, 13), "color": "#e5e7eb"},
    "D": {"rows": (6, 8), "cols": (2, 5), "pickup": (9, 3), "color": "#bbf7d0"},
    "E": {"rows": (6, 8), "cols": (7, 10), "pickup": (9, 8), "color": "#fde68a"},
    "F": {"rows": (6, 8), "cols": (12, 14), "pickup": (9, 13), "color": "#ddd6fe"},
}


def zone_letter(zone_name):
    letter = str(zone_name or "").strip()[:1].upper()
    return letter if letter in ZONE_LAYOUT else None


def shelf_cells():
    cells = set()
    for zone in ZONE_LAYOUT.values():
        for r in range(zone["rows"][0], zone["rows"][1] + 1):
            for c in range(zone["cols"][0], zone["cols"][1] + 1):
                cells.add((r, c))
    return cells


def pickup_cells():
    return {z["pickup"] for z in ZONE_LAYOUT.values()}


def protected_cells():
    return {DOCK} | pickup_cells()


def can_place_obstacle(cell, rows=GRID_ROWS, cols=GRID_COLS):
    r, c = cell
    return (
        0 <= r < rows
        and 0 <= c < cols
        and cell not in shelf_cells()
        and cell not in protected_cells()
    )


# =========================================================
# A* PATHFINDING
# =========================================================


def astar_path(start, goal, blocked, rows=GRID_ROWS, cols=GRID_COLS):
    """Shortest 4-direction path, or [] if none exists."""
    if start in blocked or goal in blocked:
        return []
    if start == goal:
        return [start]

    def h(cell):
        return abs(cell[0] - goal[0]) + abs(cell[1] - goal[1])

    heap = [(h(start), 0, start)]
    best = {start: 0}
    parent = {}

    while heap:
        _, cost, current = heapq.heappop(heap)

        if current == goal:
            path = [goal]
            while path[-1] != start:
                path.append(parent[path[-1]])
            path.reverse()
            return path

        if cost > best.get(current, float("inf")):
            continue

        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nxt = (current[0] + dr, current[1] + dc)
            if not (0 <= nxt[0] < rows and 0 <= nxt[1] < cols):
                continue
            if nxt in blocked:
                continue
            new_cost = cost + 1
            if new_cost < best.get(nxt, float("inf")):
                best[nxt] = new_cost
                parent[nxt] = current
                heapq.heappush(heap, (new_cost + h(nxt), new_cost, nxt))

    return []


# =========================================================
# PICK-LIST ROUTE PLANNING (route optimisation)
# =========================================================


def plan_route(
    stops,
    obstacles=None,
    start=DOCK,
    return_to_start=True,
    optimise=True,
    rows=GRID_ROWS,
    cols=GRID_COLS,
):
    """
    Plan a robot route from `start` through every stop.

    stops: list of {"cell": (r, c), "zone": "A", "items": [...]}  (unique cells)
    Returns a dict with the visiting order, per-leg paths, the full route,
    total moves, the moves for the requested (unoptimised) order and any
    stops that are unreachable because of obstacles.
    """
    blocked = set(obstacles or set()) | shelf_cells()
    cache = {}

    def path(a, b):
        key = (a, b) if a <= b else (b, a)
        if key not in cache:
            cache[key] = astar_path(key[0], key[1], blocked, rows, cols)
        p = cache[key]
        return p if (a, b) == key else list(reversed(p))

    reachable, unreachable = [], []
    for stop in stops:
        (reachable if path(start, stop["cell"]) else unreachable).append(stop)

    def tour_moves(order):
        points = [start] + [s["cell"] for s in order]
        if return_to_start:
            points.append(start)
        return sum(len(path(a, b)) - 1 for a, b in zip(points, points[1:]))

    requested_moves = tour_moves(reachable) if reachable else 0
    order = list(reachable)

    if optimise and len(reachable) > 1:
        if len(reachable) <= 7:
            order = list(min(itertools.permutations(reachable), key=tour_moves))
        else:
            remaining, order, here = list(reachable), [], start
            while remaining:
                nearest = min(remaining, key=lambda s: len(path(here, s["cell"])))
                order.append(nearest)
                remaining.remove(nearest)
                here = nearest["cell"]

    points = [start] + [s["cell"] for s in order]
    if return_to_start and order:
        points.append(start)

    legs, route = [], []
    for a, b in zip(points, points[1:]):
        leg_path = path(a, b)
        legs.append({"from": a, "to": b, "path": leg_path, "moves": len(leg_path) - 1})
        route.extend(leg_path if not route else leg_path[1:])

    return {
        "order": order,
        "legs": legs,
        "route": route,
        "moves": max(len(route) - 1, 0),
        "requested_moves": requested_moves,
        "unreachable": unreachable,
    }


# =========================================================
# OBSTACLES (dynamic environment changes)
# =========================================================


def _all_pickups_reachable(obstacles, rows=GRID_ROWS, cols=GRID_COLS):
    blocked = set(obstacles) | shelf_cells()
    return all(astar_path(DOCK, p, blocked, rows, cols) for p in pickup_cells())


def random_obstacles(count, existing=None, seed=None, rows=GRID_ROWS, cols=GRID_COLS):
    """Pick `count` new obstacle cells that never cut the dock off from a zone."""
    existing = set(existing or set())
    rng = random.Random(seed)
    free = [
        (r, c)
        for r in range(rows)
        for c in range(cols)
        if can_place_obstacle((r, c), rows, cols) and (r, c) not in existing
    ]
    for _ in range(60):
        picked = set(rng.sample(free, min(count, len(free))))
        if _all_pickups_reachable(existing | picked, rows, cols):
            return picked
    return set()


def obstacle_on_route(route, existing=None, seed=None, rows=GRID_ROWS, cols=GRID_COLS):
    """Simulate a sudden blockage: choose a cell on the current route to block."""
    existing = set(existing or set())
    candidates = [
        c
        for c in route[1:-1]
        if can_place_obstacle(c, rows, cols) and c not in existing
    ]
    random.Random(seed).shuffle(candidates)
    for cell in candidates:
        if _all_pickups_reachable(existing | {cell}, rows, cols):
            return cell
    return None


# =========================================================
# HTML GRID RENDERER
# =========================================================


def render_grid_html(
    obstacles=None,
    route=None,
    stop_numbers=None,
    robot_index=None,
    rows=GRID_ROWS,
    cols=GRID_COLS,
):
    """Return the warehouse floor as a single-line HTML table."""
    obstacles = set(obstacles or set())
    route = list(route or [])
    route_set = set(route)
    stop_numbers = stop_numbers or {}
    travelled = set(route[: robot_index + 1]) if robot_index is not None and route else set()
    robot = route[robot_index] if robot_index is not None and route else None

    shelf_info = {}
    for letter, zone in ZONE_LAYOUT.items():
        mid_r = (zone["rows"][0] + zone["rows"][1]) // 2
        mid_c = (zone["cols"][0] + zone["cols"][1]) // 2
        for r in range(zone["rows"][0], zone["rows"][1] + 1):
            for c in range(zone["cols"][0], zone["cols"][1] + 1):
                shelf_info[(r, c)] = (zone["color"], letter if (r, c) == (mid_r, mid_c) else "")

    base = (
        "width:30px;height:30px;text-align:center;font:600 12px/30px monospace;"
        "border:1px solid #e2e8f0;color:#0f172a;padding:0;"
    )
    body = []
    for r in range(rows):
        cells = []
        for c in range(cols):
            cell = (r, c)
            bg, label = "#f8fafc", ""
            if cell in shelf_info:
                bg, label = shelf_info[cell]
            elif cell in obstacles:
                bg, label = "#ef4444", "&#10006;"
            elif cell in travelled:
                bg, label = "#60a5fa", "&middot;"
            elif cell in route_set:
                bg, label = "#bfdbfe", "&middot;"

            if cell == DOCK:
                bg, label = "#22c55e", "D"
            if cell in stop_numbers:
                bg, label = "#f59e0b", html.escape(str(stop_numbers[cell]))
            if cell == robot:
                label = "&#129302;"
            cells.append(f'<td style="{base}background:{bg};">{label}</td>')
        body.append("<tr>" + "".join(cells) + "</tr>")

    return (
        '<div style="overflow-x:auto;">'
        '<table style="border-collapse:collapse;margin:auto;">'
        + "".join(body)
        + "</table></div>"
    )
