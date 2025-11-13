#!/usr/bin/env python3
"""
Lint templates to ensure exactly one occurrence of each placeholder
(first_name, surname, company_name, company_address, place, phone_number).
"""
import re
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates"
FIELDS = ["first_name","surname","company_name","company_address","place","phone_number"]

def count_occurrences(text, field):
    # Matches {{ field }} with optional spaces/newlines
    pat = re.compile(r"{{\s*" + re.escape(field) + r"\s*}}")
    return len(pat.findall(text))

def main():
    ok = True
    for t in TEMPLATES.glob("*.tex.j2"):
        txt = t.read_text(encoding="utf-8")
        for f in FIELDS:
            c = count_occurrences(txt, f)
            if c != 1:
                ok = False
                print(f"[FAIL] {t.name}: {f} appears {c} times (must be exactly 1)")
    if ok:
        print("All templates OK: exactly one occurrence per placeholder.")
    else:
        raise SystemExit(1)

if __name__ == "__main__":
    main()
