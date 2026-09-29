"""FastAPI interface for the non-streaming ReAct Agent."""

import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from configuration import PROJECT_ROOT, Settings
from runtime import create_runtime

logger = logging.getLogger(__name__)
load_dotenv(PROJECT_ROOT / ".env")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings.from_environment()
    async with create_runtime(settings) as agent_runtime:
        app.state.runtime = agent_runtime
        try:
            yield
        finally:
            app.state.runtime = None


app = FastAPI(title="MCP ReAct Agent", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[item.strip() for item in os.getenv(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",") if item.strip()],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=20000)
    thread_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message cannot be blank")
        return value.strip()


class ChatResponse(BaseModel):
    content: str
    thread_id: str
    status: str = "success"
    error: str | None = None


def get_runtime(request: Request):
    agent_runtime = getattr(request.app.state, "runtime", None)
    if agent_runtime is None:
        raise HTTPException(status_code=503, detail="Agent 尚未就绪")
    return agent_runtime


@app.get("/health")
async def health(request: Request):
    agent_runtime = get_runtime(request)
    return {
        "status": "degraded" if agent_runtime.degraded_servers else "ok",
        "model": agent_runtime.settings.model,
        "tools": agent_runtime.tool_names,
        "degraded_servers": agent_runtime.degraded_servers,
    }


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(payload: ChatRequest, request: Request):
    agent_runtime = get_runtime(request)
    try:
        content = await agent_runtime.chat(payload.message, payload.thread_id)
        return ChatResponse(
            content=content, thread_id=payload.thread_id,
            status="success" if content else "empty",
        )
    except TimeoutError:
        return ChatResponse(
            content="", thread_id=payload.thread_id, status="error",
            error="处理超时，请稍后重试或开启新对话。",
        )
    except Exception as exc:
        logger.error("Agent request failed (%s)", type(exc).__name__)
        return ChatResponse(
            content="", thread_id=payload.thread_id, status="error",
            error="暂时无法完成请求，请检查模型服务或工具配置后重试。",
        )


if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    uvicorn.run(app, host="127.0.0.1", port=8000)
