"""An MCP tool writing UTF-8 notes into a fixed project directory."""

from datetime import datetime
from pathlib import Path
from uuid import uuid4

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("WriteServer")
OUTPUT_DIR = Path(__file__).resolve().parent / "output"


@mcp.tool()
async def write_file(content: str) -> str:
    """将 content 字符串写入本地文本文件，返回保存路径。"""
    if not content.strip():
        return "写入失败：内容不能为空。"
    filename = f"note_{datetime.now():%Y%m%d_%H%M%S_%f}_{uuid4().hex[:8]}.txt"
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        path = OUTPUT_DIR / filename
        path.write_text(content, encoding="utf-8")
    except OSError:
        return "写入失败：请检查 output 目录的磁盘空间及写入权限。"
    return f"已成功写入文件: {path}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
