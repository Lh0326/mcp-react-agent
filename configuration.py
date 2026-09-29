"""Portable, environment-aware configuration for the MCP Agent."""

import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
ENV_PATTERN = re.compile(r"\$\{([A-Z][A-Z0-9_]*)(?::-([^}]*))?\}")


def expand_environment(value: Any) -> Any:
    if isinstance(value, str):
        def replace(match: re.Match) -> str:
            name = match.group(1)
            if name == "PYTHON_EXECUTABLE":
                return sys.executable
            result = os.getenv(name)
            if not result:
                if match.group(2) is not None:
                    return match.group(2)
                raise ValueError(f"Missing environment variable: {name}")
            return result
        return ENV_PATTERN.sub(replace, value)
    if isinstance(value, list):
        return [expand_environment(item) for item in value]
    if isinstance(value, dict):
        return {key: expand_environment(item) for key, item in value.items()}
    return value


@dataclass
class Settings:
    api_key: str
    model: str = "qwen-plus"
    timeout_seconds: float = 120
    cors_origins: list[str] = field(default_factory=lambda: [
        "http://localhost:5173", "http://127.0.0.1:5173",
    ])

    @classmethod
    def from_environment(cls) -> "Settings":
        load_dotenv(PROJECT_ROOT / ".env")
        api_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
        if not api_key:
            raise ValueError("请在 .env 中配置 DASHSCOPE_API_KEY，参考 .env.example")
        timeout = float(os.getenv("AGENT_TIMEOUT_SECONDS", "120"))
        if timeout <= 0:
            raise ValueError("AGENT_TIMEOUT_SECONDS must be positive")
        return cls(
            api_key=api_key,
            model=os.getenv("MODEL", "qwen-plus"),
            timeout_seconds=timeout,
            cors_origins=[origin.strip() for origin in os.getenv(
                "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173",
            ).split(",") if origin.strip()],
        )


def load_servers(path: Path | None = None) -> dict[str, dict[str, Any]]:
    path = path or PROJECT_ROOT / "servers_config.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    servers = data.get("mcpServers")
    if not isinstance(servers, dict) or not servers:
        raise ValueError("servers_config.json must contain a nonempty mcpServers object")
    return servers


def resolve_connection(raw: dict[str, Any]) -> dict[str, Any]:
    connection = expand_environment({
        key: value for key, value in raw.items() if key not in {"enabled", "optional"}
    })
    transport = connection.get("transport")
    if transport == "stdio":
        inherited = {name: os.environ[name] for name in (
            "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY", "SSL_CERT_FILE", "SSL_CERT_DIR",
        ) if name in os.environ}
        connection["env"] = {**inherited, "PYTHONUTF8": "1", **connection.get("env", {})}
        connection["args"] = [
            str((PROJECT_ROOT / arg).resolve())
            if arg.endswith(".py") and not Path(arg).is_absolute() else arg
            for arg in connection.get("args", [])
        ]
        connection.setdefault("cwd", str(PROJECT_ROOT))
    elif transport == "sse":
        if not connection.get("url", "").startswith(("https://", "http://")):
            raise ValueError("SSE server url must use http or https")
    else:
        raise ValueError("This project supports stdio and sse transports")
    return connection
