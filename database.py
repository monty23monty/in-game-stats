"""Database helpers for caching player statistic metadata."""

import os
import sqlite3
import threading
from contextlib import contextmanager
from typing import Any, Dict, Iterable, List, Optional


DATABASE_FILE = os.path.join(os.path.dirname(__file__), "player_stats.db")
_DB_LOCK = threading.Lock()


def _get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_FILE)
    connection.row_factory = sqlite3.Row
    return connection


@contextmanager
def _managed_connection() -> sqlite3.Connection:
    connection = _get_connection()
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def init_db() -> None:
    """Initialise the SQLite database with the required schema."""

    schema = """
        CREATE TABLE IF NOT EXISTS teams (
            team_id TEXT PRIMARY KEY,
            name TEXT,
            logo TEXT,
            color TEXT,
            color_secondary TEXT
        );

        CREATE TABLE IF NOT EXISTS players (
            player_id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id TEXT NOT NULL,
            player_number TEXT NOT NULL,
            first_name TEXT,
            last_name TEXT,
            position TEXT,
            UNIQUE(team_id, player_number),
            FOREIGN KEY(team_id) REFERENCES teams(team_id)
        );

        CREATE TABLE IF NOT EXISTS stat_titles (
            player_id INTEGER NOT NULL,
            context TEXT NOT NULL,
            title TEXT NOT NULL,
            PRIMARY KEY (player_id, context, title),
            FOREIGN KEY(player_id) REFERENCES players(player_id)
        );
    """

    with _DB_LOCK:
        with _managed_connection() as connection:
            connection.executescript(schema)


def _upsert_team(connection: sqlite3.Connection, team_id: str, team_meta: Dict[str, Any]) -> None:
    name = team_meta.get("name")
    logo = team_meta.get("logo")
    color = team_meta.get("color")
    color_secondary = team_meta.get("color-s")

    connection.execute(
        """
        INSERT INTO teams (team_id, name, logo, color, color_secondary)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(team_id) DO UPDATE SET
            name=excluded.name,
            logo=excluded.logo,
            color=excluded.color,
            color_secondary=excluded.color_secondary
        """,
        (team_id, name, logo, color, color_secondary),
    )


def _upsert_player(
    connection: sqlite3.Connection,
    team_id: str,
    player_number: str,
    first_name: Optional[str],
    last_name: Optional[str],
    position: Optional[str],
) -> int:
    player = connection.execute(
        """
        SELECT player_id, first_name, last_name, position
        FROM players
        WHERE team_id = ? AND player_number = ?
        """,
        (team_id, player_number),
    ).fetchone()

    if player is None:
        cursor = connection.execute(
            """
            INSERT INTO players (team_id, player_number, first_name, last_name, position)
            VALUES (?, ?, ?, ?, ?)
            """,
            (team_id, player_number, first_name, last_name, position),
        )
        return int(cursor.lastrowid)

    updates: List[str] = []
    params: List[Any] = []

    if first_name and first_name != player["first_name"]:
        updates.append("first_name = ?")
        params.append(first_name)

    if last_name and last_name != player["last_name"]:
        updates.append("last_name = ?")
        params.append(last_name)

    if position and position != player["position"]:
        updates.append("position = ?")
        params.append(position)

    if updates:
        params.append(player["player_id"])
        connection.execute(
            f"UPDATE players SET {', '.join(updates)} WHERE player_id = ?",
            params,
        )

    return int(player["player_id"])


def cache_stat_titles(
    team_id: str,
    player_number: str,
    context: str,
    titles: Iterable[str],
    player_meta: Dict[str, Optional[str]],
    team_meta: Dict[str, Any],
) -> None:
    """Persist player metadata and the stat titles available for a context."""

    normalized_titles = sorted({title for title in titles if title})
    if not normalized_titles:
        return

    with _DB_LOCK:
        with _managed_connection() as connection:
            _upsert_team(connection, team_id, team_meta)

            player_id = _upsert_player(
                connection,
                team_id,
                player_number,
                player_meta.get("first_name"),
                player_meta.get("last_name"),
                player_meta.get("position"),
            )

            connection.execute(
                "DELETE FROM stat_titles WHERE player_id = ? AND context = ?",
                (player_id, context),
            )

            connection.executemany(
                """
                INSERT INTO stat_titles (player_id, context, title)
                VALUES (?, ?, ?)
                """,
                [(player_id, context, title) for title in normalized_titles],
            )


def get_cached_stat_titles(
    team_id: str, player_number: str, context: str
) -> Optional[Dict[str, Any]]:
    """Retrieve cached stat titles and associated metadata for a player/context."""

    with _DB_LOCK:
        with _managed_connection() as connection:
            player_row = connection.execute(
                """
                SELECT
                    p.player_id,
                    p.first_name,
                    p.last_name,
                    p.position,
                    t.logo,
                    t.color,
                    t.color_secondary
                FROM players p
                LEFT JOIN teams t ON t.team_id = p.team_id
                WHERE p.team_id = ? AND p.player_number = ?
                """,
                (team_id, player_number),
            ).fetchone()

            if player_row is None:
                return None

            titles = [
                row["title"]
                for row in connection.execute(
                    """
                    SELECT title
                    FROM stat_titles
                    WHERE player_id = ? AND context = ?
                    ORDER BY title
                    """,
                    (player_row["player_id"], context),
                ).fetchall()
            ]

            if not titles:
                return None

            return {
                "stat_titles": titles,
                "player": {
                    "first_name": player_row["first_name"],
                    "last_name": player_row["last_name"],
                    "position": player_row["position"],
                },
                "team": {
                    "logo": player_row["logo"],
                    "color": player_row["color"],
                    "color_secondary": player_row["color_secondary"],
                },
            }
