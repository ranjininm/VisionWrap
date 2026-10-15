import json
import sqlite3
from pathlib import Path
from datetime import datetime


# =========================================================
# DATABASE CONFIGURATION
# =========================================================

BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "warehouse.db"


# =========================================================
# DATABASE CONNECTION
# =========================================================

def get_connection():
    """Create a connection to the local warehouse database."""

    connection = sqlite3.connect(
        str(DB_PATH),
        timeout=10,
    )

    connection.row_factory = sqlite3.Row

    return connection


# =========================================================
# SERIALIZATION HELPERS
# =========================================================

def to_json(value):
    """Convert Python values into JSON text."""

    return json.dumps(
        value if value is not None else [],
        ensure_ascii=False,
    )


def from_json(value, default=None):
    """Convert JSON text back into Python data."""

    if default is None:
        default = []

    if value is None or value == "":
        return default

    try:
        return json.loads(value)

    except (json.JSONDecodeError, TypeError):
        return default


def row_to_dict(row):
    """Convert a SQLite row into a dictionary."""

    if row is None:
        return None

    result = dict(row)

    json_fields = (
        "protection_features",
        "risk_factors",
        "packing_steps",
        "warnings",
    )

    for field in json_fields:
        result[field] = from_json(
            result.get(field),
            [],
        )

    # Parse the workflow packaging snapshots.
    result["original_packaging"] = from_json(
        result.get("original_packaging"),
        {},
    )

    result["finalized_packaging"] = from_json(
        result.get("finalized_packaging"),
        {},
    )

    return result


# =========================================================
# DATABASE INITIALIZATION
# =========================================================

def init_database():
    """
    Create the inventory table if it does not exist.

    Existing inventory records are preserved.
    """

    with get_connection() as connection:

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS inventory (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                product_name TEXT NOT NULL,
                product_category TEXT,
                description TEXT,
                visible_material TEXT,
                confidence TEXT,
                fragility TEXT,
                estimated_size_class TEXT,

                dimensions_cm TEXT,
                weight_g REAL,

                recommended_box TEXT,
                outer_material TEXT,
                cushioning TEXT,
                void_fill TEXT,
                orientation TEXT,

                protection_features TEXT,
                risk_factors TEXT,
                packing_steps TEXT,
                warnings TEXT,

                packaging_reasoning TEXT,
                sustainability_tip TEXT,

                confirmed INTEGER NOT NULL DEFAULT 1,

                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )


# =========================================================
# WORKFLOW DATABASE MIGRATION
# =========================================================

def ensure_workflow_columns():
    """
    Add the additional workflow columns to existing databases.

    Safe to run repeatedly.
    Does not delete existing inventory records.
    """

    new_columns = {
        "workflow_status": (
            "TEXT NOT NULL DEFAULT 'pending'"
        ),
        "original_packaging": "TEXT",
        "finalized_packaging": "TEXT",
        "packaging_edited": (
            "INTEGER NOT NULL DEFAULT 0"
        ),
        "storage_zone": "TEXT",
        "storage_status": (
            "TEXT NOT NULL DEFAULT 'unassigned'"
        ),
    }

    with get_connection() as connection:

        existing_columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(inventory)"
            ).fetchall()
        }

        for column, definition in new_columns.items():

            if column not in existing_columns:

                connection.execute(
                    f"""
                    ALTER TABLE inventory
                    ADD COLUMN {column} {definition}
                    """
                )


# =========================================================
# PACKAGING HELPERS
# =========================================================

def extract_packaging(product):
    """Extract packaging information from a product dictionary."""

    packaging = product.get("packaging", {})

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
        "protection_features": (
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


# =========================================================
# SAVE CONFIRMED PRODUCT
# =========================================================

def save_product(product, record_id=None):
    """
    Save a confirmed product.

    record_id=None:
        Create a new inventory record.

    record_id=<existing ID>:
        Update that existing record.

    A new product starts with workflow_status='pending'.
    Packaging must be explicitly finalized before transfer.
    """

    if not isinstance(product, dict):
        raise ValueError("Product must be a dictionary.")

    if not product.get("confirmed", False):
        raise ValueError(
            "Only confirmed products can be saved."
        )

    product_name = str(
        product.get("product_name", "")
    ).strip()

    if not product_name:
        raise ValueError(
            "Product name cannot be empty."
        )

    packaging = extract_packaging(product)

    now = datetime.now().isoformat(
        timespec="seconds"
    )

    dimensions = product.get("dimensions_cm")

    if dimensions is not None:
        dimensions = json.dumps(
            dimensions,
            ensure_ascii=False,
        )

    weight = product.get("weight_g")

    if weight is not None:
        try:
            weight = float(weight)

        except (ValueError, TypeError):
            raise ValueError(
                "Weight must be a valid number."
            )

        if weight < 0:
            raise ValueError(
                "Weight cannot be negative."
            )

    values = {
        "product_name": product_name,
        "product_category": product.get(
            "product_category",
            "other",
        ),
        "description": product.get(
            "description",
            "",
        ),
        "visible_material": product.get(
            "visible_material",
            "unknown",
        ),
        "confidence": product.get(
            "confidence",
            "low",
        ),
        "fragility": product.get(
            "fragility",
            "unknown",
        ),
        "estimated_size_class": product.get(
            "estimated_size_class",
            "unknown",
        ),

        "dimensions_cm": dimensions,
        "weight_g": weight,

        "recommended_box": packaging["recommended_box"],
        "outer_material": packaging["outer_material"],
        "cushioning": packaging["cushioning"],
        "void_fill": packaging["void_fill"],
        "orientation": packaging["orientation"],

        "protection_features": to_json(
            packaging["protection_features"]
        ),
        "risk_factors": to_json(
            product.get("risk_factors", [])
        ),
        "packing_steps": to_json(
            product.get("packing_steps", [])
        ),
        "warnings": to_json(
            product.get("warnings", [])
        ),

        "packaging_reasoning": packaging["reasoning"],
        "sustainability_tip": packaging["sustainability_tip"],

        "confirmed": 1,
        "updated_at": now,
    }

    with get_connection() as connection:

        if record_id is not None:

            existing = connection.execute(
                """
                SELECT id
                FROM inventory
                WHERE id = ?
                """,
                (record_id,),
            ).fetchone()

            if existing is None:
                raise ValueError(
                    f"Product record {record_id} does not exist."
                )

            columns = list(values.keys())

            assignments = ", ".join(
                f"{column} = ?"
                for column in columns
            )

            connection.execute(
                f"""
                UPDATE inventory
                SET {assignments}
                WHERE id = ?
                """,
                [
                    values[column]
                    for column in columns
                ] + [record_id],
            )

            return record_id

        columns = list(values.keys())

        placeholders = ", ".join(
            "?" for _ in columns
        )

        connection.execute(
            f"""
            INSERT INTO inventory (
                {", ".join(columns)},
                created_at,
                workflow_status,
                storage_status
            )
            VALUES (
                {placeholders},
                ?,
                'pending',
                'unassigned'
            )
            """,
            [
                values[column]
                for column in columns
            ] + [now],
        )

        record_id = connection.execute(
            "SELECT last_insert_rowid()"
        ).fetchone()[0]

        return record_id


# =========================================================
# FINALIZE PACKAGING
# =========================================================

def finalize_packaging(
    record_id,
    packaging,
    original_packaging=None,
):
    """
    Finalize packaging for an existing inventory record.

    Original AI packaging is stored separately from the
    finalized selection.

    Finalization does not itself transfer the product
    into the warehouse.
    """

    if not isinstance(packaging, dict):
        raise ValueError(
            "Packaging must be a dictionary."
        )

    original_packaging = (
        original_packaging
        if isinstance(original_packaging, dict)
        else {}
    )

    required_fields = (
        "recommended_box",
        "outer_material",
        "cushioning",
        "void_fill",
        "orientation",
    )

    for field in required_fields:

        value = packaging.get(field)

        if value is None or not str(value).strip():

            raise ValueError(
                f"Please provide {field.replace('_', ' ')}."
            )

    final_packaging = dict(packaging)

    now = datetime.now().isoformat(
        timespec="seconds"
    )

    with get_connection() as connection:

        existing = connection.execute(
            """
            SELECT id
            FROM inventory
            WHERE id = ?
            """,
            (record_id,),
        ).fetchone()

        if existing is None:
            raise ValueError(
                f"Product record {record_id} does not exist."
            )

        connection.execute(
            """
            UPDATE inventory

            SET original_packaging = ?,
                finalized_packaging = ?,
                packaging_edited = ?,
                workflow_status = 'finalized',
                storage_zone = NULL,
                storage_status = 'unassigned',
                updated_at = ?

            WHERE id = ?
            """,
            (
                json.dumps(
                    original_packaging,
                    ensure_ascii=False,
                ),
                json.dumps(
                    final_packaging,
                    ensure_ascii=False,
                ),
                int(
                    final_packaging != original_packaging
                ),
                now,
                record_id,
            ),
        )

    return record_id


# =========================================================
# TRANSFER PRODUCT TO WAREHOUSE
# =========================================================

def transfer_to_warehouse(record_id, storage_zone):
    """
    Assign a finalized product to a warehouse zone.

    A product cannot be transferred before finalization.
    """

    storage_zone = str(
        storage_zone or ""
    ).strip()

    if not storage_zone:
        raise ValueError(
            "Please select a warehouse storage zone."
        )

    now = datetime.now().isoformat(
        timespec="seconds"
    )

    with get_connection() as connection:

        product = connection.execute(
            """
            SELECT
                id,
                workflow_status
            FROM inventory
            WHERE id = ?
            """,
            (record_id,),
        ).fetchone()

        if product is None:
            raise ValueError(
                f"Product record {record_id} does not exist."
            )

        if product["workflow_status"] != "finalized":
            raise ValueError(
                "Finalize packaging before transferring "
                "the product to the warehouse."
            )

        connection.execute(
            """
            UPDATE inventory

            SET workflow_status = 'warehouse',
                storage_zone = ?,
                storage_status = 'assigned',
                updated_at = ?

            WHERE id = ?
            """,
            (
                storage_zone,
                now,
                record_id,
            ),
        )

    return record_id


# =========================================================
# UPDATE STORAGE ASSIGNMENT
# =========================================================

def update_storage_zone(record_id, storage_zone):
    """
    Change the storage zone of a product already transferred
    to the warehouse.
    """

    storage_zone = str(
        storage_zone or ""
    ).strip()

    if not storage_zone:
        raise ValueError(
            "Storage zone cannot be empty."
        )

    with get_connection() as connection:

        product = connection.execute(
            """
            SELECT workflow_status
            FROM inventory
            WHERE id = ?
            """,
            (record_id,),
        ).fetchone()

        if product is None:
            raise ValueError(
                f"Product record {record_id} does not exist."
            )

        if product["workflow_status"] != "warehouse":
            raise ValueError(
                "Only warehouse products can have their "
                "storage assignment changed."
            )

        connection.execute(
            """
            UPDATE inventory
            SET storage_zone = ?,
                storage_status = 'assigned',
                updated_at = ?
            WHERE id = ?
            """,
            (
                storage_zone,
                datetime.now().isoformat(
                    timespec="seconds"
                ),
                record_id,
            ),
        )


# =========================================================
# RETRIEVE ALL PRODUCTS
# =========================================================

def get_all_products():
    """Return every inventory record, newest first."""

    with get_connection() as connection:

        rows = connection.execute(
            """
            SELECT *
            FROM inventory
            ORDER BY created_at DESC, id DESC
            """
        ).fetchall()

    return [
        row_to_dict(row)
        for row in rows
    ]


# =========================================================
# RETRIEVE ONE PRODUCT
# =========================================================

def get_product(record_id):
    """Retrieve a product by its database ID."""

    with get_connection() as connection:

        row = connection.execute(
            """
            SELECT *
            FROM inventory
            WHERE id = ?
            """,
            (record_id,),
        ).fetchone()

    return row_to_dict(row)


# =========================================================
# SEARCH INVENTORY
# =========================================================

def search_products(query):
    """
    Search products by name, category, or visible material.
    """

    query = str(query or "").strip()

    if not query:
        return get_all_products()

    pattern = f"%{query}%"

    with get_connection() as connection:

        rows = connection.execute(
            """
            SELECT *
            FROM inventory

            WHERE product_name LIKE ?
               OR product_category LIKE ?
               OR visible_material LIKE ?

            ORDER BY created_at DESC, id DESC
            """,
            (
                pattern,
                pattern,
                pattern,
            ),
        ).fetchall()

    return [
        row_to_dict(row)
        for row in rows
    ]


# =========================================================
# GET PRODUCTS BY WORKFLOW STATUS
# =========================================================

def get_products_by_status(status):
    """Return products matching a workflow status."""

    allowed_statuses = {
        "pending",
        "finalized",
        "warehouse",
    }

    if status not in allowed_statuses:
        raise ValueError(
            "Invalid workflow status."
        )

    with get_connection() as connection:

        rows = connection.execute(
            """
            SELECT *
            FROM inventory
            WHERE workflow_status = ?
            ORDER BY created_at DESC, id DESC
            """,
            (status,),
        ).fetchall()

    return [
        row_to_dict(row)
        for row in rows
    ]


# =========================================================
# DELETE PRODUCT
# =========================================================

def delete_product(record_id):
    """Delete a product from inventory."""

    with get_connection() as connection:

        cursor = connection.execute(
            """
            DELETE FROM inventory
            WHERE id = ?
            """,
            (record_id,),
        )

        return cursor.rowcount > 0


# =========================================================
# INVENTORY STATISTICS
# =========================================================

def get_inventory_stats():
    """Return inventory and workflow statistics."""

    with get_connection() as connection:

        total = connection.execute(
            """
            SELECT COUNT(*)
            FROM inventory
            """
        ).fetchone()[0]

        categories = connection.execute(
            """
            SELECT COUNT(DISTINCT product_category)
            FROM inventory
            """
        ).fetchone()[0]

        fragile = connection.execute(
            """
            SELECT COUNT(*)
            FROM inventory
            WHERE fragility = 'potentially_fragile'
            """
        ).fetchone()[0]

        pending = connection.execute(
            """
            SELECT COUNT(*)
            FROM inventory
            WHERE workflow_status = 'pending'
            """
        ).fetchone()[0]

        finalized = connection.execute(
            """
            SELECT COUNT(*)
            FROM inventory
            WHERE workflow_status = 'finalized'
            """
        ).fetchone()[0]

        warehouse = connection.execute(
            """
            SELECT COUNT(*)
            FROM inventory
            WHERE workflow_status = 'warehouse'
            """
        ).fetchone()[0]

    return {
        "total_products": total,
        "categories": categories,
        "potentially_fragile": fragile,
        "pending_products": pending,
        "finalized_products": finalized,
        "warehouse_products": warehouse,
    }


# =========================================================
# INITIALIZE DATABASE AND MIGRATIONS
# =========================================================

init_database()
ensure_workflow_columns()