import sqlite3
import json
from typing import Any, Dict, List


def extract(cursor: sqlite3.Cursor, table: str, column: str = None) -> List[Any]:

    if column:
        query = f"SELECT {column} FROM {table}"
        cursor.execute(query)
        rows = [row[column] for row in cursor.fetchall()]
    else:
        query = f"SELECT * FROM {table}"
        cursor.execute(query)
        rows = [dict(row) for row in cursor.fetchall()]

    return rows


def load_config(path: str = "config.json") -> Dict[str, Any]:
    """Load database configuration from a JSON file."""
    with open(path, "r") as f:
        return json.load(f)

def insert(cursor:sqlite3.Cursor, config: Dict[str, Any]) -> None:
    table = next(iter(config))
    row_data = config[table]

    print(table)
    print(row_data)

    columns = ", ".join(row_data.keys())
    print(columns)
    values = [str(value) if isinstance(value, int) else f'"{value}"' for value in list(row_data.values())]
    placeholders = ", ".join(values)

    query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
    print(values)
    print(query)
    cursor.execute(query)
    



if __name__=="__main__":
    db_path = "orbility_data/Parking.db"
    config_path = "dependencies/config_insert.json"

    config = load_config(config_path)
    print(config, config['event'])
    config["event"]["payload_json"] = str(config["event"]["payload_json"])

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    rows = extract(cursor=cursor, table="session", column="licence_plate_entry")

    insert(cursor=cursor, config=config)
    print(rows)
    conn.commit()
    conn.close()