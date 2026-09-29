"""Weather tools implemented against OpenWeather's public HTTP API."""

import logging
import os
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv(Path(__file__).resolve().parent / ".env")
mcp = FastMCP("WeatherServer")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
GEOCODING_URL = "https://api.openweathermap.org/geo/1.0/direct"
CURRENT_WEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"
SEASON_TIPS = {
    "spring": "春季出行留意天气变化；有花粉过敏史时关注当地花粉情况。",
    "summer": "夏季尽量避开正午高温时段，安排饮水、遮阳与休息。",
    "autumn": "秋季早晚可能温差较大，出门前查看气温并准备可增减的外套。",
    "winter": "冬季注意低温和结冰预警，选择保暖衣物并留意路面状况。",
}


async def fetch_weather(city: str) -> dict[str, Any]:
    api_key = os.getenv("OPENWEATHER_API_KEY", "").strip()
    if not api_key:
        return {"error": "未配置 OPENWEATHER_API_KEY，暂时无法查询实时天气。"}
    if not city.strip():
        return {"error": "请提供城市英文名称，例如 Beijing,CN。"}
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            location_response = await client.get(
                GEOCODING_URL,
                params={"q": city.strip(), "limit": 1, "appid": api_key},
            )
            location_response.raise_for_status()
            locations = location_response.json()
            if not isinstance(locations, list) or not locations:
                return {"error": "未找到该城市，请补充英文城市名和国家代码。"}
            location = locations[0]
            response = await client.get(
                CURRENT_WEATHER_URL,
                params={"lat": location["lat"], "lon": location["lon"],
                        "appid": api_key, "units": "metric", "lang": "zh_cn"},
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        code = exc.response.status_code
        reason = {401: "天气服务凭据无效或尚未激活", 429: "天气服务请求额度已达上限"}.get(
            code, "天气服务暂时不可用",
        )
        return {"error": f"{reason}（HTTP {code}）。"}
    except httpx.RequestError:
        return {"error": "无法连接天气服务，请检查网络后重试。"}
    except (ValueError, KeyError, TypeError):
        return {"error": "天气服务返回了无法识别的数据。"}


def format_weather(data: dict[str, Any]) -> str:
    if "error" in data:
        return f"天气查询失败：{data['error']}"
    try:
        main = data["main"]
        conditions = data.get("weather") or [{}]
        place = f"{data.get('name', '未知城市')}, {data.get('sys', {}).get('country', '')}".strip(", ")
        return (
            f"### {place} 当前天气\n\n"
            f"- 天气：{conditions[0].get('description', '暂无描述')}\n"
            f"- 温度：{main['temp']} °C\n"
            f"- 湿度：{main.get('humidity', '未知')} %\n"
            f"- 风速：{data.get('wind', {}).get('speed', '未知')} m/s\n\n"
            "数据来源：OpenWeather。"
        )
    except (KeyError, TypeError, IndexError):
        return "天气查询失败：返回数据缺少必要字段。"


@mcp.tool()
async def query_weather(city: str) -> str:
    """查询英文城市名称的当前天气；可附国家代码，如 Beijing,CN。返回温度、湿度和风速。"""
    return format_weather(await fetch_weather(city))


@mcp.tool()
async def get_weather_tips(season: str) -> str:
    """获取季节出行提示。season 只接受 spring、summer、autumn、winter，不需要 API Key。"""
    return SEASON_TIPS.get(season.strip().lower(), "季节参数无效，请使用 spring、summer、autumn 或 winter。")


if __name__ == "__main__":
    mcp.run(transport="stdio")
