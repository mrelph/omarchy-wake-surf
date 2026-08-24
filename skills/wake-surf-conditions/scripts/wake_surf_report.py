#!/usr/bin/env python3
"""Create live Lake Washington wake-surf reports as text, JSON, or HTML.

The HTML output is a self-contained artifact: styles, an inline SVG chart, and
successfully fetched WSDOT camera JPEGs are embedded in the document. The
script uses only the Python standard library and requires no API keys.
"""

from __future__ import annotations

import argparse
import base64
import html
import json
import math
import os
import ssl
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


LATITUDE = 47.6415
LONGITUDE = -122.2570
LOCATION_LABEL = "SR 520 Bridge · Lake Washington"
TIMEZONE_NAME = "America/Los_Angeles"
PACIFIC = ZoneInfo(TIMEZONE_NAME)
USER_AGENT = "wake-surf-conditions-skill/1.0 (personal conditions report)"

OPEN_METEO_FORECAST = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_AIR = "https://air-quality-api.open-meteo.com/v1/air-quality"
NWS_ALERTS = "https://api.weather.gov/alerts/active"
LAKEMONSTER_PAGE = "https://lakemonster.com/lake/Washington/Lake-Washington-320"
WSDOT_IMAGE = "https://images.wsdot.wa.gov/nw/{camera_id}.jpg"

CAMERAS = (
    ("520vc00241", "SR 520 · Camera 1"),
    ("520vc00293", "SR 520 · Camera 2"),
    ("520vc00341", "SR 520 · Camera 3"),
)

# images.wsdot.wa.gov has intermittently omitted this public intermediate from
# its served chain. Supplying the issuer here is scoped to these camera fetches
# and still chains to a root in the system trust store.
WSDOT_ISSUER_PEM = """\
-----BEGIN CERTIFICATE-----
MIIFPDCCBCSgAwIBAgIQAWePH++IIlXYsKcOa3uyIDANBgkqhkiG9w0BAQsFADBh
MQswCQYDVQQGEwJVUzEVMBMGA1UEChMMRGlnaUNlcnQgSW5jMRkwFwYDVQQLExB3
d3cuZGlnaWNlcnQuY29tMSAwHgYDVQQDExdEaWdpQ2VydCBHbG9iYWwgUm9vdCBH
MjAeFw0yMDA3MDIxMjQyNTBaFw0zMDA3MDIxMjQyNTBaMEQxCzAJBgNVBAYTAlVT
MRUwEwYDVQQKEwxEaWdpQ2VydCBJbmMxHjAcBgNVBAMTFURpZ2lDZXJ0IEVWIFJT
QSBDQSBHMjCCASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoCggEBAK0eZsx/neTr
f4MXJz0R2fJTIDfN8AwUAu7hy4gI0vp7O8LAAHx2h3bbf8wl+pGMSxaJK9ffDDCD
63FqqFBqE9eTmo3RkgQhlu55a04LsXRLcK6crkBOO0djdonybmhrfGrtBqYvbRat
xenkv0Sg4frhRl4wYh4dnW0LOVRGhbt1G5Q19zm9CqMlq7LlUdAE+6d3a5++ppfG
cnWLmbEVEcLHPAnbl+/iKauQpQlU1Mi+wEBnjE5tK8Q778naXnF+DsedQJ7NEi+b
QoonTHEz9ryeEcUHuQTv7nApa/zCqes5lXn1pMs4LZJ3SVgbkTLj+RbBov/uiwTX
tkBEWawvZH8CAwEAAaOCAgswggIHMB0GA1UdDgQWBBRqTlC/mGidW3sgddRZAXlI
ZpIyBjAfBgNVHSMEGDAWgBROIlQgGJXm427mD/r6uRLtBhePOTAOBgNVHQ8BAf8E
BAMCAYYwHQYDVR0lBBYwFAYIKwYBBQUHAwEGCCsGAQUFBwMCMBIGA1UdEwEB/wQI
MAYBAf8CAQAwNAYIKwYBBQUHAQEEKDAmMCQGCCsGAQUFBzABhhhodHRwOi8vb2Nz
cC5kaWdpY2VydC5jb20wewYDVR0fBHQwcjA3oDWgM4YxaHR0cDovL2NybDMuZGln
aWNlcnQuY29tL0RpZ2lDZXJ0R2xvYmFsUm9vdEcyLmNybDA3oDWgM4YxaHR0cDov
L2NybDQuZGlnaWNlcnQuY29tL0RpZ2lDZXJ0R2xvYmFsUm9vdEcyLmNybDCBzgYD
VR0gBIHGMIHDMIHABgRVHSAAMIG3MCgGCCsGAQUFBwIBFhxodHRwczovL3d3dy5k
aWdpY2VydC5jb20vQ1BTMIGKBggrBgEFBQcCAjB+DHxBbnkgdXNlIG9mIHRoaXMg
Q2VydGlmaWNhdGUgY29uc3RpdHV0ZXMgYWNjZXB0YW5jZSBvZiB0aGUgUmVseWlu
ZyBQYXJ0eSBBZ3JlZW1lbnQgbG9jYXRlZCBhdCBodHRwczovL3d3dy5kaWdpY2Vy
dC5jb20vcnBhLXVhMA0GCSqGSIb3DQEBCwUAA4IBAQBSMgrCdY2+O9spnYNvwHiG
+9lCJbyELR0UsoLwpzGpSdkHD7pVDDFJm3//B8Es+17T1o5Hat+HRDsvRr7d3MEy
o9iXkkxLhKEgApA2Ft2eZfPrTolc95PwSWnn3FZ8BhdGO4brTA4+zkPSKoMXi/X+
WLBNN29Z/nbCS7H/qLGt7gViEvTIdU8x+H4l/XigZMUDaVmJ+B5d7cwSK7yOoQdf
oIBGmA5Mp4LhMzo52rf//kXPfE3wYIZVHqVuxxlnTkFYmffCX9/Lon7SWaGdg6Rc
k4RHhHLWtmz2lTZ5CEo2ljDsGzCFGJP7oT4q6Q8oFC38irvdKIJ95cUxYzj4tnOI
-----END CERTIFICATE-----
"""


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return now_utc().isoformat(timespec="seconds")


def as_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def rounded(value: Any, digits: int = 0) -> int | float | None:
    number = as_number(value)
    if number is None:
        return None
    return round(number, digits) if digits else round(number)


def fahrenheit(celsius: Any) -> float | None:
    number = as_number(celsius)
    return None if number is None else number * 9 / 5 + 32


def temperature_record(celsius: Any) -> dict[str, float | None]:
    c = as_number(celsius)
    return {
        "c": None if c is None else round(c, 1),
        "f": None if c is None else round(fahrenheit(c), 1),
    }


def format_temperature(record: dict[str, Any] | None, compact: bool = False) -> str:
    if not record or as_number(record.get("c")) is None:
        return "—"
    c = round(float(record["c"]))
    f = round(float(record["f"]))
    return f"{c}/{f}" if compact else f"{c}°C / {f}°F"


def compass_direction(degrees: Any) -> str:
    value = as_number(degrees)
    if value is None:
        return "—"
    directions = (
        "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
        "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
    )
    return directions[round(value / 22.5) % 16]


def condition_label(code: Any) -> str:
    value = rounded(code)
    if value == 0:
        return "Clear"
    if value in (1, 2):
        return "Partly Cloudy"
    if value == 3:
        return "Cloudy"
    if value in (45, 48):
        return "Fog"
    if value in (51, 53, 55):
        return "Drizzle"
    if value in (56, 57):
        return "Freezing Drizzle"
    if value in (61, 63, 65):
        return "Rain"
    if value in (66, 67):
        return "Freezing Rain"
    if value in (71, 73, 75, 77):
        return "Snow"
    if value in (80, 81, 82):
        return "Rain Showers"
    if value in (85, 86):
        return "Snow Showers"
    if value in (95, 96, 99):
        return "Thunderstorm"
    return "Unknown"


def condition_emoji(code: Any) -> str:
    value = rounded(code)
    if value == 0:
        return "☀️"
    if value in (1, 2):
        return "🌤️"
    if value == 3:
        return "☁️"
    if value in (45, 48):
        return "🌫️"
    if value in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82):
        return "🌧️"
    if value in (71, 73, 75, 77, 85, 86):
        return "🌨️"
    if value in (95, 96, 99):
        return "⛈️"
    return "•"


def aqi_category(value: Any) -> str:
    number = as_number(value)
    if number is None:
        return "Unavailable"
    if number <= 50:
        return "Good"
    if number <= 100:
        return "Moderate"
    if number <= 150:
        return "Unhealthy for sensitive groups"
    if number <= 200:
        return "Unhealthy"
    if number <= 300:
        return "Very unhealthy"
    return "Hazardous"


def uv_category(value: Any) -> str:
    number = as_number(value)
    if number is None:
        return "Unavailable"
    if number < 3:
        return "Low"
    if number < 6:
        return "Moderate"
    if number < 8:
        return "High"
    if number < 11:
        return "Very high"
    return "Extreme"


def local_datetime(raw: Any) -> datetime | None:
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(str(raw))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=PACIFIC)
    return parsed.astimezone(PACIFIC)


def hour_label(moment: datetime) -> str:
    return moment.strftime("%I%p").lstrip("0")


def report_time_label(moment: datetime, *, long: bool = False) -> str:
    hour = moment.strftime("%I").lstrip("0") or "12"
    clock = f"{hour}:{moment.strftime('%M %p %Z')}"
    if long:
        return f"{moment.strftime('%A, %B')} {moment.day} · {clock}"
    return f"{moment.strftime('%a %b')} {moment.day}, {clock}"


def http_bytes(
    url: str,
    timeout: float,
    *,
    headers: dict[str, str] | None = None,
    context: ssl.SSLContext | None = None,
) -> bytes:
    request_headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    if headers:
        request_headers.update(headers)
    request = urllib.request.Request(url, headers=request_headers)
    with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status}")
        return response.read()


def http_json(url: str, timeout: float, *, headers: dict[str, str] | None = None) -> dict[str, Any]:
    payload = http_bytes(url, timeout, headers=headers)
    decoded = json.loads(payload.decode("utf-8"))
    if not isinstance(decoded, dict):
        raise ValueError("expected a JSON object")
    return decoded


def forecast_url() -> str:
    query = urllib.parse.urlencode(
        {
            "latitude": LATITUDE,
            "longitude": LONGITUDE,
            "current": "temperature_2m,wind_speed_10m,wind_direction_10m,wind_gusts_10m,weather_code,is_day",
            "hourly": "temperature_2m,wind_speed_10m,wind_gusts_10m,weather_code,precipitation_probability",
            "daily": "temperature_2m_max,weather_code,uv_index_max",
            "forecast_days": 7,
            "wind_speed_unit": "mph",
            "timezone": TIMEZONE_NAME,
        }
    )
    return f"{OPEN_METEO_FORECAST}?{query}"


def air_quality_url() -> str:
    query = urllib.parse.urlencode(
        {
            "latitude": LATITUDE,
            "longitude": LONGITUDE,
            "current": "uv_index,us_aqi",
            "timezone": TIMEZONE_NAME,
        }
    )
    return f"{OPEN_METEO_AIR}?{query}"


def alerts_url() -> str:
    query = urllib.parse.urlencode({"point": f"{LATITUDE},{LONGITUDE}"})
    return f"{NWS_ALERTS}?{query}"


def value_at(values: Any, index: int) -> Any:
    return values[index] if isinstance(values, list) and index < len(values) else None


def weather_entry(data: dict[str, Any], index: int, moment: datetime) -> dict[str, Any]:
    hourly = data.get("hourly") if isinstance(data.get("hourly"), dict) else {}
    code = value_at(hourly.get("weather_code"), index)
    return {
        "time": moment.isoformat(),
        "label": hour_label(moment),
        "temperature": temperature_record(value_at(hourly.get("temperature_2m"), index)),
        "windMph": rounded(value_at(hourly.get("wind_speed_10m"), index), 1),
        "gustMph": rounded(value_at(hourly.get("wind_gusts_10m"), index), 1),
        "rainChancePct": rounded(value_at(hourly.get("precipitation_probability"), index)),
        "weatherCode": rounded(code),
        "condition": condition_label(code),
        "emoji": condition_emoji(code),
    }


def normalize_weather(data: dict[str, Any], generated: datetime) -> dict[str, Any]:
    current_raw = data.get("current") if isinstance(data.get("current"), dict) else {}
    hourly = data.get("hourly") if isinstance(data.get("hourly"), dict) else {}
    daily = data.get("daily") if isinstance(data.get("daily"), dict) else {}
    if as_number(current_raw.get("temperature_2m")) is None and current_raw.get("weather_code") is None:
        raise ValueError("forecast response did not contain current conditions")

    local_now = generated.astimezone(PACIFIC)
    times = hourly.get("time") if isinstance(hourly.get("time"), list) else []
    parsed_times = [local_datetime(item) for item in times]

    nearest_index: int | None = None
    nearest_delta: float | None = None
    for index, moment in enumerate(parsed_times):
        if moment is None:
            continue
        delta = abs((moment - local_now).total_seconds())
        if nearest_delta is None or delta < nearest_delta:
            nearest_index, nearest_delta = index, delta

    current_code = current_raw.get("weather_code")
    current = {
        "time": str(current_raw.get("time") or generated.astimezone(PACIFIC).isoformat()),
        "temperature": temperature_record(current_raw.get("temperature_2m")),
        "windMph": rounded(current_raw.get("wind_speed_10m"), 1),
        "gustMph": rounded(current_raw.get("wind_gusts_10m"), 1),
        "windDirectionDeg": rounded(current_raw.get("wind_direction_10m")),
        "windDirection": compass_direction(current_raw.get("wind_direction_10m")),
        "rainChancePct": (
            rounded(value_at(hourly.get("precipitation_probability"), nearest_index))
            if nearest_index is not None
            else None
        ),
        "weatherCode": rounded(current_code),
        "condition": condition_label(current_code),
        "emoji": condition_emoji(current_code),
        "isDay": bool(current_raw.get("is_day")),
    }

    cutoff = local_now - timedelta(minutes=30)
    hourly_today = [
        weather_entry(data, index, moment)
        for index, moment in enumerate(parsed_times)
        if moment is not None and moment.date() == local_now.date() and moment >= cutoff
    ]

    tomorrow_date = local_now.date() + timedelta(days=1)

    def nearest_tomorrow(target_hour: int) -> dict[str, Any] | None:
        candidates = [
            (abs(moment.hour - target_hour), index, moment)
            for index, moment in enumerate(parsed_times)
            if moment is not None and moment.date() == tomorrow_date
        ]
        if not candidates:
            return None
        _, index, moment = min(candidates, key=lambda item: item[0])
        return weather_entry(data, index, moment)

    tomorrow_uv = None
    daily_times = daily.get("time") if isinstance(daily.get("time"), list) else []
    for index, raw_day in enumerate(daily_times):
        if str(raw_day) == tomorrow_date.isoformat():
            tomorrow_uv = rounded(value_at(daily.get("uv_index_max"), index), 1)
            break

    week = []
    for index, raw_day in enumerate(daily_times[:7]):
        try:
            day = date.fromisoformat(str(raw_day))
        except ValueError:
            continue
        code = value_at(daily.get("weather_code"), index)
        week.append(
            {
                "date": day.isoformat(),
                "label": "Today" if day == local_now.date() else day.strftime("%a"),
                "high": temperature_record(value_at(daily.get("temperature_2m_max"), index)),
                "weatherCode": rounded(code),
                "condition": condition_label(code),
                "emoji": condition_emoji(code),
            }
        )

    return {
        "current": current,
        "hourlyToday": hourly_today,
        "tomorrow": {
            "morning": nearest_tomorrow(9),
            "evening": nearest_tomorrow(18),
            "uvIndex": tomorrow_uv,
            "uvCategory": uv_category(tomorrow_uv),
        },
        "weekAhead": week,
    }


def fetch_water_temperature(timeout: float) -> dict[str, Any]:
    page = http_bytes(LAKEMONSTER_PAGE, timeout).decode("utf-8", errors="replace")
    escaped_quote = chr(92) + chr(34)
    anchor_text = escaped_quote + "imgUrl" + escaped_quote + ":" + escaped_quote + "320.jpg"
    anchor = page.find(anchor_text)
    if anchor < 0:
        raise ValueError("Lake Washington record not found in page")
    key = escaped_quote + "waterTemp" + escaped_quote + ":" + escaped_quote
    start = page.find(key, anchor, anchor + 4000)
    if start < 0:
        raise ValueError("water temperature field not found")
    start += len(key)
    end = page.find(escaped_quote, start)
    if end < 0:
        raise ValueError("water temperature value was incomplete")
    temp_f = float(page[start:end])
    temp_c = (temp_f - 32) * 5 / 9
    return {
        "ok": True,
        "temperature": temperature_record(temp_c),
        "fetchedAt": iso_now(),
        "source": "LakeMonster",
    }


def normalize_air_quality(data: dict[str, Any]) -> dict[str, Any]:
    current = data.get("current") if isinstance(data.get("current"), dict) else {}
    uv = rounded(current.get("uv_index"), 1)
    aqi = rounded(current.get("us_aqi"))
    return {
        "ok": uv is not None or aqi is not None,
        "uvIndex": uv,
        "uvCategory": uv_category(uv),
        "usAqi": aqi,
        "aqiCategory": aqi_category(aqi),
    }


def normalize_alerts(data: dict[str, Any]) -> list[dict[str, str]]:
    alerts = []
    features = data.get("features") if isinstance(data.get("features"), list) else []
    for feature in features:
        props = feature.get("properties") if isinstance(feature, dict) else None
        if not isinstance(props, dict):
            continue
        alerts.append(
            {
                "event": str(props.get("event") or "Alert"),
                "headline": str(props.get("headline") or ""),
                "severity": str(props.get("severity") or "Unknown"),
                "urgency": str(props.get("urgency") or "Unknown"),
                "web": str(props.get("web") or props.get("@id") or ""),
            }
        )
    return alerts


def camera_ssl_context() -> ssl.SSLContext:
    context = ssl.create_default_context()
    context.load_default_certs()
    context.load_verify_locations(cadata=WSDOT_ISSUER_PEM)
    return context


def fetch_camera(camera_id: str, label: str, timeout: float) -> dict[str, Any]:
    url = WSDOT_IMAGE.format(camera_id=camera_id)
    payload = http_bytes(url, timeout, context=camera_ssl_context())
    if not payload.startswith(b"\xff\xd8\xff"):
        raise ValueError("WSDOT response was not a JPEG")
    return {
        "id": camera_id,
        "label": label,
        "url": url,
        "ok": True,
        "status": "available",
        "bytes": len(payload),
        "fetchedAt": iso_now(),
        "dataUri": "data:image/jpeg;base64," + base64.b64encode(payload).decode("ascii"),
    }


def error_text(error: BaseException) -> str:
    if isinstance(error, urllib.error.HTTPError):
        return f"HTTP {error.code}"
    if isinstance(error, urllib.error.URLError):
        return str(error.reason)
    return str(error) or error.__class__.__name__


def gather_report(timeout: float, include_cameras: bool) -> dict[str, Any]:
    generated = now_utc()
    report: dict[str, Any] = {
        "schemaVersion": 1,
        "generatedAt": generated.isoformat(timespec="seconds"),
        "location": {
            "label": LOCATION_LABEL,
            "latitude": LATITUDE,
            "longitude": LONGITUDE,
            "timezone": TIMEZONE_NAME,
        },
        "weather": None,
        "water": {"ok": False, "temperature": {"c": None, "f": None}, "source": "LakeMonster"},
        "airQuality": {"ok": False, "uvIndex": None, "usAqi": None},
        "alerts": [],
        "cameras": [
            {
                "id": camera_id,
                "label": label,
                "url": WSDOT_IMAGE.format(camera_id=camera_id),
                "ok": None,
                "status": "not-fetched",
            }
            for camera_id, label in CAMERAS
        ],
        "errors": {},
        "sources": [
            {"name": "Open-Meteo Forecast", "url": OPEN_METEO_FORECAST},
            {"name": "Open-Meteo Air Quality", "url": OPEN_METEO_AIR},
            {"name": "National Weather Service", "url": NWS_ALERTS},
            {"name": "LakeMonster", "url": LAKEMONSTER_PAGE},
            {"name": "WSDOT Traffic Cameras", "url": "https://wsdot.com/Travel/Real-time/Map/"},
        ],
    }

    tasks: dict[Any, tuple[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=7) as executor:
        tasks[executor.submit(http_json, forecast_url(), timeout)] = ("weather", None)
        tasks[executor.submit(http_json, air_quality_url(), timeout)] = ("airQuality", None)
        tasks[executor.submit(
            http_json,
            alerts_url(),
            timeout,
            headers={"Accept": "application/geo+json"},
        )] = ("alerts", None)
        tasks[executor.submit(fetch_water_temperature, timeout)] = ("water", None)
        if include_cameras:
            for camera_id, label in CAMERAS:
                tasks[executor.submit(fetch_camera, camera_id, label, timeout)] = (
                    "camera",
                    camera_id,
                )

        for future in as_completed(tasks):
            source, identity = tasks[future]
            try:
                result = future.result()
                if source == "weather":
                    report["weather"] = normalize_weather(result, generated)
                elif source == "airQuality":
                    report["airQuality"] = normalize_air_quality(result)
                elif source == "alerts":
                    report["alerts"] = normalize_alerts(result)
                elif source == "water":
                    report["water"] = result
                elif source == "camera":
                    for index, camera in enumerate(report["cameras"]):
                        if camera["id"] == identity:
                            report["cameras"][index] = result
                            break
            except Exception as error:  # Partial reports are intentional.
                key = f"camera:{identity}" if source == "camera" else source
                message = error_text(error)
                report["errors"][key] = message
                if source == "camera":
                    for camera in report["cameras"]:
                        if camera["id"] == identity:
                            camera["ok"] = False
                            camera["status"] = "unavailable"
                            camera["error"] = message
                            break

    return report


def format_wind(
    entry: dict[str, Any] | None,
    include_direction: bool = False,
    include_gusts: bool = True,
) -> str:
    if not entry or as_number(entry.get("windMph")) is None:
        return "—"
    wind = round(float(entry["windMph"]))
    gust = as_number(entry.get("gustMph"))
    direction = f" {entry.get('windDirection', '')}" if include_direction else ""
    result = f"{wind} mph{direction}".rstrip()
    if include_gusts and gust is not None and round(gust) - wind >= 3:
        result += f", gusts {round(gust)}"
    return result


def render_text(report: dict[str, Any]) -> str:
    generated = local_datetime(report.get("generatedAt"))
    generated_label = report_time_label(generated) if generated else "unknown time"
    weather = report.get("weather") or {}
    current = weather.get("current") or {}
    water = report.get("water") or {}
    air = report.get("airQuality") or {}

    lines = [
        f"Wake Surf Conditions — {LOCATION_LABEL}",
        f"Updated {generated_label}",
        "",
    ]
    if current:
        lines.extend(
            [
                f"{current.get('emoji', '•')} {current.get('condition', 'Unknown')}",
                f"Air {format_temperature(current.get('temperature'))} · "
                f"Water {format_temperature(water.get('temperature'))}",
                f"Wind {format_wind(current, include_direction=True)} · "
                f"Rain {current.get('rainChancePct') if current.get('rainChancePct') is not None else '—'}%",
                f"AQI {air.get('usAqi') if air.get('usAqi') is not None else '—'} "
                f"({air.get('aqiCategory', 'Unavailable')}) · "
                f"UV {air.get('uvIndex') if air.get('uvIndex') is not None else '—'} "
                f"({air.get('uvCategory', 'Unavailable')})",
            ]
        )
    else:
        lines.append("Current weather unavailable.")

    alerts = report.get("alerts") or []
    lines.append("")
    if alerts:
        lines.append("Active alerts:")
        for alert in alerts:
            lines.append(f"  ⚠ {alert.get('event', 'Alert')} — {alert.get('headline', '')}".rstrip(" —"))
    else:
        lines.append("Active NWS alerts: none reported")

    hourly = weather.get("hourlyToday") or []
    lines.extend(["", "Today by hour (°C/°F, wind):"])
    if hourly:
        for entry in hourly:
            lines.append(
                f"  {entry['label']:>4} {entry['emoji']} "
                f"{format_temperature(entry.get('temperature'), compact=True):>5} · "
                f"{round(entry['windMph']) if entry.get('windMph') is not None else '—'} mph"
            )
    else:
        lines.append("  No more forecast hours today")

    tomorrow = weather.get("tomorrow") or {}
    lines.extend(["", "Tomorrow:"])
    for label, key in (("Morning", "morning"), ("Evening", "evening")):
        entry = tomorrow.get(key)
        if entry:
            lines.append(
                f"  {label}: {entry['emoji']} {format_temperature(entry.get('temperature'))} · "
                f"{format_wind(entry)}"
            )
    lines.append(
        f"  UV max: {tomorrow.get('uvIndex') if tomorrow.get('uvIndex') is not None else '—'}"
    )

    week = weather.get("weekAhead") or []
    if week:
        lines.extend(["", "Week ahead highs (°C/°F):"])
        lines.append(
            "  " + "  ".join(
                f"{day['label']} {day['emoji']} {format_temperature(day.get('high'), compact=True)}"
                for day in week
            )
        )

    if report.get("errors"):
        lines.extend(["", "Data notes:"])
        for source, message in report["errors"].items():
            lines.append(f"  {source}: {message}")

    lines.extend(
        [
            "",
            "Sources: Open-Meteo, NWS, LakeMonster, WSDOT",
            "Conditions are observational context, not a boating-safety guarantee.",
        ]
    )
    return "\n".join(lines) + "\n"


def public_report(report: dict[str, Any]) -> dict[str, Any]:
    rendered = json.loads(json.dumps(report))
    for camera in rendered.get("cameras", []):
        camera.pop("dataUri", None)
    return rendered


def svg_hourly_chart(entries: list[dict[str, Any]]) -> str:
    usable = [
        entry for entry in entries
        if as_number((entry.get("temperature") or {}).get("f")) is not None
        and as_number(entry.get("windMph")) is not None
    ]
    if len(usable) < 2:
        return '<div class="empty">Not enough hourly data to draw the chart.</div>'

    width, height = 1040, 280
    left, right, top, bottom = 54, 30, 32, 58
    plot_width = width - left - right
    plot_height = height - top - bottom
    temperatures = [float(entry["temperature"]["f"]) for entry in usable]
    winds = [float(entry["windMph"]) for entry in usable]
    min_temp, max_temp = min(temperatures), max(temperatures)
    if min_temp == max_temp:
        min_temp -= 1
        max_temp += 1
    max_wind = max(max(winds), 5.0)

    def x_at(index: int) -> float:
        return left + index * plot_width / (len(usable) - 1)

    def temp_y(value: float) -> float:
        return top + (max_temp - value) * plot_height / (max_temp - min_temp)

    def wind_y(value: float) -> float:
        return top + (max_wind - value) * plot_height / max_wind

    temp_points = " ".join(f"{x_at(i):.1f},{temp_y(value):.1f}" for i, value in enumerate(temperatures))
    wind_points = " ".join(f"{x_at(i):.1f},{wind_y(value):.1f}" for i, value in enumerate(winds))

    grid = []
    for step in range(5):
        y = top + step * plot_height / 4
        grid.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width-right}" y2="{y:.1f}" class="grid-line"/>')

    labels = []
    stride = 2 if len(usable) > 10 else 1
    for index, entry in enumerate(usable):
        if index % stride and index != len(usable) - 1:
            continue
        labels.append(
            f'<text x="{x_at(index):.1f}" y="{height-22}" text-anchor="middle" class="axis-label">'
            f'{html.escape(str(entry.get("label", "")))}</text>'
        )

    dots = []
    for index, (temp, wind) in enumerate(zip(temperatures, winds)):
        dots.append(f'<circle cx="{x_at(index):.1f}" cy="{temp_y(temp):.1f}" r="3.2" class="temp-dot"/>')
        dots.append(f'<circle cx="{x_at(index):.1f}" cy="{wind_y(wind):.1f}" r="3.2" class="wind-dot"/>')

    return f"""
<svg class="hourly-chart" viewBox="0 0 {width} {height}" role="img" aria-label="Hourly air temperature and wind chart">
  {''.join(grid)}
  <text x="{left}" y="18" class="legend temp-legend">● AIR TEMP °F</text>
  <text x="190" y="18" class="legend wind-legend">● WIND MPH</text>
  <text x="{width-right}" y="18" text-anchor="end" class="range-label">{round(max_temp)}°–{round(min_temp)}°F · wind to {round(max_wind)} mph</text>
  <polyline points="{temp_points}" class="temp-line"/>
  <polyline points="{wind_points}" class="wind-line"/>
  {''.join(dots)}
  {''.join(labels)}
</svg>"""


def metric_card(label: str, value: str, detail: str = "", urgent: bool = False) -> str:
    urgent_class = " urgent" if urgent else ""
    return (
        f'<article class="metric{urgent_class}"><div class="eyebrow">{html.escape(label)}</div>'
        f'<div class="metric-value">{html.escape(value)}</div>'
        f'<div class="metric-detail">{html.escape(detail)}</div></article>'
    )


def render_html(report: dict[str, Any]) -> str:
    generated = local_datetime(report.get("generatedAt"))
    generated_label = report_time_label(generated, long=True) if generated else "Unknown time"
    weather = report.get("weather") or {}
    current = weather.get("current") or {}
    water = report.get("water") or {}
    air = report.get("airQuality") or {}
    hourly = weather.get("hourlyToday") or []
    tomorrow = weather.get("tomorrow") or {}
    week = weather.get("weekAhead") or []

    alerts_html = ""
    if report.get("alerts"):
        alert_cards = []
        for alert in report["alerts"]:
            headline = alert.get("headline") or alert.get("event") or "Active alert"
            alert_cards.append(
                '<article class="alert"><span class="alert-icon">⚠</span><div>'
                f'<strong>{html.escape(str(alert.get("event") or "Alert"))}</strong>'
                f'<p>{html.escape(str(headline))}</p></div></article>'
            )
        alerts_html = '<section class="alerts" aria-label="Active weather alerts">' + "".join(alert_cards) + "</section>"

    metrics = "".join(
        [
            metric_card("AIR TEMP", format_temperature(current.get("temperature")), current.get("condition", "Unavailable")),
            metric_card("WATER TEMP", format_temperature(water.get("temperature")), "LakeMonster" if water.get("ok") else "Unavailable"),
            metric_card("WIND", format_wind(current, include_direction=True, include_gusts=False), "Sustained"),
            metric_card("GUSTS", f"{rounded(current.get('gustMph'))} mph" if rounded(current.get("gustMph")) is not None else "—", "Current"),
            metric_card("RAIN CHANCE", f"{current.get('rainChancePct')}%" if current.get("rainChancePct") is not None else "—", "Nearest hour"),
            metric_card("AIR QUALITY", str(air.get("usAqi") if air.get("usAqi") is not None else "—"), air.get("aqiCategory", "Unavailable"), (air.get("usAqi") or 0) > 100),
            metric_card("UV INDEX", str(air.get("uvIndex") if air.get("uvIndex") is not None else "—"), air.get("uvCategory", "Unavailable")),
        ]
    )

    hourly_cards = "".join(
        '<article class="hour-card">'
        f'<div class="hour-label">{html.escape(str(entry.get("label", "")))}</div>'
        f'<div class="weather-icon">{entry.get("emoji", "•")}</div>'
        f'<strong>{format_temperature(entry.get("temperature"), compact=True)}</strong>'
        f'<span>{rounded(entry.get("windMph")) if rounded(entry.get("windMph")) is not None else "—"} mph</span>'
        '</article>'
        for entry in hourly
    ) or '<div class="empty">No more forecast hours today.</div>'

    tomorrow_cards = []
    for label, key in (("MORNING · 9AM", "morning"), ("EVENING · 6PM", "evening")):
        entry = tomorrow.get(key)
        if entry:
            tomorrow_cards.append(
                '<article class="tomorrow-card">'
                f'<div class="eyebrow">{label}</div>'
                f'<div class="tomorrow-main"><span>{entry.get("emoji", "•")}</span>'
                f'<strong>{format_temperature(entry.get("temperature"))}</strong></div>'
                f'<p>{html.escape(format_wind(entry))}</p></article>'
            )
    tomorrow_cards.append(
        '<article class="tomorrow-card uv-card"><div class="eyebrow">UV MAX</div>'
        f'<div class="uv-value">{html.escape(str(tomorrow.get("uvIndex") if tomorrow.get("uvIndex") is not None else "—"))}</div>'
        f'<p>{html.escape(str(tomorrow.get("uvCategory", "Unavailable")))}</p></article>'
    )

    week_cards = "".join(
        '<article class="day-card">'
        f'<div class="eyebrow">{html.escape(str(day.get("label", "")))}</div>'
        f'<div class="weather-icon">{day.get("emoji", "•")}</div>'
        f'<strong>{format_temperature(day.get("high"), compact=True)}</strong>'
        f'<span>{html.escape(str(day.get("condition", "")))}</span></article>'
        for day in week
    ) or '<div class="empty">Week-ahead forecast unavailable.</div>'

    camera_cards = []
    for camera in report.get("cameras") or []:
        if camera.get("ok") and camera.get("dataUri"):
            visual = (
                f'<img src="{camera["dataUri"]}" alt="Live WSDOT still from {html.escape(str(camera.get("label", "camera")))}">'
            )
        else:
            visual = '<div class="camera-empty"><span>CAMERA UNAVAILABLE</span></div>'
        camera_cards.append(
            '<figure class="camera-card">' + visual + '<figcaption>'
            f'<span>{html.escape(str(camera.get("label", "WSDOT camera")))}</span>'
            f'<code>{html.escape(str(camera.get("id", "")))}</code></figcaption></figure>'
        )

    notes = ""
    if report.get("errors"):
        items = "".join(
            f'<li><strong>{html.escape(str(source))}:</strong> {html.escape(str(message))}</li>'
            for source, message in report["errors"].items()
        )
        notes = f'<details class="notes" open><summary>Data notes</summary><ul>{items}</ul></details>'

    source_links = " · ".join(
        f'<a href="{html.escape(str(source["url"]), quote=True)}">{html.escape(str(source["name"]))}</a>'
        for source in report.get("sources") or []
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="dark">
  <title>Wake Surf Conditions · Lake Washington</title>
  <style>
    :root {{ --bg:#06151d; --surface:#0b222d; --surface2:#10303d; --line:#214653; --text:#effcff; --muted:#93b7c1; --cyan:#65d8e8; --blue:#2fa5c5; --sun:#ffc76b; --urgent:#ff7f74; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:radial-gradient(circle at 80% -10%,#164f62 0,transparent 34rem),var(--bg); color:var(--text); font:15px/1.5 Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
    main {{ width:min(1180px,calc(100% - 32px)); margin:0 auto; padding:34px 0 48px; }}
    .hero {{ position:relative; overflow:hidden; min-height:220px; display:flex; align-items:flex-end; justify-content:space-between; gap:28px; padding:34px; border:1px solid #2b6070; border-radius:28px; background:linear-gradient(135deg,rgba(17,73,89,.92),rgba(7,30,40,.94)); box-shadow:0 24px 70px rgba(0,0,0,.25); }}
    .hero:after {{ content:""; position:absolute; width:300px; height:300px; right:-70px; top:-110px; border-radius:50%; background:radial-gradient(circle,var(--sun) 0 23%,rgba(255,199,107,.2) 24% 41%,transparent 42%); opacity:.85; }}
    .hero-copy,.hero-condition {{ position:relative; z-index:1; }}
    .kicker,.eyebrow {{ color:var(--muted); font-size:11px; font-weight:800; letter-spacing:.14em; text-transform:uppercase; }}
    h1 {{ margin:8px 0 6px; max-width:720px; font-size:clamp(34px,6vw,68px); line-height:.98; letter-spacing:-.045em; }}
    .location {{ margin:0; color:#c4e2e8; font-size:16px; }}
    .hero-condition {{ min-width:180px; text-align:right; }} .hero-condition .icon {{ font-size:64px; line-height:1; }} .hero-condition strong {{ display:block; margin-top:9px; font-size:20px; }} .hero-condition span {{ color:var(--muted); }}
    .alerts {{ display:grid; gap:10px; margin-top:18px; }} .alert {{ display:flex; gap:14px; padding:16px 18px; border:1px solid rgba(255,127,116,.45); border-radius:16px; background:rgba(255,127,116,.1); }} .alert-icon {{ font-size:22px; }} .alert p {{ margin:3px 0 0; color:#ffc4be; }}
    section.block {{ margin-top:34px; }} .section-head {{ display:flex; justify-content:space-between; align-items:end; gap:18px; margin-bottom:13px; }} h2 {{ margin:0; font-size:18px; letter-spacing:-.01em; }} .section-head span {{ color:var(--muted); font-size:12px; }}
    .metrics {{ display:grid; grid-template-columns:repeat(7,minmax(125px,1fr)); gap:10px; overflow-x:auto; padding-bottom:3px; }} .metric {{ min-width:125px; min-height:124px; padding:17px; border:1px solid var(--line); border-radius:17px; background:linear-gradient(180deg,var(--surface2),var(--surface)); }} .metric.urgent {{ border-color:rgba(255,127,116,.65); }} .metric-value {{ margin:14px 0 5px; font-size:19px; font-weight:800; white-space:nowrap; }} .metric-detail {{ color:var(--muted); font-size:12px; }}
    .chart-wrap {{ padding:16px 18px 3px; border:1px solid var(--line); border-radius:20px; background:var(--surface); overflow-x:auto; }} .hourly-chart {{ display:block; min-width:760px; width:100%; }} .grid-line {{ stroke:#214653; stroke-width:1; }} .temp-line,.wind-line {{ fill:none; stroke-width:3.2; stroke-linecap:round; stroke-linejoin:round; }} .temp-line {{ stroke:var(--sun); }} .wind-line {{ stroke:var(--cyan); }} .temp-dot {{ fill:var(--sun); }} .wind-dot {{ fill:var(--cyan); }} .axis-label,.legend,.range-label {{ fill:var(--muted); font:700 11px system-ui,sans-serif; }} .temp-legend {{ fill:var(--sun); }} .wind-legend {{ fill:var(--cyan); }}
    .hour-strip {{ display:flex; gap:8px; overflow-x:auto; padding:12px 2px 3px; }} .hour-card {{ flex:0 0 76px; text-align:center; padding:13px 8px; border:1px solid var(--line); border-radius:15px; background:var(--surface); }} .hour-label {{ color:var(--muted); font-size:11px; font-weight:800; }} .weather-icon {{ margin:7px 0; font-size:24px; }} .hour-card strong,.hour-card span {{ display:block; }} .hour-card span {{ margin-top:3px; color:var(--muted); font-size:11px; }}
    .tomorrow-grid {{ display:grid; grid-template-columns:1fr 1fr .65fr; gap:12px; }} .tomorrow-card {{ min-height:150px; padding:20px; border:1px solid var(--line); border-radius:19px; background:var(--surface); }} .tomorrow-main {{ display:flex; align-items:center; gap:13px; margin:18px 0 5px; font-size:27px; }} .tomorrow-main strong {{ font-size:21px; }} .tomorrow-card p {{ color:var(--muted); margin:8px 0 0; }} .uv-value {{ margin:12px 0 0; color:var(--sun); font-size:55px; font-weight:850; line-height:1; }}
    .week-grid {{ display:grid; grid-template-columns:repeat(7,1fr); gap:10px; }} .day-card {{ min-width:110px; padding:17px 10px; text-align:center; border:1px solid var(--line); border-radius:17px; background:var(--surface); }} .day-card strong,.day-card span {{ display:block; }} .day-card span {{ margin-top:5px; color:var(--muted); font-size:11px; }}
    .camera-grid {{ display:grid; grid-template-columns:repeat(3,1fr); gap:12px; }} .camera-card {{ margin:0; overflow:hidden; border:1px solid var(--line); border-radius:19px; background:var(--surface); }} .camera-card img,.camera-empty {{ display:block; width:100%; aspect-ratio:16/9; object-fit:cover; background:#071117; }} .camera-empty {{ display:grid; place-items:center; color:var(--muted); font-size:11px; font-weight:800; letter-spacing:.12em; }} .camera-card figcaption {{ display:flex; justify-content:space-between; gap:10px; padding:12px 14px; color:var(--muted); font-size:12px; }} code {{ color:#bcecf2; }}
    .notes {{ margin-top:24px; padding:15px 18px; border:1px solid #644b2d; border-radius:15px; background:rgba(255,199,107,.06); color:#e8cfaa; }} .notes summary {{ cursor:pointer; font-weight:750; }} .notes ul {{ margin:10px 0 0; padding-left:20px; }}
    footer {{ margin-top:36px; padding-top:18px; border-top:1px solid var(--line); color:var(--muted); font-size:12px; }} footer a {{ color:#a9e7ef; }} footer p {{ margin:7px 0; }} .empty {{ padding:24px; color:var(--muted); border:1px dashed var(--line); border-radius:15px; }}
    @media (max-width:800px) {{ main {{ width:min(100% - 20px,1180px); padding-top:10px; }} .hero {{ min-height:300px; align-items:flex-start; flex-direction:column; padding:25px; }} .hero-condition {{ text-align:left; }} .tomorrow-grid,.camera-grid {{ grid-template-columns:1fr; }} .week-grid {{ overflow-x:auto; grid-template-columns:repeat(7,110px); }} }}
    @media print {{ body {{ background:#fff; color:#111; }} main {{ width:100%; padding:0; }} .hero,.metric,.chart-wrap,.hour-card,.tomorrow-card,.day-card,.camera-card {{ box-shadow:none; break-inside:avoid; }} }}
  </style>
</head>
<body>
<main>
  <header class="hero">
    <div class="hero-copy"><div class="kicker">LIVE LAKE REPORT</div><h1>Wake Surf Conditions</h1><p class="location">{html.escape(LOCATION_LABEL)} · {html.escape(generated_label)}</p></div>
    <div class="hero-condition"><div class="icon">{current.get('emoji','•')}</div><strong>{html.escape(str(current.get('condition','Unavailable')))}</strong><span>{format_temperature(current.get('temperature'))}</span></div>
  </header>
  {alerts_html}
  <section class="block"><div class="section-head"><h2>Current conditions</h2><span>°C / °F · wind in mph</span></div><div class="metrics">{metrics}</div></section>
  <section class="block"><div class="section-head"><h2>Today by the hour</h2><span>Air temperature and sustained wind</span></div><div class="chart-wrap">{svg_hourly_chart(hourly)}</div><div class="hour-strip">{hourly_cards}</div></section>
  <section class="block"><div class="section-head"><h2>Tomorrow</h2><span>Representative morning and evening</span></div><div class="tomorrow-grid">{''.join(tomorrow_cards)}</div></section>
  <section class="block"><div class="section-head"><h2>Week ahead</h2><span>Daily high · °C / °F</span></div><div class="week-grid">{week_cards}</div></section>
  <section class="block"><div class="section-head"><h2>SR 520 bridge cameras</h2><span>WSDOT still images fetched with this report</span></div><div class="camera-grid">{''.join(camera_cards)}</div></section>
  {notes}
  <footer><p>{source_links}</p><p>Fixed point: {LATITUDE}, {LONGITUDE} · Times shown in {TIMEZONE_NAME}.</p><p>Conditions and camera stills are observational context, not a boating-safety guarantee.</p></footer>
</main>
</body>
</html>
"""


def atomic_write(path: Path, content: str) -> None:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent, text=True)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(content)
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("text", "json", "html"), default="text")
    parser.add_argument("--output", type=Path, help="Write to this path instead of stdout")
    parser.add_argument("--timeout", type=float, default=12.0, help="Per-source network timeout in seconds")
    parser.add_argument("--no-cameras", action="store_true", help="Do not fetch/embed WSDOT images in HTML")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.timeout <= 0:
        raise SystemExit("--timeout must be greater than zero")

    include_cameras = args.format == "html" and not args.no_cameras
    report = gather_report(args.timeout, include_cameras)

    if args.format == "json":
        content = json.dumps(public_report(report), indent=2, ensure_ascii=False) + "\n"
    elif args.format == "html":
        content = render_html(report)
    else:
        content = render_text(report)

    output = args.output
    if args.format == "html" and output is None:
        output = Path.cwd() / "wake-surf-conditions.html"

    if output is not None:
        atomic_write(output, content)
        print(str(output.expanduser().resolve()))
    else:
        sys.stdout.write(content)

    return 0 if report.get("weather") else 2


if __name__ == "__main__":
    raise SystemExit(main())
