from __future__ import annotations

import hmac
import os
import sqlite3
from pathlib import Path

import yaml
from aiohttp import web

from core.utils.content_filter import check_user_input
from core.utils.conversation_store import conversation_store
from core.utils.runtime_state import runtime_state

SERVER_ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGE_DB = SERVER_ROOT / "data" / "knowledge.db"
SENSITIVE_WORDS = SERVER_ROOT / "config" / "sensitive_words.yaml"


class ParentConsoleHandler:
    def __init__(self, config: dict):
        self.config = config
        parent_config = config.get("parent_console", {})
        self.token_env = str(
            parent_config.get("token_env", "PARENT_CONSOLE_TOKEN")
        )

    def _authorized(self, request: web.Request) -> bool:
        expected = os.environ.get(self.token_env, "")
        if not expected:
            return True
        header = request.headers.get("Authorization", "")
        token = header[7:] if header.startswith("Bearer ") else ""
        return bool(token) and hmac.compare_digest(token, expected)

    def _unauthorized(self) -> web.Response:
        return web.json_response(
            {"error": "unauthorized", "message": "家长端访问令牌无效"},
            status=401,
        )

    def _knowledge_summary(self) -> dict:
        if not KNOWLEDGE_DB.exists():
            return {"available": False, "items": 0, "categories": []}
        try:
            conn = sqlite3.connect(f"file:{KNOWLEDGE_DB}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
            try:
                items = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
                categories = [
                    {
                        "name": row["category"] or "未分类",
                        "count": row["count"],
                    }
                    for row in conn.execute(
                        "SELECT category, COUNT(*) AS count FROM chunks "
                        "GROUP BY category ORDER BY count DESC"
                    )
                ]
                titles = [
                    row["title"]
                    for row in conn.execute(
                        "SELECT DISTINCT title FROM chunks ORDER BY title LIMIT 30"
                    )
                ]
            finally:
                conn.close()
            return {
                "available": True,
                "items": items,
                "categories": categories,
                "titles": titles,
            }
        except sqlite3.Error:
            return {"available": False, "items": 0, "categories": [], "titles": []}

    def _music_summary(self) -> dict:
        music_config = self.config.get("plugins", {}).get("play_music", {})
        music_dir = Path(music_config.get("music_dir", "./music/儿歌"))
        if not music_dir.is_absolute():
            music_dir = SERVER_ROOT / music_dir
        extensions = {".mp3", ".wav", ".p3"}
        items = []
        if music_dir.exists():
            items = sorted(
                path.stem
                for path in music_dir.iterdir()
                if path.is_file() and path.suffix.lower() in extensions
            )
        return {"count": len(items), "items": items, "path": str(music_dir)}

    def _filter_summary(self) -> dict:
        try:
            data = yaml.safe_load(SENSITIVE_WORDS.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            return {"enabled": False, "categories": 0, "rules": 0, "safe_reply": ""}
        categories = data.get("categories") or {}
        rules = 0
        for spec in categories.values():
            if isinstance(spec, dict):
                rules += len(spec.get("words", []) or [])
                rules += len(spec.get("patterns", []) or [])
        return {
            "enabled": bool(data.get("enabled", True)),
            "categories": len(categories),
            "rules": rules,
            "safe_reply": data.get("safe_reply", ""),
        }

    async def overview(self, request: web.Request) -> web.Response:
        if not self._authorized(request):
            return self._unauthorized()
        selected = self.config.get("selected_module", {})
        llm_name = selected.get("LLM", "")
        tts_name = selected.get("TTS", "")
        asr_name = selected.get("ASR", "")
        llm_config = self.config.get("LLM", {}).get(llm_name, {})
        runtime = runtime_state.snapshot()
        return web.json_response(
            {
                "server": {
                    "status": "online",
                    "version": "1.0.0",
                    **runtime,
                },
                "auth": {
                    "enabled": bool(os.environ.get(self.token_env, "")),
                    "token_env": self.token_env,
                },
                "modules": {
                    "llm": llm_name,
                    "model": llm_config.get("model_name", ""),
                    "asr": asr_name,
                    "tts": tts_name,
                    "intent": selected.get("Intent", ""),
                },
                "rag": {
                    "enabled": bool(self.config.get("rag", {}).get("enabled", False)),
                    **self._knowledge_summary(),
                },
                "music": self._music_summary(),
                "safety": self._filter_summary(),
            }
        )

    async def conversations(self, request: web.Request) -> web.Response:
        if not self._authorized(request):
            return self._unauthorized()
        session_id = request.query.get("session_id", "").strip() or None
        try:
            limit = int(request.query.get("limit", "30"))
        except ValueError:
            limit = 30
        result = conversation_store.dashboard(session_id=session_id, limit=limit)
        if session_id and result["selected"] is None:
            return web.json_response(
                {"error": "not_found", "message": "对话记录不存在"},
                status=404,
            )
        return web.json_response(result)

    async def check_content(self, request: web.Request) -> web.Response:
        if not self._authorized(request):
            return self._unauthorized()
        try:
            payload = await request.json()
        except Exception:
            payload = {}
        text = str(payload.get("text", "")).strip()[:2000]
        if not text:
            return web.json_response(
                {"error": "empty_text", "message": "请输入需要检测的文字"},
                status=400,
            )
        result = check_user_input(text)
        return web.json_response(
            {
                "blocked": result.blocked,
                "action": result.action,
                "category": result.category,
                "keyword": result.keyword,
                "text": result.text,
            }
        )
