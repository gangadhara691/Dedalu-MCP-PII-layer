Dual‑LLM Trust Layer for Dedalus Agents
======================================

This project shows how to run a fully working “dual LLM” security barrier: a quarantined LiquidAI judge handles unsafe input and a privileged Dedalus agent completes the business task. The pattern keeps sensitive prompts, PII, and tool commands inside a sandbox while exposing only sanitized text to the worker agent.

Concept
-------

1. **LLM #1 – Judge (Quarantined layer).** `redact/judge_service.py` receives the original prompt, checks it for malicious intent, extracts/masks PII through a LiquidAI endpoint, and emits a structured command.
2. **LLM #2 – Worker (Privileged layer).** Dedalus agents (`hello_world.py`, `data_analyst_agent.py`, etc.) call the judge through MCP tools (`mcp_tool_adapter.py`). They only see placeholders and whitelisted instructions, so the confused-deputy risk disappears.

Expected outcome: a Dedalus agent can summarize or analyze any document containing PII without ever seeing the real names or raw prompt, while still delivering accurate results once the judge rehydrates the final answer.

Environment Setup
-----------------

```powershell
python -m venv dedalu
.\dedalu\Scripts\activate
pip install -r requirements.txt
```

Set the required secrets:

```
DEDALUS_API_KEY=sk-your-key
HF_TOKEN=hf_xxx
HF_ENDPOINT=https://<your-endpoint>.aws.endpoints.huggingface.cloud
PII_BACKEND=remote        # switch to "offline" for local-only heuristics
```

Running the stack
-----------------

1. **Start the judge service (LLM #1).**
   ```powershell
   .\dedalu\Scripts\python -m uvicorn redact.judge_service:app --host 127.0.0.1 --port 9000
   ```
2. **Inspect or batch local samples.**
   ```powershell
   cd redact
   ..\dedalu\Scripts\python run_liquidai_pii.py --input data\txt\paddle_Redactor_sample_0002.txt --limit 1
   ```
3. **Launch the MCP proxy for Dedalus (LLM #2).**
   ```powershell
   $env:JUDGE_URL="http://127.0.0.1:9000"
   .\dedalu\Scripts\python mcp_tool_adapter.py
   ```
4. **Register the MCP tools in your Dedalus runner** and run `hello_world.py` or `data_analyst_agent.py`. The runner calls `sanitize` before every tool invocation and `rehydrate` before returning a response, so the worker LLM never touches raw PII.

Validation
----------

* `.\dedalu\Scripts\python -m pytest` exercises the sanitize/rehydrate flow (`tests/test_secure_pii_service.py`), the LiquidAI extractor (`tests/test_liquidai_pii.py`), and the judge heuristics (`tests/test_judge_service.py`).
* `redact/run_liquidai_pii.py` confirms the LiquidAI endpoint produces masked text and JSON replacements for the included sample dataset.

Project status
--------------

**Completed**

* Dual-LLM architecture (judge service + MCP adapter).
* LiquidAI integration with both remote endpoints and offline heuristics.
* Session-aware PII masking + rehydration.
* Automated tests and usage docs.

**In progress / planned**

* Automated deployment scripts for the judge layer (container + IaC).
* Expanded intent-detector prompts using Llama Guard or OpenGuardrails.
* Full Dedalus agent examples that log every sanitize/rehydrate event for auditing.

Roadmap ideas
-------------

1. **Stronger prompt vetting.** Plug a dedicated safety model into `judge_service.py` so intent checks move beyond simple heuristics.
2. **Secrets vault integration.** Store PII mappings in an encrypted backend (DynamoDB, Postgres, etc.) so the judge becomes horizontally scalable.
3. **Observability.** Add OpenTelemetry traces for every judge decision so SOC teams can monitor blocked vs. approved prompts.

Each enhancement only requires extending the judge service; the worker agents remain unchanged, which keeps the system easy to maintain and ready for enterprise showcases.
