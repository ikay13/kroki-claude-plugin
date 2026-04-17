"""Subprocess tests for scripts/validate-references.sh."""
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "validate-references.sh"


def run(*args):
    return subprocess.run([str(SCRIPT), *args], capture_output=True, text=True)


def test_usage_no_args():
    r = run()
    assert r.returncode != 0


def test_passes_on_valid_snippet(tmp_path):
    ref = tmp_path / "plantuml.md"
    ref.write_text(
        "# PlantUML\n\n```plantuml\n@startuml\nA -> B\n@enduml\n```\n"
    )
    r = run(str(ref))
    assert r.returncode == 0, r.stderr


def test_fails_on_broken_snippet(tmp_path):
    ref = tmp_path / "plantuml.md"
    ref.write_text(
        "# PlantUML\n\n```plantuml\nthis is not plantuml\n```\n"
    )
    r = run(str(ref))
    assert r.returncode != 0


def test_skips_non_renderable_codefences(tmp_path):
    ref = tmp_path / "plantuml.md"
    ref.write_text(
        "# PlantUML\n\n```bash\necho hi\n```\n\n"
        "```plantuml\n@startuml\nA -> B\n@enduml\n```\n"
    )
    r = run(str(ref))
    assert r.returncode == 0
