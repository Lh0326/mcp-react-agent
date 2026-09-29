import asyncio
import sys
from pathlib import Path

import httpx
import pytest

import configuration
import weather_server
import write_server
from configuration import expand_environment, resolve_connection


def test_local_connection_uses_active_interpreter_and_absolute_path():
    config = resolve_connection({
        "transport": "stdio", "command": "${PYTHON_EXECUTABLE}",
        "args": ["weather_server.py"], "enabled": True, "optional": False,
    })
    assert config["command"] == sys.executable
    assert Path(config["args"][0]).is_absolute()
    assert config["cwd"] == str(configuration.PROJECT_ROOT)
    assert "enabled" not in config and "optional" not in config


def test_missing_environment_variable_reports_name_without_value(monkeypatch):
    monkeypatch.delenv("TEST_MCP_SECRET", raising=False)
    with pytest.raises(ValueError, match="TEST_MCP_SECRET"):
        expand_environment({"url": "https://example.com/${TEST_MCP_SECRET}"})


def test_stdio_weather_credentials_are_explicit_and_utf8_is_portable(monkeypatch):
    monkeypatch.setenv("OPENWEATHER_API_KEY", "weather-test-key")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "model-test-key")
    config = resolve_connection(configuration.load_servers()["weather"])
    assert config["env"]["OPENWEATHER_API_KEY"] == "weather-test-key"
    assert config["env"]["PYTHONUTF8"] == "1"
    assert "DASHSCOPE_API_KEY" not in config["env"]
    monkeypatch.delenv("OPENWEATHER_API_KEY")
    assert resolve_connection(configuration.load_servers()["weather"])["env"]["OPENWEATHER_API_KEY"] == ""


async def test_concurrent_file_writes_do_not_overwrite(tmp_path, monkeypatch):
    monkeypatch.setattr(write_server, "OUTPUT_DIR", tmp_path)
    results = await asyncio.gather(*(write_server.write_file(f"note {n}") for n in range(10)))
    files = list(tmp_path.glob("*.txt"))
    assert len(set(results)) == len(files) == 10
    assert {p.read_text(encoding="utf-8") for p in files} == {f"note {n}" for n in range(10)}


async def test_weather_without_key_is_explicit_and_offline(monkeypatch):
    monkeypatch.delenv("OPENWEATHER_API_KEY", raising=False)
    result = await weather_server.query_weather("Beijing")
    assert "OPENWEATHER_API_KEY" in result and "失败" in result
    assert "夏季" in await weather_server.get_weather_tips("summer")


async def test_weather_geocoding_and_metric_units(monkeypatch):
    calls = []
    def handler(request):
        calls.append(request)
        if "/geo/" in request.url.path:
            return httpx.Response(200, json=[{"lat": 39.9, "lon": 116.4}])
        return httpx.Response(200, json={
            "name": "Beijing", "sys": {"country": "CN"},
            "main": {"temp": 25, "humidity": 40}, "weather": [], "wind": {"speed": 2},
        })
    original = httpx.AsyncClient
    monkeypatch.setenv("OPENWEATHER_API_KEY", "test-only-key")
    monkeypatch.setattr(weather_server.httpx, "AsyncClient", lambda **kwargs: original(
        **kwargs, transport=httpx.MockTransport(handler),
    ))
    result = await weather_server.query_weather("Beijing,CN")
    assert "25 °C" in result and "OpenWeather" in result
    assert len(calls) == 2
    assert calls[1].url.params["units"] == "metric"
    assert calls[1].url.params["lat"] == "39.9"


async def test_weather_error_does_not_expose_api_key(monkeypatch):
    original = httpx.AsyncClient
    monkeypatch.setenv("OPENWEATHER_API_KEY", "secret-that-must-not-leak")
    monkeypatch.setattr(weather_server.httpx, "AsyncClient", lambda **kwargs: original(
        **kwargs, transport=httpx.MockTransport(lambda request: httpx.Response(401)),
    ))
    result = await weather_server.query_weather("Beijing")
    assert "401" in result and "secret-that-must-not-leak" not in result


def test_malformed_weather_does_not_crash():
    assert "失败" in weather_server.format_weather({})
