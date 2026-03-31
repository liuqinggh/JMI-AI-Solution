from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException


class SkillLoader:
    def __init__(self, root: Path | None = None):
        self.root = root or Path.cwd()

    def load(self, skill_name: str) -> str:
        path = self.root / ".claude" / "skills" / skill_name / "SKILL.md"
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")
        return path.read_text(encoding="utf-8")
