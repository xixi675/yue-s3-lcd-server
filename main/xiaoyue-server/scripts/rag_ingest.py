#!/usr/bin/env python3
"""Build data/knowledge.db from structured children's content."""

import argparse
import csv
import json
import re
import sqlite3
import sys
from pathlib import Path

import jieba

SERVER_ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_DIR = SERVER_ROOT / "data" / "knowledge"
DB_PATH = SERVER_ROOT / "data" / "knowledge.db"
SUPPORTED = {".txt", ".md", ".markdown", ".csv", ".json", ".pdf"}


def read_file(path: Path) -> str | None:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        from pypdf import PdfReader
        return "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
    if suffix in {".txt", ".md", ".markdown"}:
        return path.read_text(encoding="utf-8", errors="replace")
    if suffix == ".csv":
        lines = []
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.reader(handle):
                cells = [cell.strip() for cell in row if cell.strip()]
                if cells:
                    lines.append(" | ".join(cells))
        return "\n".join(lines)
    if suffix == ".json":
        return path.read_text(encoding="utf-8")
    return None


def iter_items(path: Path):
    suffix = path.suffix.lower()
    if suffix == ".json":
        raw = path.read_text(encoding="utf-8")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            print(f"[WARN] invalid JSON {path}: {exc}")
            return
        items = data.get("items") if isinstance(data, dict) else data
        if isinstance(items, list) and items and all(isinstance(i, dict) and i.get("content") for i in items):
            for item in items:
                yield item
            return
        yield {"content": raw}
        return
    text = read_file(path)
    if text and text.strip():
        yield {"content": text}


def compose_item(item: dict) -> tuple[str, dict]:
    title = str(item.get("title") or "未命名内容")
    item_type = str(item.get("type") or "通用")
    category = str(item.get("category") or item_type)
    difficulty = str(item.get("difficulty") or "")
    tags = item.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]
    tags_text = "、".join(str(tag) for tag in tags if str(tag).strip())
    content = str(item.get("content") or "").strip()
    pinyin = str(item.get("pinyin") or "").strip()
    explanation = str(item.get("explanation") or "").strip()
    meta = [
        f"【标题】{title}",
        f"【类型】{item_type}",
        f"【分类】{category}",
    ]
    if difficulty:
        meta.append(f"【难度】{difficulty}")
    if tags_text:
        meta.append(f"【标签】{tags_text}")
    body = "\n".join(meta) + f"\n【正文】{content}"
    if pinyin:
        body += f"\n【拼音】{pinyin}"
    if explanation:
        body += f"\n【讲解】{explanation}"
    return body, {
        "title": title,
        "item_type": item_type,
        "category": category,
        "difficulty": difficulty,
        "tags": tags_text,
    }


def chunk_text(text: str, chunk_size: int = 400, overlap: int = 50) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text or "") if p.strip()]
    if not paragraphs:
        return []
    chunks: list[str] = []
    buffer = ""
    for paragraph in paragraphs:
        if len(buffer) + len(paragraph) + 1 <= chunk_size:
            buffer = (buffer + "\n" + paragraph).strip()
            continue
        if buffer:
            chunks.append(buffer)
        while len(paragraph) > chunk_size:
            chunks.append(paragraph[:chunk_size])
            paragraph = paragraph[chunk_size - overlap:]
        buffer = paragraph
    if buffer:
        chunks.append(buffer)
    result: list[str] = []
    previous = ""
    for chunk in chunks:
        result.append((previous[-overlap:] + "\n" + chunk).strip() if previous else chunk)
        previous = chunk
    return result


def tokenize(text: str) -> str:
    return " ".join(
        token.strip().lower()
        for token in jieba.cut_for_search(text or "")
        if token.strip() and not re.fullmatch(r"[\W_]+", token.strip())
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build local RAG knowledge base")
    parser.add_argument("--knowledge-dir", default=str(KNOWLEDGE_DIR))
    parser.add_argument("--db", default=str(DB_PATH))
    parser.add_argument("--chunk-size", type=int, default=400)
    parser.add_argument("--overlap", type=int, default=50)
    args = parser.parse_args()

    knowledge_dir = Path(args.knowledge_dir)
    db_path = Path(args.db)
    if not knowledge_dir.exists():
        print(f"[ERROR] knowledge directory not found: {knowledge_dir}")
        return 1

    files = sorted(
        p for p in knowledge_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in SUPPORTED
    )
    if not files:
        print(f"[WARN] no supported files in {knowledge_dir}")
        return 1

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    total_items = 0
    total_chunks = 0
    try:
        conn.executescript(
            """
            DROP TABLE IF EXISTS chunks_fts;
            DROP TABLE IF EXISTS chunks;
            CREATE TABLE chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                tokens TEXT NOT NULL,
                item_type TEXT,
                category TEXT,
                difficulty TEXT,
                tags TEXT
            );
            CREATE VIRTUAL TABLE chunks_fts USING fts5(tokens, tokenize='unicode61');
            """
        )
        for path in files:
            relative = path.relative_to(knowledge_dir).as_posix()
            file_items = 0
            file_chunks = 0
            for item in iter_items(path):
                file_items += 1
                body, meta = compose_item(item)
                for chunk in chunk_text(body, args.chunk_size, args.overlap):
                    tokens = tokenize(chunk)
                    cursor = conn.execute(
                        "INSERT INTO chunks(source, title, content, tokens, item_type, category, difficulty, tags) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            relative,
                            meta["title"],
                            chunk,
                            tokens,
                            meta["item_type"],
                            meta["category"],
                            meta["difficulty"],
                            meta["tags"],
                        ),
                    )
                    conn.execute(
                        "INSERT INTO chunks_fts(rowid, tokens) VALUES (?, ?)",
                        (cursor.lastrowid, tokens),
                    )
                    file_chunks += 1
            total_items += file_items
            total_chunks += file_chunks
            print(f"[OK] {relative}: {file_items} items, {file_chunks} chunks")
        conn.commit()
    finally:
        conn.close()

    print(f"[DONE] {len(files)} files -> {total_items} items -> {total_chunks} chunks")
    print(f"[DONE] database: {db_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())