import json
import threading
import time
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from app.core.config import settings

try:
    from pydantic import BaseModel
except Exception:  # pragma: no cover
    BaseModel = None  # type: ignore


class TraceLogger:
    def __init__(
        self,
        file_path: str = "logs/trace.jsonl",
        max_str_len: int = 4000,
        max_list_len: int = 50,
        max_dict_len: int = 200,
        max_depth: int = 5,
    ):
        self._file_path = Path(file_path)
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._max_str_len = max_str_len
        self._max_list_len = max_list_len
        self._max_dict_len = max_dict_len
        self._max_depth = max_depth

    def enabled(self) -> bool:
        return bool(settings.trace.enabled)

    def should_log_prompt(self) -> bool:
        """Check if prompts should be logged based on trace settings."""
        return self.enabled() and getattr(settings.trace, 'log_llm_prompt', False)

    def _should_log(self, level: str | None) -> bool:
        if not self.enabled():
            return False

        cfg_level = settings.trace.level
        if cfg_level == "debug":
            return True
        if cfg_level == "info":
            return level in {None, "info", "error"}
        if cfg_level == "error":
            return level == "error"
        return True

    def log_event(self, event: dict[str, Any]) -> None:
        level = event.get("level", "info")
        if not self._should_log(level):
            return
        payload = self._safe_obj(event, depth=0)
        if isinstance(payload, dict):
            payload.setdefault("ts", time.time())
        line = json.dumps(payload, ensure_ascii=False, default=str)
        with self._lock:
            with self._file_path.open("a", encoding="utf-8") as f:
                f.write(line)
                f.write("\n")

    def _safe_obj(self, obj: Any, depth: int) -> Any:
        if depth >= self._max_depth:
            return "<max_depth>"

        if obj is None or isinstance(obj, (bool, int, float)):
            return obj

        if isinstance(obj, str):
            if len(obj) > self._max_str_len:
                return obj[: self._max_str_len] + "...<truncated>"
            return obj

        if BaseModel is not None and isinstance(obj, BaseModel):
            try:
                return self._safe_obj(obj.model_dump(), depth + 1)
            except Exception:
                return self._safe_obj(str(obj), depth + 1)

        if is_dataclass(obj):
            try:
                return self._safe_obj(asdict(obj), depth + 1)
            except Exception:
                return self._safe_obj(str(obj), depth + 1)

        if isinstance(obj, dict):
            out: dict[str, Any] = {}
            for idx, (k, v) in enumerate(obj.items()):
                if idx >= self._max_dict_len:
                    out["<truncated>"] = f"{len(obj) - self._max_dict_len} more keys"
                    break
                key = str(k)
                lowered = key.lower()
                if lowered in {"dialogs", "history_dialog", "history_dialogs", "conversation", "messages", "current_conversation"}:
                    try:
                        out[key] = f"<list len={len(v)}>"
                    except Exception:
                        out[key] = "<list>"
                    continue
                out[key] = self._safe_obj(v, depth + 1)
            return out

        if isinstance(obj, (list, tuple, set)):
            seq = list(obj)
            trimmed = seq[: self._max_list_len]
            out = [self._safe_obj(v, depth + 1) for v in trimmed]
            if len(seq) > self._max_list_len:
                out.append(f"<truncated {len(seq) - self._max_list_len} more items>")
            return out

        try:
            return self._safe_obj(vars(obj), depth + 1)
        except Exception:
            return self._safe_obj(str(obj), depth + 1)


trace_logger = TraceLogger(file_path=settings.trace.file_path)
