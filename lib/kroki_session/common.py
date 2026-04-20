"""Shared utilities for kroki-session mode-dispatch modules.

Responsibilities:
- Parse/write project memory files (~/.claude/projects/-home-orin/memory/project_<snake>.md)
- Parse/write Obsidian session log files (~/Documents/Obsidian Vault/<Project>/sessions/*.md)
- Git state detection (detached HEAD, merge-in-progress, no-repo, no-git)
- Git diff detection (modified/new/deleted diagram sources)
- Git tag detection with semver filter
- Vault path resolution per obsidian-project-sync.md convention
- Atomic file writes
- Purpose extraction from diagram source first-comment lines
"""
from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Literal, TypedDict


class ProjectFolderNotFoundError(Exception):
    """Raised when vault folder for project cannot be resolved."""


class GitState(Enum):
    OK = "ok"
    DETACHED = "detached"
    MERGE = "merge"
    NO_REPO = "no-repo"
    NO_GIT = "no-git"


def vault_paths(project: str, override: Path | None = None) -> Path:
    """Resolve the Obsidian vault folder for a project.

    Convention: ~/Documents/Obsidian Vault/<project>/ (per obsidian-project-sync.md).
    Override: if provided and exists, returned verbatim (bypasses convention).

    Raises:
        ProjectFolderNotFoundError: if override does not exist, or if convention
            path does not exist. Error message names the bypass flag.
    """
    if override is not None:
        if not override.is_dir():
            raise ProjectFolderNotFoundError(
                f"--vault-path override {override} does not exist or is not a directory"
            )
        return override

    home = Path(os.environ.get("HOME", Path.home()))
    path = home / "Documents" / "Obsidian Vault" / project
    if not path.is_dir():
        raise ProjectFolderNotFoundError(
            f"Expected vault folder at {path} (per obsidian-project-sync.md naming rule). "
            f"Not found. Fix: rename the vault folder to match project name '{project}' exactly. "
            f"Bypass for this session: pass --vault-path /path/to/folder"
        )
    return path


def atomic_write(path: Path, content: str) -> None:
    """Atomic file write via tmpfile + rename. POSIX-only (uses os.rename semantics)."""
    tmp = path.with_suffix(path.suffix + ".kroki-tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


# Matches the comment-stripping behavior of scripts/update-index.sh extract_purpose():
# strips one leading comment token from: // # ' %% --
_COMMENT_RE = re.compile(r"^\s*(?://|#|'|%%|--)\s*(.*?)\s*$")


def extract_purpose(source_file: Path) -> str:
    """Return the first comment line of a diagram source file, truncated to 120 chars.

    Mirrors the bash implementation in scripts/update-index.sh. Recognizes comment tokens
    //, #, ', %% , and --. Returns '' if no leading comment.
    """
    try:
        with source_file.open("r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.rstrip("\n")
                if not line.strip():
                    continue  # skip blank lines
                m = _COMMENT_RE.match(line)
                if m:
                    return m.group(1)[:120]
                return ""  # first non-blank is not a comment
    except OSError:
        return ""
    return ""


_MEMORY_DIR_REL = Path(".claude/projects/-home-orin/memory")


def _memory_filename(project: str) -> str:
    """Convert project name to snake_case memory filename per memory-schema.md."""
    snake = re.sub(r"[-\s]+", "_", project.strip()).lower()
    snake = re.sub(r"[^a-z0-9_]", "", snake)
    return f"project_{snake}.md"


def _memory_path(project: str) -> Path:
    home = Path(os.environ.get("HOME", Path.home()))
    return home / _MEMORY_DIR_REL / _memory_filename(project)


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Split a markdown doc into (frontmatter_dict, body_text). Tolerant of malformed YAML."""
    if not text.startswith("---\n"):
        return {}, text

    # Find closing --- (must be on its own line)
    lines = text.split("\n")
    close_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            close_idx = i
            break

    if close_idx is None:
        # Malformed — no closing ---
        print("kroki-session: warning — memory frontmatter malformed (no closing ---)",
              file=__import__("sys").stderr)
        return {}, text

    # Simple YAML-ish parse (we only need scalar fields + flat list fields)
    frontmatter: dict = {}
    for line in lines[1:close_idx]:
        line = line.rstrip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^([a-zA-Z_][\w-]*)\s*:\s*(.*)$", line)
        if not m:
            continue
        key, raw_val = m.group(1), m.group(2).strip()
        if raw_val.startswith("[") and raw_val.endswith("]"):
            inner = raw_val[1:-1].strip()
            frontmatter[key] = [v.strip() for v in inner.split(",") if v.strip()] if inner else []
        else:
            # Strip surrounding quotes if present
            if (raw_val.startswith('"') and raw_val.endswith('"')) or (raw_val.startswith("'") and raw_val.endswith("'")):
                raw_val = raw_val[1:-1]
            frontmatter[key] = raw_val

    body = "\n".join(lines[close_idx + 1:])
    return frontmatter, body


def _parse_body_sections(body: str) -> dict:
    """Parse ## sections into a dict keyed by header, values as lists of lines."""
    sections: dict = {}
    current: str | None = None
    buf: list[str] = []
    for line in body.split("\n"):
        m = re.match(r"^##\s+([^\n]+)$", line)
        if m:
            if current is not None:
                sections[current] = "\n".join(buf).strip()
            current = m.group(1).strip()
            buf = []
        else:
            buf.append(line)
    if current is not None:
        sections[current] = "\n".join(buf).strip()
    return sections


def parse_memory(project: str) -> dict:
    """Parse project_<snake>.md into a dict with frontmatter fields + body-section contents.

    Fields returned (subset, all optional):
        project_name, status, profile, latest_session_log, obsidian_folder,
        touched_diagrams (list), current_status (str), next_steps (list), pointers (list)

    Returns empty dict if file missing. Returns partial dict on malformed frontmatter
    (prints warning to stderr).
    """
    path = _memory_path(project)
    if not path.exists():
        return {}

    text = path.read_text(encoding="utf-8")
    frontmatter, body = _parse_frontmatter(text)
    sections = _parse_body_sections(body)

    # Extract touched-diagrams and next-steps as lists (one item per bullet line)
    def _bullet_list(section_text: str) -> list[str]:
        out = []
        for line in section_text.split("\n"):
            m = re.match(r"^\s*[-*]\s+(.+?)\s*$", line)
            if m:
                out.append(m.group(1))
        return out

    result = dict(frontmatter)
    result["touched_diagrams"] = _bullet_list(sections.get("touched-diagrams", ""))
    result["next_steps"] = _bullet_list(sections.get("next-steps", ""))
    result["current_status"] = sections.get("current-status", "")
    result["pointers"] = _bullet_list(sections.get("pointers", ""))
    return result


def write_memory(project: str, data: dict) -> None:
    """Atomic write of memory file. Overwrites existing. Updates last_updated to today.

    Layout: frontmatter (from data dict scalar fields) + body sections
    (from touched_diagrams, next_steps, current_status, pointers).
    """
    import datetime as _dt
    path = _memory_path(project)
    path.parent.mkdir(parents=True, exist_ok=True)

    today = _dt.date.today().isoformat()
    data = dict(data)  # avoid mutating caller
    data["last_updated"] = today

    scalar_keys = [
        "name", "description", "type", "project_name", "profile", "status",
        "blocked_by", "obsidian_folder", "tracker", "latest_session_log",
        "last_updated", "originSessionId",
    ]

    out = ["---"]
    for k in scalar_keys:
        if k in data:
            v = data[k]
            if isinstance(v, list):
                out.append(f"{k}: [{', '.join(str(x) for x in v)}]")
            else:
                out.append(f"{k}: {v}")
    out.append("---")
    out.append("")

    if data.get("current_status"):
        out.append("## current-status")
        out.append("")
        out.append(data["current_status"])
        out.append("")

    if data.get("next_steps"):
        out.append("## next-steps")
        out.append("")
        for item in data["next_steps"]:
            out.append(f"- {item}")
        out.append("")

    if data.get("touched_diagrams"):
        out.append("## touched-diagrams")
        out.append("")
        for item in data["touched_diagrams"]:
            out.append(f"- {item}")
        out.append("")

    if data.get("pointers"):
        out.append("## pointers")
        out.append("")
        for item in data["pointers"]:
            out.append(f"- {item}")
        out.append("")

    atomic_write(path, "\n".join(out))
