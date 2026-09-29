"""Local SSE transport fixture; no third-party credentials or services."""

import sys

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("SSEFixture", host="127.0.0.1", port=int(sys.argv[1]))


@mcp.tool()
async def sse_echo(text: str) -> str:
    """Echo text to verify SSE tool execution."""
    return f"SSE received: {text}"


if __name__ == "__main__":
    mcp.run(transport="sse")
