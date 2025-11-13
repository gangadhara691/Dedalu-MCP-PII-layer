Dedalu Labs SDK Quickstart
==========================

This repo provisions a `dedalu` virtual environment with the `dedalus-labs` SDK preinstalled and provides two runnable examples that mirror the official quick-start snippets.

Prerequisites
-------------

* Python 3.11+
* A Dedalus API key stored in an `.env` file (see below)

Environment Setup
-----------------

```powershell
python -m venv dedalu
.\dedalu\Scripts\activate
pip install -r requirements.txt
```

> A pre-built `dedalu` environment already lives in this repo. Recreate it with the commands above if needed.

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

Running either script:

```powershell
.\dedalu\Scripts\python hello_world.py
.\dedalu\Scripts\python data_analyst_agent.py
```

Both scripts automatically load `.env`, so your API key never leaves local config.
