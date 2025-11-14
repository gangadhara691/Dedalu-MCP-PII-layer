Dedalu Labs SDK Quickstart
==========================

This repo provisions a `dedalu` virtual environment with the `dedalus-labs` SDK preinstalled and adds the infrastructure to run a dual‑LLM trust layer for sensitive workflows.

Prerequisites
-------------

* Python 3.11+
* Dedalus API key in `.env`
* Hugging Face access token + private inference endpoint (for LiquidAI judge layer)

Environment Setup
-----------------

```powershell
python -m venv dedalu
.\dedalu\Scripts\activate
pip install -r requirements.txt
```

Configuration
-------------

Copy `.env.example` to `.env` and drop your API key:

```
DEDALUS_API_KEY=sk-your-key
```

For the judge layer, set:

```
HF_TOKEN=hf_xxx
HF_ENDPOINT=https://<your-endpoint>.aws.endpoints.huggingface.cloud
PII_BACKEND=remote  # use "offline" for heuristic masking/tests
```

Examples
--------

* `hello_world.py` – minimal chat completion against `openai/gpt-5-mini`
* `data_analyst_agent.py` – multi-tool agent that streams responses while hitting Brave Search MCP
* `redact/judge_service.py` – quarantined FastAPI “judge” that fronts the LiquidAI PII extractor
* `mcp_tool_adapter.py` – MCP tool server that surfaces the judge to Dedalus agents
* `redact/run_liquidai_pii.py` – CLI to batch local `.txt` files through the judge

Running the quick-start scripts:

```powershell
.\dedalu\Scripts\python hello_world.py
.\dedalu\Scripts\python data_analyst_agent.py
```

Testing the trust layer:

```powershell
.\dedalu\Scripts\python -m pytest
```

Dual-LLM Mediator Architecture
------------------------------

The repo demonstrates how to wrap a privileged agent (Dedalus) behind a quarantined mediator (LiquidAI):

1. **LLM #1 – Judge / Sandbox.** `redact/judge_service.py` is the first LLM in the chain. It receives raw user prompts, vets them for injection attempts, masks PII via the LiquidAI endpoint, and emits a sanitized command. This is the only layer that touches untrusted text.
2. **LLM #2 – Worker / Privileged agent.** Dedalus agents consume the sanitized command and masked text via MCP tools. They never ingest raw input, so the “confused deputy” problem is removed.

### Running the sandbox locally

1. **Start the judge service (LLM #1).**
   ```powershell
   $env:HF_TOKEN="hf_your_token"
   $env:HF_ENDPOINT="https://your-endpoint.aws.endpoints.huggingface.cloud"
   $env:PII_BACKEND="remote"   # default "offline" works for quick tests
   .\dedalu\Scripts\python -m uvicorn redact.judge_service:app --host 127.0.0.1 --port 9000
   ```

2. **Optionally inspect the flow with a local file.**
   ```powershell
   cd redact
   $env:PYTHONIOENCODING="utf-8"
   ..\dedalu\Scripts\python run_liquidai_pii.py --input data\txt\paddle_Redactor_sample_0002.txt --limit 1
   ```

3. **Launch the MCP proxy for Dedalus (LLM #2).**
   ```powershell
   $env:JUDGE_URL="http://127.0.0.1:9000"
   .\dedalu\Scripts\python mcp_tool_adapter.py
   ```
   The `sanitize` tool now returns a JSON blob: `{is_allowed, sanitized_command, masked_text, replacements}`. `rehydrate` swaps placeholders back to their originals.

4. **Register the tools with your Dedalus runner.**
   ```python
   result = await runner.run(
       input="Summarize the masked contract.",
       model="openai/gpt-5-mini",
       tools=[sanitize, rehydrate],
       mcp_servers=["local/judge-tools"],
   )
   ```

Why this is the “next AI trust layer”
-------------------------------------

* **Quarantined vs. privileged LLMs:** LiquidAI plays the “judge,” isolating raw prompts and PII. Dedalus models only touch approved commands.
* **Sandboxed mediator:** Every request flows through the judge + MCP proxy before an agent can call tools, mirroring the “dual LLM” security posture recommended by enterprise red teams.
* **Stateful privacy boundary:** Placeholder→real mappings never leave the judge service, yet the privileged agent still completes its task with placeholders.
* **Provable behavior:** Automated pytest coverage (`tests/test_secure_pii_service.py`, `tests/test_liquidai_pii.py`, `tests/test_judge_service.py`) spans masking, session isolation, and prompt-vetting heuristics so adopters can evaluate the trust layer before handling regulated data.
