[English](README.md) | [繁體中文](README.zh-TW.md)

# 📍 iPhone GPS Controller Pro

透過 Mac（USB / WiFi）即時模擬 iPhone GPS 位置的全功能工具。  
從 [LocWarp](https://github.com/keezxc1223/locwarp) 移植完整功能集，採用輕量 **aiohttp + Vanilla JS** 架構——不需 Electron、不需 React，只要 `./start.sh`。

> **Author:** Aroha Lin · **License:** MIT · **Copyright (c) 2026 Aroha Lin**  
> **Repo:** https://github.com/ArohaLin/iphone-gps-controller-pro

---

## 目錄

1. [功能一覽](#功能一覽)
2. [系統需求](#系統需求)
3. [安裝與快速開始](#安裝與快速開始)
4. [架構說明](#架構說明)
5. [模式操作說明](#模式操作說明)
6. [HTTP API 參考](#http-api-參考)
7. [WebSocket 事件](#websocket-事件)
8. [鍵盤快速鍵](#鍵盤快速鍵)
9. [常見問題](#常見問題)
10. [第三方授權](#第三方授權)

---

## 功能一覽

### 基礎功能

| 功能 | 說明 |
|------|------|
| 📍 點擊傳送 | 點擊地圖或輸入座標，即時推送 GPS 至 iPhone |
| 🧭 方向移動 | 8 方向位移，可設定步距（公尺） |
| 🔄 自動重連 | Tunnel / GPS 斷線後指數退避自動重試 |
| 📱 多裝置管理 | 同時管理多支 iPhone；主要裝置 👑 標示 + 從機同步 |
| 🌐 WebSocket 推送 | 即時位置 / 狀態更新，無輪詢延遲 |
| 📲 iOS 16 & 17+ | DVT（iOS 17+）與 DtSimulateLocation（iOS 16）雙路徑支援 |

### 移動模式

| 模式 | 說明 |
|------|------|
| 🗺 導航 | 透過 OSRM 取得真實路網路線——右鍵地圖選「導航到此」 |
| 🛳 巡航 | 多航點路線（前端插值，舊版） |
| 🕹 搖桿 | WASD / 方向鍵 5 Hz 連續移動 |
| 🚶 隨機漫步 | Seed 決定性隨機漫步，面積均勻分布，支援群組同步 |
| 📌 多點導航 | 逐段 OSRM 路線，支援停留時間、跳躍模式、循環 |
| 🔁 路線循環 | 閉環路線，可設定圈數 |

### 進階功能

| 功能 | 說明 |
|------|------|
| ⏱ Pokemon 冷卻 | 距離制軟封禁計時器（對應 LocWarp 冷卻表） |
| 👑 領導交接 | 主機斷線 → 快照 → 自動提升下一台繼續 |
| 📶 WiFi Tunnel | USB 配對後切換為 WiFi 連線 |
| 🎮 GoldDitto 循環 | 跨越 S2 邊界的 Teleport 序列，觸發 Ditto 機制 |
| 🗺 S2 網格疊圖 | 在地圖上繪製 L14（黃）/ L17（紅）Cell 邊界 |
| ⭐ 雲端書籤 | 後端 JSON 持久化最愛地點，無痕視窗仍可存取 |
| 📤 GPX 匯出 | 航點路線匯出為標準 `.gpx` 檔案 |
| 🔍 地點搜尋 | Nominatim 全球地理編碼 |

---

## 系統需求

| 項目 | 需求 |
|------|------|
| **作業系統** | macOS（需 `sudo` 建立 USB tunnel / utun 介面） |
| **Python** | 3.11 以上 |
| **iPhone iOS** | iOS 16 以上 |
| **開發者模式** | iPhone 上**必須開啟**（設定 → 隱私與安全性 → 開發者模式） |
| **連線方式** | USB（Lightning 或 USB-C）；初次配對後可切換 WiFi |
| **瀏覽器** | Chrome / Firefox / Safari |
| **網路** | 後端僅需本機；OSRM 路由與地理搜尋需可連外網 |

---

## 安裝與快速開始

### 1. 信任 iPhone 並開啟開發者模式

用 USB 連接 iPhone，點選「**信任此電腦**」，再開啟開發者模式：

```bash
# 方法 A — 命令列（iPhone 需已解鎖並完成信任）
python3 -m pymobiledevice3 amfi enable-developer-mode

# 方法 B — 手動操作
# iPhone：設定 → 隱私與安全性 → 開發者模式 → 開啟 → 重新啟動
```

### 2. Clone 並啟動

```bash
git clone https://github.com/ArohaLin/iphone-gps-controller-pro.git
cd iphone-gps-controller-pro
./start.sh          # 自動建立 venv、安裝相依套件、啟動後端、開啟瀏覽器
```

首次執行時腳本會自動建立 Python venv 並安裝所有套件。macOS 會要求 `sudo`（建立 USB tunnel 需要 root 才能操作 utun 介面）。

### 3. 設定 GPS 位置

1. 確認左側裝置清單中 iPhone 顯示**綠點（已連線）**
2. 點擊地圖上任意位置 → iPhone GPS 約 1 秒內更新
3. 右鍵地圖可選擇：導航到此 / 加入航點

### 停止服務

```bash
./stop.sh           # 終止 8090 port 上的 process
# 或在執行 ./start.sh 的終端機按 Ctrl+C
```

自訂 port：

```bash
./start.sh 9000
./stop.sh  9000
```

---

## 架構說明

```
iphone-gps-controller-pro/
├── backend/
│   ├── main.py                    # aiohttp 應用入口、AppState、路由註冊
│   ├── config.py                  # 常數、速度設定檔、冷卻表
│   ├── core/
│   │   ├── device_manager.py      # USB 掃描（三層 fallback）、Tunnel 生命週期
│   │   ├── simulation_engine.py   # 中央 FSM、tick-budgeted _move_along_route
│   │   ├── navigator.py           # 單目標 OSRM 路線
│   │   ├── joystick.py            # 5 Hz tick handler（WASD WebSocket 輸入）
│   │   ├── random_walk.py         # Seed 決定性、面積均勻、連線錯誤退避
│   │   ├── multi_stop.py          # 逐段路線、跳躍模式、循環
│   │   ├── route_loop.py          # 閉環、每圈重取 OSRM、lap_count
│   │   └── goldditto.py           # Pokemon GO S2 邊界 Teleport 循環
│   ├── api/
│   │   ├── location.py            # 所有移動模式的 REST 端點
│   │   ├── device.py              # WiFi Tunnel 切換
│   │   ├── bookmark.py            # 書籤 CRUD + localStorage 遷移
│   │   └── websocket.py           # /ws/status WebSocket 廣播
│   ├── services/
│   │   ├── interpolator.py        # haversine、move_point、add_jitter、random_point_in_radius
│   │   ├── route_service.py       # OSRM 客戶端 + 直線 fallback
│   │   ├── cooldown.py            # Pokemon 風格距離制冷卻計時器
│   │   ├── bookmark_service.py    # JSON 持久化（asyncio 鎖）
│   │   └── wifi_tunnel.py         # WiFi Tunnel 輔助
│   └── models/
│       └── schemas.py             # @dataclass Coordinate/SimulationStatus、Enum State/Mode
├── frontend/
│   ├── index.html                 # 單頁應用，所有 JS 內嵌
│   └── css/base.css               # 調色盤 + 元件樣式
├── start.sh                       # 一鍵啟動
├── stop.sh                        # 終止 port process
└── requirements.txt
```

### 運作流程

```
./start.sh
 └─ backend/main.py（aiohttp）
      ├─ AppState  ──── engines: {udid → SimulationEngine}
      │                 cooldown: CooldownTimer
      │                 USB 斷線 → 快照 → 提升下一台 → resume
      │
      ├─ device_scanner（每 6 秒）
      │    ├─ 新裝置 → setup_device → tunnel → gps_worker → SimulationEngine
      │    └─ 裝置移除 → 快照 → 提升新主機 → resume_from_snapshot
      │
      ├─ SimulationEngine（每台裝置）
      │    ├─ teleport / navigate / start_joystick / start_random_walk / …
      │    └─ _move_along_route ← tick-budgeted（先 anchor tick_start 再推送）
      │
      └─ /ws/status ← WebSocket 廣播（position_update、state_change、…）

瀏覽器（frontend/index.html）
 ├─ WebSocket 客戶端 → position_update → 標記即時更新（無輪詢延遲）
 ├─ 6 秒輪詢         → /api/devices    → 僅同步裝置清單
 └─ 右鍵選單         → /api/device/{idx}/navigate、/joystick/start、…
```

---

## 模式操作說明

### 📍 一般模式

- **點擊地圖** → 立即 Teleport GPS  
- **手動輸入** → 在側欄輸入 Lat/Lon → 前往  
- **方向鍵盤** → 8 方向移動，可設定步距（公尺）  
- **右鍵選單** → 設定 GPS / 導航到此 / 加入航點  
- **移動速度** → 步行 / 跑步 / 駕車（用於導航模式）  
- **清除 GPS** → 解除模擬，iPhone 回復真實 GPS  

---

### 🗺 導航（右鍵選單）

1. 右鍵點擊地圖任意位置 → **導航到此**
2. 後端向 OSRM 公開 Demo API 取得真實路網路線
3. iPhone 沿街道移動；地圖繪製虛線路徑
4. 導航完成 → Toast 通知 + 路徑線消失

若 OSRM 失敗，自動改用直線插值 fallback（每 25 m 一點）。

---

### 🛳 巡航模式

前端插值的舊版模式。  
在「巡航」分頁點擊地圖加入航點 → 播放 / 停止 / 循環 / 匯出 GPX。  
需要真實路網建議改用**多點導航**（後端 OSRM）。

---

### 🕹 搖桿模式

1. 先在一般模式設定起始位置（Teleport）
2. 切換到**搖桿**分頁 → 選擇移動速度 → **啟動搖桿**
3. 按住 **WASD** 或**方向鍵**持續移動（5 Hz）
4. 放開按鍵 → 停止；自動送出 WS `joystick_stop`

---

### 🚶 隨機漫步模式

1. 點擊「使用目前位置」設定中心點
2. 設定半徑（公尺）與可選的 Seed
3. **開始漫步** → iPhone 在半徑內以真實路網隨機遊走

Seed 同步：兩台裝置相同 Seed → 路徑 100% 相同。  
連線錯誤最多重試 60 次（指數退避）。

---

### 📌 多點導航

使用「**巡航**分頁」中加入的航點。

| 選項 | 說明 |
|------|------|
| 停留秒數 | 每站停留時間（0 = 隨機 1–3 秒） |
| 模式 | 步行 / 跑步 / 駕車 |
| 跳躍模式 | 直接 Teleport 到每站（不走路線） |
| 循環 | 跑完最後一站後從頭再跑 |

WS 事件：`stop_reached`、`multi_stop_complete`、`lap_complete`

---

### 🔁 路線循環

使用「**巡航**分頁」的航點，最後一點自動銜接回起點。

| 選項 | 說明 |
|------|------|
| 圈數 | 0 = 無限；>0 = 跑完 N 圈後停止 |
| 模式 | 步行 / 跑步 / 駕車 |

每圈重新向 OSRM 取路線。WS：`lap_complete`、`loop_complete`

---

### ⏱ Pokemon 冷卻

Teleport 時自動觸發，依距離查表：

| 距離 | 冷卻時間 |
|------|----------|
| ≤ 1 km   | 0 秒     |
| ≤ 5 km   | 30 秒    |
| ≤ 10 km  | 2 分鐘   |
| ≤ 25 km  | 5 分鐘   |
| ≤ 100 km | 15 分鐘  |
| ≤ 250 km | 25 分鐘  |
| ≤ 500 km | 45 分鐘  |
| ≤ 750 km | 1 小時   |
| ≤ 1000 km| 1.5 小時 |
| > 1000 km| 2 小時   |

冷卻期間：Teleport 請求回傳 HTTP 429，地圖頂部顯示倒數 Banner。

---

### 🎮 Pokemon GO 工具組（Pogo 分頁）

**GoldDitto 循環**

以中心點為基準，向 10 個跨越 S2 L17 邊界的點依序 Teleport，觸發 Ditto 出沒機制。可設定每點停留秒數與重複次數。

**S2 網格疊圖**

| 等級 | 顏色 | 顯示縮放 |
|------|------|----------|
| L17  | 紅色 | ≥ 15     |
| L14  | 黃色 | ≥ 13     |

---

### 👑 領導交接（多裝置）

主要裝置（Primary）斷線時：
1. 抓取目前模擬快照（位置、路段索引、Seed 計數等）
2. 下一台可用裝置升格為主機（顯示 👑 標誌）
3. 新主機從快照位置繼續執行原路線

新裝置加入時，自動 Teleport 到當前主機位置並開始同步。

---

## HTTP API 參考

Base URL：`http://127.0.0.1:8090`（CORS 全開放）

### 裝置

| Method | 路徑 | 說明 |
|--------|------|------|
| GET | `/api/devices` | 取得所有裝置清單 |
| GET | `/api/device/{idx}/status` | 單一裝置狀態 |
| POST | `/api/device/{idx}/set` | Teleport GPS（`{lat, lon}`） |
| POST | `/api/device/{idx}/clear` | 清除 GPS 模擬 |
| POST | `/api/device/{idx}/wifi-tunnel` | 切換 WiFi Tunnel |

### 移動模式

| Method | 路徑 | Request Body |
|--------|------|------|
| POST | `/api/device/{idx}/navigate` | `{lat, lng, mode, speed_kmh?}` |
| POST | `/api/device/{idx}/stop` | — |
| POST | `/api/device/{idx}/joystick/start` | `{mode}` |
| POST | `/api/device/{idx}/random-walk/start` | `{center_lat, center_lng, radius_m, mode, seed?}` |
| POST | `/api/device/{idx}/multi-stop/start` | `{waypoints, mode, stop_duration, loop, jump_mode}` |
| POST | `/api/device/{idx}/route-loop/start` | `{waypoints, mode, lap_count?}` |
| POST | `/api/device/{idx}/goldditto/start` | `{center_lat, center_lng, dwell_sec, repeat}` |

### 書籤

| Method | 路徑 | 說明 |
|--------|------|------|
| GET | `/api/bookmarks` | 取得所有書籤 |
| POST | `/api/bookmarks` | 新增書籤（`{name, lat, lng}`） |
| DELETE | `/api/bookmarks/{id}` | 刪除書籤 |
| POST | `/api/bookmarks/{id}/rename` | 重新命名（`{name}`） |
| POST | `/api/bookmarks/migrate` | 從 localStorage 遷移（`[{name,lat,lng}]`） |

### 其他

| Method | 路徑 | 說明 |
|--------|------|------|
| GET | `/api/cooldown` | 冷卻狀態 |
| GET | `/ws/status` | WebSocket 升級 |

---

## WebSocket 事件

連線至 `ws://localhost:8090/ws/status`，所有訊息格式：

```json
{ "type": "<event>", "data": { ... } }
```

| 事件 | 資料欄位 | 說明 |
|------|----------|------|
| `position_update` | `udid, state, position{lat,lng}` | 每個 GPS tick 發送 |
| `state_change` | `udid, state` | 模式 FSM 狀態切換 |
| `device_connected` | `udid, name, ios, is_primary` | 新裝置就緒 |
| `device_disconnected` | `udid` | 裝置移除 |
| `leadership_change` | `udid` | 新主機選出 |
| `route_path` | `udid, coords[[lat,lng],…]` | 繪製路線折線 |
| `navigation_complete` | `udid, lat, lng` | 導航完成 |
| `stop_reached` | `udid, stop_idx, lat, lng` | 多點到站 |
| `lap_complete` | `udid, lap` | 完成一圈 |
| `loop_complete` | `udid, laps` | 所有圈數完成 |
| `multi_stop_complete` | `udid` | 多點路線結束 |
| `goldditto_complete` | `udid` | Ditto 循環完成 |
| `cooldown_active` | `active, remaining_sec, total_sec, distance_km` | 冷卻開始 |
| `cooldown_ended` | — | 冷卻結束 |

---

## 鍵盤快速鍵

> 焦點在輸入框時快速鍵不生效。  
> **搖桿模式**下，WASD 與方向鍵改為送出 `joystick_input`。

| 按鍵 | 動作 |
|------|------|
| `↑` / `W` | 向北移動 |
| `↓` / `S` | 向南移動 |
| `←` / `A` | 向西移動 |
| `→` / `D` | 向東移動 |
| `Q` | 向西北移動 |
| `E` | 向東北移動 |
| `Z` | 向西南移動 |
| `C` | 向東南移動 |
| `+` / `=` | 地圖放大 |
| `-` | 地圖縮小 |
| `F` | 地圖回到目前座標 |

---

## 常見問題

**Q1：啟動後沒有偵測到裝置？**
- 確認 iPhone 已解鎖並選擇「信任此電腦」
- 嘗試重新插拔 USB 線
- 執行 `python3 -m pymobiledevice3 usbmux list` 確認裝置可被偵測

**Q2：Tunnel 一直失敗？**
- 確認 iPhone 已開啟開發者模式（設定 → 隱私與安全性 → 開發者模式）
- 確認已安裝最新版 Xcode Command Line Tools：`xcode-select --install`
- 嘗試重新啟動 iPhone 再連線

**Q3：GPS 設定後 iPhone 位置沒有改變？**
- 確認裝置卡顯示**綠點（已連線）**
- 確認裝置狀態不是 `disconnected` 或 `reconnecting`
- 部分 App 需重新開啟才能讀取到新位置

**Q4：後端無法連線 / 「Backend 未啟動」？**
- 確認 `./start.sh` 正在執行——查看終端機顯示的 port 號
- 若 port 有變更，重新執行 `./stop.sh && ./start.sh`
- 瀏覽器開發者工具 → Network：確認對 `localhost:8090` 的請求是否成功

**Q5：冷卻 Banner 一直不消失？**
- Banner 反映真實冷卻時間，等待倒數結束即可
- 或重啟後端（`./stop.sh && ./start.sh`）重置冷卻狀態

**Q6：OSRM 導航很慢 / 改走直線？**
- 公開 OSRM Demo 伺服器（`router.project-osrm.org`）可能有速率限制
- 若需穩定使用，可自行架設 OSRM 並修改 `backend/config.py` 中的 `OSRM_BASE_URL`

**Q7：S2 網格沒有顯示？**
- L17 需縮放至 ≥ 15，L14 需縮放至 ≥ 13
- 確認瀏覽器主控台中 s2-geometry CDN 已成功載入

---

## 第三方授權

| 套件 | 授權 |
|------|------|
| [Leaflet.js](https://leafletjs.com/) | BSD 2-Clause |
| [OpenStreetMap / Nominatim](https://www.openstreetmap.org/) | ODbL |
| [Open-Meteo API](https://open-meteo.com/) | CC BY 4.0 |
| [OSRM](https://project-osrm.org/) | BSD 2-Clause |
| [s2-geometry](https://github.com/nicktacular/node-s2) | Apache 2.0 |
| [pymobiledevice3](https://github.com/doronz88/pymobiledevice3) | GPL-3.0 |
| [aiohttp](https://docs.aiohttp.org/) | Apache 2.0 |
| [httpx](https://www.python-httpx.org/) | BSD 3-Clause |

---

*Copyright (c) 2026 Aroha Lin — MIT License*
