"""Research log — every operation recorded (§27)."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone


@dataclass
class LogEntry:
    time: str
    action: str
    source: str
    result: str
    error: str = ""
    hash: str = ""
    version: str = ""


@dataclass
class ResearchLog:
    entries: list[LogEntry] = field(default_factory=list)

    def log(self, action: str, source: str, result: str,
            error: str = "", hash: str = "", version: str = "") -> LogEntry:
        entry = LogEntry(
            time=datetime.now(timezone.utc).strftime("%H:%M:%S"),
            action=action, source=source, result=result,
            error=error, hash=hash, version=version,
        )
        self.entries.append(entry)
        return entry

    def to_json(self) -> str:
        return json.dumps([asdict(e) for e in self.entries], indent=2)

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(self.to_json())

    def render_text(self) -> str:
        lines: list[str] = []
        for e in self.entries:
            lines.append(f"[{e.time}]\n{e.action}\n{e.source}\n{e.result}")
            if e.error:
                lines.append(f"ERROR: {e.error}")
        return "\n\n".join(lines)
