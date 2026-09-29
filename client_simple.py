"""One-shot function invocation; web requests reuse the API lifespan."""

import argparse
import asyncio
from uuid import uuid4

from runtime import create_runtime


async def process_user_query(query: str) -> str:
    async with create_runtime() as agent_runtime:
        return await agent_runtime.chat(query, uuid4().hex)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run one MCP Agent query")
    parser.add_argument("query", nargs="?", default="请查询夏季天气提示并保存到文件。")
    args = parser.parse_args()
    print(asyncio.run(process_user_query(args.query)))
