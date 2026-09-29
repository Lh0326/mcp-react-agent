import asyncio
import os
import socket
import subprocess
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult

import api_server
import runtime
from configuration import Settings


class ScriptedModel(BaseChatModel):
    """Deterministic model; the graph and stdio tools are real in this test."""

    @property
    def _llm_type(self):
        return "scripted-test-model"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        last = messages[-1]
        if isinstance(last, HumanMessage) and last.content == "save summer tips":
            reply = AIMessage(content="", tool_calls=[{
                "name": "get_weather_tips", "args": {"season": "summer"}, "id": "tips-call",
            }])
        elif isinstance(last, HumanMessage) and last.content == "echo over SSE":
            reply = AIMessage(content="", tool_calls=[{
                "name": "sse_echo", "args": {"text": "transport-ok"}, "id": "sse-call",
            }])
        elif isinstance(last, ToolMessage) and last.name == "get_weather_tips":
            reply = AIMessage(content="", tool_calls=[{
                "name": "write_file", "args": {"content": str(last.content)}, "id": "write-call",
            }])
        elif isinstance(last, ToolMessage):
            reply = AIMessage(content=f"Saved: {last.content}")
        else:
            user_messages = [str(m.content) for m in messages if isinstance(m, HumanMessage)]
            reply = AIMessage(content=" | ".join(user_messages))
        return ChatResult(generations=[ChatGeneration(message=reply)])


async def test_real_stdio_discovery_react_chain_and_thread_isolation():
    # No remote key is used. File tool has its fixed output directory.
    async with runtime.create_runtime(Settings(api_key="test-only"), model=ScriptedModel()) as agent:
        assert set(agent.tool_names) == {"query_weather", "get_weather_tips", "write_file"}
        assert agent.degraded_servers == []
        saved = await agent.chat("save summer tips", "chain-test")
        assert "Saved:" in saved and "note_" in saved
        first = await agent.chat("Alice", "session-a")
        second = await agent.chat("Bob", "session-b")
        continued = await agent.chat("remember", "session-a")
        assert first == "Alice"
        assert second == "Bob"
        assert continued == "Alice | remember" and "Bob" not in continued


async def test_optional_server_configuration_failure_preserves_local_tools(monkeypatch):
    definitions = runtime.load_servers()
    definitions["amap-maps"]["enabled"] = True
    monkeypatch.delenv("AMAP_MCP_SSE_URL", raising=False)
    monkeypatch.setattr(runtime, "load_servers", lambda: definitions)
    async with runtime.create_runtime(Settings(api_key="test-only"), model=ScriptedModel()) as agent:
        assert agent.degraded_servers == ["amap-maps"]
        assert len(agent.tool_names) == 3


async def test_required_server_failure_is_not_silent(monkeypatch):
    monkeypatch.setattr(runtime, "load_servers", lambda: {
        "broken": {"transport": "sse", "url": "not-a-url"},
    })
    with pytest.raises(ValueError):
        async with runtime.create_runtime(Settings(api_key="test-only"), model=ScriptedModel()):
            pass


async def test_real_sse_discovery_and_execution(monkeypatch):
    with socket.socket() as socket_probe:
        socket_probe.bind(("127.0.0.1", 0))
        port = socket_probe.getsockname()[1]
    flags = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    process = await asyncio.create_subprocess_exec(
        sys.executable, str(Path(__file__).parent / "fixtures" / "sse_server.py"), str(port),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **flags,
    )
    try:
        for _ in range(100):
            try:
                reader, writer = await asyncio.open_connection("127.0.0.1", port)
                writer.close()
                await writer.wait_closed()
                break
            except OSError:
                await asyncio.sleep(0.1)
        else:
            raise AssertionError("SSE fixture did not start")
        monkeypatch.setattr(runtime, "load_servers", lambda: {
            "sse-fixture": {"transport": "sse", "url": f"http://127.0.0.1:{port}/sse"},
        })
        async with runtime.create_runtime(Settings(api_key="test-only"), model=ScriptedModel()) as agent:
            assert agent.tool_names == ["sse_echo"]
            result = await agent.chat("echo over SSE", "sse-thread")
            assert "SSE received: transport-ok" in result
    finally:
        if process.returncode is None:
            process.terminate()
        await process.wait()


async def test_same_thread_serializes_invocations():
    active = 0
    peak = 0
    class Agent:
        async def ainvoke(self, *args):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.01)
            active -= 1
            return {"messages": [AIMessage(content="ok")]}
    agent = runtime.AgentRuntime(Agent(), [], [], Settings(api_key="test"), None)
    assert await asyncio.gather(agent.chat("one", "same"), agent.chat("two", "same")) == ["ok", "ok"]
    assert peak == 1


async def test_timeout_is_bounded():
    class Agent:
        async def ainvoke(self, *args):
            await asyncio.sleep(1)
    agent = runtime.AgentRuntime(
        Agent(), [], [], Settings(api_key="test", timeout_seconds=0.01), None,
    )
    with pytest.raises(TimeoutError):
        await agent.chat("hello", "timeout-test")


@pytest.fixture
def api_client(monkeypatch):
    class FakeRuntime:
        settings = Settings(api_key="test")
        tool_names = ["get_weather_tips"]
        degraded_servers = []

        async def chat(self, message, thread_id):
            if message == "fail":
                raise RuntimeError("secret-connection-url")
            return "hello"

    @asynccontextmanager
    async def fake_runtime(settings):
        yield FakeRuntime()

    monkeypatch.setattr(api_server.Settings, "from_environment", lambda: Settings(api_key="test"))
    monkeypatch.setattr(api_server, "create_runtime", fake_runtime)
    with TestClient(api_server.app) as client:
        yield client


def test_api_requires_valid_nonempty_message_and_thread(api_client):
    for payload in [{"message": "hi"}, {"message": " ", "thread_id": "one"},
                    {"message": "hi", "thread_id": "../bad"}]:
        assert api_client.post("/chat", json=payload).status_code == 422
    result = api_client.post("/chat", json={"message": "hi", "thread_id": "one"}).json()
    assert result == {"content": "hello", "thread_id": "one", "status": "success", "error": None}


def test_api_health_and_error_redaction(api_client):
    assert api_client.get("/health").json()["tools"] == ["get_weather_tips"]
    result = api_client.post("/chat", json={"message": "fail", "thread_id": "one"}).json()
    assert result["status"] == "error"
    assert "secret-connection-url" not in str(result)
