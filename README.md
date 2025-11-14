Dual LLM Trust Layer for Dedalus Agents
=======================================

This repo proves that Dedalus agents can stay fast and useful while a separate LLM firewall keeps the raw prompts, PII, and tool routing under control. The first LLM (LiquidAI on Hugging Face) sits in front of every Dedalus run, cleans the input, and only hands the worker agent the command set it is allowed to execute. The second LLM (your Dedalus workflow) stays blissfully unaware of real names or secrets.

How the two LLMs split duties
-----------------------------

1. **LLM #1: Judge / Sandbox (`redact/judge_service.py`)**  
   * Receives the exact user prompt.  
   * Screens for prompt-injection attempts.  
   * Calls the LiquidAI endpoint to extract and mask PII.  
   * Returns a JSON payload describing the masked text, placeholder map, and the action it wants the worker to perform.

2. **LLM #2: Worker / Dedalus agent (`hello_world.py`, `data_analyst_agent.py`, your own flows)**  
   * Talks to the judge through MCP tools defined in `mcp_tool_adapter.py`.  
   * Only sees placeholders and the judge-approved command set.  
   * Sends any final answer back through the same MCP adapter so the judge can rehydrate the placeholders before a user ever sees it.

The MCP hook is the glue: the Dedalus runner registers `sanitize` and `rehydrate`, and the MCP call path proves you understand their stack end-to-end.

What you get
------------

* Dedalus agents that can summarize or analyze PII-heavy docs without ever touching the raw identifiers.  
* Tool access runs through the judge, so confused-deputy attacks have nowhere to land.  
* Audit logs that mostly show placeholders, but can be rehydrated on demand.  
* A clear drop-in story: keep your existing Dedalus code, add the MCP tool server, and point it at the judge.

Environment setup
-----------------

```powershell
python -m venv dedalu
.\dedalu\Scripts\activate
pip install -r requirements.txt
```

Secrets and config:

```
DEDALUS_API_KEY=sk-your-key
HF_TOKEN=hf_your_token
HF_ENDPOINT=https://your-endpoint.aws.endpoints.huggingface.cloud
PII_BACKEND=remote   # use "offline" to run without Hugging Face
```

Running the stack
-----------------

1. **Judge service (LLM #1).**
   ```powershell
   .\dedalu\Scripts\python -m uvicorn redact.judge_service:app --host 127.0.0.1 --port 9000
   ```
2. **Optional batch inspection.**
   ```powershell
   cd redact
   ..\dedalu\Scripts\python run_liquidai_pii.py --input data\txt\paddle_Redactor_sample_0002.txt --limit 1
   ```
3. **MCP proxy (bindings for Dedalus).**
   ```powershell
   $env:JUDGE_URL="http://127.0.0.1:9000"
   .\dedalu\Scripts\python mcp_tool_adapter.py
   ```
4. **Dedalus runners.**  
   Register the MCP tools with your Dedalus `AsyncDedalus` runner. The agent calls `sanitize` before any tool invocation and `rehydrate` before returning a response.

Validation checklist
--------------------

* `.\dedalu\Scripts\python -m pytest` covers the judge heuristics, LiquidAI masking logic, and the stateful sanitize/rehydrate flow.  
* `redact/run_liquidai_pii.py` lets you point at specific `.txt` exports and see the exact JSON + masked text the judge will hand off.  
* Dedalus quickstart scripts (`hello_world.py`, `data_analyst_agent.py`) continue to run, now with the MCP adapter in front of them.

Status and next steps
---------------------

**Done**

* Dual LLM architecture wired into Dedalus via MCP.  
* LiquidAI endpoint client with fallback offline heuristics.  
* Session-aware PII masking and rehydration.  
* Tests and docs so others can reproduce the workflow.

**Upcoming polish**

* IaC/container scripts to deploy the judge automatically.  
* Stronger intent vetting using Llama Guard or OpenGuardrails.  
* Extended Dedalus tutorials with logging hooks for compliance teams.

Ways to extend it
-----------------

1. Drop in a secrets store (KMS, DynamoDB, Postgres) so judge state survives restarts.  
2. Pipe judge decisions into OpenTelemetry for easy dashboards.  
3. Swap the LiquidAI endpoint for another policy model if you want language coverage beyond JP/EN.

All of those upgrades live in the judge layer; the Dedalus worker and MCP adapter already know how to consume whatever sanitized payload you decide to emit. That is the whole point of this project: Dedalus stays productive while a dedicated LLM sandbox keeps everything safe, visible, and under your control.
