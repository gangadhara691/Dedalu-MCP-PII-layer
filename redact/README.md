# Redactor

2025-10-11~12 LiquidAI Hackathon

### przm setup
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh

python -m venv .venv
source .venv/bin/activate
uv pip install -r requirements-przm.txt

# freeze
uv pip freeze > requirements-przm.txt
```

## LiquidAI inference integration

The repository now includes `liquidai_pii.py` and `run_liquidai_pii.py`, which wrap the official [LiquidAI/LFM2-350M-PII-Extract-JP](https://huggingface.co/LiquidAI/LFM2-350M-PII-Extract-JP) (or any compatible LiquidAI checkpoint) using the Hugging Face Inference API.

### Quick start

```bash
cd redact
set HF_TOKEN=hf_xxx   # or pass --hf-token on the command line
..\dedalu\Scripts\python run_liquidai_pii.py --input data/txt/paddle_Redactor_sample_0002.txt --limit 1
```

Optional flags:

* `--model LiquidAI/LFM2-350M-PII-Extract-JP` (default) or `kainoj/LiquidAI-LFM2-1.2B-ja-pii-finetuned`
* `--hf-token hf_xxx` if you need an authenticated Hugging Face call
* `--limit N` to cap how many `.txt` files to process inside `redact/data/txt`
* `--output redact/output/liquidai_predictions.jsonl` to change the output location

Each run writes newline-delimited JSON with the original file path, the model used, the raw entity JSON, and a masked-text preview.

> **Heads-up:** Hugging Face now requires authentication for router-based inference. Obtain a free access token from <https://huggingface.co/settings/tokens>, then either export it as `HF_TOKEN` or provide `--hf-token` when you run `run_liquidai_pii.py`. Without a token you'll see `LiquidAIPIIExtractor needs a Hugging Face token...` and no inference will be executed.
