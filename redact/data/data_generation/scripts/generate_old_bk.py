#!/usr/bin/env python3
"""
Build PDFs from a master CSV (one row -> one PDF).

CSV columns (required):
  file_name, full_name, first_name, surname,
  company_name, company_address, place, phone_number, template_id

Behavior:
- Reads CSV (tab- or comma-delimited; auto-detected).
- template_id accepts either numbers 1..N (mapped to format1..N) or names like "format3".
- Output: build/<template_id>/<file_name>.pdf
- Engine: defaults to xelatex on Windows, pdflatex elsewhere (change with --engine).
- Jinja comment delimiters are customized so LaTeX "{#1}" doesn’t break templates.

Note: Templates should only use the six placeholders once:
  {{ first_name }}, {{ surname }}, {{ company_name }},
  {{ company_address }}, {{ place }}, {{ phone_number }}
"""

import argparse
import csv
import json
import os
import re
import subprocess
import sys
import importlib.util
from pathlib import Path
from typing import Dict, List

from jinja2 import Environment, FileSystemLoader, StrictUndefined

# Paths
ROOT = Path(__file__).resolve().parents[1]     # .../data_generation
TEMPLATES = ROOT / "templates"
DATA = ROOT / "data"                           # not used by CSV mode, kept for parity
BUILD = ROOT / "build"
MODULES_DIR = Path(__file__).resolve().parent / "modules"

# Required keys that templates actually consume
PLACEHOLDER_KEYS = [
    "first_name",
    "surname",
    "company_name",
    "company_address",
    "place",
    "phone_number",
]

# CSV keys expected
CSV_REQUIRED = PLACEHOLDER_KEYS + ["file_name", "template_id"]
CSV_OPTIONAL = ["full_name"]  # accepted but not required by templates


# ---------- Utils ----------
def load_plugins():
    plugins = []
    if MODULES_DIR.exists():
        for p in MODULES_DIR.glob("*.py"):
            if p.name.startswith("_"):
                continue
            spec = importlib.util.spec_from_file_location(p.stem, p)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)  # type: ignore
            plugins.append(mod)
    return plugins

def call_hook(mods, hook, *args, **kwargs):
    for m in mods:
        fn = getattr(m, hook, None)
        if callable(fn):
            fn(*args, **kwargs)

def resolve_template_id(val: str) -> str:
    """Map '1' -> 'format1'; leave 'format3' as is."""
    s = str(val).strip()
    if re.fullmatch(r"\d+", s):
        return f"format{s}"
    return s

def sanitize_base(name: str) -> str:
    """
    Sanitize file_name into a safe base:
    - strip extension if present
    - remove characters invalid on Windows: \ / : * ? " < > | 
    - trim whitespace
    (Japanese and most Unicode letters are fine to keep)
    """
    base = name
    # strip extension
    if "." in base:
        base = ".".join(base.split(".")[:-1])  # remove last extension only
    # replace invalid chars
    base = re.sub(r'[\\/:*?"<>|]', "_", base)
    # trim
    base = base.strip()
    if not base:
        raise ValueError("Empty file_name after sanitization.")
    return base

def read_csv_rows(csv_path: Path) -> List[Dict]:
    """Read CSV with dialect sniffing (UTF-8 or UTF-8 BOM)."""
    text = csv_path.read_text(encoding="utf-8-sig")
    # sniff comma vs tab
    try:
        dialect = csv.Sniffer().sniff(text.splitlines()[0])
    except Exception:
        # fallback: tab if it looks tabby, else comma
        dialect = csv.excel_tab if "\t" in text.splitlines()[0] else csv.excel
    reader = csv.DictReader(text.splitlines(), dialect=dialect)
    rows = []
    for i, row in enumerate(reader, start=2):  # header is line 1
        # Normalize keys -> lower and strip
        norm = {k.strip(): (v.strip() if isinstance(v, str) else v) for k, v in row.items() if k}
        # Accept both English and Japanese columns if ever added; current spec uses English.
        rows.append(norm)
    return rows

def validate_row(row: Dict, line_hint: str):
    missing = [k for k in CSV_REQUIRED if not row.get(k)]
    if missing:
        raise ValueError(f"{line_hint}: missing required fields {missing}")
    # Ensure strings
    for k in CSV_REQUIRED + CSV_OPTIONAL:
        if k in row and not isinstance(row[k], str):
            row[k] = str(row[k])

def jinja_env() -> Environment:
    # Custom comment delimiters avoid LaTeX "{#1}" collision
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
        undefined=StrictUndefined,
        comment_start_string='((*',
        comment_end_string='*))',
    )

def render_tex(env: Environment, template_id: str, ctx: Dict, out_base: str) -> Path:
    tpl_file = f"{template_id}.tex.j2"
    tpl_path = TEMPLATES / tpl_file
    if not tpl_path.exists():
        raise FileNotFoundError(f"Template not found: {tpl_path}")
    out_dir = BUILD / template_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_tex = out_dir / f"{out_base}.tex"
    tex = env.get_template(tpl_file).render(**ctx)
    out_tex.write_text(tex, encoding="utf-8")
    return out_tex

def run_cmd(cmd, cwd: Path):
    try:
        proc = subprocess.run(
            cmd, cwd=cwd, check=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        return True, proc.stdout
    except subprocess.CalledProcessError as e:
        return False, e.stdout

def compile_pdf(tex_path: Path, engine: str):
    """
    Compile using latexmk; fallback to direct engine twice.
    engine in {"xelatex","lualatex","pdflatex"}
    """
    out_dir = tex_path.parent
    base = tex_path.stem
    pdf = out_dir / f"{base}.pdf"

    # latexmk first
    if engine == "xelatex":
        ok, log = run_cmd(
            ["latexmk", "-xelatex", "-interaction=nonstopmode", "-halt-on-error", "-file-line-error", tex_path.name],
            cwd=out_dir,
        )
    elif engine == "lualatex":
        ok, log = run_cmd(
            ["latexmk", "-lualatex", "-interaction=nonstopmode", "-halt-on-error", "-file-line-error", tex_path.name],
            cwd=out_dir,
        )
    else:
        ok, log = run_cmd(
            ["latexmk", "-pdf", "-interaction=nonstopmode", "-halt-on-error", "-file-line-error", tex_path.name],
            cwd=out_dir,
        )

    if ok and pdf.exists():
        return pdf, log

    # Fallback: call engine directly twice
    if engine == "xelatex":
        ok1, log1 = run_cmd(["xelatex", "-interaction=nonstopmode", "-halt-on-error", tex_path.name], cwd=out_dir)
        ok2, log2 = run_cmd(["xelatex", "-interaction=nonstopmode", "-halt-on-error", tex_path.name], cwd=out_dir)
    elif engine == "lualatex":
        ok1, log1 = run_cmd(["lualatex", "-interaction=nonstopmode", "-halt-on-error", tex_path.name], cwd=out_dir)
        ok2, log2 = run_cmd(["lualatex", "-interaction=nonstopmode", "-halt-on-error", tex_path.name], cwd=out_dir)
    else:
        ok1, log1 = run_cmd(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", tex_path.name], cwd=out_dir)
        ok2, log2 = run_cmd(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", tex_path.name], cwd=out_dir)

    log_all = (log or "") + "\n" + (log1 or "") + "\n" + (log2 or "")
    if pdf.exists():
        return pdf, log_all
    raise RuntimeError("PDF compilation failed.\n" + log_all)


# ---------- Main ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, help="Path to master CSV (tab or comma delimited)")
    ap.add_argument("--open", action="store_true", help="Open build folder (Windows)")
    ap.add_argument("--render-only", action="store_true", help="Only render .tex; skip PDF compile")
    ap.add_argument(
        "--engine",
        choices=["pdflatex", "xelatex", "lualatex"],
        default=None,
        help="TeX engine (default: xelatex on Windows, pdflatex elsewhere)"
    )
    args = ap.parse_args()

    # Decide engine default
    engine = args.engine
    if engine is None:
        engine = "xelatex" if os.name == "nt" else "pdflatex"

    env = jinja_env()
    plugins = load_plugins()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"CSV not found: {csv_path}", file=sys.stderr)
        sys.exit(2)

    rows = read_csv_rows(csv_path)
    if not rows:
        print("No rows in CSV.", file=sys.stderr)
        sys.exit(2)

    # Detect and prevent duplicate (template_id, file_name) outputs
    seen = set()

    built = []
    for idx, row in enumerate(rows, start=2):
        line_hint = f"{csv_path.name}:line{idx}"

        # Validate presence
        validate_row(row, line_hint)

        # Normalize / map
        template_id = resolve_template_id(row["template_id"])
        base = sanitize_base(row["file_name"])

        key = (template_id, base)
        if key in seen:
            print(f"[SKIP DUP] {line_hint}: duplicate output for template={template_id}, file_name={base}", file=sys.stderr)
            continue
        seen.add(key)

        # Context for templates: ONLY the six placeholders (extra cols ignored)
        ctx = {k: row[k] for k in PLACEHOLDER_KEYS}

        # Hooks before render (optional)
        call_hook(plugins, "on_record", rec=ctx, base=base)

        # Render .tex
        tex = render_tex(env, template_id, ctx, base)
        call_hook(plugins, "on_render", rec=ctx, base=base, tex_path=tex)

        # Compile or skip
        if args.render_only:
            print(f"Rendered: {tex} (skipped PDF)")
            continue

        pdf, _log = compile_pdf(tex, engine)
        call_hook(plugins, "on_pdf", rec=ctx, base=base, pdf_path=pdf)
        built.append(pdf)
        print(f"OK: {pdf}")

    if args.open and os.name == "nt":
        os.startfile(str(BUILD))

if __name__ == "__main__":
    main()
