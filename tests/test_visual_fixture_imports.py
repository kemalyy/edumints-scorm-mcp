"""Görsel fixture üreteci sunucuyu REPODAN import etmeli. CI `pip install -e .` yapar ve
pyproject `server.py`'yi force-include ile site-packages'a KOPYALAR; o kopyanın yanında themes/
olmadığından tema yüklemesi sessizce varsayılana düşüyordu (bütün tema fixture'ları aynı görünür)."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_generator_imports_server_from_repo_root():
    code = ("import runpy; runpy.run_path('tests/visual/generate_fixtures.py', run_name='probe'); "
            "import server; print(server.__file__)")
    out = subprocess.run([sys.executable, "-I", "-c", code], cwd=ROOT, capture_output=True,
                         text=True, timeout=120)
    assert out.returncode == 0, out.stderr[-2000:]
    assert Path(out.stdout.strip().splitlines()[-1]).resolve() == (ROOT / "server.py").resolve()


def test_generator_theme_variants_really_use_the_preset():
    code = ("import runpy; g = runpy.run_path('tests/visual/generate_fixtures.py', run_name='p'); "
            "s = {'type': 'title_slide', 'title': 'x'}; "
            "html = g['render_fixture']('t', s, [], 'corporate/brand-academy', 'light'); "
            "import server; print(server._load_theme('corporate/brand-academy').color.primary in html)")
    out = subprocess.run([sys.executable, "-I", "-c", code], cwd=ROOT, capture_output=True,
                         text=True, timeout=120)
    assert out.returncode == 0, out.stderr[-2000:]
    assert out.stdout.strip().splitlines()[-1] == "True"
