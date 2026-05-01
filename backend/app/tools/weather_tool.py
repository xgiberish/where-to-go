"""Live conditions tool — current weather (wttr.in) + routes from BEY (AviationStack).

Weather: wttr.in provides current conditions as JSON with no API key required.
Routes: AviationStack free plan (100 req/month) — set AVIATIONSTACK_API_KEY in .env.
        Without a key the route section degrades gracefully with an explanatory message.
        Note: free plan uses HTTP, not HTTPS.

All users depart from Beirut Rafic Hariri International (BEY).
"""
from typing import Any

import httpx
import structlog
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import Settings

log = structlog.get_logger()

# IATA airport codes for the 15 RAG-indexed destinations
DESTINATION_AIRPORTS: dict[str, str] = {
    "bangkok": "BKK",
    "kyoto": "KIX",       # Osaka Kansai — nearest international to Kyoto
    "bali": "DPS",
    "hanoi": "HAN",
    "siem reap": "REP",
    "kathmandu": "KTM",
    "singapore": "SIN",
    "luang prabang": "LPQ",
    "chiang mai": "CNX",
    "tokyo": "NRT",
    "pokhara": "PKR",
    "hoi an": "DAD",       # Da Nang — nearest international to Hoi An
    "penang": "PEN",
    "boracay": "MPH",      # Caticlan
    "colombo": "CMB",
}


class LiveConditionsInput(BaseModel):
    destination: str = Field(..., min_length=1, max_length=100, description="Destination city name")
    country: str = Field(..., min_length=1, max_length=100, description="Destination country name")


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
async def _fetch_weather(destination: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"https://wttr.in/{destination}?format=j1",
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()
        return resp.json()


async def _fetch_routes(destination: str, settings: Settings) -> str:
    api_key = settings.aviationstack_api_key

    if not api_key:
        return (
            "Route search not configured. "
            "Add AVIATIONSTACK_API_KEY to .env "
            "(free 100 req/month: https://aviationstack.com)."
        )

    iata = DESTINATION_AIRPORTS.get(destination.lower())
    if not iata:
        return f"No IATA airport code mapped for '{destination}'. Route search unavailable."

    # Free plan requires HTTP (not HTTPS)
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            "http://api.aviationstack.com/v1/routes",
            params={
                "access_key": api_key,
                "dep_iata": "BEY",
                "arr_iata": iata,
                "limit": "5",
            },
        )
        resp.raise_for_status()
        data = resp.json()

    routes = data.get("data") or []
    if not routes:
        return f"No routes found from BEY → {iata} ({destination})."

    lines = [f"Routes from Beirut (BEY) → {destination} ({iata}):"]
    for i, route in enumerate(routes[:5], 1):
        airline = route.get("airline", {})
        airline_name = airline.get("name", "Unknown airline")
        airline_iata = airline.get("iata", "")
        flight_num = (route.get("flight") or {}).get("iataNumber", "")
        label = f"{airline_name} ({airline_iata})" if airline_iata else airline_name
        flight_label = f" — flight {flight_num}" if flight_num else ""
        lines.append(f"  {i}. {label}{flight_label}")
    lines.append("Pricing and schedules: check Google Flights or the airline's website.")
    return "\n".join(lines)


def make_live_conditions_tool(settings: Settings) -> StructuredTool:
    """Return a LangChain StructuredTool for current weather + flights from BEY.

    Captures settings via closure — no global state.
    Weather comes from wttr.in (no key). Flights from Amadeus sandbox (keys optional).
    """

    async def _execute(destination: str, country: str) -> str:
        parts: list[str] = []

        # ── Weather ───────────────────────────────────────────────────────────
        try:
            data = await _fetch_weather(destination)
            cond = data.get("current_condition", [{}])[0]
            temp_c = cond.get("temp_C", "?")
            feels = cond.get("FeelsLikeC", "?")
            desc = cond.get("weatherDesc", [{"value": "?"}])[0]["value"]
            humidity = cond.get("humidity", "?")
            nearest = data.get("nearest_area", [{}])[0]
            area = nearest.get("areaName", [{"value": destination}])[0]["value"]
            parts.append(
                f"Current weather in {area}, {country}: "
                f"{desc}, {temp_c}°C (feels like {feels}°C), humidity {humidity}%"
            )
            log.info("weather_fetched", destination=destination, temp_c=temp_c, desc=desc)
        except Exception as exc:
            log.warning("weather_fetch_failed", destination=destination, error=str(exc))
            parts.append(f"Weather data unavailable for {destination}: {exc}")

        # ── Routes from BEY ──────────────────────────────────────────────────
        try:
            route_info = await _fetch_routes(destination, settings)
            parts.append(route_info)
        except Exception as exc:
            log.warning("routes_fetch_failed", destination=destination, error=str(exc))
            parts.append(f"Route data unavailable: {exc}")

        return "\n\n".join(parts)

    return StructuredTool.from_function(
        name="live_conditions",
        description=(
            "Get current weather AND flight options from Beirut (BEY) to the destination. "
            "Always call this for the recommended destination so the user has up-to-date "
            "conditions and can book flights from Lebanon."
        ),
        args_schema=LiveConditionsInput,
        coroutine=_execute,
    )
