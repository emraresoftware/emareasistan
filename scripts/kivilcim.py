#!/usr/bin/env python3
"""
🔥 Kıvılcım — Copilot'un AI asistanı için otomasyon script'i.

Bu script KIVILCIM.md'deki görevleri otomatik yapar:
  - Kullanılmayan import'ları bulur
  - TODO/FIXME tarar
  - Docstring eksiklerini listeler
  - API endpoint'leri çıkarır
  - Hardcoded secret tarar
  - Auth kontrolü eksik endpoint'leri bulur
  - vb.

Kullanım:
  python scripts/kivilcim.py                    # Tüm taramaları çalıştır
  python scripts/kivilcim.py --task imports     # Sadece import taraması
  python scripts/kivilcim.py --task todos       # Sadece TODO/FIXME
  python scripts/kivilcim.py --task endpoints   # API endpoint listesi
  python scripts/kivilcim.py --task secrets     # Hardcoded secret tarama
  python scripts/kivilcim.py --task env         # Env değişkenleri kataloğu
  python scripts/kivilcim.py --task docstrings  # Docstring eksikleri
"""
import os
import re
import ast
import sys
import argparse
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
REPORT_FILE = ROOT / "KIVILCIM_RAPOR.md"

PY_DIRS = ["admin", "config", "integrations", "middleware", "models", "services", "scripts", "scraper"]
EXCLUDE_DIRS = {"__pycache__", ".venv", "venv", "node_modules", ".git", "whatsapp-bridge"}


def find_py_files():
    """Proje içindeki tüm .py dosyalarını bul."""
    files = []
    # root level
    for f in ROOT.glob("*.py"):
        files.append(f)
    for d in PY_DIRS:
        dp = ROOT / d
        if dp.exists():
            for f in dp.rglob("*.py"):
                if not any(ex in str(f) for ex in EXCLUDE_DIRS):
                    files.append(f)
    return sorted(set(files))


# ── Görev 1: TODO/FIXME Tarama ─────────────────────────────
def scan_todos():
    """Koddaki TODO, FIXME, HACK, XXX yorumlarını bul."""
    results = []
    pattern = re.compile(r"#\s*(TODO|FIXME|HACK|XXX|WARN)\b[:\s]*(.*)", re.IGNORECASE)
    for f in find_py_files():
        try:
            lines = f.read_text(errors="ignore").splitlines()
            for i, line in enumerate(lines, 1):
                m = pattern.search(line)
                if m:
                    rel = f.relative_to(ROOT)
                    results.append((str(rel), i, m.group(1).upper(), m.group(2).strip()))
        except Exception:
            pass
    return results


# ── Görev 2: Hardcoded Secret Tarama ───────────────────────
def scan_secrets():
    """Kodda hardcoded password, key, token, secret ara."""
    results = []
    patterns = [
        re.compile(r"""(?:password|passwd|pwd|secret|token|api_key|apikey)\s*=\s*["']([^"']{4,})["']""", re.I),
        re.compile(r"""(?:Bearer|Basic)\s+[A-Za-z0-9+/=]{20,}""", re.I),
        re.compile(r"""sk[-_](?:live|test)_[A-Za-z0-9]{20,}"""),  # Stripe keys
        re.compile(r"""AIza[A-Za-z0-9_-]{35}"""),  # Google API key
    ]
    for f in find_py_files():
        try:
            content = f.read_text(errors="ignore")
            for i, line in enumerate(content.splitlines(), 1):
                # .env dosyaları ve config örnekleri hariç
                if "example" in str(f).lower() or ".env" in str(f):
                    continue
                for pat in patterns:
                    m = pat.search(line)
                    if m:
                        # Env referansları hariç
                        if "os.getenv" in line or "os.environ" in line or "settings." in line:
                            continue
                        if "placeholder" in line.lower() or "change-me" in line.lower() or "xxx" in line.lower():
                            continue
                        rel = f.relative_to(ROOT)
                        val = m.group(0)[:40] + "..." if len(m.group(0)) > 40 else m.group(0)
                        results.append((str(rel), i, val))
        except Exception:
            pass
    return results


# ── Görev 3: API Endpoint Listesi ──────────────────────────
def scan_endpoints():
    """FastAPI route dekoratörlerinden endpoint listesi çıkar."""
    results = []
    pattern = re.compile(r"""@\w+\.(get|post|put|delete|patch)\(\s*["']([^"']+)["']""", re.I)
    for f in find_py_files():
        try:
            content = f.read_text(errors="ignore")
            for i, line in enumerate(content.splitlines(), 1):
                m = pattern.search(line)
                if m:
                    method = m.group(1).upper()
                    path = m.group(2)
                    # Sonraki satırda fonksiyon adını bul
                    lines = content.splitlines()
                    func_name = ""
                    for j in range(i, min(i + 5, len(lines))):
                        fm = re.match(r"\s*(?:async\s+)?def\s+(\w+)", lines[j])
                        if fm:
                            func_name = fm.group(1)
                            break
                    rel = f.relative_to(ROOT)
                    results.append((method, path, func_name, str(rel)))
        except Exception:
            pass
    # Sırala: method + path
    results.sort(key=lambda x: (x[1], x[0]))
    return results


# ── Görev 4: Env Değişkenleri ──────────────────────────────
def scan_env_vars():
    """Koddaki os.getenv, os.environ ve settings.* kullanımlarını tara."""
    results = set()
    getenv_pat = re.compile(r"""os\.(?:getenv|environ\.get)\(\s*["']([^"']+)["']""")
    environ_pat = re.compile(r"""os\.environ\[["']([^"']+)["']\]""")
    for f in find_py_files():
        try:
            content = f.read_text(errors="ignore")
            for m in getenv_pat.finditer(content):
                results.add(m.group(1))
            for m in environ_pat.finditer(content):
                results.add(m.group(1))
        except Exception:
            pass
    return sorted(results)


# ── Görev 5: Docstring Eksikleri ───────────────────────────
def scan_docstrings():
    """Fonksiyon ve sınıflarda docstring olmayanları listele."""
    results = []
    for f in find_py_files():
        try:
            tree = ast.parse(f.read_text(errors="ignore"))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    # Özel/dahili fonksiyonları atla
                    if node.name.startswith("_") and not node.name.startswith("__"):
                        continue
                    docstring = ast.get_docstring(node)
                    if not docstring:
                        rel = f.relative_to(ROOT)
                        kind = "class" if isinstance(node, ast.ClassDef) else "def"
                        results.append((str(rel), node.lineno, kind, node.name))
        except (SyntaxError, Exception):
            pass
    return results


# ── Görev 6: Auth Kontrolü Eksik Endpoint'ler ─────────────
def scan_unprotected_endpoints():
    """check_admin veya auth kontrolü olmayan admin endpoint'lerini bul."""
    results = []
    route_pat = re.compile(r"""@\w+\.(get|post|put|delete|patch)\(\s*["'](/admin[^"']*)["']""", re.I)
    for f in find_py_files():
        try:
            content = f.read_text(errors="ignore")
            lines = content.splitlines()
            for i, line in enumerate(lines):
                m = route_pat.search(line)
                if m:
                    path = m.group(2)
                    # Sonraki 10 satırda check_admin veya auth kontrol ara
                    block = "\n".join(lines[i:i+15])
                    has_auth = any(kw in block for kw in [
                        "check_admin", "check_super", "is_super_admin",
                        "session", "Depends", "get_current_user",
                        "partner_admin", "HTTPException(401",
                    ])
                    if not has_auth:
                        rel = f.relative_to(ROOT)
                        results.append((m.group(1).upper(), path, str(rel), i + 1))
        except Exception:
            pass
    return results


# ── Rapor Oluştur ──────────────────────────────────────────
def generate_report(tasks=None):
    """Tüm tarama sonuçlarını KIVILCIM_RAPOR.md'ye yaz."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    sections = []
    sections.append(f"# 🔥 Kıvılcım Raporu\n\n> Oluşturulma: {now}\n")

    run_all = tasks is None or "all" in tasks

    # TODO/FIXME
    if run_all or "todos" in tasks:
        todos = scan_todos()
        sections.append(f"## 📝 TODO / FIXME ({len(todos)} adet)\n")
        if todos:
            sections.append("| Dosya | Satır | Tür | Not |")
            sections.append("|-------|-------|-----|-----|")
            for f, line, kind, note in todos:
                sections.append(f"| `{f}` | {line} | {kind} | {note} |")
        else:
            sections.append("Bulunamadı ✅")
        sections.append("")

    # Secrets
    if run_all or "secrets" in tasks:
        secrets = scan_secrets()
        sections.append(f"## 🔐 Hardcoded Secret Şüphelileri ({len(secrets)} adet)\n")
        if secrets:
            sections.append("| Dosya | Satır | Değer (kısaltılmış) |")
            sections.append("|-------|-------|---------------------|")
            for f, line, val in secrets:
                sections.append(f"| `{f}` | {line} | `{val}` |")
        else:
            sections.append("Bulunamadı ✅")
        sections.append("")

    # Endpoints
    if run_all or "endpoints" in tasks:
        endpoints = scan_endpoints()
        sections.append(f"## 🌐 API Endpoint'leri ({len(endpoints)} adet)\n")
        if endpoints:
            sections.append("| Method | Path | Fonksiyon | Dosya |")
            sections.append("|--------|------|-----------|-------|")
            for method, path, func, f in endpoints:
                sections.append(f"| {method} | `{path}` | {func} | `{f}` |")
        sections.append("")

    # Env vars
    if run_all or "env" in tasks:
        env_vars = scan_env_vars()
        sections.append(f"## ⚙️ Env Değişkenleri ({len(env_vars)} adet)\n")
        if env_vars:
            sections.append("| Değişken |")
            sections.append("|----------|")
            for v in env_vars:
                sections.append(f"| `{v}` |")
        sections.append("")

    # Docstring eksikleri
    if run_all or "docstrings" in tasks:
        docs = scan_docstrings()
        sections.append(f"## 📖 Docstring Eksikleri ({len(docs)} adet)\n")
        if docs:
            sections.append("| Dosya | Satır | Tür | İsim |")
            sections.append("|-------|-------|-----|------|")
            for f, line, kind, name in docs[:50]:  # İlk 50
                sections.append(f"| `{f}` | {line} | {kind} | `{name}` |")
            if len(docs) > 50:
                sections.append(f"\n... ve {len(docs) - 50} adet daha")
        else:
            sections.append("Bulunamadı ✅")
        sections.append("")

    # Korumasız endpoint'ler
    if run_all or "auth" in tasks:
        unprotected = scan_unprotected_endpoints()
        sections.append(f"## 🛡️ Auth Kontrolü Şüpheli Endpoint'ler ({len(unprotected)} adet)\n")
        if unprotected:
            sections.append("| Method | Path | Dosya | Satır |")
            sections.append("|--------|------|-------|-------|")
            for method, path, f, line in unprotected:
                sections.append(f"| {method} | `{path}` | `{f}` | {line} |")
        else:
            sections.append("Bulunamadı ✅")
        sections.append("")

    report = "\n".join(sections)
    REPORT_FILE.write_text(report)
    print(f"📄 Rapor yazıldı: {REPORT_FILE}")
    print(f"   Boyut: {len(report)} karakter")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="🔥 Kıvılcım — kod tarama ve rapor")
    parser.add_argument("--task", nargs="*", default=["all"],
                        help="Çalıştırılacak görevler: todos, secrets, endpoints, env, docstrings, auth, all")
    args = parser.parse_args()
    generate_report(tasks=args.task)
