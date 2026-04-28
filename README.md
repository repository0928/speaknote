# 🎙️ SpeakNote 語音筆記

一個輕量的語音轉文字筆記 Widget，無需安裝、無需後端，用瀏覽器打開即可使用。

## 功能

- 🎤 **語音轉文字** — 使用 Web Speech API，支援中文（台灣 / 大陸）、英文、日文
- 📝 **多筆記列表** — 每次錄音自動新增一則，可手動編輯
- 💾 **自動儲存** — 所有筆記存在瀏覽器 localStorage，關閉後不消失
- 📤 **複製 / 下載** — 一鍵複製到剪貼簿或下載為 .txt 檔案
- 📱 **響應式設計** — 手機、平板、桌機皆可使用

## 使用方式

直接打開部署後的網址，點擊「開始錄音」即可。

> **注意：** 語音辨識功能需要使用 **Chrome** 或 **Edge** 瀏覽器，並允許麥克風權限。

## 本機執行

```bash
# 任意靜態伺服器皆可，例如：
npx serve .
# 或
python -m http.server 3000
```

## 部署（Zeabur）

1. 將此 repo push 到 GitHub
2. 在 Zeabur 建立新專案 → 選「從 GitHub 匯入」→ 選此 repo
3. Zeabur 自動偵測靜態網站並部署
4. 取得公開網址分享給其他裝置

## 技術架構

- 純 HTML / CSS / JavaScript（無框架、無依賴）
- Web Speech API（瀏覽器原生）
- localStorage（本地持久化）

## 檔案結構

```
speaknote/
├── index.html      # 主頁面
├── style.css       # 樣式
├── app.js          # 邏輯（語音 + 筆記管理）
├── manifest.json   # PWA 設定
└── README.md
```

## 授權

MIT License
