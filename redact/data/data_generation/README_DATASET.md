# Setup & Run Guide (Windows, macOS, Linux)

This project renders fixed **LaTeX templates** using **Jinja2** and builds PDFs from a **master CSV**. Each run produces a folder like `data/generations/Generation_<N>_<time>/` with two subfolders:
- `pdf/` — final PDFs
- `text/` — plain text extracted from the LaTeX (no markup)

The six placeholders appear **once** per template:
`first_name`, `surname`, `company_name`, `company_address`, `place`, `phone_number`

---

## 0) Prerequisites

- **Python** 3.9+ (3.10/3.11 recommended)
- **LaTeX** distribution
  - **Windows**: MiKTeX. In MiKTeX Console → *Settings*, set **Install missing packages on-the-fly** = *Yes/Always*.
  - **macOS/Linux**: TeX Live or MacTeX.
- (Recommended) **VS Code** or any editor.

### Verify TeX tools
After LaTeX install, open a **new terminal** and check:
- Windows (CMD):
  ```bat
  where xelatex
  where latexmk
  ```
- macOS/Linux:
  ```bash
  which xelatex
  which latexmk
  ```

If `where/which` doesn’t show a path on Windows, add MiKTeX to PATH for this session:
```bat
set "PATH=%LOCALAPPDATA%\Programs\MiKTeX\miktex\bin\x64;%PATH%"
```

To persist (Windows CMD):
```bat
setx PATH "%LOCALAPPDATA%\Programs\MiKTeX\miktex\bin\x64;%PATH%"
```

> **Tip:** We default to **XeLaTeX** on Windows to avoid legacy CJK font tool errors (e.g., `udmj.cfg`, `miktex-makemf` failures).

---

## 1) Create & activate a Python venv

> You can name it anything; examples use **liqAI**.

### Windows — PowerShell
```powershell
cd "<your>\LIquid\redact"    # project root
py -m venv .\liqAI
.\liqAI\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

If activation is blocked:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\liqAI\Scripts\Activate.ps1
```

### Windows — CMD
```bat
cd "<your>\LIquid\redact"
py -m venv .\liqAI
call .\liqAI\Scripts\activate.bat
python -m pip install --upgrade pip
```

### macOS / Linux
```bash
cd "<your>/LIquid/redact"
python3 -m venv ./liqAI
source ./liqAI/bin/activate
python -m pip install --upgrade pip
```

---

## 2) Install Python requirements

From your activated venv:
```bash
pip install -r data_generation/requirements.txt
```
`requirements.txt` currently contains:
```
jinja2
```

> Optional (only if you plan to use the dataset loaders):  
> `pip install pandas datasets`

---

## 3) Lint templates (safety check)

Ensures each of the six placeholders appears **exactly once** in every template.
```bash
python data_generation/scripts/lint_templates.py
```

---

## 4) Prepare your master CSV

A **tab- or comma-separated** file with columns:
```
file_name, full_name, first_name, surname,
company_name, company_address, place, phone_number, template_id
```
- `template_id` can be **1/2/3/4** (mapped to `format1..format4`) or a literal name like `format3`.
- `file_name` becomes the base of output files.

**Example (TSV):**
```
file_name	full_name	first_name	surname	company_name	company_address	place	phone_number	template_id
Redactor_sample_0001	ジョン・ドウ	ジョン	ドウ	早稲田ロボティクス株式会社	〒169-8050 東京都新宿区西早稲田1-6-1	東京都新宿区	03-1234-5678	1
Redactor_sample_0002	山本 一郎	一郎	山本	早稲田ロボティクス株式会社	〒169-8050 東京都新宿区西早稲田1-6-1	東京都新宿区	03-1234-5678	2
```

> Encoding: **UTF-8** (with or without BOM is fine).

---

## 5) Generate a batch

Run from project root (venv active):
```bash
python data_generation/scripts/generate.py --csv data_generation/master_label.csv
```
Outputs:
```
data/generations/Generation_<N>_<time>/
  pdf/  <file_name>.pdf
  text/ <file_name>.txt
```

### Useful flags
- `--engine xelatex|lualatex|pdflatex`  
  Default: **xelatex** on Windows, **pdflatex** elsewhere.
- `--out-root <path>`  
  Default: `data/generations`
- `--run-name "Generation_42_2-03am"`  
  Override auto-naming.
- `--open` (Windows only)  
  Opens the generated run folder.
- `--render-only`  
  Renders `.tex` in-memory → plain text; **skips PDF** build.

---

## 6) How it works (short version)

- Templates in `data_generation/templates/format*.tex.j2` are **engine-agnostic** (XeLaTeX/LuaLaTeX prefer system fonts; pdfLaTeX falls back to `CJKutf8`).  
- We render the template with Jinja2 (custom comment delimiters to avoid `{#1}` collisions).  
- We compile in a temporary directory via `latexmk` (fallback to engine twice).  
- We extract **visible text** with a tuned regex pipeline that removes tabular column specs, spacing commands, and all begin/end wrappers.

---

## 7) Troubleshooting

**A. CJK font / MiKTeX errors (e.g., `udmj.cfg`, `miktex-makemf`, `TFM not found`)**  
Use **XeLaTeX**:
```bash
python data_generation/scripts/generate.py --csv ... --engine xelatex
```
Make sure `xelatex` exists:
```bat
where xelatex   # Windows
```
If not found, add to PATH:
```bat
set "PATH=%LOCALAPPDATA%\Programs\MiKTeX\miktex\bin\x64;%PATH%"
```

**B. `latexmk` not found**  
Install it via MiKTeX package manager (Windows) or TeX Live. The script will fall back to `xelatex/pdflatex` directly if `latexmk` is missing.

**C. “Missing end of comment tag” from Jinja**  
You’re using the updated `generate.py` which sets:
```python
comment_start_string='((*', comment_end_string='*))'
```
This avoids clashes with LaTeX `{#1}`. Replace your script if you still see this.

**D. Text extractor leaves junk like `@ >p35mm X @`, `flushright`, `center`**  
Use the updated `generate.py` with the **robust LaTeX→text stripper** (removes full tabular begin/end lines, column specs, and wrappers).

**E. PATH and OneDrive**  
If your path contains spaces/JP chars, always **quote** it in CMD/PowerShell.

**F. PowerShell activation blocked**  
Use:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

---

## 8) Optional: Hooks (custom logic)

Drop modules in `data_generation/scripts/modules/` implementing any of:
```python
def on_record(rec, base, **kwargs): pass
def on_render(rec, base, tex_source=None, tex_path=None, **kwargs): pass
def on_pdf(rec, base, pdf_path=None, **kwargs): pass
```
They’re auto-discovered and called if present.

---

## 9) Quick commands (cheatsheet)

**Windows CMD**
```bat
REM venv
cd "<your>\LIquid\redact"
py -m venv .\liqAI
call .\liqAI\Scripts\activate.bat
pip install -r data_generation\requirements.txt

REM verify TeX
where xelatex
where latexmk

REM build
python data_generation\scripts\lint_templates.py
python data_generation\scripts\generate.py --csv data_generation\master_label.csv --open
```

**macOS/Linux**
```bash
cd "<your>/LIquid/redact"
python3 -m venv ./liqAI
source ./liqAI/bin/activate
pip install -r data_generation/requirements.txt

which xelatex
which latexmk

python data_generation/scripts/lint_templates.py
python data_generation/scripts/generate.py --csv data_generation/master_label.csv
```

---

## 10) Structure recap
```
data_generation/
  templates/
    format1.tex.j2
    format2.tex.j2
    format3.tex.j2
    format4.tex.j2
  scripts/
    generate.py          # CSV → Generation_<N>_<time>/{pdf,text}
    lint_templates.py    # exactly-once placeholder check
    modules/
      sample_hook.py     # optional hooks (accept **kwargs)
  requirements.txt
data/
  generations/
    Generation_<N>_<time>/
      pdf/*.pdf
      text/*.txt
```
