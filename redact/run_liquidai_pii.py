"""
CLI utility to run LiquidAI PII extraction on local data files.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional

try:  # pragma: no cover - convenience for direct execution
    from .liquidai_pii import LiquidAIPIIExtractor, iter_text_files
except ImportError:  # pragma: no cover
    from liquidai_pii import LiquidAIPIIExtractor, iter_text_files  # type: ignore


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run LiquidAI PII masking against .txt exports in redact/data."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("redact/data/txt"),
        help="Path to a .txt file or a directory containing .txt files.",
    )
    parser.add_argument(
        "--model",
        default="LiquidAI/LFM2-350M-PII-Extract-JP",
        help="Hugging Face model repo to use for extraction.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional limit on how many files to process.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("redact/output/liquidai_predictions.jsonl"),
        help="Where to write newline-delimited JSON results.",
    )
    parser.add_argument(
        "--hf-token",
        default=None,
        help="Optional Hugging Face access token if you have one.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    extractor = LiquidAIPIIExtractor(model_name=args.model, hf_token=args.hf_token)
    args.output.parent.mkdir(parents=True, exist_ok=True)

    files_processed = 0
    with args.output.open("w", encoding="utf-8") as writer:
        for file_path in iter_text_files(args.input):
            if args.limit is not None and files_processed >= args.limit:
                break
            text = file_path.read_text(encoding="utf-8")
            result = extractor.extract(text)
            payload = {
                "file": str(file_path),
                "model": args.model,
                "raw_json": result.raw_json,
                "masked_text": result.masked_text,
                "replacements": result.replacements,
            }
            writer.write(json.dumps(payload, ensure_ascii=False) + "\n")
            print(f"Processed {file_path} -> {result.raw_json}")
            files_processed += 1

    print(f"Wrote {files_processed} records to {args.output}")


if __name__ == "__main__":
    main()
