"""A'zolarni hisobga olish uchun SQLite (aiosqlite) bazasi."""
import os
from typing import Any

import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS members (
    chat_id    INTEGER NOT NULL,
    user_id    INTEGER NOT NULL,
    username   TEXT,
    first_name TEXT,
    is_bot     INTEGER NOT NULL DEFAULT 0,
    last_seen  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (chat_id, user_id)
);
CREATE TABLE IF NOT EXISTS tagged (
    chat_id   INTEGER NOT NULL,
    user_id   INTEGER NOT NULL,
    tagged_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (chat_id, user_id)
);
CREATE TABLE IF NOT EXISTS settings (
    chat_id     INTEGER PRIMARY KEY,
    skip_admins INTEGER NOT NULL DEFAULT 1,
    skip_bots   INTEGER NOT NULL DEFAULT 1,
    skip_tagged INTEGER NOT NULL DEFAULT 0
);
"""

BOOL_SETTINGS = ("skip_admins", "skip_bots", "skip_tagged")


class Database:
    def __init__(self, path: str) -> None:
        self.path = path
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        folder = os.path.dirname(self.path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.executescript(SCHEMA)
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()

    async def upsert_member(self, chat_id: int, user_id: int, username: str | None,
                            first_name: str | None, is_bot: bool) -> None:
        await self._conn.execute(
            """INSERT INTO members (chat_id, user_id, username, first_name, is_bot, last_seen)
               VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(chat_id, user_id) DO UPDATE SET
                   username = excluded.username,
                   first_name = excluded.first_name,
                   is_bot = excluded.is_bot,
                   last_seen = CURRENT_TIMESTAMP""",
            (chat_id, user_id, username, first_name, int(is_bot)),
        )
        await self._conn.commit()

    async def remove_member(self, chat_id: int, user_id: int) -> None:
        await self._conn.execute(
            "DELETE FROM members WHERE chat_id=? AND user_id=?", (chat_id, user_id))
        await self._conn.execute(
            "DELETE FROM tagged WHERE chat_id=? AND user_id=?", (chat_id, user_id))
        await self._conn.commit()

    async def get_members(self, chat_id: int) -> list[dict[str, Any]]:
        cur = await self._conn.execute(
            "SELECT user_id, username, first_name, is_bot FROM members "
            "WHERE chat_id=? ORDER BY user_id", (chat_id,))
        return [dict(r) for r in await cur.fetchall()]

    async def count_members(self, chat_id: int) -> int:
        cur = await self._conn.execute(
            "SELECT COUNT(*) FROM members WHERE chat_id=?", (chat_id,))
        return (await cur.fetchone())[0]

    async def tagged_ids(self, chat_id: int) -> set[int]:
        cur = await self._conn.execute(
            "SELECT user_id FROM tagged WHERE chat_id=?", (chat_id,))
        return {r[0] for r in await cur.fetchall()}

    async def mark_tagged(self, chat_id: int, user_ids: list[int]) -> None:
        await self._conn.executemany(
            "INSERT OR REPLACE INTO tagged (chat_id, user_id) VALUES (?, ?)",
            [(chat_id, uid) for uid in user_ids])
        await self._conn.commit()

    async def reset_tagged(self, chat_id: int) -> None:
        await self._conn.execute("DELETE FROM tagged WHERE chat_id=?", (chat_id,))
        await self._conn.commit()

    async def get_settings(self, chat_id: int) -> dict[str, bool]:
        await self._conn.execute(
            "INSERT OR IGNORE INTO settings (chat_id) VALUES (?)", (chat_id,))
        await self._conn.commit()
        cur = await self._conn.execute(
            "SELECT skip_admins, skip_bots, skip_tagged FROM settings WHERE chat_id=?",
            (chat_id,))
        row = await cur.fetchone()
        return {k: bool(row[k]) for k in BOOL_SETTINGS}

    async def set_setting(self, chat_id: int, key: str, value: bool) -> None:
        if key not in BOOL_SETTINGS:
            raise ValueError(f"Noma'lum sozlama: {key}")
        await self.get_settings(chat_id)
        await self._conn.execute(
            f"UPDATE settings SET {key}=? WHERE chat_id=?", (int(value), chat_id))
        await self._conn.commit()
