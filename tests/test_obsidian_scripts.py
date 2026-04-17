"""Tests for kroki-obsidian bash scripts (Plan 3).

Each script is invoked via subprocess in an isolated ``tmp_path`` so tests
never touch the user's real vault or repo. All fixtures are inline.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
STYLES = REPO_ROOT / "styles"


def run_script(script_name: str, *args: str) -> subprocess.CompletedProcess:
    cmd = [str(SCRIPTS / script_name), *args]
    return subprocess.run(cmd, capture_output=True, text=True)


class TestEnsureSymlink:
    def test_creates_symlink_when_target_missing(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        (repo / "diagrams").mkdir(parents=True)
        vault_project = tmp_path / "vault" / "MyProject"
        vault_project.mkdir(parents=True)

        result = run_script("ensure-symlink.sh", str(repo), str(vault_project))

        assert result.returncode == 0, result.stderr
        target = vault_project / "diagrams"
        assert target.is_symlink()
        assert target.resolve() == (repo / "diagrams").resolve()

    def test_idempotent_when_symlink_already_correct(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        (repo / "diagrams").mkdir(parents=True)
        vault_project = tmp_path / "vault" / "MyProject"
        vault_project.mkdir(parents=True)
        (vault_project / "diagrams").symlink_to(repo / "diagrams")

        result = run_script("ensure-symlink.sh", str(repo), str(vault_project))

        assert result.returncode == 0, result.stderr
        assert (vault_project / "diagrams").is_symlink()

    def test_errors_when_symlink_points_to_wrong_target(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        (repo / "diagrams").mkdir(parents=True)
        other = tmp_path / "other"
        (other / "diagrams").mkdir(parents=True)
        vault_project = tmp_path / "vault" / "MyProject"
        vault_project.mkdir(parents=True)
        (vault_project / "diagrams").symlink_to(other / "diagrams")

        result = run_script("ensure-symlink.sh", str(repo), str(vault_project))

        assert result.returncode == 1
        assert "wrong target" in result.stderr

    def test_errors_when_target_exists_as_real_dir(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        (repo / "diagrams").mkdir(parents=True)
        vault_project = tmp_path / "vault" / "MyProject"
        (vault_project / "diagrams").mkdir(parents=True)

        result = run_script("ensure-symlink.sh", str(repo), str(vault_project))

        assert result.returncode == 1
        assert "not a symlink" in result.stderr

    def test_usage_error_on_missing_args(self, tmp_path: Path) -> None:
        result = run_script("ensure-symlink.sh")
        assert result.returncode == 3


class TestUpdateIndex:
    def test_writes_index_with_single_entry(self, tmp_path: Path) -> None:
        diagrams = tmp_path / "diagrams"
        diagrams.mkdir()
        (diagrams / "arch-demo-foo.puml").write_text(
            "' Test architecture diagram\n@startuml\nA -> B\n@enduml\n"
        )
        (diagrams / "arch-demo-foo.light.svg").write_text("<svg></svg>")
        (diagrams / "arch-demo-foo.dark.svg").write_text("<svg></svg>")

        result = run_script("update-index.sh", str(diagrams))

        assert result.returncode == 0, result.stderr
        index = diagrams / "INDEX.md"
        assert index.exists()
        content = index.read_text()
        assert "# Diagram Index" in content
        assert "## arch" in content
        assert "arch-demo-foo" in content
        assert "Test architecture diagram" in content
        assert "arch-demo-foo.puml" in content

    def test_groups_by_prefix(self, tmp_path: Path) -> None:
        diagrams = tmp_path / "diagrams"
        diagrams.mkdir()
        for basename, comment_prefix, ext in [
            ("arch-demo-one", "'", "puml"),
            ("arch-demo-two", "'", "puml"),
            ("seq-demo-three", "%%", "mmd"),
        ]:
            (diagrams / f"{basename}.{ext}").write_text(
                f"{comment_prefix} {basename} purpose\n"
            )
            (diagrams / f"{basename}.light.svg").write_text("<svg></svg>")
            (diagrams / f"{basename}.dark.svg").write_text("<svg></svg>")

        result = run_script("update-index.sh", str(diagrams))
        assert result.returncode == 0

        content = (diagrams / "INDEX.md").read_text()
        assert "## arch" in content
        assert "## seq" in content
        # arch group appears before seq group (alphabetical)
        assert content.index("## arch") < content.index("## seq")

    def test_handles_missing_source_file(self, tmp_path: Path) -> None:
        diagrams = tmp_path / "diagrams"
        diagrams.mkdir()
        (diagrams / "arch-orphan.light.svg").write_text("<svg></svg>")
        (diagrams / "arch-orphan.dark.svg").write_text("<svg></svg>")

        result = run_script("update-index.sh", str(diagrams))
        assert result.returncode == 0

        content = (diagrams / "INDEX.md").read_text()
        assert "arch-orphan" in content
        assert "(none)" in content

    def test_handles_empty_dir(self, tmp_path: Path) -> None:
        diagrams = tmp_path / "diagrams"
        diagrams.mkdir()

        result = run_script("update-index.sh", str(diagrams))
        assert result.returncode == 0

        index = diagrams / "INDEX.md"
        assert index.exists()
        assert "No diagrams found" in index.read_text()

    def test_error_on_missing_dir(self, tmp_path: Path) -> None:
        result = run_script("update-index.sh", str(tmp_path / "does-not-exist"))
        assert result.returncode != 0

    def test_detects_mermaid_percent_comment(self, tmp_path: Path) -> None:
        diagrams = tmp_path / "diagrams"
        diagrams.mkdir()
        (diagrams / "seq-flow-demo.mmd").write_text(
            "%% Mermaid flow purpose line\nsequenceDiagram\nA->>B: hi\n"
        )
        (diagrams / "seq-flow-demo.light.svg").write_text("<svg></svg>")
        (diagrams / "seq-flow-demo.dark.svg").write_text("<svg></svg>")

        result = run_script("update-index.sh", str(diagrams))
        assert result.returncode == 0

        content = (diagrams / "INDEX.md").read_text()
        assert "Mermaid flow purpose line" in content


class TestEmbedInMd:
    def test_appends_section_and_block_when_section_absent(self, tmp_path: Path) -> None:
        target = tmp_path / "note.md"
        target.write_text("# Hello\n\nBody text.\n")

        result = run_script(
            "embed-in-md.sh",
            str(target),
            "arch-demo",
            "--caption",
            "Test caption",
        )

        assert result.returncode == 0, result.stderr
        content = target.read_text()
        assert "## Diagrams" in content
        assert '<div class="kroki-dual">' in content
        assert "[[arch-demo.light.svg]]" in content
        assert "[[arch-demo.dark.svg]]" in content
        assert "</div>" in content
        assert "*Figure -- Test caption*" in content

    def test_omits_caption_when_not_provided(self, tmp_path: Path) -> None:
        target = tmp_path / "note.md"
        target.write_text("# Hello\n")

        result = run_script("embed-in-md.sh", str(target), "arch-demo")

        assert result.returncode == 0, result.stderr
        content = target.read_text()
        assert "[[arch-demo.light.svg]]" in content
        assert "Figure --" not in content

    def test_idempotent_on_repeat_call(self, tmp_path: Path) -> None:
        target = tmp_path / "note.md"
        target.write_text("# Hello\n")

        run_script("embed-in-md.sh", str(target), "arch-demo")
        run_script("embed-in-md.sh", str(target), "arch-demo")

        content = target.read_text()
        assert content.count("[[arch-demo.light.svg]]") == 1

    def test_inserts_under_existing_section(self, tmp_path: Path) -> None:
        target = tmp_path / "note.md"
        target.write_text(
            "# Session Log\n\n"
            "## Insights\n\nFoo.\n\n"
            "## Diagrams\n\n"
            "## Next Steps\n\nDo X.\n"
        )

        result = run_script("embed-in-md.sh", str(target), "arch-demo")
        assert result.returncode == 0

        content = target.read_text()
        i_diag = content.index("## Diagrams")
        i_next = content.index("## Next Steps")
        assert i_diag < content.index("[[arch-demo.light.svg]]") < i_next

    def test_respects_custom_section(self, tmp_path: Path) -> None:
        target = tmp_path / "note.md"
        target.write_text("# Hello\n\n## Architecture\n\nProse.\n")

        result = run_script(
            "embed-in-md.sh",
            str(target),
            "arch-demo",
            "--section",
            "## Architecture",
        )
        assert result.returncode == 0

        content = target.read_text()
        i_arch = content.index("## Architecture")
        i_link = content.index("[[arch-demo.light.svg]]")
        assert i_arch < i_link

    def test_usage_error_on_missing_args(self, tmp_path: Path) -> None:
        result = run_script("embed-in-md.sh")
        assert result.returncode == 3

    def test_error_when_target_missing(self, tmp_path: Path) -> None:
        result = run_script(
            "embed-in-md.sh", str(tmp_path / "nope.md"), "arch-demo"
        )
        assert result.returncode == 3


class TestInstallVaultTheme:
    def test_copies_css_into_snippets_dir(self, tmp_path: Path) -> None:
        vault = tmp_path / "Vault"
        vault.mkdir()

        result = run_script("install-vault-theme.sh", str(vault))

        assert result.returncode == 0, result.stderr
        target = vault / ".obsidian" / "snippets" / "kroki-theme.css"
        assert target.exists()
        content = target.read_text()
        assert ".kroki-dual" in content
        assert "display: none" in content

    def test_creates_snippets_dir_if_absent(self, tmp_path: Path) -> None:
        vault = tmp_path / "Vault"
        vault.mkdir()

        assert not (vault / ".obsidian").exists()

        result = run_script("install-vault-theme.sh", str(vault))
        assert result.returncode == 0, result.stderr
        assert (vault / ".obsidian" / "snippets").is_dir()

    def test_idempotent_when_content_matches(self, tmp_path: Path) -> None:
        vault = tmp_path / "Vault"
        vault.mkdir()

        first = run_script("install-vault-theme.sh", str(vault))
        assert first.returncode == 0

        second = run_script("install-vault-theme.sh", str(vault))
        assert second.returncode == 0
        assert "already up-to-date" in second.stdout

    def test_overwrites_stale_css(self, tmp_path: Path) -> None:
        vault = tmp_path / "Vault"
        snippets = vault / ".obsidian" / "snippets"
        snippets.mkdir(parents=True)
        (snippets / "kroki-theme.css").write_text("/* stale */\n")

        result = run_script("install-vault-theme.sh", str(vault))

        assert result.returncode == 0
        content = (snippets / "kroki-theme.css").read_text()
        assert ".kroki-dual" in content
        assert "stale" not in content

    def test_error_when_vault_missing(self, tmp_path: Path) -> None:
        result = run_script("install-vault-theme.sh", str(tmp_path / "nope"))
        assert result.returncode == 1
