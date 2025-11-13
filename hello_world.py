"""
Simple chat completion example using the Dedalus SDK.
"""

import asyncio
from dedalus_labs import AsyncDedalus, DedalusRunner
from dotenv import load_dotenv


load_dotenv()


async def main() -> None:
    client = AsyncDedalus()
    runner = DedalusRunner(client)

    response = await runner.run(
        input="What was the score of the 2025 Wimbledon final?",
        model="openai/gpt-5-mini",
        mcp_servers=["windsor/exa-search-mcp"],
    )

    print(response.final_output)


if __name__ == "__main__":
    asyncio.run(main())
