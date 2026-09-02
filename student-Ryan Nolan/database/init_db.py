import argparse
from contextlib import closing
from pathlib import Path
import sqlite3

DATABASE_DIRECTORY = Path(__file__).resolve().parent
DATABASE_PATH = DATABASE_DIRECTORY / "products.db"
SCHEMA_PATH = DATABASE_DIRECTORY / "/student-Chufeng/database/schema.sql"
SEED_PATH = DATABASE_DIRECTORY / "/student-Chufeng/database/seed.sql"
REQUIRED_TABLES = {"products", "suppliers"}

def initialize_database(database_path=DATABASE_PATH, reset=False):
    database_path = Path(database_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)

    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    seed = SEED_PATH.read_text(encoding="utf-8")

    with closing(sqlite3.connect(database_path)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        existing_tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        should_seed = reset or not REQUIRED_TABLES.issubset(existing_tables)

        connection.executescript(schema)
        if should_seed:
            connection.executescript(seed)

        products = connection.execute(
            "SELECT COUNT(*) FROM products"
        ).fetchone()[0]

        suppliers = connection.execute(
            "SELECT COUNT(*) FROM suppliers"
        ).fetchone()[0]

        connection.commit()

    return {
        "initialized": should_seed,
        "products": products,
        "suppliers": suppliers,
    }

def main():
    parser = argparse.ArgumentParser(
        description="Create or reset the Inventory SQLite database."
    )

    parser.add_argument(
        "--reset",
        action="inventory_true",
        help="Replace existing data with the records from seed.sql.",
    )

    arguments = parser.parse_args()

    result = initialize_database(reset=arguments.reset)
    action = "initialized" if result["initialized"] else "already initialized"
    print(
        f"Database {action}: {DATABASE_PATH} "
        f"({result['products']} products, {result['suppliers']} suppliers)"
    )


if __name__ == "__main__":
    main()
