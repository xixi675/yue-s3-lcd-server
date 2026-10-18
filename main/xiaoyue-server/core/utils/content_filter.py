from __future__ import annotations

import logging
import re
import threading
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger("content_filter")

_SERVER_ROOT = Path(__file__).resolve().parents[2]
_WORD_FILE = _SERVER_ROOT / "config" / "sensitive_words.yaml"
_DEFAULT_REPLY = "这个话题我还不适合聊，我们换个话题吧。"
_PUNCT_RE = re.compile(r"[\s\W_]+", re.UNICODE)


@dataclass(frozen=True)
class FilterResult:
    blocked: bool
    text: str
    category: str = ""
    keyword: str = ""
    action: str = "allow"


class ContentFilter:
    def __init__(self, path: Path = _WORD_FILE):
        self._path = path
        self._lock = threading.RLock()
        self._mtime = 0.0
        self._enabled = True
        self._safe_reply = _DEFAULT_REPLY
        self._categories: dict[str, dict[str, Any]] = {}
        self._load(force=True)

    def _load(self, force: bool = False) -> None:
        with self._lock:
            try:
                mtime = self._path.stat().st_mtime
            except FileNotFoundError:
                self._enabled = False
                return
            if not force and mtime == self._mtime:
                return
            with self._path.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            self._enabled = bool(data.get("enabled", True))
            self._safe_reply = str(data.get("safe_reply") or _DEFAULT_REPLY)
            self._categories = data.get("categories") or {}
            self._mtime = mtime

    @staticmethod
    def _normalize(text: str) -> str:
        text = unicodedata.normalize("NFKC", text or "").casefold()
        return _PUNCT_RE.sub("", text)

    def check(self, text: str, scene: str = "output") -> FilterResult:
        self._load()
        if not self._enabled or not text:
            return FilterResult(False, text or "")
        raw = text
        normalized = self._normalize(raw)

        for category, spec in self._categories.items():
            if not isinstance(spec, dict):
                continue
            action = str(spec.get("action", "audit")).lower()
            for allow in spec.get("allow_words", []) or []:
                allow_norm = self._normalize(str(allow))
                if allow_norm:
                    normalized = normalized.replace(allow_norm, "")

            hit = ""
            for word in spec.get("words", []) or []:
                word_norm = self._normalize(str(word))
                if word_norm and word_norm in normalized:
                    hit = str(word)
                    break
            if not hit:
                for pattern in spec.get("patterns", []) or []:
                    try:
                        if re.search(str(pattern), raw, re.IGNORECASE):
                            hit = str(pattern)
                            break
                    except re.error:
                        logger.warning("Invalid content filter regex: %s", pattern)
            if not hit:
                continue

            logger.warning(
                "Content filter hit: scene=%s category=%s keyword=%s action=%s",
                scene, category, hit, action,
            )
            if action == "audit":
                continue
            if action == "replace":
                replaced = raw
                plain_hit = not any(ch in str(hit) for ch in "[]()\\d.*+?$^|{}")
                if plain_hit:
                    replaced = re.sub(re.escape(hit), "***", raw, flags=re.IGNORECASE)
                if replaced == raw:
                    replaced = self._safe_reply
                return FilterResult(True, replaced, category, hit, action)
            return FilterResult(True, self._safe_reply, category, hit, action)

        return FilterResult(False, raw)


_FILTER = ContentFilter()


def check_user_input(text: str) -> FilterResult:
    return _FILTER.check(text, scene="user")


def check_output(text: str) -> FilterResult:
    return _FILTER.check(text, scene="output")