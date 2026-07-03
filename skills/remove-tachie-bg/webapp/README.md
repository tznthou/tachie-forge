# 立繪去背系統 — 本地 Web UI

方向三「帶圖去背」的圖形介面。拖一張現成立繪進來,去背成透明 PNG,並排看深底/白底雙檢查,滿意就下載。

## 啟動

依賴(含 flask)已列在專案根目錄 `requirements.txt`,用 uv 建環境(在**專案根目錄**執行,只需一次):

```bash
uv venv .venv --python 3.13
uv pip install -r requirements.txt
```

之後雙擊 `start.command`(macOS,自動使用專案 `.venv`),或從專案根目錄手動:

```bash
.venv/bin/python3 skills/remove-tachie-bg/webapp/app.py
```

瀏覽器開 <http://localhost:8765>。

## 操作

1. 拖圖進來(或點擊選擇)
2. 選原圖背景類型 —— **只有「綠幕」會觸發去綠**,其餘走標準去背
3. 按「開始去背」
4. 看三欄:**透明成品** / **深底檢查**(抓亮邊:白邊、亮飄髮)/ **白底檢查**(抓暗/綠邊:green spill)
5. 滿意就下載透明 PNG

## 為什麼要雙底檢查

去背瑕疵有方向性:亮色瑕疵(白邊、飄髮)只在深底現形、白底隱形;綠邊/暗邊只在白底現形、深底被藏。**單看一種會漏判**,所以並排給眼睛看兩張。這是這幾天測試驗證出來的核心方法論。

## 架構

- `app.py` — Flask 後端,subprocess 呼叫 `../scripts/remove_bg.py`(**不動已驗證的去背核心**)
- `static/index.html` — 前端(vanilla JS,自包含,無外部依賴)
- `start.command` — macOS 雙擊啟動器

## 邊界

- 動漫風格立繪(`isnet-anime` 模型的能力範圍)
- **封閉輪廓**(頭髮/配件圈住背景,含髮束細縫的微觀版——縫隙殘留)、**畫在稿裡的飄髮** = 去背救不了,得回生圖端調整。主變數是輪廓開放度;背景色是保險絲(綠殘留可去綠,棋盤格灰白殘留無解)
- 不做批次、背景自動偵測(v2 scope)
