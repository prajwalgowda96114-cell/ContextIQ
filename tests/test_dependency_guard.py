"""Fails if the retired google-generativeai SDK or 2.x/2.0 model IDs sneak back in."""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
CODE_DIRS = [
    ROOT / "backend" / "app",
    ROOT / "backend" / "eval",
    ROOT / "backend" / "scripts",
    ROOT / "eval",
    ROOT / "scripts",
    ROOT / "app",
]
REQ_FILES = [ROOT / "backend" / "requirements.txt", ROOT / "backend" / "requirements-dev.txt"]

BANNED_IMPORT = re.compile(r"^\s*(import|from)\s+google\.generativeai\b", re.M)
BANNED_PKG = re.compile(r"^\s*google-generativeai\b", re.M | re.I)
BANNED_MODEL = re.compile(r"gemini-(2\.5|2\.0)[-\w.]*")


def _py_files():
    for d in CODE_DIRS:
        if d.exists():
            yield from d.rglob("*.py")


def test_requirements_do_not_list_retired_sdk():
    for f in REQ_FILES:
        if f.exists():
            assert not BANNED_PKG.search(f.read_text()), f"{f.name} lists google-generativeai"


def test_requirements_include_unified_sdk_and_vector_search():
    text = (ROOT / "backend" / "requirements.txt").read_text()
    assert re.search(r"^google-genai\b", text, re.M)
    assert re.search(r"^google-cloud-vectorsearch\b", text, re.M)


def test_code_does_not_import_retired_sdk():
    for f in _py_files():
        assert not BANNED_IMPORT.search(f.read_text()), f"{f} imports google.generativeai"


def test_code_does_not_hardcode_retiring_models():
    for f in _py_files():
        if f.name == "test_dependency_guard.py":
            continue
        assert not BANNED_MODEL.search(f.read_text()), f"{f} references a retiring Gemini 2.x model"
