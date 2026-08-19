import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui
import "Model.js" as Model

// Lake Washington wake surf conditions: air temp/wind/gusts/rain chance and
// today's hourly forecast from Open-Meteo, active marine/weather warnings
// from the NWS, live WSDOT 520 bridge cams, and water temp from
// lakemonster.com. Fixed on the 520 bridge (Evergreen Point) rather than
// user-configurable, since this widget only ever means one spot on the lake.
Panel {
  id: root
  moduleName: "mrelph.wake-surf"
  ipcTarget: "mrelph.wake-surf"
  manageIpc: false

  readonly property real lakeLat: 47.6415
  readonly property real lakeLon: -122.2570
  readonly property string locationLabel: "520 Bridge · Lake Washington"

  readonly property var cameraIds: ["520vc00241", "520vc00293", "520vc00341"]
  property int cameraBust: 0
  function cameraUrl(id) { return "https://images.wsdot.wa.gov/nw/" + id + ".jpg?a=" + root.cameraBust }
  property string expandedCameraId: ""

  readonly property string home: Quickshell.env("HOME") || ""
  readonly property string stateHome: Quickshell.env("XDG_STATE_HOME") || (home + "/.local/state")
  readonly property string stateDir: stateHome + "/omarchy/wake-surf"
  readonly property string waterStatusPath: stateDir + "/water.json"
  readonly property string waterFetchScript: home + "/.config/omarchy/plugins/mrelph.wake-surf/bin/wake-surf-water-fetch"

  readonly property color foreground: bar ? bar.foreground : Color.foreground
  readonly property color dim: Qt.darker(foreground, 1.5)
  readonly property string fontFamily: bar ? bar.fontFamily : Style.font.family

  property var forecast: null
  property var alerts: []
  property var waterStatus: null
  property var airQuality: null

  readonly property bool hasAlerts: alerts.length > 0
  readonly property var currentPop: Model.nearestHourlyPop(forecast ? forecast.hourlyTimes : [], forecast ? forecast.hourlyPop : [])
  readonly property var hourlyForecast: forecast
    ? Model.remainingHoursToday(forecast.hourlyTimes, forecast.hourlyTemp, forecast.hourlyWind, forecast.hourlyCode)
    : []
  readonly property var tomorrowForecast: forecast
    ? Model.tomorrowMorningEvening(forecast.hourlyTimes, forecast.hourlyTemp, forecast.hourlyCode, forecast.hourlyWind, forecast.hourlyGust)
    : { morning: null, evening: null }
  readonly property var tomorrowUv: forecast ? Model.tomorrowUvIndex(forecast.dailyTimes, forecast.dailyUvMax) : null
  readonly property string tomorrowUvText: (tomorrowUv === null || tomorrowUv === undefined) ? "—" : String(Math.round(Number(tomorrowUv)))
  readonly property var weekAhead: forecast
    ? Model.weekAheadDays(forecast.dailyTimes, forecast.dailyMax, forecast.dailyCode)
    : []

  readonly property string airTempText: forecast ? Model.formatTempBothCompact(forecast.tempC) : "—"
  readonly property string windText: forecast ? Math.round(forecast.windMph) + " mph " + Model.compassDirection(forecast.windDirDeg) : "—"
  readonly property string gustText: forecast ? Math.round(forecast.windGustMph) + " mph" : "—"
  readonly property string rainChanceText: currentPop !== null ? currentPop + "%" : "—"
  readonly property string conditionText: forecast ? Model.conditionLabel(forecast.weatherCode) : "Checking…"

  readonly property string waterTempText: waterStatus && waterStatus.waterTempC !== null && waterStatus.waterTempC !== undefined
    ? Model.formatTempBothCompact(waterStatus.waterTempC) : "—"
  readonly property bool waterStale: !waterStatus || !waterStatus.lastSuccessAt || Model.isStale(waterStatus.lastSuccessAt, 6 * 60)
  readonly property string waterUpdatedText: waterStatus && waterStatus.lastSuccessAt ? Model.relativeTime(waterStatus.lastSuccessAt) : "never"

  readonly property string uvIndexText: airQuality && airQuality.uvIndex !== undefined && airQuality.uvIndex !== null
    ? String(Math.round(Number(airQuality.uvIndex))) : "—"
  readonly property string aqiText: airQuality && airQuality.usAqi !== undefined && airQuality.usAqi !== null
    ? String(Math.round(Number(airQuality.usAqi))) : "—"
  readonly property bool aqiElevated: airQuality && airQuality.usAqi !== undefined && airQuality.usAqi !== null && Number(airQuality.usAqi) > 100

  function refresh() {
    if (!weatherProc.running) weatherProc.running = true
    if (!alertsProc.running) alertsProc.running = true
    if (!airQualityProc.running) airQualityProc.running = true
    root.cameraBust = Date.now()
  }

  function refreshWater() {
    if (!waterFetchProc.running) waterFetchProc.running = true
  }

  visible: true
  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  onOpenedChanged: if (opened) {
    refresh()
    Qt.callLater(function() { keyCatcher.forceActiveFocus() })
  }

  Process {
    id: weatherProc
    command: ["curl", "-fsS", "--max-time", "8",
      "https://api.open-meteo.com/v1/forecast?latitude=" + root.lakeLat + "&longitude=" + root.lakeLon
      + "&current=temperature_2m,wind_speed_10m,wind_direction_10m,wind_gusts_10m,weather_code,is_day"
      + "&hourly=temperature_2m,wind_speed_10m,wind_gusts_10m,weather_code,precipitation_probability"
      + "&daily=temperature_2m_max,weather_code,uv_index_max"
      + "&forecast_days=7&wind_speed_unit=mph&timezone=auto"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        var parsed = Model.parseForecast(text)
        if (parsed) root.forecast = parsed
      }
    }
  }

  Process {
    id: alertsProc
    command: ["curl", "-fsS", "--max-time", "8",
      "-H", "User-Agent: mrelph-wake-surf-widget/1.0 (personal desktop widget)",
      "https://api.weather.gov/alerts/active?point=" + root.lakeLat + "," + root.lakeLon]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.alerts = Model.parseAlerts(text)
    }
  }

  Process {
    id: airQualityProc
    command: ["curl", "-fsS", "--max-time", "8",
      "https://air-quality-api.open-meteo.com/v1/air-quality?latitude=" + root.lakeLat + "&longitude=" + root.lakeLon
      + "&current=uv_index,us_aqi&timezone=auto"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        var parsed = Model.parseAirQuality(text)
        if (parsed) root.airQuality = parsed
      }
    }
  }

  Process {
    id: waterFetchProc
    command: [root.waterFetchScript]
    onExited: waterStatusFile.reload()
  }

  FileView {
    id: waterStatusFile
    path: root.waterStatusPath
    watchChanges: true
    printErrors: false
    onFileChanged: reload()
    onLoaded: {
      try {
        root.waterStatus = JSON.parse(text())
      } catch (e) {
        root.waterStatus = null
      }
    }
    onLoadFailed: root.waterStatus = null
  }

  Timer {
    interval: 10 * 60 * 1000
    running: true
    repeat: true
    triggeredOnStart: true
    onTriggered: root.refresh()
  }

  Timer {
    interval: 30 * 60 * 1000
    running: true
    repeat: true
    triggeredOnStart: true
    onTriggered: root.refreshWater()
  }

  // Cameras refresh a bit faster while the panel is actually open, and stop
  // polling entirely once it's closed.
  Timer {
    interval: 45 * 1000
    running: root.opened
    repeat: true
    onTriggered: root.cameraBust = Date.now()
  }

  IpcHandler {
    target: root.ipcTarget
    function open(): void { root.open() }
    function close(): void { root.close() }
    function show(): void { root.open() }
    function hide(): void { root.close() }
    function toggle(): void { root.toggle() }
    function refresh(): string { root.refresh(); root.refreshWater(); return "ok" }
  }

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    slotSize: Style.bar.iconSlot
    tooltipText: ""
    iconComponent: Component {
      Item {
        Text {
          anchors.centerIn: parent
          text: "🏄"
          font.pixelSize: Style.font.body
        }
        Rectangle {
          visible: root.hasAlerts
          width: Style.space(5)
          height: width
          radius: width / 2
          anchors.right: parent.right
          anchors.bottom: parent.bottom
          anchors.rightMargin: Style.space(2)
          anchors.bottomMargin: Style.space(2)
          color: Color.urgent
        }
      }
    }

    onPressed: function(buttonCode) {
      if (buttonCode === Qt.MiddleButton) root.refresh()
      else root.toggle()
    }
  }

  KeyboardPanel {
    id: panel
    anchorItem: button
    owner: root
    bar: root.bar
    open: root.opened
    centerOnBar: true
    focusTarget: keyCatcher
    contentWidth: panel.fittedContentWidth(Style.space(600))
    contentHeight: panel.fittedContentHeight(scroll.contentHeight, Style.space(860))

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      blocked: root.expandedCameraId !== ""
      onCloseRequested: root.close()
      onTabRequested: function(direction) { root.switchPanel(direction) }
      onActivateRequested: root.refresh()
      onTextKey: function(t) { if (t === "r" || t === "R") root.refresh() }

      Flickable {
        id: scroll
        anchors.fill: parent
        contentWidth: width
        contentHeight: content.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        interactive: contentHeight > height

        Column {
          id: content
          width: scroll.width
          spacing: Style.space(14)

          PanelHero {
            width: parent.width
            title: "Wake Surf Conditions"
            meta: root.locationLabel + " · " + root.conditionText
            foreground: root.foreground
            fontFamily: root.fontFamily
            iconComponent: Component {
              Text {
                text: "🏄"
                font.pixelSize: Style.font.display
              }
            }
          }

          BorderSurface {
            visible: root.hasAlerts
            width: parent.width
            implicitHeight: alertColumn.implicitHeight + Style.space(20)
            color: Qt.rgba(Color.urgent.r, Color.urgent.g, Color.urgent.b, 0.12)
            borderSpec: Border.flat(Qt.rgba(Color.urgent.r, Color.urgent.g, Color.urgent.b, 0.4), 1)
            radius: Style.cornerRadius

            Column {
              id: alertColumn
              anchors.left: parent.left
              anchors.right: parent.right
              anchors.verticalCenter: parent.verticalCenter
              anchors.leftMargin: Style.space(12)
              anchors.rightMargin: Style.space(12)
              spacing: Style.space(4)

              Repeater {
                model: root.alerts
                delegate: Text {
                  required property var modelData
                  width: alertColumn.width
                  text: "⚠ " + modelData.event
                  color: root.foreground
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.bodySmall
                  font.bold: true
                  wrapMode: Text.WordWrap
                }
              }
            }
          }

          PanelSeparator { width: parent.width; foreground: root.foreground }

          Text {
            text: "CURRENT CONDITIONS (°C/°F)"
            color: root.dim
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
            font.letterSpacing: 1
          }

          Row {
            width: parent.width
            spacing: Style.space(10)

            property var stats: [
              { label: "AIR TEMP", value: root.airTempText, dim: false },
              { label: "WATER TEMP", value: root.waterTempText, dim: root.waterStale },
              { label: "WIND", value: root.windText, dim: false },
              { label: "GUSTS", value: root.gustText, dim: false },
              { label: "RAIN CHANCE", value: root.rainChanceText, dim: false },
              { label: "AIR QUALITY", value: root.aqiText, dim: false, urgent: root.aqiElevated },
              { label: "UV INDEX", value: root.uvIndexText, dim: false }
            ]

            Repeater {
              model: parent.stats
              delegate: Column {
                required property var modelData
                width: (content.width - Style.space(60)) / 7
                spacing: Style.space(5)

                Text {
                  text: modelData.label
                  color: root.dim
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.caption
                  font.letterSpacing: 1
                  wrapMode: Text.WordWrap
                  width: parent.width
                }
                Text {
                  text: modelData.value
                  color: modelData.urgent ? Color.urgent : (modelData.dim ? root.dim : root.foreground)
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.body
                  font.bold: true
                }
              }
            }
          }

          PanelSeparator { width: parent.width; foreground: root.foreground }

          Text {
            text: "TODAY, BY THE HOUR (°C/°F)"
            color: root.dim
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
            font.letterSpacing: 1
          }

          Text {
            visible: root.hourlyForecast.length === 0
            text: "No more hours forecast today"
            color: root.dim
            font.family: root.fontFamily
            font.pixelSize: Style.font.bodySmall
            font.italic: true
          }

          ListView {
            visible: root.hourlyForecast.length > 0
            width: parent.width
            height: Style.space(92)
            orientation: ListView.Horizontal
            spacing: Style.space(6)
            clip: true
            model: root.hourlyForecast

            delegate: Column {
              required property var modelData
              width: Style.space(64)
              height: ListView.view.height
              spacing: Style.space(4)

              Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: modelData.label
                color: root.dim
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption
              }
              Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: Model.conditionEmoji(modelData.code)
                font.pixelSize: Style.font.title
              }
              Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: Model.formatTempBothCompact(modelData.tempC)
                color: root.foreground
                font.family: root.fontFamily
                font.pixelSize: Style.font.bodySmall
                font.bold: true
              }
              Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: modelData.windMph !== null ? Math.round(modelData.windMph) + "mph" : "—"
                color: root.dim
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption
              }
            }
          }

          PanelSeparator { width: parent.width; foreground: root.foreground }

          Text {
            text: "TOMORROW (°C/°F)"
            color: root.dim
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
            font.letterSpacing: 1
          }

          Row {
            width: parent.width
            spacing: Style.space(32)

            Column {
              spacing: Style.space(5)
              Text { text: "MORNING"; color: root.dim; font.family: root.fontFamily; font.pixelSize: Style.font.bodySmall; font.letterSpacing: 1 }
              Row {
                spacing: Style.space(8)
                Text {
                  anchors.verticalCenter: parent.verticalCenter
                  text: Model.conditionEmoji(root.tomorrowForecast.morning ? root.tomorrowForecast.morning.code : null)
                  font.pixelSize: Style.font.title
                }
                Text {
                  anchors.verticalCenter: parent.verticalCenter
                  text: root.tomorrowForecast.morning ? Model.formatTempBothFull(root.tomorrowForecast.morning.tempC) : "—"
                  color: root.foreground
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.body
                  font.bold: true
                }
              }
              Text {
                text: Model.formatWindGust(root.tomorrowForecast.morning ? root.tomorrowForecast.morning.windMph : null, root.tomorrowForecast.morning ? root.tomorrowForecast.morning.gustMph : null)
                color: root.dim
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption
              }
            }

            Column {
              spacing: Style.space(5)
              Text { text: "EVENING"; color: root.dim; font.family: root.fontFamily; font.pixelSize: Style.font.bodySmall; font.letterSpacing: 1 }
              Row {
                spacing: Style.space(8)
                Text {
                  anchors.verticalCenter: parent.verticalCenter
                  text: Model.conditionEmoji(root.tomorrowForecast.evening ? root.tomorrowForecast.evening.code : null)
                  font.pixelSize: Style.font.title
                }
                Text {
                  anchors.verticalCenter: parent.verticalCenter
                  text: root.tomorrowForecast.evening ? Model.formatTempBothFull(root.tomorrowForecast.evening.tempC) : "—"
                  color: root.foreground
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.body
                  font.bold: true
                }
              }
              Text {
                text: Model.formatWindGust(root.tomorrowForecast.evening ? root.tomorrowForecast.evening.windMph : null, root.tomorrowForecast.evening ? root.tomorrowForecast.evening.gustMph : null)
                color: root.dim
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption
              }
            }

            Column {
              spacing: Style.space(5)
              Text { text: "UV INDEX"; color: root.dim; font.family: root.fontFamily; font.pixelSize: Style.font.bodySmall; font.letterSpacing: 1 }
              Text {
                text: root.tomorrowUvText
                color: root.foreground
                font.family: root.fontFamily
                font.pixelSize: Style.font.title
                font.bold: true
              }
            }
          }

          PanelSeparator { width: parent.width; foreground: root.foreground }

          Text {
            text: "WEEK AHEAD — HIGH (°C/°F)"
            color: root.dim
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
            font.letterSpacing: 1
          }

          Row {
            width: parent.width
            spacing: Style.space(10)

            Repeater {
              model: root.weekAhead
              delegate: Column {
                required property var modelData
                width: (content.width - Style.space(60)) / 7
                spacing: Style.space(4)

                Text {
                  anchors.horizontalCenter: parent.horizontalCenter
                  text: modelData.label
                  color: root.dim
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.caption
                }
                Text {
                  anchors.horizontalCenter: parent.horizontalCenter
                  text: Model.conditionEmoji(modelData.code)
                  font.pixelSize: Style.font.body
                }
                Text {
                  anchors.horizontalCenter: parent.horizontalCenter
                  text: Model.formatTempBothCompact(modelData.maxC)
                  color: root.foreground
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.bodySmall
                  font.bold: true
                }
              }
            }
          }

          PanelSeparator { width: parent.width; foreground: root.foreground }

          Text {
            text: "520 BRIDGE CAMERAS"
            color: root.dim
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
            font.letterSpacing: 1
          }

          Row {
            width: parent.width
            spacing: Style.space(12)

            Repeater {
              model: root.cameraIds
              delegate: BorderSurface {
                required property var modelData
                width: (content.width - Style.space(24)) / 3
                height: Style.space(150)
                radius: Style.cornerRadius
                color: Style.normalFillFor(root.foreground, Color.accent)
                borderSpec: Border.controlSpec("normal", root.foreground, Color.accent)

                Image {
                  anchors.fill: parent
                  anchors.margins: Style.space(2)
                  fillMode: Image.PreserveAspectCrop
                  asynchronous: true
                  cache: false
                  source: root.cameraUrl(modelData)
                }

                MouseArea {
                  anchors.fill: parent
                  cursorShape: Qt.PointingHandCursor
                  onClicked: root.expandedCameraId = modelData
                }
              }
            }
          }

          Text {
            width: parent.width
            text: "Press R to refresh · water temp via lakemonster.com"
            color: root.dim
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
          }
        }
      }

      // In-panel camera lightbox: clicking a thumbnail expands it here
      // instead of jumping out to a browser.
      Rectangle {
        id: cameraOverlay
        visible: root.expandedCameraId !== ""
        anchors.fill: parent
        color: Qt.rgba(0, 0, 0, 0.8)
        z: 10

        Image {
          anchors.centerIn: parent
          width: parent.width - Style.space(48)
          height: parent.height - Style.space(48)
          fillMode: Image.PreserveAspectFit
          asynchronous: true
          cache: false
          source: root.expandedCameraId !== "" ? root.cameraUrl(root.expandedCameraId) : ""
        }

        Text {
          anchors.top: parent.top
          anchors.right: parent.right
          anchors.margins: Style.space(14)
          text: "✕"
          color: "#ffffff"
          font.family: root.fontFamily
          font.pixelSize: Style.font.heading
        }

        MouseArea {
          anchors.fill: parent
          cursorShape: Qt.PointingHandCursor
          onClicked: root.expandedCameraId = ""
        }
      }
    }
  }
}
