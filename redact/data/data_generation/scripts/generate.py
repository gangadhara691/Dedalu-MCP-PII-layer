#!/usr/bin/env python3
"""
Build PDFs from a master CSV (one row -> one PDF) and also write clean plain-text
versions (LaTeX stripped). Each run creates a folder:

  <out-root>/Generation_<number>_<time>/
    pdf/  -> final PDFs
    text/ -> plain text files (same basenames as PDFs)

CSV columns (required):
  file_name, full_name, first_name, surname,
  company_name, company_address, place, phone_number, template_id

- template_id accepts numbers 1..N (mapped to format1..N) or names like "format3".
- Engine: defaults to xelatex on Windows, pdflatex elsewhere (change with --engine).
- Jinja comment delimiters customized to avoid LaTeX "{#1}" collision.
- The six placeholders must appear exactly once in the templates:
    {{ first_name }}, {{ surname }}, {{ company_name }},
    {{ company_address }}, {{ place }}, {{ phone_number }}

Usage:
  python data_generation/scripts/generate.py --csv data_generation/master_label.csv
  python data_generation/scripts/generate.py --csv ... --out-root data/generations
  python data_generation/scripts/generate.py --csv ... --run-name "Generation_MyBatch"
"""

import argparse
import csv
import os
import re
import shutil
import subprocess
import sys
import tempfile
import importlib.util
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from jinja2 import Environment, FileSystemLoader, StrictUndefined

# Paths
ROOT = Path(__file__).resolve().parents[1]     # .../data_generation
TEMPLATES = ROOT / "templates"
OUT_ROOT_DEFAULT = ROOT.parent / "generations"
MODULES_DIR = Path(__file__).resolve().parent / "modules"

# Placeholders actually used in templates
PLACEHOLDER_KEYS = [
    "full_name",
    "company_name",
    "company_address",
    "phone_number",
]

# CSV required keys (full_name is optional for now)
CSV_REQUIRED = PLACEHOLDER_KEYS + ["file_name", "template_id"]
CSV_OPTIONAL = ["full_name"]


# ---------- Plugin hooks (optional) ----------
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

# ---------- CSV & naming ----------
def read_csv_rows(csv_path: Path) -> List[Dict]:
    """Read CSV with simple auto-detection of tab vs comma; UTF-8 with/without BOM."""
    text = csv_path.read_text(encoding="utf-8-sig")
    lines = [ln for ln in text.splitlines() if ln.strip() != ""]
    if not lines:
        return []
    delimiter = "\t" if ("\t" in lines[0]) else ","
    reader = csv.DictReader(lines, delimiter=delimiter)
    rows = []
    for row in reader:
        norm = { (k.strip() if k else k): (v.strip() if isinstance(v, str) else v) for k, v in row.items() }
        rows.append(norm)
    return rows

def validate_row(row: Dict, line_hint: str):
    missing = [k for k in CSV_REQUIRED if not row.get(k)]
    if missing:
        raise ValueError(f"{line_hint}: missing required fields {missing}")
    for k in CSV_REQUIRED + CSV_OPTIONAL:
        if k in row and not isinstance(row[k], str):
            row[k] = str(row[k])

def resolve_template_id(val: str) -> str:
    s = str(val).strip()
    return f"format{s}" if re.fullmatch(r"\d+", s) else s

def sanitize_base(name: str) -> str:
    base = name
    if "." in base:
        base = ".".join(base.split(".")[:-1])  # drop last extension
    base = re.sub(r'[\\/:*?"<>|]', "_", base).strip()
    if not base:
        raise ValueError("Empty file_name after sanitization.")
    return base

# ---------- Run folder ----------
def next_generation_name(out_root: Path) -> str:
    max_n = 0
    for d in out_root.glob("Generation_*"):
        m = re.match(r"Generation_(\d+)", d.name)
        if m:
            try:
                max_n = max(max_n, int(m.group(1)))
            except ValueError:
                pass
    num = max_n + 1
    now = datetime.now()
    label = now.strftime("%I-%M%p").lower()  # 01-25am
    if label.startswith("0"):
        label = label[1:]
    return f"Generation_{num}_{label}"

def make_run_dirs(out_root: Path, run_name: str | None):
    out_root.mkdir(parents=True, exist_ok=True)
    run_dir = out_root / (run_name if run_name else next_generation_name(out_root))
    pdf_dir = run_dir / "pdf"
    txt_dir = run_dir / "text"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    txt_dir.mkdir(parents=True, exist_ok=True)
    return run_dir, pdf_dir, txt_dir

# ---------- LaTeX rendering & compile ----------
def jinja_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
        undefined=StrictUndefined,
        comment_start_string='((*',
        comment_end_string='*))',
    )

def render_tex_to_string(env: Environment, template_id: str, ctx: Dict) -> str:
    tpl_file = f"{template_id}.tex.j2"
    tpl_path = TEMPLATES / tpl_file
    if not tpl_path.exists():
        raise FileNotFoundError(f"Template not found: {tpl_path}")
    return env.get_template(tpl_file).render(**ctx)

def run_cmd(cmd, cwd: Path):
    try:
        proc = subprocess.run(
            cmd, cwd=cwd, check=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        return True, proc.stdout
    except subprocess.CalledProcessError as e:
        return False, e.stdout

def compile_pdf(tex_source: str, engine: str, out_pdf: Path):
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmpd:
        tmpdir = Path(tmpd)
        tex_path = tmpdir / "doc.tex"
        tex_path.write_text(tex_source, encoding="utf-8")

        if engine == "xelatex":
            ok, log = run_cmd(["latexmk","-xelatex","-interaction=nonstopmode","-halt-on-error","-file-line-error","doc.tex"], cwd=tmpdir)
        elif engine == "lualatex":
            ok, log = run_cmd(["latexmk","-lualatex","-interaction=nonstopmode","-halt-on-error","-file-line-error","doc.tex"], cwd=tmpdir)
        else:
            ok, log = run_cmd(["latexmk","-pdf","-interaction=nonstopmode","-halt-on-error","-file-line-error","doc.tex"], cwd=tmpdir)

        pdf_tmp = tmpdir / "doc.pdf"
        if not (ok and pdf_tmp.exists()):
            if engine == "xelatex":
                ok1, log1 = run_cmd(["xelatex","-interaction=nonstopmode","-halt-on-error","doc.tex"], cwd=tmpdir)
                ok2, log2 = run_cmd(["xelatex","-interaction=nonstopmode","-halt-on-error","doc.tex"], cwd=tmpdir)
            elif engine == "lualatex":
                ok1, log1 = run_cmd(["lualatex","-interaction=nonstopmode","-halt-on-error","doc.tex"], cwd=tmpdir)
                ok2, log2 = run_cmd(["lualatex","-interaction=nonstopmode","-halt-on-error","doc.tex"], cwd=tmpdir)
            else:
                ok1, log1 = run_cmd(["pdflatex","-interaction=nonstopmode","-halt-on-error","doc.tex"], cwd=tmpdir)
                ok2, log2 = run_cmd(["pdflatex","-interaction=nonstopmode","-halt-on-error","doc.tex"], cwd=tmpdir)
            if not pdf_tmp.exists():
                combined = (log or "") + "\n" + (log1 or "") + "\n" + (log2 or "")
                raise RuntimeError("PDF compilation failed.\n" + combined)

        shutil.copy2(pdf_tmp, out_pdf)

# ---------- LaTeX -> plain text (simple stripper tuned to these templates) ----------
# ---------- LaTeX -> plain text (robust stripper) ----------
# Remove entire begin/end lines for tabular/tabularx so column specs never leak.
TABULAR_LINES = re.compile(r'^.*\\begin\{tabularx?\}.*$\n?|^.*\\end\{tabularx?\}.*$\n?', flags=re.M)

# Remove vspace/hspace & relatives completely (don’t leave "0.8em")
LATEX_DROP_WHOLE = re.compile(
    r'\\(?:vspace|hspace|smallskip|medskip|bigskip|pagestyle)\*?\s*(?:\[[^\]]*\])?\s*(?:\{[^{}]*\})?',
    flags=re.S
)

# Simple inline formatting: keep the argument only
LATEX_INLINE_KEEPARG_RE = re.compile(
    r'\\(?:textbf|textit|emph)\*?\s*(?:\[[^\]]*\])?\s*\{([^{}]*)\}'
)

# Spacing commands → a single space
LATEX_INLINE_SPACES = re.compile(r'(?:\\quad|\\qquad|\\,|\\;|\\:|~)')

# Misc commands with no visible effect
LATEX_MISC_CMDS = re.compile(r'(?:\\checked|\\unchecked|\\ding\{[^}]*\}|\\hfill|\\bfseries|\\large|\\Large|\\normalsize)')

# Generic \command{arg} → keep arg
LATEX_CMD_ARG_TO_ARG = re.compile(r'\\[a-zA-Z]+\*?\s*(?:\[[^\]]*\])?\s*\{([^{}]*)\}')

# Generic \command[...] or bare \command → drop
LATEX_CMD_DROP = re.compile(r'\\[a-zA-Z]+\*?(?:\[[^\]]*\])?')
BEGIN_END_ANY = re.compile(r'\\(?:begin|end)\{[^}]+\}')

# Column-spec leftovers (after begin-line removal) — nuke them:
#  - {@...@}, >{...}, <{...}, p{...}, m{...}, b{...}, and stray single " X "
COLSPEC_GARBAGE_1 = re.compile(r'\{@[^{}]*@\}')
COLSPEC_GARBAGE_2 = re.compile(r'>\{[^{}]*\}|<\{[^{}]*\}|p\{[^{}]*\}|m\{[^{}]*\}|b\{[^{}]*\}')
COLSPEC_STANDALONE_LINE = re.compile(r'^\s*\{?@.*@}?\s*$', flags=re.M)   # lines that are just @ ... @
COLSPEC_ISOLATED_X = re.compile(r'(?<=\s)X(?=\s)')  # rare; only if it’s separated by spaces

def latex_to_plain_text(tex_source: str) -> str:
    # keep only the document body
    m = re.search(r'\\begin\{document\}(.*)\\end\{document\}', tex_source, re.S)
    body = m.group(1) if m else tex_source

    # drop LaTeX comments
    body = re.sub(r'(?<!\\)%.*', '', body)

    # row breaks first
    body = body.replace('\\\\', '\n')

    # 1) kill entire tabular/tabularx begin/end lines (removes column specs)
    body = TABULAR_LINES.sub('', body)

    # 2) remove ANY remaining \begin{...} / \end{...} (stops "flushright"/"center" leaking)
    body = BEGIN_END_ANY.sub('', body)

    # 3) drop spacing/page-style commands entirely (so we don’t keep "0.8em")
    body = LATEX_DROP_WHOLE.sub('', body)

    # 4) unwrap simple inline formatting
    body = LATEX_INLINE_KEEPARG_RE.sub(r'\1', body)

    # 5) spacing commands -> single space
    body = LATEX_INLINE_SPACES.sub(' ', body)

    # 6) misc commands -> drop
    body = LATEX_MISC_CMDS.sub('', body)

    # 7) generic \cmd{arg} -> arg
    body = LATEX_CMD_ARG_TO_ARG.sub(r'\1', body)

    # 8) leftover \cmd[...] / \cmd -> drop
    body = LATEX_CMD_DROP.sub('', body)

    # 9) nuke any column-spec crumbs just in case
    body = COLSPEC_GARBAGE_1.sub('', body)
    body = COLSPEC_GARBAGE_2.sub('', body)
    body = COLSPEC_STANDALONE_LINE.sub('', body)
    body = COLSPEC_ISOLATED_X.sub('', body)

    # 10) braces -> remove
    body = body.replace('{', '').replace('}', '')

    # 11) table cell separators -> space (or ': ' if you prefer)
    body = re.sub(r'\s*&\s*', ' ', body)

    # 12) tidy whitespace
    body = re.sub(r'[ \t]+\n', '\n', body)
    body = re.sub(r'\n{3,}', '\n\n', body)
    body = re.sub(r'[ \t]{2,}', ' ', body)

    return body.strip()

# ---------- Main ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, help="Path to master CSV (tab or comma delimited)")
    ap.add_argument("--out-root", default=str(OUT_ROOT_DEFAULT), help="Base folder for generations (default: data/generations)")
    ap.add_argument("--run-name", help='Override run folder name (default: "Generation_<n>_<time>")')
    ap.add_argument("--open", action="store_true", help="Open run folder (Windows)")
    ap.add_argument("--engine", choices=["pdflatex","xelatex","lualatex"], default=None,
                    help="TeX engine (default: xelatex on Windows, pdflatex elsewhere)")
    args = ap.parse_args()

    engine = args.engine or ("xelatex" if os.name == "nt" else "pdflatex")

    out_root = Path(args.out_root)
    run_dir, pdf_dir, txt_dir = make_run_dirs(out_root, args.run_name)

    env = jinja_env()
    plugins = load_plugins()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"CSV not found: {csv_path}", file=sys.stderr); sys.exit(2)
    rows = read_csv_rows(csv_path)
    if not rows:
        print("No rows in CSV.", file=sys.stderr); sys.exit(2)

    seen = set()
    for idx, row in enumerate(rows, start=2):
        line_hint = f"{csv_path.name}:line{idx}"
        validate_row(row, line_hint)
        template_id = resolve_template_id(row["template_id"])
        base = sanitize_base(row["file_name"])

        key = (template_id, base)
        if key in seen:
            print(f"[SKIP DUP] {line_hint}: duplicate output for template={template_id}, file_name={base}", file=sys.stderr)
            continue
        seen.add(key)

        ctx = {k: row[k] for k in PLACEHOLDER_KEYS}

        # Pre-render hook
        call_hook(plugins, "on_record", rec=ctx, base=base)

        # Render LaTeX to string
        tex_source = render_tex_to_string(env, template_id, ctx)

        # Render hook (be liberal with args so older hooks don't break)
        call_hook(plugins, "on_render", rec=ctx, base=base, tex_source=tex_source, tex_path=None)

        # Compile to PDF in tmp and copy to run/pdf/<base>.pdf
        out_pdf = pdf_dir / f"{base}.pdf"
        compile_pdf(tex_source, engine, out_pdf)

        # Plain text to run/text/<base>.txt
        plain = latex_to_plain_text(tex_source)
        (txt_dir / f"{base}.txt").write_text(plain, encoding="utf-8")

        # Post-PDF hook
        call_hook(plugins, "on_pdf", rec=ctx, base=base, pdf_path=out_pdf)

        print(f"OK: {out_pdf}")

    print(f"\nRun folder: {run_dir}")
    print(f"PDFs:  {pdf_dir}")
    print(f"TEXT:  {txt_dir}")

    if args.open and os.name == "nt":
        os.startfile(str(run_dir))

if __name__ == "__main__":
    main()
