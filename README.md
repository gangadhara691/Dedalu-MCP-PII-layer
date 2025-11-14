Dedalu Labs SDK Quickstart
==========================

This repo provisions a `dedalu` virtual environment with the `dedalus-labs` SDK preinstalled and provides runnable examples that mirror the official quick-start snippets.

Prerequisites
-------------

* Python 3.11+
* Dedalus API key stored in an `.env` file (see below)

Environment Setup
-----------------

```powershell
python -m venv dedalu
.\dedalu\Scripts\activate
pip install -r requirements.txt
```

> A pre-built `dedalu` virtual environment already exists here. Recreate it with the commands above if needed.

Configuration
-------------

Copy `.env.example` to `.env` and drop your API key:

```
DEDALUS_API_KEY=sk-your-key
```

Examples
--------

* `hello_world.py` – minimal chat completion against `openai/gpt-5-mini`
* `data_analyst_agent.py` – multi-tool agent that streams responses while hitting Brave Search MCP
* `secure_pii_service.py` & `mcp_tool_adapter.py` – stateful PII vault surfaced as a stateless Dedalus MCP tool

Running the quick-start scripts:

```powershell
.\dedalu\Scripts\python hello_world.py
.\dedalu\Scripts\python data_analyst_agent.py
```

Testing the trust layer:

```powershell
.\dedalu\Scripts\python -m pytest
```

> **Dedalus agent runs require credentials.** The hello-world and analyst examples expect a valid `DEDALUS_API_KEY` plus access to the referenced MCP servers. Without that configuration, Dedalus requests fail at authentication—highlighting exactly why the PII proxy is built to operate independently of the hosted Dedalus control plane.

PII Protection Architecture
---------------------------

The `secure_pii_service.py` / `mcp_tool_adapter.py` pair demonstrates how to wrap a stateful, on-prem vault behind a stateless Dedalus MCP adapter:

1. Launch the FastAPI vault so it can store per-session placeholder maps:
   ```powershell
   .\dedalu\Scripts\python secure_pii_service.py
   ```
2. In a new shell, run the MCP proxy so Dedalus agents can access the vault via `sanitize`/`rehydrate` tools:
   ```powershell
   .\dedalu\Scripts\python mcp_tool_adapter.py
   ```
3. Register those tools with your Dedalus runner and pass a shared `session_id`. The runner calls `sanitize` before sending data to any untrusted LLM and `rehydrate` on the way back, keeping raw PII confined to the secure service.

Why this becomes the next AI trust layer
----------------------------------------

* **Stateful privacy boundary:** Sensitive placeholder→real mappings never leave `secure_pii_service.py`, yet the Dedalus agent remains stateless and compliant with MCP requirements.
* **Composable security:** Any agent—legal, finance, healthcare—can bolt on the MCP proxy without changing downstream tools. Only sanitized text reaches cloud LLMs.
* **Provable behavior:** Automated pytest coverage (`tests/test_secure_pii_service.py`) now spans round-trips, idempotency, session isolation, and error handling so adopters can verify correctness before integrating in regulated workflows.
