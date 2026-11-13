"""ZikoTodo least-privilege project ACL, independently owned by ZIKO.

No implicit owner and no shared-password fallback. The database is stored
inside this app's own /data volume; it is NOT shared with the Vikunja app.
"""
from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path

DEFAULT_DB = Path(os.environ.get("ZIKO_ACL_DB", "/data/acl.sqlite3"))
ROLES = {
    "viewer": frozenset({"read"}),
    "editor": frozenset({"read", "write_tasks"}),
    "manager": frozenset({"read", "write_tasks", "manage_members"}),
}
USER_RE = re.compile(r"[A-Za-z0-9_-]{1,128}\Z", re.ASCII)
SLUG_RE = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}\Z", re.ASCII)


def valid_user(value: str) -> bool:
    return isinstance(value, str) and bool(USER_RE.fullmatch(value))


def valid_slug(value: str) -> bool:
    return isinstance(value, str) and bool(SLUG_RE.fullmatch(value))


def db_connect(path: str | Path = DEFAULT_DB) -> sqlite3.Connection:
    con = sqlite3.connect(str(path), timeout=3)
    con.execute("PRAGMA foreign_keys=ON")
    con.row_factory = sqlite3.Row
    return con


def init_db(path: str | Path = DEFAULT_DB) -> None:
    location = Path(path)
    location.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with db_connect(location) as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS projects (
            slug TEXT PRIMARY KEY NOT NULL,
            title TEXT NOT NULL CHECK(length(title) BETWEEN 1 AND 150),
            active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1))
        );
        CREATE TABLE IF NOT EXISTS memberships (
            project_slug TEXT NOT NULL REFERENCES projects(slug) ON DELETE CASCADE,
            ha_user_id TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('viewer','editor','manager')),
            PRIMARY KEY(project_slug, ha_user_id)
        );
        CREATE INDEX IF NOT EXISTS memberships_by_user ON memberships(ha_user_id);
        """)
    os.chmod(location, 0o600)


def create_project(path: str | Path, slug: str, title: str) -> None:
    if not valid_slug(slug) or not isinstance(title, str) or not 1 <= len(title.strip()) <= 150:
        raise ValueError("invalid project")
    with db_connect(path) as con:
        con.execute("INSERT INTO projects(slug,title) VALUES (?,?)", (slug, title.strip()))


def grant(path: str | Path, slug: str, ha_user_id: str, role: str) -> None:
    if not valid_slug(slug) or not valid_user(ha_user_id) or role not in ROLES:
        raise ValueError("invalid membership")
    with db_connect(path) as con:
        con.execute(
            "INSERT INTO memberships(project_slug,ha_user_id,role) VALUES (?,?,?) "
            "ON CONFLICT(project_slug,ha_user_id) DO UPDATE SET role=excluded.role",
            (slug, ha_user_id, role),
        )


def revoke(path: str | Path, slug: str, ha_user_id: str) -> None:
    if not valid_slug(slug) or not valid_user(ha_user_id):
        raise ValueError("invalid membership")
    with db_connect(path) as con:
        con.execute("DELETE FROM memberships WHERE project_slug=? AND ha_user_id=?",
                    (slug, ha_user_id))


def accessible_projects(path: str | Path, ha_user_id: str) -> list[dict]:
    """Every read is restricted by the session's stable Home Assistant ID."""
    if not valid_user(ha_user_id) or not Path(path).is_file():
        return []
    with db_connect(path) as con:
        rows = con.execute(
            "SELECT p.slug, p.title, m.role FROM projects p "
            "JOIN memberships m ON m.project_slug=p.slug "
            "WHERE p.active=1 AND m.ha_user_id=? ORDER BY p.title COLLATE NOCASE",
            (ha_user_id,),
        ).fetchall()
        return [dict(x) for x in rows]


def get_project(path: str | Path, ha_user_id: str, slug: str) -> dict | None:
    """Missing/unauthorized projects are deliberately indistinguishable."""
    if not valid_user(ha_user_id) or not valid_slug(slug) or not Path(path).is_file():
        return None
    with db_connect(path) as con:
        row = con.execute(
            "SELECT p.slug, p.title, m.role FROM projects p "
            "JOIN memberships m ON m.project_slug=p.slug "
            "WHERE p.active=1 AND m.ha_user_id=? AND p.slug=?",
            (ha_user_id, slug),
        ).fetchone()
        return dict(row) if row else None


def permitted(path: str | Path, ha_user_id: str, slug: str, operation: str) -> bool:
    role = get_project(path, ha_user_id, slug)
    return role is not None and operation in ROLES[role["role"]]
