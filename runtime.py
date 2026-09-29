"""One lifecycle shared by the Web API and CLI entry points."""

import asyncio
import logging
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

from langchain_community.chat_models import ChatTongyi
from langchain_core.messages import HumanMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import create_react_agent

from configuration import PROJECT_ROOT, Settings, load_servers, resolve_connection

logger = logging.getLogger(__name__)
# Remote MCP URLs and weather request parameters may contain credentials.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


@dataclass
class AgentRuntime:
    agent: Any
    tool_names: list[str]
    degraded_servers: list[str]
    settings: Settings
    client: MultiServerMCPClient
    locks: dict[str, asyncio.Lock] = field(default_factory=dict)

    async def chat(self, message: str, thread_id: str) -> str:
        lock = self.locks.setdefault(thread_id, asyncio.Lock())
        async with lock:
            async with asyncio.timeout(self.settings.timeout_seconds):
                result = await self.agent.ainvoke(
                    {"messages": [HumanMessage(content=message)]},
                    {"configurable": {"thread_id": thread_id}, "recursion_limit": 40},
                )
        messages = result.get("messages", [])
        if not messages:
            return ""
        content = messages[-1].content
        if isinstance(content, str):
            return content
        return "\n".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        )


@asynccontextmanager
async def create_runtime(settings: Settings | None = None, *, model=None):
    settings = settings or Settings.from_environment()
    server_definitions = load_servers()
    connections = {}
    degraded = []
    for name, raw in server_definitions.items():
        if not raw.get("enabled", True):
            continue
        try:
            connections[name] = resolve_connection(raw)
        except (ValueError, TypeError):
            if not raw.get("optional", False):
                raise
            degraded.append(name)
            logger.warning("Optional MCP server configuration unavailable: %s", name)

    client = MultiServerMCPClient(connections)
    # SDK session contexts own subprocesses and sockets. Keep their entry and exit
    # in the lifespan task; MultiServerMCPClient has no cleanup() method.
    async with AsyncExitStack() as stack:
        tools = []
        for name in connections:
            server_stack = AsyncExitStack()
            try:
                session = await server_stack.enter_async_context(client.session(name))
                server_tools = await load_mcp_tools(session)
            except Exception as exc:
                await server_stack.aclose()
                if not server_definitions[name].get("optional", False):
                    raise RuntimeError(f"Required MCP server failed: {name}") from None
                degraded.append(name)
                logger.warning("Optional MCP server unavailable: %s (%s)", name, type(exc).__name__)
                continue
            await stack.enter_async_context(server_stack)
            tools.extend(server_tools)
        tool_names = [tool.name for tool in tools]
        if len(tool_names) != len(set(tool_names)):
            raise ValueError("MCP tool names must be unique across enabled servers")
        if not tools:
            raise RuntimeError("No MCP tools were discovered")
        if model is None:
            model = ChatTongyi(
                model=settings.model,
                dashscope_api_key=settings.api_key,
                streaming=False,
            )
        agent = create_react_agent(
            model=model,
            tools=tools,
            prompt=(PROJECT_ROOT / "agent_prompts.txt").read_text(encoding="utf-8"),
            checkpointer=InMemorySaver(),
        )
        logger.info("MCP tools loaded: %s", ", ".join(tool_names))
        yield AgentRuntime(agent, tool_names, degraded, settings, client)
    logger.info("MCP sessions closed")
