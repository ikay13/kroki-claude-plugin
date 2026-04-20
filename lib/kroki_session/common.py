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


def _run_git(*args: str, cwd: Path | None = None, check: bool = False) -> subprocess.CompletedProcess:
    """Helper: run a git command, capture stdout/stderr, return CompletedProcess."""
    return subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd else None,
        check=check,
    )


def git_state_check(cwd: Path | None = None) -> GitState:
    """Detect the current git state for mode=end preflight.

    Order of checks:
    1. git binary present (else NO_GIT)
    2. Inside a working tree (else NO_REPO)
    3. Merge in progress (.git/MERGE_HEAD exists) → MERGE
    4. Detached HEAD (git symbolic-ref HEAD fails) → DETACHED
    5. Otherwise → OK
    """
    try:
        v = _run_git("--version")
    except FileNotFoundError:
        return GitState.NO_GIT
    if v.returncode != 0:
        return GitState.NO_GIT

    work_tree = _run_git("rev-parse", "--is-inside-work-tree", cwd=cwd)
    if work_tree.returncode != 0 or work_tree.stdout.strip() != "true":
        return GitState.NO_REPO

    # Locate .git dir to check for MERGE_HEAD
    git_dir_result = _run_git("rev-parse", "--git-dir", cwd=cwd)
    if git_dir_result.returncode == 0:
        git_dir = Path(git_dir_result.stdout.strip())
        if not git_dir.is_absolute():
            git_dir = (cwd or Path.cwd()) / git_dir
        if (git_dir / "MERGE_HEAD").exists():
            return GitState.MERGE

    symref = _run_git("symbolic-ref", "--quiet", "HEAD", cwd=cwd)
    if symref.returncode != 0:
        return GitState.DETACHED

    return GitState.OK


def git_detect_changes(diagrams_dir: Path, cwd: Path | None = None) -> dict:
    """Return modified/new/deleted source files under diagrams_dir per git.

    Paths returned are absolute. Empty lists if none.
    """
    if cwd is None:
        # Use the repo root containing diagrams_dir
        rr = _run_git("rev-parse", "--show-toplevel", cwd=diagrams_dir)
        if rr.returncode != 0:
            return {"modified": [], "new": [], "deleted": []}
        cwd = Path(rr.stdout.strip())

    rel = diagrams_dir.resolve().relative_to(cwd.resolve())

    # Modified (tracked, changed in working tree)
    mod = _run_git("diff", "--name-only", "HEAD", "--", str(rel), cwd=cwd)
    modified_rel = [Path(p) for p in mod.stdout.splitlines() if p.strip()]

    # New (untracked)
    new = _run_git("ls-files", "--others", "--exclude-standard", str(rel), cwd=cwd)
    new_rel = [Path(p) for p in new.stdout.splitlines() if p.strip()]

    # Deleted (tracked, removed from working tree)
    deleted_output = _run_git("ls-files", "--deleted", str(rel), cwd=cwd)
    deleted_rel = [Path(p) for p in deleted_output.stdout.splitlines() if p.strip()]

    # git diff picks up deletes as well; filter them out of modified to avoid double-count
    deleted_set = set(deleted_rel)
    modified_rel = [p for p in modified_rel if p not in deleted_set]

    return {
        "modified": [cwd / p for p in modified_rel],
        "new": [cwd / p for p in new_rel],
        "deleted": [cwd / p for p in deleted_rel],
    }


def git_detect_tags_on_head(pattern: str = "v*", cwd: Path | None = None) -> list[str]:
    """Return tags pointing at HEAD matching the glob pattern.

    Default pattern 'v*' filters for semver-style release tags.
    """
    result = _run_git("tag", "--points-at", "HEAD", "--list", pattern, cwd=cwd)
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def resolve_session_log(project: str, which: Literal["latest", "previous"] = "latest") -> Path | None:
    """Find a session log.

    Primary path: read memory's latest_session_log frontmatter field → resolve to absolute path.
    Fallback: glob <vault>/sessions/YYYY-MM-DD-<project>-session-NN.md, sort by NN.

    which="latest" → highest NN. which="previous" → second-highest (None if only one exists).
    Returns None if no session log found.
    """
    # Try memory first
    memory = parse_memory(project)
    latest_rel = memory.get("latest_session_log")

    try:
        vault_dir = vault_paths(project)
    except ProjectFolderNotFoundError:
        return None

    sessions_dir = vault_dir / "sessions"

    if which == "latest" and latest_rel:
        # memory.latest_session_log is a path relative to the vault project folder
        candidate = vault_dir / latest_rel
        if candidate.is_file():
            return candidate

    # Fallback: glob + NN sort
    if not sessions_dir.is_dir():
        return None
    pattern = re.compile(rf"^\d{{4}}-\d{{2}}-\d{{2}}-{re.escape(project)}-session-(\d+)\.md$")
    logs_with_nn: list[tuple[int, Path]] = []
    for p in sessions_dir.iterdir():
        m = pattern.match(p.name)
        if m:
            logs_with_nn.append((int(m.group(1)), p))
    if not logs_with_nn:
        return None
    logs_with_nn.sort(key=lambda t: t[0])

    if which == "latest":
        return logs_with_nn[-1][1]
    elif which == "previous":
        if len(logs_with_nn) < 2:
            return None
        return logs_with_nn[-2][1]
    else:
        return None


# Match basenames in `<div class="kroki-dual">...![[<basename>.light.svg]]...![[<basename>.dark.svg]]...</div>`
_DUAL_EMBED_RE = re.compile(
    r'<div\s+class="kroki-dual">.*?!\[\[(?P<basename>[^\]|.]+)\.light\.svg\]\].*?</div>',
    re.DOTALL,
)


def parse_session_log(path: Path) -> dict:
    """Parse a session log into frontmatter + diagram basenames + section raw texts.

    Returns:
        {
          "frontmatter": dict (may be {} on malformed),
          "diagrams": list[str] of basenames found in ## diagrams section embeds,
          "sections": dict of section-name → raw content,
        }
    """
    if not path.exists():
        return {"frontmatter": {}, "diagrams": [], "sections": {}}

    text = path.read_text(encoding="utf-8")
    frontmatter, body = _parse_frontmatter(text)
    sections = _parse_body_sections(body)

    diagrams_section = sections.get("diagrams", "")
    basenames: list[str] = []
    for m in _DUAL_EMBED_RE.finditer(diagrams_section):
        basenames.append(m.group("basename"))

    return {"frontmatter": frontmatter, "diagrams": basenames, "sections": sections}


def write_session_log_section(path: Path, section_header: str, content: str) -> None:
    """Replace-or-append the named ## section idempotently. Atomic.

    Algorithm per spec §4.1:
    - Read file; split into lines.
    - Find all occurrences of section_header at line-start.
    - Delete each from its header line through the line before the next "## " (or EOF).
    - Insert one new "{section_header}\n\n{content_stripped}\n" at position of first original occurrence,
      or at EOF if none existed.
    - Atomic write.
    """
    if not path.exists():
        # Defensive: create with just the new section
        atomic_write(path, f"{section_header}\n\n{content.rstrip()}\n")
        return

    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")

    header_norm = section_header.strip()
    # Find all section boundaries: indices where a line starts "## " (level-2 heading)
    occurrences: list[int] = []  # indices of matching section headers
    next_h2: list[int] = []      # for each occurrence, the end index (start of next ## or len(lines))

    for i, line in enumerate(lines):
        if line.strip() == header_norm:
            occurrences.append(i)

    # For each occurrence, find the next "## " heading
    for start in occurrences:
        end = len(lines)
        for j in range(start + 1, len(lines)):
            if lines[j].startswith("## "):
                end = j
                break
        next_h2.append(end)

    if occurrences:
        # Delete all occurrences from highest index down
        insert_at = occurrences[0]
        for start, end in sorted(zip(occurrences, next_h2), reverse=True):
            del lines[start:end]
        # Remove trailing blank lines left behind right before insert_at
        while insert_at > 0 and lines[insert_at - 1] == "":
            lines.pop(insert_at - 1)
            insert_at -= 1
        # Prepare insertion
        block = [section_header, "", content.rstrip(), ""]
        # Ensure one blank line separator before the inserted block if previous line exists and isn't blank
        if insert_at > 0 and lines[insert_at - 1] != "":
            block.insert(0, "")
        for k, new_line in enumerate(block):
            lines.insert(insert_at + k, new_line)
    else:
        # Append at end
        if lines and lines[-1] != "":
            lines.append("")
        lines.append(section_header)
        lines.append("")
        lines.append(content.rstrip())
        lines.append("")

    atomic_write(path, "\n".join(lines))


class ReferenceEntry(TypedDict):
    basename: str
    purpose: str
    last_updated: str


# Matches INDEX.md row: | [[basename.svg|Title]] | Purpose | YYYY-MM-DD | source.ext |
_INDEX_ROW_RE = re.compile(
    r"^\|\s*\[\[(?P<basename>[^.|\]]+)\.svg\|[^\]]*\]\]\s*\|"
    r"\s*(?P<purpose>[^|]+?)\s*\|"
    r"\s*(?P<date>\d{4}-\d{2}-\d{2})\s*\|"
)


def parse_index_summary(path: Path) -> list[ReferenceEntry]:
    """Parse diagrams/INDEX.md table rows into ReferenceEntry list.

    Empty list if file absent or unparseable.
    """
    if not path.exists():
        return []
    entries: list[ReferenceEntry] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = _INDEX_ROW_RE.match(line)
        if m:
            entries.append({
                "basename": m.group("basename"),
                "purpose": m.group("purpose").strip(),
                "last_updated": m.group("date"),
            })
    return entries
