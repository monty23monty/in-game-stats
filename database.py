"""Database helpers for caching player statistics."""

import os
import sqlite3
import threading
from contextlib import contextmanager
from typing import Any, Dict, Optional


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

        CREATE TABLE IF NOT EXISTS season_stats (
            player_id INTEGER PRIMARY KEY,
            games_played INTEGER,
            goals INTEGER,
            assists INTEGER,
            points INTEGER,
            pim INTEGER,
            header TEXT,
            FOREIGN KEY(player_id) REFERENCES players(player_id)
        );

        CREATE TABLE IF NOT EXISTS game_stats (
            player_id INTEGER NOT NULL,
            game_id TEXT NOT NULL,
            games_played INTEGER,
            goals INTEGER,
            assists INTEGER,
            points INTEGER,
            pim INTEGER,
            header TEXT,
            PRIMARY KEY(player_id, game_id),
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

    updates = []
    params = []

    if first_name and not player["first_name"]:
        updates.append("first_name = ?")
        params.append(first_name)

    if last_name and not player["last_name"]:
        updates.append("last_name = ?")
        params.append(last_name)

    if position and not player["position"]:
        updates.append("position = ?")
        params.append(position)

    if updates:
        params.append(player["player_id"])
        connection.execute(
            f"UPDATE players SET {', '.join(updates)} WHERE player_id = ?",
            params,
        )

    return int(player["player_id"])


def _safe_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None

    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _int_to_str(value: Optional[int]) -> str:
    if value is None:
        return "0"
    return str(value)


def cache_season_stats(
    team_id: str,
    player_number: str,
    stats: Dict[str, Any],
    team_meta: Dict[str, Any],
) -> None:
    with _DB_LOCK:
        with _managed_connection() as connection:
            _upsert_team(connection, team_id, team_meta)

            player_id = _upsert_player(
                connection,
                team_id,
                player_number,
                stats.get("First Name"),
                stats.get("Last Name"),
                stats.get("Position"),
            )

            connection.execute(
                """
                INSERT INTO season_stats (
                    player_id, games_played, goals, assists, points, pim, header
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(player_id) DO UPDATE SET
                    games_played=excluded.games_played,
                    goals=excluded.goals,
                    assists=excluded.assists,
                    points=excluded.points,
                    pim=excluded.pim,
                    header=excluded.header
                """,
                (
                    player_id,
                    _safe_int(stats.get("Games Played")),
                    _safe_int(stats.get("Goals")),
                    _safe_int(stats.get("Assists")),
                    _safe_int(stats.get("Points")),
                    _safe_int(stats.get("PIM")),
                    stats.get("header"),
                ),
            )


def cache_game_stats(
    team_id: str,
    player_number: str,
    game_id: str,
    stats: Dict[str, Any],
    team_meta: Dict[str, Any],
) -> None:
    with _DB_LOCK:
        with _managed_connection() as connection:
            _upsert_team(connection, team_id, team_meta)

            player_id = _upsert_player(
                connection,
                team_id,
                player_number,
                stats.get("First Name"),
                stats.get("Last Name"),
                stats.get("Position"),
            )

            connection.execute(
                """
                INSERT INTO game_stats (
                    player_id, game_id, games_played, goals, assists, points, pim, header
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(player_id, game_id) DO UPDATE SET
                    games_played=excluded.games_played,
                    goals=excluded.goals,
                    assists=excluded.assists,
                    points=excluded.points,
                    pim=excluded.pim,
                    header=excluded.header
                """,
                (
                    player_id,
                    game_id,
                    _safe_int(stats.get("Games Played")),
                    _safe_int(stats.get("Goals")),
                    _safe_int(stats.get("Assists")),
                    _safe_int(stats.get("Points")),
                    _safe_int(stats.get("PIM")),
                    stats.get("header"),
                ),
            )


def get_cached_season_stats(team_id: str, player_number: str) -> Optional[Dict[str, Any]]:
    with _DB_LOCK:
        with _managed_connection() as connection:
            row = connection.execute(
                """
                SELECT
                    p.player_number,
                    p.first_name,
                    p.last_name,
                    p.position,
                    s.games_played,
                    s.goals,
                    s.assists,
                    s.points,
                    s.pim,
                    s.header,
                    t.logo,
                    t.color,
                    t.color_secondary
                FROM players p
                JOIN season_stats s ON s.player_id = p.player_id
                JOIN teams t ON t.team_id = p.team_id
                WHERE p.team_id = ? AND p.player_number = ?
                """,
                (team_id, player_number),
            ).fetchone()

            if row is None:
                return None

            return {
                "Player Number": row["player_number"],
                "First Name": row["first_name"] or "",
                "Last Name": row["last_name"] or "",
                "Games Played": _int_to_str(row["games_played"]),
                "Goals": _int_to_str(row["goals"]),
                "Assists": _int_to_str(row["assists"]),
                "Points": _int_to_str(row["points"]),
                "PIM": _int_to_str(row["pim"]),
                "Logo": row["logo"],
                "header": row["header"] or "Season So Far",
                "Position": row["position"] or "",
                "Color": row["color"],
                "Color-s": row["color_secondary"],
            }


def get_cached_game_stats(
    team_id: str, player_number: str, game_id: str
) -> Optional[Dict[str, Any]]:
    with _DB_LOCK:
        with _managed_connection() as connection:
            row = connection.execute(
                """
                SELECT
                    p.player_number,
                    p.first_name,
                    p.last_name,
                    p.position,
                    g.games_played,
                    g.goals,
                    g.assists,
                    g.points,
                    g.pim,
                    g.header,
                    t.logo,
                    t.color,
                    t.color_secondary
                FROM players p
                JOIN game_stats g ON g.player_id = p.player_id
                JOIN teams t ON t.team_id = p.team_id
                WHERE p.team_id = ? AND p.player_number = ? AND g.game_id = ?
                """,
                (team_id, player_number, game_id),
            ).fetchone()

            if row is None:
                return None

            return {
                "Player Number": row["player_number"],
                "First Name": row["first_name"] or "",
                "Last Name": row["last_name"] or "",
                "Games Played": _int_to_str(row["games_played"]),
                "Goals": _int_to_str(row["goals"]),
                "Assists": _int_to_str(row["assists"]),
                "Points": _int_to_str(row["points"]),
                "PIM": _int_to_str(row["pim"]),
                "Logo": row["logo"],
                "header": row["header"] or "So Far This Game",
                "Position": row["position"] or "",
                "Color": row["color"],
                "Color-s": row["color_secondary"],
            }

