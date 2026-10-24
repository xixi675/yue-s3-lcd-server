from __future__ import annotations

import logging
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)

SERVER_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = Path(
    os.environ.get(
        "XIAOYUE_CONVERSATION_DB",
        SERVER_ROOT / "data" / "conversations.db",
    )
)


class ConversationStore:
    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self._lock = threading.RLock()
        self._schema_ready = False
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    def _ensure_schema(self) -> None:
        if self._schema_ready:
            return
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock, self._connect() as connection:
                connection.execute("PRAGMA journal_mode = WAL")
                connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS conversations (
                        id TEXT PRIMARY KEY,
                        device_id TEXT NOT NULL DEFAULT '',
                        started_at REAL NOT NULL,
                        updated_at REAL NOT NULL,
                        ended_at REAL
                    );

                    CREATE TABLE IF NOT EXISTS messages (
                        message_id TEXT PRIMARY KEY,
                        conversation_id TEXT NOT NULL,
                        role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                        content TEXT NOT NULL,
                        created_at REAL NOT NULL,
                        FOREIGN KEY (conversation_id)
                            REFERENCES conversations(id)
                            ON DELETE CASCADE
                    );

                    CREATE INDEX IF NOT EXISTS idx_conversations_updated
                        ON conversations(updated_at DESC);
                    CREATE INDEX IF NOT EXISTS idx_messages_conversation
                        ON messages(conversation_id, created_at);
                    """
                )
                connection.execute(
                    """
                    UPDATE conversations
                    SET ended_at = updated_at
                    WHERE ended_at IS NULL
                    """
                )
            self._schema_ready = True
        except (OSError, sqlite3.Error) as error:
            logger.error("初始化对话数据库失败: %s", error)

    def add_message(
        self,
        conversation_id: str,
        device_id: str,
        role: str,
        content: str,
        message_id: str,
        created_at: float | None = None,
    ) -> bool:
        content = str(content or "").strip()
        if not conversation_id or role not in {"user", "assistant"} or not content:
            return False
        self._ensure_schema()
        if not self._schema_ready:
            return False

        now = float(created_at if created_at is not None else time.time())
        try:
            with self._lock, self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO conversations (
                        id, device_id, started_at, updated_at, ended_at
                    ) VALUES (?, ?, ?, ?, NULL)
                    ON CONFLICT(id) DO UPDATE SET
                        device_id = CASE
                            WHEN excluded.device_id <> '' THEN excluded.device_id
                            ELSE conversations.device_id
                        END,
                        updated_at = MAX(conversations.updated_at, excluded.updated_at)
                    """,
                    (conversation_id, device_id or "", now, now),
                )
                connection.execute(
                    """
                    INSERT OR IGNORE INTO messages (
                        message_id, conversation_id, role, content, created_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (message_id, conversation_id, role, content, now),
                )
            return True
        except sqlite3.Error as error:
            logger.error("保存对话消息失败: %s", error)
            return False

    def end_conversation(self, conversation_id: str) -> None:
        if not conversation_id:
            return
        self._ensure_schema()
        if not self._schema_ready:
            return
        now = time.time()
        try:
            with self._lock, self._connect() as connection:
                connection.execute(
                    """
                    UPDATE conversations
                    SET ended_at = COALESCE(ended_at, ?),
                        updated_at = MAX(updated_at, ?)
                    WHERE id = ?
                    """,
                    (now, now, conversation_id),
                )
        except sqlite3.Error as error:
            logger.error("结束对话记录失败: %s", error)

    def dashboard(self, session_id: str | None = None, limit: int = 30) -> dict[str, Any]:
        self._ensure_schema()
        if not self._schema_ready:
            return {
                "current": None,
                "selected": None,
                "sessions": [],
                "counts": {"sessions": 0},
            }

        limit = max(1, min(int(limit), 100))
        try:
            with self._lock, self._connect() as connection:
                rows = connection.execute(
                    """
                    SELECT
                        c.id,
                        c.device_id,
                        c.started_at,
                        c.updated_at,
                        c.ended_at,
                        COUNT(m.message_id) AS message_count,
                        COALESCE(
                            (
                                SELECT content
                                FROM messages
                                WHERE conversation_id = c.id AND role = 'user'
                                ORDER BY created_at, message_id
                                LIMIT 1
                            ),
                            ''
                        ) AS preview
                    FROM conversations c
                    LEFT JOIN messages m ON m.conversation_id = c.id
                    GROUP BY c.id
                    ORDER BY c.updated_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()

                current_row = connection.execute(
                    """
                    SELECT id
                    FROM conversations
                    WHERE ended_at IS NULL
                    ORDER BY updated_at DESC
                    LIMIT 1
                    """
                ).fetchone()
                if current_row is None:
                    current_row = connection.execute(
                        """
                        SELECT id
                        FROM conversations
                        ORDER BY updated_at DESC
                        LIMIT 1
                        """
                    ).fetchone()

                current = (
                    self._conversation_detail(connection, current_row["id"])
                    if current_row
                    else None
                )
                selected = (
                    self._conversation_detail(connection, session_id)
                    if session_id
                    else current
                )
                sessions = [self._conversation_summary(row) for row in rows]
                total = connection.execute(
                    "SELECT COUNT(*) AS count FROM conversations"
                ).fetchone()["count"]
        except sqlite3.Error as error:
            logger.error("读取对话记录失败: %s", error)
            return {
                "current": None,
                "selected": None,
                "sessions": [],
                "counts": {"sessions": 0},
            }

        return {
            "current": current,
            "selected": selected,
            "sessions": sessions,
            "counts": {"sessions": int(total)},
        }

    def _conversation_detail(
        self, connection: sqlite3.Connection, session_id: str
    ) -> dict[str, Any] | None:
        row = connection.execute(
            """
            SELECT id, device_id, started_at, updated_at, ended_at
            FROM conversations
            WHERE id = ?
            """,
            (session_id,),
        ).fetchone()
        if row is None:
            return None
        messages = connection.execute(
            """
            SELECT message_id, role, content, created_at
            FROM messages
            WHERE conversation_id = ?
            ORDER BY created_at, rowid
            """,
            (session_id,),
        ).fetchall()
        return {
            "id": row["id"],
            "device_id": row["device_id"],
            "started_at": float(row["started_at"]),
            "updated_at": float(row["updated_at"]),
            "ended_at": float(row["ended_at"]) if row["ended_at"] else None,
            "active": row["ended_at"] is None,
            "messages": [
                {
                    "id": message["message_id"],
                    "role": message["role"],
                    "content": message["content"],
                    "created_at": float(message["created_at"]),
                }
                for message in messages
            ],
        }

    @staticmethod
    def _conversation_summary(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "device_id": row["device_id"],
            "started_at": float(row["started_at"]),
            "updated_at": float(row["updated_at"]),
            "ended_at": float(row["ended_at"]) if row["ended_at"] else None,
            "active": row["ended_at"] is None,
            "message_count": int(row["message_count"]),
            "preview": row["preview"],
        }


conversation_store = ConversationStore()
