from app.database import get_connection


def get_runtime_value(key: str, default: str = "") -> str:
    conn = get_connection()
    row = conn.execute("SELECT value FROM app_state WHERE key = ?", (key,)).fetchone()
    conn.close()
    if not row:
        return default
    return row["value"] or default


def get_runtime_state(*keys: str) -> dict[str, str]:
    if not keys:
        return {}

    conn = get_connection()
    placeholders = ",".join("?" * len(keys))
    rows = conn.execute(
        f"SELECT key, value FROM app_state WHERE key IN ({placeholders})",
        list(keys),
    ).fetchall()
    conn.close()
    values = {row["key"]: row["value"] or "" for row in rows}
    return {key: values.get(key, "") for key in keys}


def set_runtime_state(**entries: str):
    if not entries:
        return

    conn = get_connection()
    for key, value in entries.items():
        conn.execute(
            """
            INSERT INTO app_state (key, value, updated_at)
            VALUES (?, ?, datetime('now'))
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (key, str(value)),
        )
    conn.commit()
    conn.close()


def get_runtime_bool(key: str, default: bool = False) -> bool:
    value = get_runtime_value(key, "1" if default else "0")
    return value == "1"


def get_runtime_int(key: str, default: int = 0) -> int:
    value = get_runtime_value(key, str(default))
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
