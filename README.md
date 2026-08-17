# PowerPoint 簡報翻譯與語音嵌入網站

這是一個公司內部使用的本機全端專案。前端使用 Next.js、TypeScript 與 Tailwind CSS；後端使用 Python 3.11、FastAPI、Pydantic、python-pptx，正式音訊嵌入模式使用 pywin32 操作 Microsoft PowerPoint。

## 專案結構

```text
backend/
  app/
    api/                FastAPI 路由與下載端點
    core/               設定與安全錯誤類型
    models/             工作狀態模型
    pptx/               PowerPoint 解析、寫回、音訊嵌入與輸出驗證
    services/           工作管理、翻譯、TTS、清理與處理流程
    utils/              檔名安全處理
  tests/                後端自動測試
frontend/
  app/                  Next.js 頁面與全域樣式
  components/           上傳、語言、進度、完成、錯誤與說明元件
  lib/                  API client 與型別
```

## 後端啟動

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

若要使用 Windows SAPI 或 Microsoft PowerPoint COM，請在互動式 PowerShell 中啟動後端：

```powershell
cd backend
.\start-backend-interactive.ps1
```

## 前端啟動

```powershell
cd frontend
pnpm install --frozen-lockfile
Copy-Item .env.local.example .env.local
pnpm dev
```

開啟 `http://localhost:3000`。

## 模擬模式

`.env.example` 預設使用：

```text
TRANSLATION_PROVIDER=mock
TTS_PROVIDER=mock
AUDIO_EMBED_PROVIDER=mock
```

此模式不需要 API 金鑰，也不會啟動 Microsoft PowerPoint，可測試上傳、進度、翻譯寫回、下載流程。Mock TTS 會建立測試音訊檔；Mock audio embedder 不會真正將音訊嵌入簡報。

## 正式服務設定位置

在 `backend/.env` 設定：

```text
TRANSLATION_PROVIDER=external
TRANSLATION_API_KEY=...
TRANSLATION_API_URL=...
TTS_PROVIDER=external
TTS_API_KEY=...
TTS_API_URL=...
AUDIO_EMBED_PROVIDER=com
```

正式翻譯服務請在 `backend/app/services/translation.py` 的 `ExternalTranslationService` 串接公司 API。正式語音服務請在 `backend/app/services/tts.py` 的 `ExternalTextToSpeechService` 串接公司 API，輸出每頁一個 MP3。

## Windows 與 PowerPoint 設定

- 使用 Windows。
- 安裝 Microsoft PowerPoint 桌面版。
- 後端執行帳號需要能啟動 PowerPoint COM Automation。
- 正式嵌入音訊時將 `AUDIO_EMBED_PROVIDER=com`。
- 建議不要把此服務放在無互動桌面的 Windows Service 中執行；PowerPoint COM 自動化通常需要一般桌面工作階段。

## 操作流程

1. 開啟網站。
2. 上傳單一 `.pptx`，大小不可超過 50 MB。
3. 選擇原始語言與目標語言，兩者不可相同。
4. 按下「開始翻譯」。
5. 等待後端進度更新。
6. 完成後下載輸出簡報。
7. 檔案保留 30 分鐘，可在保存期限內重複下載。

## 測試

```powershell
cd backend
pytest
```

前端可執行：

```powershell
cd frontend
pnpm build
```
## 目前限制

- 第一版同一時間只處理一個 PowerPoint 檔案。
- 不支援登入、資料庫、多檔案排隊、PDF、OCR、圖片文字辨識或圖片文字翻譯。
- 不翻譯表格、SmartArt、圖表、WordArt、群組物件、嵌入物件、頁碼、日期與頁尾。
- Mock audio embedder 不會真正嵌入音訊；正式嵌入需 Windows、PowerPoint 與 pywin32。
- 複雜版面仍可能需要人工確認。
