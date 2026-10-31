
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_required_project_files_exist():
    required = [
        "app.py",
        "requirements.txt",
        "src",
        "templates",
        "data",
    ]

    for item in required:
        assert (ROOT / item).exists(), f"Missing: {item}"


def test_python_files_have_valid_syntax():
    python_files = list(ROOT.glob("src/**/*.py"))
    python_files.append(ROOT / "app.py")

    for file in python_files:
        source = file.read_text(encoding="utf-8")
        ast.parse(source, filename=str(file))


def test_required_api_routes_exist():
    source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert '"/health"' in source
    assert '"/generate-pitch"' in source
    assert '"/generate-ppt"' in source
