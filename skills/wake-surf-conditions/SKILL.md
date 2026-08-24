---
name: wake-surf-conditions
description: Fetch and present live wake-surf conditions for the SR 520 Bridge area of Lake Washington, including air and water temperature, wind and gusts, rain chance, air quality, UV, NWS alerts, forecasts, and WSDOT cameras. Use for Lake Washington wake-surf condition checks or when a text, JSON, or visual HTML conditions report is requested; do not use for ocean-surf forecasts or other lakes.
---

# Wake Surf Conditions

Report conditions at the fixed location used by the Wake Surf Omarchy plugin:
SR 520 Bridge / Evergreen Point, Lake Washington (`47.6415, -122.2570`).

## Run the report

Resolve paths relative to this `SKILL.md`, then use the bundled standard-library
script. It has no API keys or package-install step.

```bash
# Concise chat-ready report (default)
python3 scripts/wake_surf_report.py

# Structured data for further analysis
python3 scripts/wake_surf_report.py --format json

# Self-contained visual artifact with an hourly chart and embedded bridge cams
python3 scripts/wake_surf_report.py --format html --output /absolute/path/wake-surf-conditions.html
```

Use text for an ordinary conditions question. Use HTML when the user asks for
an artifact, dashboard, graphics, cameras, or a richer presentation. Return or
attach the created HTML file and include a one- or two-sentence current summary
in the response. Use JSON only when the caller wants machine-readable data or
further computation.

The script fetches Open-Meteo weather and air quality, active NWS alerts,
LakeMonster water temperature, and three WSDOT SR 520 camera stills. HTML is
fully self-contained: CSS, the SVG chart, and successful camera images are
embedded in the file. `--no-cameras` makes a smaller HTML report when images
are unwanted or network policy disallows them.

## Interpret the result

- Treat each source independently. A missing water reading or camera must not
  erase otherwise valid weather data. Mention material source failures shown
  under `Data notes` / `errors`.
- Keep units in both Celsius and Fahrenheit for temperatures and mph for wind,
  matching the plugin. Interpret all forecast times in `America/Los_Angeles`.
- Surface active NWS alerts prominently. Do not convert this conditions report
  into a safety guarantee or claim the lake is safe; boating decisions also
  depend on local observation, equipment, operator experience, and official
  guidance.
- The camera stills are observational context, not proof of conditions across
  the whole lake. Their WSDOT IDs and capture-fetch time remain in the report.
- Do not silently reuse an older artifact as a live answer. Run the script for
  each current-conditions request and preserve the generated timestamp.

If the essential weather request fails, the script still writes a partial
artifact but exits nonzero. Return the partial result only with a clear note
that current forecast data was unavailable.
