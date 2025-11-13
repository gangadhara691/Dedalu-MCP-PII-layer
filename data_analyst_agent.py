"""
Data analyst agent that can search the web and execute python snippets.
"""

import asyncio
from typing import Dict, Any

from dedalus_labs import AsyncDedalus, DedalusRunner
from dedalus_labs.utils.stream import stream_async
from dotenv import load_dotenv


load_dotenv()


def execute_python_code(code: str) -> str:
    """Execute a python snippet and surface the result or error."""
    namespace: Dict[str, Any] = {}
    try:
        exec(code, {"__builtins__": __builtins__}, namespace)
    except Exception as exc:  # pragma: no cover - surfaced via agent output
        return f"Error executing code: {exc}"

    if "result" in namespace:
        return str(namespace["result"])

    filtered = {k: v for k, v in namespace.items() if not k.startswith("_")}
    return str(filtered) if filtered else "Code executed successfully"


async def main() -> None:
    client = AsyncDedalus()
    runner = DedalusRunner(client)

    result = runner.run(
        input=(
            "Research the current stock price of Tesla (TSLA) and Apple (AAPL).\n"
            "Then write and execute Python code to:\n"
            "1. Compare their current prices\n"
            "2. Calculate the percentage difference\n"
            "3. Determine which stock has grown more in the past year\n"
            "4. Provide investment insights based on your analysis\n"
            "Use web search to get the latest stock information."
        ),
        model="openai/gpt-5",
        tools=[execute_python_code],
        mcp_servers=["windsor/brave-search-mcp"],
        stream=True,
    )

    await stream_async(result)


if __name__ == "__main__":
    asyncio.run(main())
