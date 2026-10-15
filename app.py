import json
import heapq
import math
from datetime import datetime

import streamlit as st
from PIL import Image

import warehouse_db as db
from multi_ai_analyzer import MultiAIProductAnalyzer


# =========================================================
# PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="VisionWrap | Smart Packaging",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)


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

FRAGILITY_OPTIONS = [
    "potentially_fragile",
    "potentially_durable",
    "unknown",
]

SIZE_OPTIONS = ["small", "medium", "large", "unknown"]

STORAGE_ZONES = [
    "A - Fragile Goods",
    "B - Electronics",
    "C - General Storage",
    "D - Lightweight Goods",
    "E - Large Items",
    "F - Restricted / Special Handling",
]

GRID_ROWS = 12
GRID_COLS = 16


# =========================================================
# SESSION STATE
# =========================================================

DEFAULT_STATE = {
    "visionwrap_result": None,
    "visionwrap_source_image": None,
    "visionwrap_record_to_edit": None,
    "visionwrap_pending_packaging": None,
    "visionwrap_pending_product": None,
    "visionwrap_finalized_record_id": None,
    "visionwrap_route": [],
    "visionwrap_blocked_cells": set(),
    "visionwrap_start_cell": (0, 0),
    "visionwrap_goal_cell": (11, 15),
    "visionwrap_last_error": None,
}

for key, value in DEFAULT_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = value


# =========================================================
# DESIGN SYSTEM
# =========================================================

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    :root {
      --page: #eaf0f8;
      --surface: #ffffff;
      --surface-soft: #f4f7fc;
      --navy: #102a56;
      --navy-2: #173f78;
      --text: #172b4d;
      --muted: #536782;
      --border: #c8d6e8;
      --blue: #2563eb;
      --blue-dark: #1749b0;
      --teal: #087f8c;
      --green: #087f5b;
      --orange: #9a5700;
      --red: #b42318;
    }

    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .stApp { background: var(--page) !important; color: var(--text) !important; }
    [data-testid="stMain"] { background: var(--page) !important; }
    [data-testid="stMainBlockContainer"] { padding-top: 1.6rem; max-width: 1500px; }
    [data-testid="stHeader"] { background: rgba(234,240,248,.96) !important; }

    /* Dark, high-contrast navigation against the light workspace */
    [data-testid="stSidebar"] { background: #102a56 !important; border-right: 1px solid #294a78; }
    [data-testid="stSidebar"] > div { background: #102a56 !important; padding-top: 1.2rem; }
    [data-testid="stSidebar"] * { color: #f4f8ff !important; }
    [data-testid="stSidebar"] [data-testid="stRadio"] label p { color: #f4f8ff !important; }
    [data-testid="stSidebar"] [data-testid="stWidgetLabel"] { color: #dbeafe !important; }
    [data-testid="stSidebar"] [data-baseweb="radio"] div { border-color: #9bb9e5 !important; }

    h1,h2,h3,h4 { color: var(--navy) !important; letter-spacing: -.35px; }
    p, label, span { line-height: 1.55; }
    .stApp p, .stApp label, .stApp [data-testid="stWidgetLabel"],
    .stApp [data-testid="stWidgetLabel"] p,
    .stApp [data-testid="stMarkdownContainer"] p,
    .stApp [data-testid="stRadio"] label p,
    .stApp [data-testid="stFileUploader"] label,
    .stApp [data-testid="stCameraInput"] label,
    .stApp [data-testid="stTextInput"] label,
    .stApp [data-testid="stSelectbox"] label,
    .stApp [data-testid="stNumberInput"] label,
    .stApp [data-testid="stTextArea"] label { color: var(--text) !important; opacity: 1 !important; }

    /* Keep all editable fields light with dark, readable values. Streamlit's
       number-input stepper can otherwise inherit a dark theme background. */
    .stApp input, .stApp textarea,
    .stApp [data-testid="stNumberInput"] input,
    .stApp [data-testid="stTextInput"] input,
    .stApp [data-testid="stTextArea"] textarea {
      background-color: #ffffff !important;
      color: #102a56 !important;
      -webkit-text-fill-color: #102a56 !important;
      caret-color: #102a56 !important;
      opacity: 1 !important;
    }
    .stApp [data-testid="stNumberInput"] [data-baseweb="input"],
    .stApp [data-testid="stNumberInput"] [data-baseweb="base-input"],
    .stApp [data-testid="stTextInput"] [data-baseweb="input"],
    .stApp [data-testid="stTextArea"] [data-baseweb="textarea"] {
      background-color: #ffffff !important;
      border: 1px solid #b8c8dc !important;
      border-radius: 9px !important;
    }
    .stApp [data-testid="stNumberInput"] button {
      background-color: #edf4ff !important;
      color: #102a56 !important;
      border-left: 1px solid #d2deee !important;
    }
    .stApp [data-testid="stNumberInput"] button svg {
      fill: #102a56 !important;
      color: #102a56 !important;
    }
    .stApp [data-baseweb="select"] * { color: var(--text) !important; }
    .stApp [data-testid="stFileUploader"] section,
    .stApp [data-testid="stFileUploader"] small { color: var(--text) !important; }
    .stApp [data-testid="stFileUploader"] button { color: #fff !important; background: var(--blue) !important; border-color: var(--blue) !important; }

    .hero {
      background: linear-gradient(120deg, #102a56 0%, #174783 65%, #087f8c 120%);
      padding: 30px 34px; border-radius: 22px; border: 1px solid #315b91;
      margin-bottom: 26px; box-shadow: 0 12px 28px rgba(16,42,86,.16);
    }
    .hero-title { color: #ffffff !important; font-size: 35px; font-weight: 800; margin-bottom: 8px; letter-spacing: -1px; }
    .hero-subtitle { color: #e0edff !important; font-size: 15px; margin-bottom: 16px; max-width: 850px; }
    .hero-tags { margin-top: 4px; }
    .hero-pill { display: inline-block; padding: 6px 12px; border-radius: 30px; background: #e0edff; color: #12366c !important; font-size: 11px; font-weight: 800; margin-right: 7px; margin-bottom: 5px; }

    .section-heading { font-size: 22px; font-weight: 800; color: var(--navy) !important; margin-top: 10px; margin-bottom: 4px; }
    .section-caption { color: var(--muted) !important; font-size: 13px; margin-bottom: 18px; }
    .metric-card, .surface-card, .step-box, div[data-testid="stForm"], [data-testid="stMetric"] {
      background: var(--surface) !important; color: var(--text) !important;
      border: 1px solid var(--border) !important; border-radius: 16px;
      box-shadow: 0 5px 16px rgba(16,42,86,.06);
    }
    .metric-card { padding: 20px; min-height: 120px; }
    .metric-label, .metric-note, .info-label, .step-description { color: var(--muted) !important; }
    .metric-label { font-size: 12px; font-weight: 700; margin-bottom: 12px; }
    .metric-value { color: var(--navy) !important; font-size: 29px; font-weight: 800; line-height: 1.1; }
    .metric-note { font-size: 11px; margin-top: 8px; }
    .surface-card { padding: 22px; margin-bottom: 16px; }
    .info-label { font-size: 12px; margin-bottom: 3px; }
    .info-value { color: var(--navy) !important; font-size: 15px; font-weight: 700; overflow-wrap: anywhere; }
    .status { display: inline-block; padding: 5px 11px; border-radius: 20px; font-size: 11px; font-weight: 800; }
    .status-pending { background: #fff0c2; color: #7a4b00 !important; }
    .status-finalized { background: #dceafe; color: #1749a5 !important; }
    .status-warehouse { background: #d4f5e5; color: #075e42 !important; }
    .status-unassigned { background: #e8edf4; color: #334155 !important; }
    .step-box { padding: 16px; min-height: 100px; }
    .step-number { color: var(--blue) !important; font-weight: 800; font-size: 12px; margin-bottom: 7px; }
    .step-title { font-size: 14px; font-weight: 800; color: var(--navy) !important; margin-bottom: 5px; }
    .step-description { font-size: 12px; }

    .stButton > button, .stDownloadButton > button { border-radius: 10px; border: 1px solid #b7c9e1; padding: 9px 16px; font-weight: 700; color: #17365f !important; background: #ffffff !important; }
    .stButton > button[kind="primary"], .stDownloadButton > button[kind="primary"] { background: var(--blue) !important; color: #ffffff !important; border: 1px solid var(--blue) !important; }
    .stButton > button:hover, .stDownloadButton > button:hover { border-color: var(--blue) !important; color: var(--blue-dark) !important; }
    .stButton > button[kind="primary"]:hover { background: var(--blue-dark) !important; color: #ffffff !important; }
    div[data-testid="stForm"] { padding: 22px; }
    [data-testid="stMetric"] { padding: 17px; }
    [data-testid="stMetricLabel"] { color: var(--muted) !important; }
    [data-testid="stMetricValue"] { color: var(--navy) !important; }
    [data-testid="stDataFrame"] { border: 1px solid var(--border); border-radius: 12px; overflow: hidden; }
    div[data-baseweb="select"] > div { border-radius: 9px; border-color: #b7c9e1 !important; background: #fff !important; }
    [data-testid="stFileUploader"] { background: #ffffff !important; border: 1px dashed #8ca9d0 !important; border-radius: 14px; padding: 12px; }
    [data-testid="stCameraInput"] { background: #ffffff !important; border-radius: 14px; padding: 10px; }
    [data-testid="stRadio"] [role="radiogroup"] { gap: 12px; }
    [data-testid="stAlert"] { border-radius: 12px; }
    hr { border-color: var(--border) !important; }
    .footer { text-align: center; padding: 25px 0 10px; color: var(--muted) !important; font-size: 12px; }
    .route-cell { display: inline-block; padding: 5px 0; border-radius: 5px; width: 100%; text-align: center; font-size: 10px; font-weight: 700; }

    /* Avoid controls or wide tables forcing the viewport sideways. */
    [data-testid="stMainBlockContainer"] { overflow-wrap: anywhere; }
    img { max-width: 100%; height: auto; }
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# GENERAL HELPERS
# =========================================================

def safe_text(value, default="Not available"):
    if value is None:
        return default

    if isinstance(value, str):
        value = value.strip()
        return value if value else default

    return str(value)


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
        return [
            str(item).strip()
            for item in value
            if str(item).strip()
        ]

    if not value:
        return []

    if isinstance(value, str):
        return [
            line.strip()
            for line in value.splitlines()
            if line.strip()
        ]

    return [str(value)]


def parse_json_dimensions(value):
    if isinstance(value, (dict, list)):
        return value

    if not value:
        return None

    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None


def pretty_label(value):
    return safe_text(value, "").replace("_", " ").title()


def display_value(value):
    if value is None:
        return "Not available"

    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)

    return safe_text(value)


def workflow_label(status):
    return {
        "pending": "Pending Review",
        "finalized": "Packaging Finalized",
        "warehouse": "In Warehouse",
    }.get(status, pretty_label(status))


def workflow_badge(status):
    css_class = {
        "pending": "status-pending",
        "finalized": "status-finalized",
        "warehouse": "status-warehouse",
    }.get(status, "status-unassigned")

    st.markdown(
        f"""
        <span class="status {css_class}">
            {workflow_label(status)}
        </span>
        """,
        unsafe_allow_html=True,
    )


def render_metric(label, value, note=""):
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
            <div class="metric-note">{note}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_title(title, caption=None):
    st.markdown(
        f'<div class="section-heading">{title}</div>',
        unsafe_allow_html=True,
    )

    if caption:
        st.markdown(
            f'<div class="section-caption">{caption}</div>',
            unsafe_allow_html=True,
        )


def render_list(title, items):
    items = as_list(items)

    st.markdown(f"**{title}**")

    if not items:
        st.caption("No information available.")
        return

    for item in items:
        st.markdown(f"- {display_value(item)}")


def normalize_packaging(packaging):
    if not isinstance(packaging, dict):
        packaging = {}

    return {
        "recommended_box": str(
            packaging.get("recommended_box", "")
        ),
        "outer_material": str(
            packaging.get("outer_material", "")
        ),
        "cushioning": str(
            packaging.get("cushioning", "")
        ),
        "void_fill": str(
            packaging.get("void_fill", "")
        ),
        "orientation": str(
            packaging.get("orientation", "")
        ),
        "protection_features": as_list(
            packaging.get("protection_features", [])
        ),
        "reasoning": str(
            packaging.get(
                "reasoning",
                packaging.get("packaging_reasoning", ""),
            )
        ),
        "sustainability_tip": str(
            packaging.get("sustainability_tip", "")
        ),
    }


def product_from_record(record):
    if not record:
        return None

    packaging = record.get("finalized_packaging") or {}

    if not isinstance(packaging, dict):
        packaging = {}

    if not packaging:
        packaging = {
            "recommended_box": record.get("recommended_box", ""),
            "outer_material": record.get("outer_material", ""),
            "cushioning": record.get("cushioning", ""),
            "void_fill": record.get("void_fill", ""),
            "orientation": record.get("orientation", ""),
            "protection_features": record.get(
                "protection_features", []
            ),
            "reasoning": record.get("packaging_reasoning", ""),
            "sustainability_tip": record.get(
                "sustainability_tip", ""
            ),
        }

    return {
        "product_name": record.get("product_name", ""),
        "product_category": record.get(
            "product_category", "other"
        ),
        "description": record.get("description", ""),
        "visible_material": record.get(
            "visible_material", "unknown"
        ),
        "confidence": record.get("confidence", "low"),
        "fragility": record.get("fragility", "unknown"),
        "estimated_size_class": record.get(
            "estimated_size_class", "unknown"
        ),
        "dimensions_cm": parse_json_dimensions(
            record.get("dimensions_cm")
        ),
        "weight_g": record.get("weight_g"),
        "packaging": normalize_packaging(packaging),
        "risk_factors": as_list(record.get("risk_factors", [])),
        "packing_steps": as_list(record.get("packing_steps", [])),
        "warnings": as_list(record.get("warnings", [])),
        "confirmed": bool(record.get("confirmed", 1)),
    }


def set_current_product(product, source_image=None, record_id=None):
    st.session_state.visionwrap_result = product
    st.session_state.visionwrap_source_image = source_image
    st.session_state.visionwrap_record_to_edit = record_id
    st.session_state.visionwrap_pending_packaging = None
    st.session_state.visionwrap_pending_product = None
    st.session_state.visionwrap_finalized_record_id = None
    st.session_state.visionwrap_last_error = None


def calculate_packaging_savings(baseline_l, baseline_w, baseline_h, recommended_l, recommended_w, recommended_h, baseline_cost, recommended_cost, baseline_material_g, recommended_material_g):
    """Calculate estimates from user-entered package dimensions and costs."""
    baseline_volume = float(baseline_l) * float(baseline_w) * float(baseline_h)
    recommended_volume = float(recommended_l) * float(recommended_w) * float(recommended_h)
    volume_saved = baseline_volume - recommended_volume
    volume_reduction_pct = (volume_saved / baseline_volume * 100.0) if baseline_volume > 0 else 0.0
    material_saved = float(baseline_material_g) - float(recommended_material_g)
    material_reduction_pct = (material_saved / float(baseline_material_g) * 100.0) if float(baseline_material_g) > 0 else 0.0
    cost_saved = float(baseline_cost) - float(recommended_cost)
    cost_reduction_pct = (cost_saved / float(baseline_cost) * 100.0) if float(baseline_cost) > 0 else 0.0
    return {
        "baseline_box_cm": {"length": float(baseline_l), "width": float(baseline_w), "height": float(baseline_h)},
        "recommended_box_cm": {"length": float(recommended_l), "width": float(recommended_w), "height": float(recommended_h)},
        "baseline_volume_cm3": round(baseline_volume, 2),
        "recommended_volume_cm3": round(recommended_volume, 2),
        "volume_saved_cm3": round(volume_saved, 2),
        "volume_reduction_pct": round(volume_reduction_pct, 2),
        "baseline_material_g": float(baseline_material_g),
        "recommended_material_g": float(recommended_material_g),
        "material_saved_g": round(material_saved, 2),
        "material_reduction_pct": round(material_reduction_pct, 2),
        "baseline_cost": float(baseline_cost),
        "recommended_cost": float(recommended_cost),
        "cost_saved": round(cost_saved, 2),
        "cost_reduction_pct": round(cost_reduction_pct, 2),
        "measurement_basis": "Estimated from user-entered baseline and recommended package dimensions, material weights, and costs; validate with physical packaging.",
    }


def choose_storage_zone(product):
    fragility = str(
        product.get("fragility", "unknown")
    ).lower()

    category = str(
        product.get("product_category", "other")
    ).lower()

    size = str(
        product.get("estimated_size_class", "unknown")
    ).lower()

    if fragility == "potentially_fragile":
        return STORAGE_ZONES[0]

    if "electronic" in category:
        return STORAGE_ZONES[1]

    if size == "large":
        return STORAGE_ZONES[4]

    if category == "clothing":
        return STORAGE_ZONES[3]

    return STORAGE_ZONES[2]


# =========================================================
# WAREHOUSE PATHFINDING
# =========================================================

def astar_path(start, goal, blocked, rows, cols):
    if start in blocked or goal in blocked:
        return []

    if start == goal:
        return [start]

    def heuristic(cell):
        return (
            abs(cell[0] - goal[0])
            + abs(cell[1] - goal[1])
        )

    frontier = [(heuristic(start), 0, start)]

    came_from = {}
    cost_so_far = {start: 0}

    while frontier:
        _, current_cost, current = heapq.heappop(frontier)

        if current == goal:
            break

        if current_cost != cost_so_far.get(current):
            continue

        neighbors = [
            (current[0] - 1, current[1]),
            (current[0] + 1, current[1]),
            (current[0], current[1] - 1),
            (current[0], current[1] + 1),
        ]

        for neighbor in neighbors:
            r, c = neighbor

            if not (0 <= r < rows and 0 <= c < cols):
                continue

            if neighbor in blocked:
                continue

            new_cost = current_cost + 1

            if (
                neighbor not in cost_so_far
                or new_cost < cost_so_far[neighbor]
            ):
                cost_so_far[neighbor] = new_cost
                priority = new_cost + heuristic(neighbor)

                heapq.heappush(
                    frontier,
                    (priority, new_cost, neighbor),
                )

                came_from[neighbor] = current

    if goal not in came_from:
        return []

    path = [goal]
    current = goal

    while current != start:
        current = came_from[current]
        path.append(current)

    path.reverse()
    return path


def parse_blocked_cells(text, rows, cols):
    blocked = set()

    for item in str(text or "").splitlines():
        item = item.strip()

        if not item:
            continue

        try:
            row_text, col_text = item.replace(" ", "").split(",")
            cell = (int(row_text), int(col_text))

            if (
                0 <= cell[0] < rows
                and 0 <= cell[1] < cols
            ):
                blocked.add(cell)

        except (ValueError, TypeError):
            continue

    return blocked


def make_warehouse_map(
    rows,
    cols,
    start,
    goal,
    blocked,
    path,
):
    path_set = set(path)

    lines = [
        "Legend: S = Start | G = Destination | "
        "X = Blocked | * = Route | . = Free"
    ]

    lines.append("")

    for r in range(rows):
        cells = []

        for c in range(cols):
            cell = (r, c)

            if cell == start:
                symbol = "S"
            elif cell == goal:
                symbol = "G"
            elif cell in blocked:
                symbol = "X"
            elif cell in path_set:
                symbol = "*"
            else:
                symbol = "."

            cells.append(symbol)

        lines.append(" ".join(cells))

    return "\n".join(lines)


# =========================================================
# HEADER
# =========================================================

# Keep each HTML element's content on one line. This prevents Markdown from
# interpreting indented inner lines as a literal code block in some versions.
st.markdown(
    '<div class="hero">'
    '<div class="hero-title">📦 VisionWrap</div>'
    '<div class="hero-subtitle">AI-powered packaging intelligence and warehouse logistics. '
    'Analyze products, review protection requirements, and organize warehouse operations in one workspace.</div>'
    '<div class="hero-tags">'
    '<span class="hero-pill">AI PRODUCT ANALYSIS</span>'
    '<span class="hero-pill">SMART PACKAGING</span>'
    '<span class="hero-pill">WAREHOUSE LOGISTICS</span>'
    '</div></div>',
    unsafe_allow_html=True,
)


# =========================================================
# SIDEBAR
# =========================================================

# Apply navigation requests before the sidebar radio widget is created.
if st.session_state.get("visionwrap_navigation_target"):
    st.session_state["visionwrap_navigation"] = st.session_state.pop(
        "visionwrap_navigation_target"
    )


def navigate_to(page_name):
    """Queue navigation safely; the radio key is updated on next rerun."""
    st.session_state["visionwrap_navigation_target"] = page_name


with st.sidebar:
    st.markdown("## 📦 VisionWrap")

    st.caption("Packaging & warehouse workspace")

    st.divider()

    page = st.radio(
        "WORKSPACE",
        [
            "Overview",
            "Product Analysis",
            "Packaging Review",
            "Inventory",
            "Warehouse & Routes",
        ],
        key="visionwrap_navigation",
    )

    st.divider()

    st.markdown("**Workflow**")

    workflow_steps = [
        ("01", "Analyze product"),
        ("02", "Review packaging"),
        ("03", "Finalize packaging"),
        ("04", "Transfer to warehouse"),
    ]

    for number, label in workflow_steps:
        st.markdown(
            f"""
            <div style="display:flex;gap:10px;margin:12px 0;">
                <div style="
                    background:#dbeafe;
                    color:#1d4ed8;
                    min-width:30px;
                    height:30px;
                    border-radius:9px;
                    display:flex;
                    align-items:center;
                    justify-content:center;
                    font-size:11px;
                    font-weight:800;
                ">{number}</div>
                <div style="
                    padding-top:5px;
                    color:#526985;
                    font-size:12px;
                    font-weight:600;
                ">{label}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.divider()

    st.caption(
        "AI recommendations should be reviewed before "
        "packaging and handling decisions are finalized."
    )


# =========================================================
# LOAD SHARED STATE
# =========================================================

result = st.session_state.visionwrap_result
source_image = st.session_state.visionwrap_source_image


# =========================================================
# OVERVIEW
# =========================================================

if page == "Overview":

    section_title(
        "Operations Overview",
        "A quick view of product analysis, packaging progress, "
        "and warehouse activity.",
    )

    stats = db.get_inventory_stats()

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        render_metric(
            "TOTAL PRODUCTS",
            stats["total_products"],
            "All saved records",
        )

    with col2:
        render_metric(
            "PENDING REVIEW",
            stats["pending_products"],
            "Awaiting packaging finalization",
        )

    with col3:
        render_metric(
            "FINALIZED",
            stats["finalized_products"],
            "Ready for warehouse transfer",
        )

    with col4:
        render_metric(
            "IN WAREHOUSE",
            stats["warehouse_products"],
            "Transferred products",
        )

    st.write("")

    left, right = st.columns([1.15, 0.85])

    with left:
        st.markdown(
            '<div class="surface-card">',
            unsafe_allow_html=True,
        )

        st.markdown("### Start a workflow")

        st.write(
            "Analyze an item, inspect the AI-generated packaging "
            "recommendation, and prepare it for warehouse storage."
        )

        if st.button(
            "＋ Analyze a product",
            type="primary",
            use_container_width=True,
        ):
            navigate_to("Product Analysis")
            st.rerun()

        st.write("")

        if st.button(
            "Review packaging",
            use_container_width=True,
        ):
            navigate_to("Packaging Review")
            st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown(
            '<div class="surface-card">',
            unsafe_allow_html=True,
        )

        st.markdown("### Inventory snapshot")

        st.metric(
            "Product categories",
            stats["categories"],
        )

        st.metric(
            "Potentially fragile products",
            stats["potentially_fragile"],
        )

        st.caption(
            "Fragility is based on saved product assessments."
        )

        st.markdown("</div>", unsafe_allow_html=True)

    section_title(
        "Recent Products",
        "The latest saved inventory records.",
    )

    products = db.get_all_products()

    # Packaging efficiency KPIs are calculated from saved finalized records.
    savings_records = []
    for saved_product in products:
        saved_packaging = saved_product.get("finalized_packaging") or {}
        if isinstance(saved_packaging, dict) and isinstance(saved_packaging.get("savings_analysis"), dict):
            savings_records.append(saved_packaging["savings_analysis"])
    if savings_records:
        st.divider()
        section_title("Packaging Efficiency", "Estimated savings from finalized packaging records; values are not physical measurements.")
        total_volume_saved = sum(float(x.get("volume_saved_cm3", 0) or 0) for x in savings_records)
        total_material_saved = sum(float(x.get("material_saved_g", 0) or 0) for x in savings_records)
        total_cost_saved = sum(float(x.get("cost_saved", 0) or 0) for x in savings_records)
        volume_base = sum(float(x.get("baseline_volume_cm3", 0) or 0) for x in savings_records)
        material_base = sum(float(x.get("baseline_material_g", 0) or 0) for x in savings_records)
        cost_base = sum(float(x.get("baseline_cost", 0) or 0) for x in savings_records)
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Estimated volume reduction", f"{(total_volume_saved / volume_base * 100) if volume_base else 0:.1f}%", f"{total_volume_saved:,.0f} cm³ saved")
        k2.metric("Estimated material reduction", f"{(total_material_saved / material_base * 100) if material_base else 0:.1f}%", f"{total_material_saved:,.1f} g saved")
        k3.metric("Estimated cost reduction", f"{(total_cost_saved / cost_base * 100) if cost_base else 0:.1f}%", f"{total_cost_saved:,.2f} cost units saved")
        k4.metric("Measured records", len(savings_records), "Finalized products with savings data")
        st.caption("Savings are estimates based on entered values. Confirm with actual package measurements, material weights, and supplier prices before presenting them as validated impact.")

    if not products:
        st.info(
            "No products have been saved yet. "
            "Start by analyzing your first item."
        )
    else:
        for product in products[:5]:
            with st.container(border=True):
                col_a, col_b, col_c = st.columns(
                    [2, 1, 1]
                )

                with col_a:
                    st.markdown(
                        f"**{safe_text(product.get('product_name'))}**"
                    )
                    st.caption(
                        f"Record #{product.get('id')} · "
                        f"{pretty_label(product.get('product_category'))}"
                    )

                with col_b:
                    workflow_badge(
                        product.get("workflow_status", "pending")
                    )

                with col_c:
                    st.caption(
                        safe_text(
                            product.get("storage_zone"),
                            "No zone assigned",
                        )
                    )


# =========================================================
# PRODUCT ANALYSIS
# =========================================================

elif page == "Product Analysis":

    section_title(
        "Product Analysis",
        "Upload a product photograph or capture one using your camera.",
    )

    left, right = st.columns([1, 1])

    with left:
        input_method = st.radio(
            "Image source",
            ["Upload image", "Capture image"],
            horizontal=True,
        )

        uploaded_image = None

        if input_method == "Upload image":
            uploaded_image = st.file_uploader(
                "Choose a product image",
                type=["jpg", "jpeg", "png", "webp"],
                key="visionwrap_upload",
            )

        else:
            uploaded_image = st.camera_input(
                "Capture product",
                key="visionwrap_camera",
            )

        if uploaded_image is not None:
            try:
                image = Image.open(uploaded_image).convert("RGB")

                st.image(
                    image,
                    caption="Selected product image",
                    use_container_width=True,
                )

                if st.button(
                    "Analyze Product",
                    type="primary",
                    use_container_width=True,
                ):
                    with st.spinner(
                        "Analyzing the product and generating "
                        "packaging recommendations..."
                    ):
                        try:
                            analyzer = MultiAIProductAnalyzer()
                            analysis = analyzer.analyze_image(image)

                            if not isinstance(analysis, dict):
                                raise ValueError(
                                    "The analyzer did not return "
                                    "a valid result."
                                )

                            if not analysis.get("product_name"):
                                raise ValueError(
                                    "The analyzer did not return "
                                    "a product name. Try another image."
                                )

                            analysis.setdefault(
                                "product_category", "other"
                            )
                            analysis.setdefault(
                                "description", ""
                            )
                            analysis.setdefault(
                                "visible_material", "unknown"
                            )
                            analysis.setdefault(
                                "confidence", "low"
                            )
                            analysis.setdefault(
                                "fragility", "unknown"
                            )
                            analysis.setdefault(
                                "estimated_size_class", "unknown"
                            )
                            analysis.setdefault(
                                "dimensions_cm", None
                            )
                            analysis.setdefault(
                                "weight_g", None
                            )
                            analysis.setdefault(
                                "risk_factors", []
                            )
                            analysis.setdefault(
                                "packing_steps", []
                            )
                            analysis.setdefault(
                                "warnings", []
                            )
                            analysis["packaging"] = normalize_packaging(
                                analysis.get("packaging", {})
                            )
                            analysis["confirmed"] = True

                            set_current_product(
                                analysis,
                                source_image=image,
                            )

                            st.success(
                                "Analysis completed successfully."
                            )

                            st.rerun()

                        except Exception as exc:
                            st.error(
                                f"Product analysis failed: {exc}"
                            )

            except Exception as exc:
                st.error(f"Unable to read the image: {exc}")

    with right:
        st.markdown(
            '<div class="surface-card">',
            unsafe_allow_html=True,
        )

        st.markdown("### What happens next?")

        steps = [
            (
                "01",
                "Identify",
                "The AI analyzes the visible product.",
            ),
            (
                "02",
                "Assess",
                "Review the estimated category, fragility, "
                "size, and handling risks.",
            ),
            (
                "03",
                "Recommend",
                "Inspect the suggested box, cushioning, "
                "and protective materials.",
            ),
            (
                "04",
                "Review",
                "Confirm the information before saving "
                "the product to inventory.",
            ),
        ]

        for number, title, description in steps:
            st.markdown(
                f"""
                <div class="step-box" style="margin-bottom:10px;">
                    <div class="step-number">{number}</div>
                    <div class="step-title">{title}</div>
                    <div class="step-description">{description}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("</div>", unsafe_allow_html=True)

    # Display current analysis

    result = st.session_state.visionwrap_result

    if result:
        st.divider()

        section_title(
            "Analysis Results",
            "Review the current product assessment.",
        )

        col_a, col_b, col_c = st.columns(3)

        with col_a:
            st.markdown("**Product**")
            st.markdown(
                f"### {safe_text(result.get('product_name'))}"
            )

        with col_b:
            st.markdown("**Category**")
            st.markdown(
                f"### {pretty_label(result.get('product_category'))}"
            )

        with col_c:
            st.markdown("**Confidence**")
            st.markdown(
                f"### {pretty_label(result.get('confidence'))}"
            )

        info1, info2, info3 = st.columns(3)

        info1.metric(
            "Fragility assessment",
            pretty_label(result.get("fragility")),
        )

        info2.metric(
            "Estimated size",
            pretty_label(result.get("estimated_size_class")),
        )

        info3.metric(
            "Visible material",
            pretty_label(result.get("visible_material")),
        )

        st.markdown("### Product description")

        st.write(
            safe_text(result.get("description"))
        )

        st.markdown("### AI packaging recommendation")

        packaging = normalize_packaging(
            result.get("packaging", {})
        )

        p1, p2 = st.columns(2)

        with p1:
            st.markdown(
                '<div class="surface-card">',
                unsafe_allow_html=True,
            )

            st.markdown("**Outer packaging**")

            st.write(
                f"Box: {packaging['recommended_box'] or 'Not specified'}"
            )

            st.write(
                f"Material: {packaging['outer_material'] or 'Not specified'}"
            )

            st.write(
                f"Orientation: {packaging['orientation'] or 'Not specified'}"
            )

            st.markdown("</div>", unsafe_allow_html=True)

        with p2:
            st.markdown(
                '<div class="surface-card">',
                unsafe_allow_html=True,
            )

            st.markdown("**Internal protection**")

            st.write(
                f"Cushioning: {packaging['cushioning'] or 'Not specified'}"
            )

            st.write(
                f"Void fill: {packaging['void_fill'] or 'Not specified'}"
            )

            st.write(
                f"Reasoning: {packaging['reasoning'] or 'Not specified'}"
            )

            st.markdown("</div>", unsafe_allow_html=True)

        render_list(
            "Protection features",
            packaging.get("protection_features"),
        )

        render_list(
            "Risk factors",
            result.get("risk_factors"),
        )

        render_list(
            "Packing steps",
            result.get("packing_steps"),
        )

        render_list(
            "Warnings",
            result.get("warnings"),
        )

        st.write("")

        if st.button(
            "Continue to Packaging Review →",
            type="primary",
        ):
            navigate_to("Packaging Review")
            st.rerun()

        st.download_button(
            "Download Analysis JSON",
            data=json.dumps(
                result,
                indent=2,
                ensure_ascii=False,
                default=str,
            ),
            file_name="visionwrap_analysis.json",
            mime="application/json",
        )

    else:
        st.info(
            "Upload or capture a product image to begin analysis."
        )


# =========================================================
# PACKAGING REVIEW
# =========================================================

elif page == "Packaging Review":

    section_title(
        "Packaging Review",
        "Review the AI recommendation, make necessary adjustments, "
        "and finalize the packaging configuration.",
    )

    result = st.session_state.visionwrap_result

    # Load an existing record when requested.

    edit_id = st.session_state.visionwrap_record_to_edit

    if edit_id is not None:
        if not result or result.get("_loaded_record_id") != edit_id:
            record = db.get_product(edit_id)

            if record:
                result = product_from_record(record)

                if result:
                    result["_loaded_record_id"] = edit_id
                    st.session_state.visionwrap_result = result

                    if record.get("finalized_packaging"):
                        st.session_state.visionwrap_pending_packaging = (
                            normalize_packaging(
                                record["finalized_packaging"]
                            )
                        )

    result = st.session_state.visionwrap_result

    if not result:
        st.warning(
            "No product is selected. Analyze a new product or "
            "open an existing product from Inventory."
        )

        if st.button(
            "Go to Product Analysis",
            type="primary",
        ):
            navigate_to("Product Analysis")
            st.rerun()

    else:
        st.markdown(
            f"### {safe_text(result.get('product_name'))}"
        )

        st.caption(
            "Check the values carefully. AI-generated dimensions, "
            "material identification, and fragility assessments "
            "may be estimates."
        )

        initial_packaging = normalize_packaging(
            st.session_state.visionwrap_pending_packaging
            or result.get("packaging", {})
        )

        with st.form("visionwrap_packaging_form"):

            st.markdown("#### Product details")

            col1, col2 = st.columns(2)

            with col1:
                product_name = st.text_input(
                    "Product name",
                    value=safe_text(
                        result.get("product_name"), ""
                    ),
                )

                category_current = result.get(
                    "product_category", "other"
                )

                if category_current not in CATEGORIES:
                    category_current = "other"

                category = st.selectbox(
                    "Product category",
                    CATEGORIES,
                    index=CATEGORIES.index(category_current),
                )

                description = st.text_area(
                    "Description",
                    value=safe_text(
                        result.get("description"), ""
                    ),
                    height=100,
                )

            with col2:
                material = st.text_input(
                    "Visible material",
                    value=safe_text(
                        result.get("visible_material"),
                        "unknown",
                    ),
                )

                confidence_current = result.get(
                    "confidence", "low"
                )

                if confidence_current not in CONFIDENCE_OPTIONS:
                    confidence_current = "low"

                confidence = st.selectbox(
                    "AI confidence",
                    CONFIDENCE_OPTIONS,
                    index=CONFIDENCE_OPTIONS.index(
                        confidence_current
                    ),
                )

                fragility_current = result.get(
                    "fragility", "unknown"
                )

                if fragility_current not in FRAGILITY_OPTIONS:
                    fragility_current = "unknown"

                fragility = st.selectbox(
                    "Fragility assessment",
                    FRAGILITY_OPTIONS,
                    index=FRAGILITY_OPTIONS.index(
                        fragility_current
                    ),
                )

                size_current = result.get(
                    "estimated_size_class", "unknown"
                )

                if size_current not in SIZE_OPTIONS:
                    size_current = "unknown"

                size_class = st.selectbox(
                    "Estimated size class",
                    SIZE_OPTIONS,
                    index=SIZE_OPTIONS.index(size_current),
                )

            dimensions_default = (
                result.get("dimensions_cm")
            )

            if dimensions_default is None:
                dimensions_default = ""

            if not isinstance(dimensions_default, str):
                dimensions_default = json.dumps(
                    dimensions_default,
                    ensure_ascii=False,
                )

            dimensions_text = st.text_input(
                "Dimensions in cm (optional JSON)",
                value=dimensions_default,
                help='Example: {"length": 20, "width": 10, "height": 5}',
            )

            weight_default = result.get("weight_g")

            weight_text = st.text_input(
                "Weight in grams (optional)",
                value=(
                    str(weight_default)
                    if weight_default is not None
                    else ""
                ),
            )

            st.divider()

            st.markdown("#### Packaging configuration")

            col3, col4 = st.columns(2)

            with col3:
                recommended_box = st.text_input(
                    "Recommended box",
                    value=initial_packaging["recommended_box"],
                )

                outer_material = st.text_input(
                    "Outer material",
                    value=initial_packaging["outer_material"],
                )

                cushioning = st.text_input(
                    "Cushioning",
                    value=initial_packaging["cushioning"],
                )

            with col4:
                void_fill = st.text_input(
                    "Void fill",
                    value=initial_packaging["void_fill"],
                )

                orientation = st.text_input(
                    "Orientation",
                    value=initial_packaging["orientation"],
                )

                protection_text = st.text_area(
                    "Protection features (one per line)",
                    value="\n".join(
                        str(item)
                        for item in initial_packaging[
                            "protection_features"
                        ]
                    ),
                    height=110,
                )

            reasoning = st.text_area(
                "Packaging reasoning",
                value=initial_packaging["reasoning"],
            )

            sustainability_tip = st.text_area(
                "Sustainability recommendation",
                value=initial_packaging["sustainability_tip"],
            )

            st.divider()
            st.markdown("#### Packaging savings comparison")
            st.caption("Enter the usual baseline package and the proposed package. These values are estimates until validated with real packaging.")
            base_col, proposed_col = st.columns(2)
            with base_col:
                st.markdown("**Baseline package (usual method)**")
                baseline_l = st.number_input("Baseline length (cm)", min_value=0.1, value=30.0, step=1.0, key="vw_baseline_l")
                baseline_w = st.number_input("Baseline width (cm)", min_value=0.1, value=20.0, step=1.0, key="vw_baseline_w")
                baseline_h = st.number_input("Baseline height (cm)", min_value=0.1, value=15.0, step=1.0, key="vw_baseline_h")
                baseline_material_g = st.number_input("Baseline packaging material (g)", min_value=0.0, value=250.0, step=10.0, key="vw_baseline_g")
                baseline_cost = st.number_input("Baseline packaging cost (cost units)", min_value=0.0, value=50.0, step=1.0, key="vw_baseline_cost")
            with proposed_col:
                st.markdown("**VisionWrap recommended package**")
                recommended_l = st.number_input("Recommended length (cm)", min_value=0.1, value=25.0, step=1.0, key="vw_recommended_l")
                recommended_w = st.number_input("Recommended width (cm)", min_value=0.1, value=18.0, step=1.0, key="vw_recommended_w")
                recommended_h = st.number_input("Recommended height (cm)", min_value=0.1, value=12.0, step=1.0, key="vw_recommended_h")
                recommended_material_g = st.number_input("Recommended packaging material (g)", min_value=0.0, value=180.0, step=10.0, key="vw_recommended_g")
                recommended_cost = st.number_input("Recommended packaging cost (cost units)", min_value=0.0, value=38.0, step=1.0, key="vw_recommended_cost")
            st.info("Use the same units and realistic values for both packages. Do not claim these estimates as measured savings unless you verify them physically.")

            st.divider()

            risk_text = st.text_area(
                "Risk factors (one per line)",
                value="\n".join(
                    str(item)
                    for item in as_list(
                        result.get("risk_factors")
                    )
                ),
            )

            packing_steps_text = st.text_area(
                "Packing steps (one per line)",
                value="\n".join(
                    str(item)
                    for item in as_list(
                        result.get("packing_steps")
                    )
                ),
            )

            warnings_text = st.text_area(
                "Warnings (one per line)",
                value="\n".join(
                    str(item)
                    for item in as_list(
                        result.get("warnings")
                    )
                ),
            )

            confirmed = st.checkbox(
                "I have reviewed and confirmed the product details "
                "and packaging configuration.",
                value=True,
            )

            submitted = st.form_submit_button(
                "Finalize Packaging",
                type="primary",
                use_container_width=True,
            )

        if submitted:
            try:
                if not product_name.strip():
                    raise ValueError(
                        "Product name cannot be empty."
                    )

                if not confirmed:
                    raise ValueError(
                        "Please confirm the product information."
                    )

                dimensions = None

                if dimensions_text.strip():
                    dimensions = parse_json_dimensions(
                        dimensions_text
                    )

                    if dimensions is None:
                        raise ValueError(
                            "Dimensions must be valid JSON."
                        )

                weight = None

                if weight_text.strip():
                    try:
                        weight = float(weight_text)
                    except ValueError:
                        raise ValueError(
                            "Weight must be a valid number."
                        )

                    if weight < 0:
                        raise ValueError(
                            "Weight cannot be negative."
                        )

                reviewed_packaging = {
                    "recommended_box": recommended_box.strip(),
                    "outer_material": outer_material.strip(),
                    "cushioning": cushioning.strip(),
                    "void_fill": void_fill.strip(),
                    "orientation": orientation.strip(),
                    "protection_features": split_lines(
                        protection_text
                    ),
                    "reasoning": reasoning.strip(),
                    "sustainability_tip": (
                        sustainability_tip.strip()
                    ),
                }

                required = [
                    "recommended_box",
                    "outer_material",
                    "cushioning",
                    "void_fill",
                    "orientation",
                ]

                for field in required:
                    if not reviewed_packaging[field]:
                        raise ValueError(
                            f"Please provide {field.replace('_', ' ')}."
                        )

                savings_analysis = calculate_packaging_savings(
                    baseline_l, baseline_w, baseline_h,
                    recommended_l, recommended_w, recommended_h,
                    baseline_cost, recommended_cost,
                    baseline_material_g, recommended_material_g,
                )
                reviewed_packaging["savings_analysis"] = savings_analysis

                reviewed_product = {
                    "product_name": product_name.strip(),
                    "product_category": category,
                    "description": description.strip(),
                    "visible_material": material.strip() or "unknown",
                    "confidence": confidence,
                    "fragility": fragility,
                    "estimated_size_class": size_class,
                    "dimensions_cm": dimensions,
                    "weight_g": weight,
                    "packaging": reviewed_packaging,
                    "risk_factors": split_lines(risk_text),
                    "packing_steps": split_lines(
                        packing_steps_text
                    ),
                    "warnings": split_lines(warnings_text),
                    "confirmed": True,
                }

                record_id = st.session_state.visionwrap_record_to_edit

                with st.spinner(
                    "Saving product and finalizing packaging..."
                ):
                    saved_record_id = db.save_product(
                        reviewed_product,
                        record_id=record_id,
                    )

                    original_packaging = normalize_packaging(
                        result.get("packaging", {})
                    )

                    db.finalize_packaging(
                        saved_record_id,
                        reviewed_packaging,
                        original_packaging=original_packaging,
                    )

                reviewed_product["_loaded_record_id"] = (
                    saved_record_id
                )

                st.session_state.visionwrap_result = (
                    reviewed_product
                )

                st.session_state.visionwrap_record_to_edit = (
                    saved_record_id
                )

                st.session_state.visionwrap_pending_product = (
                    reviewed_product
                )

                st.session_state.visionwrap_pending_packaging = (
                    reviewed_packaging
                )

                st.session_state.visionwrap_finalized_record_id = (
                    saved_record_id
                )

                st.session_state.visionwrap_last_error = None

                st.success(
                    f"Packaging finalized. Record ID: {saved_record_id}"
                )

                st.rerun()

            except Exception as exc:
                st.error(f"Could not finalize packaging: {exc}")

        # Warehouse transfer is separate from finalization.

        finalized_id = st.session_state.visionwrap_finalized_record_id

        if finalized_id is not None:
            st.divider()

            section_title(
                "Warehouse Transfer",
                "Your packaging configuration has been finalized. "
                "Choose a zone to transfer the product.",
            )

            pending_product = (
                st.session_state.visionwrap_pending_product
                or result
            )

            suggested_zone = choose_storage_zone(
                pending_product
            )

            zone_index = (
                STORAGE_ZONES.index(suggested_zone)
                if suggested_zone in STORAGE_ZONES
                else 0
            )

            selected_zone = st.selectbox(
                "Destination storage zone",
                STORAGE_ZONES,
                index=zone_index,
                key="visionwrap_transfer_zone",
            )

            st.info(
                "The suggested zone is a starting point based on "
                "the product assessment. Confirm that the actual "
                "warehouse location is suitable before transferring."
            )

            if st.button(
                "Transfer to Warehouse",
                type="primary",
                use_container_width=True,
            ):
                try:
                    db.transfer_to_warehouse(
                        finalized_id,
                        selected_zone,
                    )

                    st.success(
                        f"Product #{finalized_id} transferred to "
                        f"{selected_zone}."
                    )

                    st.session_state.visionwrap_finalized_record_id = None
                    st.session_state.visionwrap_pending_packaging = None
                    st.session_state.visionwrap_pending_product = None
                    st.session_state.visionwrap_record_to_edit = None

                    st.rerun()

                except Exception as exc:
                    st.error(
                        f"Warehouse transfer failed: {exc}"
                    )


# =========================================================
# INVENTORY
# =========================================================

elif page == "Inventory":

    section_title(
        "Inventory Management",
        "Search saved products, inspect workflow status, edit records, "
        "and export inventory data.",
    )

    stats = db.get_inventory_stats()

    m1, m2, m3, m4 = st.columns(4)

    with m1:
        render_metric(
            "TOTAL",
            stats["total_products"],
            "All records",
        )

    with m2:
        render_metric(
            "PENDING",
            stats["pending_products"],
            "Needs packaging review",
        )

    with m3:
        render_metric(
            "FINALIZED",
            stats["finalized_products"],
            "Awaiting warehouse transfer",
        )

    with m4:
        render_metric(
            "WAREHOUSE",
            stats["warehouse_products"],
            "Transferred products",
        )

    st.write("")

    search_col, filter_col = st.columns([2, 1])

    with search_col:
        search_query = st.text_input(
            "Search products",
            placeholder="Search name, category, or material...",
        )

    with filter_col:
        workflow_filter = st.selectbox(
            "Workflow status",
            [
                "All",
                "pending",
                "finalized",
                "warehouse",
            ],
        )

    products = db.search_products(search_query)

    if workflow_filter != "All":
        products = [
            product
            for product in products
            if product.get("workflow_status") == workflow_filter
        ]

    if not products:
        st.info(
            "No inventory records match your search and filters."
        )

    else:
        table_rows = []

        for product in products:
            table_rows.append(
                {
                    "ID": product.get("id"),
                    "Product": product.get("product_name"),
                    "Category": pretty_label(
                        product.get("product_category")
                    ),
                    "Fragility": pretty_label(
                        product.get("fragility")
                    ),
                    "Size": pretty_label(
                        product.get("estimated_size_class")
                    ),
                    "Workflow": workflow_label(
                        product.get("workflow_status", "pending")
                    ),
                    "Storage Zone": product.get("storage_zone")
                    or "Unassigned",
                    "Created": product.get("created_at"),
                }
            )

        st.dataframe(
            table_rows,
            use_container_width=True,
            hide_index=True,
        )

        st.divider()

        section_title(
            "Product Details",
            "Select a record to inspect, edit, or delete it.",
        )

        record_options = {
            (
                f"#{product['id']} — "
                f"{product.get('product_name', 'Unnamed product')}"
            ): product["id"]
            for product in products
        }

        selected_record_label = st.selectbox(
            "Select product",
            list(record_options.keys()),
        )

        selected_id = record_options[selected_record_label]

        selected_record = db.get_product(selected_id)

        if selected_record:
            left, right = st.columns([1.3, 0.7])

            with left:
                st.markdown(
                    f"### {safe_text(selected_record.get('product_name'))}"
                )

                workflow_badge(
                    selected_record.get("workflow_status", "pending")
                )

                st.write("")

                st.write(
                    selected_record.get("description")
                    or "No description provided."
                )

                st.markdown("**Packaging configuration**")

                packaging = selected_record.get(
                    "finalized_packaging"
                ) or {}

                if not packaging:
                    packaging = {
                        "recommended_box": selected_record.get(
                            "recommended_box"
                        ),
                        "outer_material": selected_record.get(
                            "outer_material"
                        ),
                        "cushioning": selected_record.get(
                            "cushioning"
                        ),
                        "void_fill": selected_record.get(
                            "void_fill"
                        ),
                        "orientation": selected_record.get(
                            "orientation"
                        ),
                        "reasoning": selected_record.get(
                            "packaging_reasoning"
                        ),
                    }

                for key, value in packaging.items():
                    if key == "savings_analysis" and isinstance(value, dict):
                        st.markdown("**Packaging savings estimate**")
                        s1, s2, s3 = st.columns(3)
                        s1.metric("Volume reduction", f"{value.get('volume_reduction_pct', 0):.1f}%", f"{value.get('volume_saved_cm3', 0):,.0f} cm³")
                        s2.metric("Material reduction", f"{value.get('material_reduction_pct', 0):.1f}%", f"{value.get('material_saved_g', 0):,.1f} g")
                        s3.metric("Cost reduction", f"{value.get('cost_reduction_pct', 0):.1f}%", f"{value.get('cost_saved', 0):,.2f} cost units")
                    else:
                        st.write(
                            f"**{pretty_label(key)}:** "
                            f"{display_value(value)}"
                        )

                st.markdown("**AI packaging snapshot**")

                original_packaging = selected_record.get(
                    "original_packaging"
                ) or {}

                if original_packaging:
                    st.json(original_packaging)
                else:
                    st.caption(
                        "No original packaging snapshot stored."
                    )

            with right:
                st.markdown(
                    '<div class="surface-card">',
                    unsafe_allow_html=True,
                )

                st.markdown("#### Record information")

                st.write(f"**Record ID:** {selected_id}")

                st.write(
                    f"**Category:** "
                    f"{pretty_label(selected_record.get('product_category'))}"
                )

                st.write(
                    f"**Confidence:** "
                    f"{pretty_label(selected_record.get('confidence'))}"
                )

                st.write(
                    f"**Fragility:** "
                    f"{pretty_label(selected_record.get('fragility'))}"
                )

                st.write(
                    f"**Size:** "
                    f"{pretty_label(selected_record.get('estimated_size_class'))}"
                )

                st.write(
                    f"**Storage zone:** "
                    f"{selected_record.get('storage_zone') or 'Unassigned'}"
                )

                st.write(
                    f"**Packaging edited:** "
                    f"{'Yes' if selected_record.get('packaging_edited') else 'No'}"
                )

                st.markdown("</div>", unsafe_allow_html=True)

            action1, action2 = st.columns(2)

            with action1:
                if st.button(
                    "Edit / Review Packaging",
                    type="primary",
                    use_container_width=True,
                ):
                    loaded_product = product_from_record(
                        selected_record
                    )

                    if loaded_product:
                        loaded_product["_loaded_record_id"] = (
                            selected_id
                        )

                        set_current_product(
                            loaded_product,
                            source_image=None,
                            record_id=selected_id,
                        )

                        if selected_record.get(
                            "finalized_packaging"
                        ):
                            st.session_state.visionwrap_pending_packaging = (
                                normalize_packaging(
                                    selected_record[
                                        "finalized_packaging"
                                    ]
                                )
                            )

                        navigate_to("Packaging Review")

                        st.rerun()

            with action2:
                if st.button(
                    "Delete Product",
                    use_container_width=True,
                ):
                    st.session_state[
                        "visionwrap_delete_confirmation"
                    ] = selected_id

            if st.session_state.get(
                "visionwrap_delete_confirmation"
            ) == selected_id:
                st.warning(
                    f"Delete product #{selected_id}? "
                    "This action cannot be undone."
                )

                confirm_col, cancel_col = st.columns(2)

                with confirm_col:
                    if st.button(
                        "Confirm Delete",
                        type="primary",
                        key=f"confirm_delete_{selected_id}",
                    ):
                        deleted = db.delete_product(selected_id)

                        if deleted:
                            st.success("Product deleted.")

                            st.session_state[
                                "visionwrap_delete_confirmation"
                            ] = None

                            if (
                                st.session_state.visionwrap_record_to_edit
                                == selected_id
                            ):
                                set_current_product(None)

                            st.rerun()

                        else:
                            st.error("Product was not found.")

                with cancel_col:
                    if st.button(
                        "Cancel",
                        key=f"cancel_delete_{selected_id}",
                    ):
                        st.session_state[
                            "visionwrap_delete_confirmation"
                        ] = None

                        st.rerun()

    st.divider()

    all_products = db.get_all_products()

    if all_products:
        export_rows = []

        for product in all_products:
            export_rows.append(
                {
                    key: (
                        json.dumps(value, ensure_ascii=False)
                        if isinstance(value, (dict, list))
                        else value
                    )
                    for key, value in product.items()
                }
            )

        import pandas as pd

        export_df = pd.DataFrame(export_rows)

        st.download_button(
            "Export Inventory CSV",
            data=export_df.to_csv(index=False).encode("utf-8-sig"),
            file_name="visionwrap_inventory.csv",
            mime="text/csv",
        )

        st.download_button(
            "Export Inventory JSON",
            data=json.dumps(
                all_products,
                indent=2,
                ensure_ascii=False,
                default=str,
            ),
            file_name="visionwrap_inventory.json",
            mime="application/json",
        )


# =========================================================
# WAREHOUSE & ROUTES
# =========================================================

elif page == "Warehouse & Routes":

    section_title(
        "Warehouse & Route Planning",
        "Inspect transferred products, manage storage assignments, "
        "and calculate a path through a warehouse grid.",
    )

    warehouse_products = db.get_products_by_status("warehouse")

    col1, col2, col3 = st.columns(3)

    with col1:
        render_metric(
            "WAREHOUSE ITEMS",
            len(warehouse_products),
            "Products transferred",
        )

    with col2:
        zones_used = len(
            {
                product.get("storage_zone")
                for product in warehouse_products
                if product.get("storage_zone")
            }
        )

        render_metric(
            "ZONES IN USE",
            zones_used,
            "Distinct assigned zones",
        )

    with col3:
        render_metric(
            "GRID SIZE",
            f"{GRID_ROWS} × {GRID_COLS}",
            "Route-planning cells",
        )

    st.divider()

    section_title(
        "Warehouse Inventory",
        "Products that have completed packaging finalization "
        "and have been transferred to the warehouse.",
    )

    if not warehouse_products:
        st.info(
            "No warehouse products yet. Finalize packaging and "
            "transfer a product from Packaging Review."
        )

    else:
        for product in warehouse_products:
            with st.container(border=True):
                product_col, zone_col = st.columns([1.4, 1])

                with product_col:
                    st.markdown(
                        f"**{safe_text(product.get('product_name'))}**"
                    )

                    st.caption(
                        f"Record #{product.get('id')} · "
                        f"{pretty_label(product.get('product_category'))}"
                    )

                    st.caption(
                        f"Fragility: "
                        f"{pretty_label(product.get('fragility'))}"
                    )

                with zone_col:
                    current_zone = product.get("storage_zone")

                    if current_zone not in STORAGE_ZONES:
                        current_zone = choose_storage_zone(product)

                    new_zone = st.selectbox(
                        "Storage zone",
                        STORAGE_ZONES,
                        index=STORAGE_ZONES.index(current_zone),
                        key=f"zone_{product['id']}",
                    )

                    if st.button(
                        "Update Zone",
                        key=f"update_zone_{product['id']}",
                    ):
                        try:
                            db.update_storage_zone(
                                product["id"],
                                new_zone,
                            )

                            st.success("Storage zone updated.")
                            st.rerun()

                        except Exception as exc:
                            st.error(
                                f"Unable to update zone: {exc}"
                            )

    st.divider()

    section_title(
        "A* Route Planner",
        "Calculate a shortest four-directional path through a "
        "grid while avoiding blocked cells.",
    )

    st.caption(
        "Coordinates are zero-based: row 0, column 0 is the "
        "top-left cell. This grid is a planning demonstration; "
        "it is not connected to physical warehouse sensors."
    )

    with st.form("visionwrap_route_form"):

        start_col, goal_col = st.columns(2)

        with start_col:
            st.markdown("**Start position**")

            start_row = st.number_input(
                "Start row",
                min_value=0,
                max_value=GRID_ROWS - 1,
                value=0,
                step=1,
            )

            start_column = st.number_input(
                "Start column",
                min_value=0,
                max_value=GRID_COLS - 1,
                value=0,
                step=1,
            )

        with goal_col:
            st.markdown("**Destination position**")

            goal_row = st.number_input(
                "Destination row",
                min_value=0,
                max_value=GRID_ROWS - 1,
                value=GRID_ROWS - 1,
                step=1,
            )

            goal_column = st.number_input(
                "Destination column",
                min_value=0,
                max_value=GRID_COLS - 1,
                value=GRID_COLS - 1,
                step=1,
            )

        blocked_text = st.text_area(
            "Blocked cells — one row,column coordinate per line",
            placeholder="Example:\n2,3\n2,4\n3,4",
            help=(
                "Use coordinates like 2,3 to block row 2, column 3. "
                "Invalid coordinates are ignored."
            ),
        )

        calculate_route = st.form_submit_button(
            "Calculate Route",
            type="primary",
            use_container_width=True,
        )

    if calculate_route:
        start = (int(start_row), int(start_column))
        goal = (int(goal_row), int(goal_column))

        blocked = parse_blocked_cells(
            blocked_text,
            GRID_ROWS,
            GRID_COLS,
        )

        if start in blocked:
            st.error("The start cell cannot be blocked.")

        elif goal in blocked:
            st.error("The destination cell cannot be blocked.")

        else:
            route = astar_path(
                start,
                goal,
                blocked,
                GRID_ROWS,
                GRID_COLS,
            )

            st.session_state.visionwrap_route = route
            st.session_state.visionwrap_blocked_cells = blocked
            st.session_state.visionwrap_start_cell = start
            st.session_state.visionwrap_goal_cell = goal

    route = st.session_state.visionwrap_route
    blocked = st.session_state.visionwrap_blocked_cells
    start = st.session_state.visionwrap_start_cell
    goal = st.session_state.visionwrap_goal_cell

    if route:
        st.success(
            f"Route found: {len(route) - 1} grid moves."
        )

        st.markdown("### Route Map")

        st.code(
            make_warehouse_map(
                GRID_ROWS,
                GRID_COLS,
                start,
                goal,
                blocked,
                route,
            ),
            language="text",
        )

        route_col1, route_col2 = st.columns(2)

        with route_col1:
            st.markdown("**Route coordinates**")

            st.write(
                " → ".join(
                    f"({row}, {col})"
                    for row, col in route
                )
            )

        with route_col2:
            st.markdown("**Route summary**")

            st.write(f"Start: {start}")
            st.write(f"Destination: {goal}")
            st.write(f"Blocked cells: {len(blocked)}")
            st.write(f"Grid moves: {len(route) - 1}")

        route_data = {
            "start": start,
            "destination": goal,
            "blocked_cells": sorted(blocked),
            "route": route,
            "grid_rows": GRID_ROWS,
            "grid_columns": GRID_COLS,
            "moves": len(route) - 1,
            "generated_at": datetime.now().isoformat(
                timespec="seconds"
            ),
        }

        st.download_button(
            "Download Route JSON",
            data=json.dumps(
                route_data,
                indent=2,
            ),
            file_name="visionwrap_route.json",
            mime="application/json",
        )

    elif calculate_route:
        st.warning(
            "No valid route exists between these positions. "
            "Check the blocked cells and try again."
        )


# =========================================================
# FOOTER
# =========================================================

st.markdown("---")

st.markdown(
    """
    <div class="footer">
        VisionWrap · Detect. Analyze. Protect. Pack Smart.<br>
        AI-assisted packaging recommendations and warehouse planning.
    </div>
    """,
    unsafe_allow_html=True,
)