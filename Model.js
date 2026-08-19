// 16-point compass label for a wind direction in degrees.
function compassDirection(deg) {
  var directions = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
    "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
  var n = Number(deg)
  if (!isFinite(n)) return ""
  var index = Math.round(n / 22.5) % 16
  if (index < 0) index += 16
  return directions[index]
}

// Open-Meteo WMO weather codes collapsed to a short label. Precise enough
// for a go/no-go glance; not trying to distinguish every WMO nuance.
function conditionLabel(code) {
  var c = parseInt(String(code), 10)
  if (!isFinite(c)) return ""
  if (c === 0) return "Clear"
  if (c === 1 || c === 2) return "Partly Cloudy"
  if (c === 3) return "Cloudy"
  if (c === 45 || c === 48) return "Fog"
  if (c === 51 || c === 53 || c === 55) return "Drizzle"
  if (c === 56 || c === 57) return "Freezing Drizzle"
  if (c === 61 || c === 63 || c === 65) return "Rain"
  if (c === 66 || c === 67) return "Freezing Rain"
  if (c === 71 || c === 73 || c === 75 || c === 77) return "Snow"
  if (c === 80 || c === 81 || c === 82) return "Rain Showers"
  if (c === 85 || c === 86) return "Snow Showers"
  if (c === 95 || c === 96 || c === 99) return "Thunderstorm"
  return "—"
}

// Same WMO codes, collapsed further to one emoji for a compact hourly strip.
function conditionEmoji(code) {
  var c = parseInt(String(code), 10)
  if (!isFinite(c)) return "•"
  if (c === 0) return "☀️"
  if (c === 1 || c === 2) return "🌤️"
  if (c === 3) return "☁️"
  if (c === 45 || c === 48) return "🌫️"
  if (c === 51 || c === 53 || c === 55 || c === 56 || c === 57
    || c === 61 || c === 63 || c === 65 || c === 66 || c === 67
    || c === 80 || c === 81 || c === 82) return "🌧️"
  if (c === 71 || c === 73 || c === 75 || c === 77 || c === 85 || c === 86) return "🌨️"
  if (c === 95 || c === 96 || c === 99) return "⛈️"
  return "•"
}

// Open-Meteo current+hourly forecast JSON -> flat fields the panel binds to.
function parseForecast(raw) {
  try {
    var data = JSON.parse(String(raw || ""))
    var current = data && data.current ? data.current : null
    if (!current) return null
    return {
      tempC: current.temperature_2m,
      windMph: current.wind_speed_10m,
      windGustMph: current.wind_gusts_10m,
      windDirDeg: current.wind_direction_10m,
      weatherCode: current.weather_code,
      isDay: current.is_day,
      hourlyTimes: (data.hourly && data.hourly.time) || [],
      hourlyPop: (data.hourly && data.hourly.precipitation_probability) || [],
      hourlyTemp: (data.hourly && data.hourly.temperature_2m) || [],
      hourlyWind: (data.hourly && data.hourly.wind_speed_10m) || [],
      hourlyGust: (data.hourly && data.hourly.wind_gusts_10m) || [],
      hourlyCode: (data.hourly && data.hourly.weather_code) || [],
      dailyTimes: (data.daily && data.daily.time) || [],
      dailyMax: (data.daily && data.daily.temperature_2m_max) || [],
      dailyCode: (data.daily && data.daily.weather_code) || [],
      dailyUvMax: (data.daily && data.daily.uv_index_max) || []
    }
  } catch (e) {
    return null
  }
}

function celsiusToFahrenheit(c) {
  var n = Number(c)
  return isFinite(n) ? n * 9 / 5 + 32 : null
}

// "21°C / 70°F" for roomier spots (stat grid, tomorrow blocks).
function formatTempBothFull(c) {
  if (c === null || c === undefined || !isFinite(Number(c))) return "—"
  var f = celsiusToFahrenheit(c)
  return Math.round(Number(c)) + "°C / " + Math.round(f) + "°F"
}

// "8 mph" or "8 mph, gusts 14" when gusts meaningfully (3mph+) exceed
// sustained wind. Explicit null/undefined checks before Number() matter
// here: Number(null) is 0, not NaN, so a naive isFinite check would read a
// missing reading as a real "0 mph."
function formatWindGust(windMph, gustMph) {
  if (windMph === null || windMph === undefined || !isFinite(Number(windMph))) return "—"
  var windRounded = Math.round(Number(windMph))
  if (gustMph === null || gustMph === undefined || !isFinite(Number(gustMph))) return windRounded + " mph"
  var gustRounded = Math.round(Number(gustMph))
  if (gustRounded - windRounded < 3) return windRounded + " mph"
  return windRounded + " mph, gusts " + gustRounded
}

// "21/70" compact form for narrow strips (hourly, week-ahead); the unit
// order is labeled once in the section header instead of per-cell.
function formatTempBothCompact(c) {
  if (c === null || c === undefined || !isFinite(Number(c))) return "—"
  var f = celsiusToFahrenheit(c)
  return Math.round(Number(c)) + "/" + Math.round(f)
}

// Open-Meteo air-quality current block -> {uvIndex, usAqi}.
function parseAirQuality(raw) {
  try {
    var data = JSON.parse(String(raw || ""))
    var current = data && data.current ? data.current : null
    if (!current) return null
    return {
      uvIndex: current.uv_index,
      usAqi: current.us_aqi
    }
  } catch (e) {
    return null
  }
}

function twoDigits(n) { return n < 10 ? "0" + n : String(n) }

// "3PM" style label for an hourly strip cell.
function hourLabel(date) {
  var hour24 = date.getHours()
  var suffix = hour24 >= 12 ? "PM" : "AM"
  var hour12 = hour24 % 12
  if (hour12 === 0) hour12 = 12
  return hour12 + suffix
}

// Hourly forecast entries from the current hour through the end of today
// (local time), as [{label, tempC, windMph, code}]. A 30-minute grace keeps
// the entry for the hour that's already in progress.
function remainingHoursToday(hourlyTimes, hourlyTemp, hourlyWind, hourlyCode) {
  if (!hourlyTimes || !hourlyTimes.length) return []
  var now = new Date()
  var todayKey = now.getFullYear() + "-" + twoDigits(now.getMonth() + 1) + "-" + twoDigits(now.getDate())
  var cutoff = now.getTime() - 30 * 60000
  var result = []
  for (var i = 0; i < hourlyTimes.length; i++) {
    var t = new Date(hourlyTimes[i])
    if (isNaN(t.getTime())) continue
    var key = t.getFullYear() + "-" + twoDigits(t.getMonth() + 1) + "-" + twoDigits(t.getDate())
    if (key !== todayKey || t.getTime() < cutoff) continue
    result.push({
      label: hourLabel(t),
      tempC: (hourlyTemp && hourlyTemp[i] !== undefined) ? hourlyTemp[i] : null,
      windMph: (hourlyWind && hourlyWind[i] !== undefined) ? hourlyWind[i] : null,
      code: (hourlyCode && hourlyCode[i] !== undefined) ? hourlyCode[i] : null
    })
  }
  return result
}

// Index into hourlyTimes closest to targetHour (0-23) on the given
// "yyyy-MM-dd" local date key; -1 if that date has no entries.
function nearestIndexToHour(hourlyTimes, dateKey, targetHour) {
  var bestIndex = -1
  var bestDelta = Infinity
  for (var i = 0; i < hourlyTimes.length; i++) {
    var t = new Date(hourlyTimes[i])
    if (isNaN(t.getTime())) continue
    var key = t.getFullYear() + "-" + twoDigits(t.getMonth() + 1) + "-" + twoDigits(t.getDate())
    if (key !== dateKey) continue
    var delta = Math.abs(t.getHours() - targetHour)
    if (delta < bestDelta) {
      bestDelta = delta
      bestIndex = i
    }
  }
  return bestIndex
}

// Tomorrow's forecast at representative morning (9am) and evening (6pm)
// hours, as {morning: {tempC, code, windMph, gustMph}|null, evening: ditto}.
function tomorrowMorningEvening(hourlyTimes, hourlyTemp, hourlyCode, hourlyWind, hourlyGust) {
  var empty = { morning: null, evening: null }
  if (!hourlyTimes || !hourlyTimes.length) return empty

  var now = new Date()
  var tomorrow = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1)
  var dateKey = tomorrow.getFullYear() + "-" + twoDigits(tomorrow.getMonth() + 1) + "-" + twoDigits(tomorrow.getDate())

  function entryAt(targetHour) {
    var index = nearestIndexToHour(hourlyTimes, dateKey, targetHour)
    if (index < 0) return null
    return {
      tempC: (hourlyTemp && hourlyTemp[index] !== undefined) ? hourlyTemp[index] : null,
      code: (hourlyCode && hourlyCode[index] !== undefined) ? hourlyCode[index] : null,
      windMph: (hourlyWind && hourlyWind[index] !== undefined) ? hourlyWind[index] : null,
      gustMph: (hourlyGust && hourlyGust[index] !== undefined) ? hourlyGust[index] : null
    }
  }

  return { morning: entryAt(9), evening: entryAt(18) }
}

// Tomorrow's daily max UV index, or null if the forecast doesn't cover it.
function tomorrowUvIndex(dailyTimes, dailyUvMax) {
  if (!dailyTimes || !dailyTimes.length) return null

  var now = new Date()
  var tomorrow = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1)
  var dateKey = tomorrow.getFullYear() + "-" + twoDigits(tomorrow.getMonth() + 1) + "-" + twoDigits(tomorrow.getDate())

  for (var i = 0; i < dailyTimes.length; i++) {
    var d = new Date(dailyTimes[i] + "T12:00:00")
    if (isNaN(d.getTime())) continue
    var key = d.getFullYear() + "-" + twoDigits(d.getMonth() + 1) + "-" + twoDigits(d.getDate())
    if (key === dateKey) return (dailyUvMax && dailyUvMax[i] !== undefined) ? dailyUvMax[i] : null
  }
  return null
}

// Day label for a Date already normalized to local noon (see weekAheadDays).
function dayShortLabel(date, todayKey) {
  var key = date.getFullYear() + "-" + twoDigits(date.getMonth() + 1) + "-" + twoDigits(date.getDate())
  if (key === todayKey) return "Today"
  return ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"][date.getDay()]
}

// Up to 7 days of {label, maxC, code} from parallel daily.time /
// daily.temperature_2m_max / daily.weather_code arrays. Each daily.time
// entry is a bare "yyyy-MM-dd" date (no time-of-day), which Date parses as
// UTC midnight -- appending noon keeps the local calendar date correct
// across timezone offsets instead of rolling back a day.
function weekAheadDays(dailyTimes, dailyMax, dailyCode) {
  if (!dailyTimes || !dailyTimes.length) return []
  var now = new Date()
  var todayKey = now.getFullYear() + "-" + twoDigits(now.getMonth() + 1) + "-" + twoDigits(now.getDate())
  var result = []
  for (var i = 0; i < dailyTimes.length && result.length < 7; i++) {
    var d = new Date(dailyTimes[i] + "T12:00:00")
    if (isNaN(d.getTime())) continue
    result.push({
      label: dayShortLabel(d, todayKey),
      maxC: (dailyMax && dailyMax[i] !== undefined) ? dailyMax[i] : null,
      code: (dailyCode && dailyCode[i] !== undefined) ? dailyCode[i] : null
    })
  }
  return result
}

// Precipitation probability for the hour nearest to now, from parallel
// hourly.time / hourly.precipitation_probability arrays.
function nearestHourlyPop(hourlyTimes, hourlyPop) {
  if (!hourlyTimes || !hourlyTimes.length) return null
  var now = Date.now()
  var bestIndex = -1
  var bestDelta = Infinity
  for (var i = 0; i < hourlyTimes.length; i++) {
    var t = new Date(hourlyTimes[i]).getTime()
    if (!isFinite(t)) continue
    var delta = Math.abs(t - now)
    if (delta < bestDelta) {
      bestDelta = delta
      bestIndex = i
    }
  }
  if (bestIndex < 0 || !hourlyPop || bestIndex >= hourlyPop.length) return null
  var value = hourlyPop[bestIndex]
  return (value === undefined || value === null) ? null : Math.round(Number(value))
}

// NWS active-alerts GeoJSON -> [{event, headline, severity}], most severe
// conditions first isn't attempted here; NWS already orders by issuance.
function parseAlerts(raw) {
  try {
    var data = JSON.parse(String(raw || ""))
    var features = (data && data.features) || []
    var alerts = []
    for (var i = 0; i < features.length; i++) {
      var props = features[i] && features[i].properties
      if (!props) continue
      alerts.push({
        event: String(props.event || "Alert"),
        headline: String(props.headline || ""),
        severity: String(props.severity || "")
      })
    }
    return alerts
  } catch (e) {
    return []
  }
}

function isStale(isoString, maxMinutes) {
  if (!isoString) return true
  var then = new Date(isoString).getTime()
  if (!isFinite(then)) return true
  return (Date.now() - then) / 60000 > maxMinutes
}

function relativeTime(isoString) {
  if (!isoString) return "never"
  var then = new Date(isoString).getTime()
  if (!isFinite(then)) return "unknown"
  var seconds = Math.max(0, Math.floor((Date.now() - then) / 1000))
  if (seconds < 60) return "just now"
  if (seconds < 3600) return Math.floor(seconds / 60) + " min ago"
  if (seconds < 86400) return Math.floor(seconds / 3600) + " hr ago"
  return Math.floor(seconds / 86400) + " days ago"
}

if (typeof module !== "undefined") {
  module.exports = {
    compassDirection: compassDirection,
    conditionLabel: conditionLabel,
    conditionEmoji: conditionEmoji,
    parseForecast: parseForecast,
    parseAirQuality: parseAirQuality,
    formatTempBothFull: formatTempBothFull,
    formatTempBothCompact: formatTempBothCompact,
    formatWindGust: formatWindGust,
    nearestHourlyPop: nearestHourlyPop,
    remainingHoursToday: remainingHoursToday,
    tomorrowMorningEvening: tomorrowMorningEvening,
    tomorrowUvIndex: tomorrowUvIndex,
    weekAheadDays: weekAheadDays,
    parseAlerts: parseAlerts,
    isStale: isStale,
    relativeTime: relativeTime
  }
}
