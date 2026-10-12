"""Çalışma anında okunan veri klasörleri imaja kopyalanmalı (Dockerfile klasörleri tek tek COPY eder;
yeni bir klasör unutulursa yerel testler geçer ama canlı sunucu katalogsuz çöker)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNTIME_DATA_DIRS = ("core", "components", "auth", "themes", "runtime", "compositions")


def test_dockerfile_copies_runtime_data_dirs():
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    missing = [d for d in RUNTIME_DATA_DIRS if f"COPY {d} ./{d}" not in text]
    assert not missing, f"Dockerfile bu klasörleri kopyalamıyor: {missing}"
