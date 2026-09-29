"""Interactive CLI using the same lifecycle as the Web API."""

import asyncio
import logging
from uuid import uuid4

from runtime import create_runtime


async def run_chat_loop() -> None:
    async with create_runtime() as agent_runtime:
        thread_id = uuid4().hex
        print("MCP Agent 已启动：输入 quit 退出，输入 /new 开启新对话。")
        while True:
            try:
                message = (await asyncio.to_thread(input, "\n你: ")).strip()
            except EOFError:
                break
            if message.lower() == "quit":
                break
            if message == "/new":
                thread_id = uuid4().hex
                print("已开启新对话。")
                continue
            if not message:
                continue
            try:
                print(f"\nAI: {await agent_runtime.chat(message, thread_id)}")
            except Exception as exc:
                print(f"请求失败（{type(exc).__name__}），请检查配置或重试。")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(run_chat_loop())
    except KeyboardInterrupt:
        print("\n已退出。")
