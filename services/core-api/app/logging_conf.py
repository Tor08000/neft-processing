
import json, logging, sys
from typing import Any, Mapping

class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # прокинем extras если были
        if hasattr(record, "extra") and isinstance(record.extra, dict):
            base.update(record.extra)
        # standard attrs (если есть)
        for attr in ("correlation_id", "user", "pathname", "lineno", "funcName"):
            if hasattr(record, attr):
                base[attr] = getattr(record, attr)
        return json.dumps(base, ensure_ascii=False)

def configure_logging():
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    # очистим хэндлеры которые поставил uvicorn по-умолчанию, поставим свой
    for h in list(root.handlers):
        root.removeHandler(h)
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(JsonFormatter())
    root.addHandler(h)
    # Подправим uvicorn/uvicorn.access чтобы не ломали формат:
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        lg.handlers = []
        lg.propagate = True
