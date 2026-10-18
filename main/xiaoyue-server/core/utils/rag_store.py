from __future__ import annotations

import logging
import re
import sqlite3
import threading
from pathlib import Path

import jieba

logger = logging.getLogger("rag_store")

_SERVER_ROOT = Path(__file__).resolve().parents[2]
_DB_PATH = _SERVER_ROOT / "data" / "knowledge.db"
_LOCK = threading.Lock()

_TYPE_KEYWORDS = [
    (("儿歌", "童谣", "古诗", "诗歌"), "儿歌"),
    (("故事", "睡前", "寓言", "成语"), "故事"),
    (("认知", "数字", "颜色", "形状", "动物", "水果", "交通工具"), "认知"),
    (("英语", "单词", "字母", "abc"), "英语"),
    (("生活常识", "刷牙", "洗手", "红绿灯", "安全"), "生活常识"),
]
_DIFFICULTY_KEYWORDS = [
    (("简单", "入门", "容易"), "简单"),
    (("中等", "进阶"), "中等"),
    (("困难", "挑战", "高级"), "困难"),
]


def _tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    seen: set[str] = set()
    for token in jieba.cut_for_search((text or "").lower()):
        token = token.strip()
        if not token or re.fullmatch(r"[\W_]+", token) or token in seen:
            continue
        seen.add(token)
        tokens.append(token)
    return tokens


def _extract_filters(query: str) -> tuple[str | None, str | None]:
    item_type = next(
        (kind for words, kind in _TYPE_KEYWORDS if any(word in (query or "").lower() for word in words)),
        None,
    )
    difficulty = next(
        (level for words, level in _DIFFICULTY_KEYWORDS if any(word in (query or "") for word in words)),
        None,
    )
    return item_type, difficulty


def _run_search(query: str, top_k: int, item_type: str | None, difficulty: str | None) -> list[dict]:
    if not query or not _DB_PATH.exists():
        return []
    tokens = _tokenize(query)
    if not tokens:
        return []
    expression = " OR ".join('"' + token.replace('"', '""') + '"' for token in tokens)
    clauses = ["chunks_fts MATCH ?"]
    params: list[object] = [expression]
    if item_type:
        clauses.append("c.item_type = ?")
        params.append(item_type)
    if difficulty:
        clauses.append("c.difficulty = ?")
        params.append(difficulty)
    params.append(max(1, int(top_k)))
    sql = (
        "SELECT c.source, c.title, c.content, c.item_type, c.category, "
        "c.difficulty, c.tags, bm25(chunks_fts) AS score "
        "FROM chunks_fts JOIN chunks c ON c.id = chunks_fts.rowid "
        "WHERE " + " AND ".join(clauses) + " ORDER BY score LIMIT ?"
    )
    try:
        with _LOCK:
            conn = sqlite3.connect(f"file:{_DB_PATH}?mode=ro", uri=True, timeout=5)
            conn.row_factory = sqlite3.Row
            try:
                rows = conn.execute(sql, params).fetchall()
            finally:
                conn.close()
        return [dict(row) for row in rows]
    except sqlite3.Error as exc:
        logger.warning("RAG search failed: %s", exc)
        return []


def _title_search(query: str, top_k: int) -> list[dict]:
    """When the user names an item, return it directly."""
    if not query or not _DB_PATH.exists():
        return []
    try:
        with _LOCK:
            conn = sqlite3.connect(f"file:{_DB_PATH}?mode=ro", uri=True, timeout=5)
            conn.row_factory = sqlite3.Row
            try:
                titles = [row["title"] for row in conn.execute("SELECT DISTINCT title FROM chunks")]
                matches = sorted(
                    (title for title in titles if title and title in query),
                    key=len,
                    reverse=True,
                )
                if not matches:
                    return []
                placeholders = ",".join("?" for _ in matches)
                rows = conn.execute(
                    "SELECT source, title, content, item_type, category, difficulty, tags "
                    "FROM chunks WHERE title IN (" + placeholders + ")",
                    matches,
                ).fetchall()
            finally:
                conn.close()
        order = {title: index for index, title in enumerate(matches)}
        result = sorted(rows, key=lambda row: order.get(row["title"], 999))
        return [dict(row) for row in result[: max(1, int(top_k))]]
    except sqlite3.Error as exc:
        logger.warning("RAG title search failed: %s", exc)
        return []


def search(query: str, top_k: int = 4) -> list[dict]:
    title_rows = _title_search(query, top_k)
    if title_rows:
        return title_rows
    item_type, difficulty = _extract_filters(query)
    return _run_search(query, top_k, item_type, difficulty)


def build_context(query: str, top_k: int = 4, max_chars: int = 3000) -> str:
    chunks = search(query, top_k=top_k)
    if not chunks:
        return ""
    parts: list[str] = []
    used = 0
    for index, chunk in enumerate(chunks, 1):
        content = (chunk.get("content") or "").strip()
        if not content:
            continue
        meta = []
        if chunk.get("item_type"):
            meta.append(f"类型：{chunk['item_type']}")
        if chunk.get("category"):
            meta.append(f"分类：{chunk['category']}")
        if chunk.get("difficulty"):
            meta.append(f"难度：{chunk['difficulty']}")
        meta.append(f"来源：{chunk.get('source', '')}")
        piece = f"[资料{index}] " + " | ".join(meta) + "\n" + content
        if used + len(piece) > max_chars:
            break
        parts.append(piece)
        used += len(piece)
    if not parts:
        return ""
    return (
        "以下是从本地儿童知识库检索到的相关资料。回答时优先依据这些资料；"
        "如果资料中没有答案，请明确说不知道，不要编造。\n\n"
        + "\n\n".join(parts)
    )