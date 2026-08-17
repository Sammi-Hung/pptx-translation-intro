# PowerPoint 簡報翻譯與語音嵌入網站規格書

版本：1.3  
更新日期：2026-07-22  
用途：公司內部使用的本機 PowerPoint 翻譯、講者備註轉語音與音訊嵌入工具

## 1. 專案目標

本系統提供一個可在 Windows 本機執行的網站，讓使用者上傳 `.pptx` PowerPoint 檔案，選擇原始語言、目標語言與翻譯模型後，自動完成：

- 投影片指定文字內容翻譯
- 講者備註翻譯
- 講者備註文字轉語音
- 將語音嵌入對應投影片
- 進度顯示、停止翻譯、檔案下載與暫存清理

第一版不包含登入、資料庫、多檔案排隊、PDF、OCR、圖片文字辨識或圖片內文字翻譯。

## 2. 執行環境

前端：
- Next.js
- TypeScript
- Tailwind CSS
- pnpm

後端：
- Python 3.11 以上
- FastAPI
- Pydantic
- python-pptx
- pywin32

Windows 需求：
- Windows 桌面環境
- 已安裝 Microsoft PowerPoint
- 已安裝目標語言對應的 Windows SAPI 語音包
- 後端需以互動式 PowerShell 啟動，不建議使用 hidden background process 或 Windows Service

## 3. 網站操作流程

1. 使用者開啟前端網站。
2. 上傳一個 `.pptx` 檔案。
3. 選擇原始語言與目標語言。
4. 選擇翻譯模型。
5. 系統檢查檔案格式、大小、語言組合與語音包狀態。
6. 使用者按下「開始翻譯」。
7. 處理期間鎖定上傳區、語言選單、模型選單與送出按鈕。
8. 前端每秒向後端查詢工作狀態。
9. 使用者可在處理中按下「停止翻譯」。
10. 完成後顯示結果統計與下載按鈕。
11. 失敗或停止時顯示可理解的錯誤或停止訊息，不提供下載。

## 4. 支援語言

| 語言 | 代碼 |
| --- | --- |
| 繁體中文 | `zh-TW` |
| 英文 | `en-US` |
| 泰文 | `th-TH` |

限制：
- 原始語言與目標語言不能相同。
- 文字轉語音語言必須與目標語言一致。
- 若缺少對應 Windows SAPI 語音包，前端需顯示警訊並禁止送出。

## 5. 檔案限制

- 僅支援 `.pptx`。
- 不支援 `.ppt`、PDF、Keynote 或其他格式。
- 最大檔案大小為 50 MB。
- 一次只能上傳一個檔案。
- 伺服器內部使用安全固定檔名保存，不直接使用使用者原始檔名作為路徑。
- 輸出檔名保留原始可辨識名稱，並在副檔名前加入目標語言代碼。

範例：
- `Training_zh-TW.pptx`
- `Training_en-US.pptx`
- `Training_th-TH.pptx`

## 6. 翻譯模型切換

前端需顯示翻譯模型選單，使用者可在送出前切換雲端或地端模型。處理期間模型選單需鎖定。

目前翻譯模型 profile：

| Profile | 顯示名稱 | Provider | Endpoint | Model |
| --- | --- | --- | --- | --- |
| `cloud` | 雲端模型 | Gemini | 後端 `.env` 設定 | `gemini-3-flash-preview` |
| `local-primary` | 地端模型一 | Ollama | `http://your-primary-ollama-host:11434/v1` | `your-primary-model` |
| `local-secondary` | 地端模型二 | Ollama | `http://your-secondary-ollama-host:11434/v1` | `your-secondary-model` |

安全要求：
- 前端不得顯示 API key。
- 前端只顯示模型名稱、provider 與地端 endpoint。
- 雲端 API key 僅由後端 `.env` 管理。
- 每個 job 需保存使用者當次選擇的 `translation_profile`、`translation_provider` 與 `translation_model`。

Ollama 行為：
- 後端使用 Ollama native `/api/chat`。
- 不送 Authorization header。
- 預設不設定 `TRANSLATION_OLLAMA_NUM_GPU`，由 Ollama host 自行決定 GPU 使用方式。
- 只有在排查 CUDA 或 GPU 權限問題時，才手動設為 `0` 強制 CPU。

## 7. 翻譯服務設定

後端 `.env` 範例：

```env
TRANSLATION_PROVIDER=ollama
TRANSLATION_API_KEY=
TRANSLATION_API_URL=http://your-ollama-host:11434/v1
TRANSLATION_MODEL=your-local-model
TRANSLATION_OLLAMA_NUM_GPU=

TRANSLATION_CLOUD_PROVIDER=gemini
TRANSLATION_CLOUD_API_URL=
TRANSLATION_CLOUD_MODEL=gemini-3-flash-preview

TRANSLATION_LOCAL_PRIMARY_API_URL=http://your-primary-ollama-host:11434/v1
TRANSLATION_LOCAL_PRIMARY_MODEL=your-primary-model

TRANSLATION_LOCAL_SECONDARY_API_URL=http://your-secondary-ollama-host:11434/v1
TRANSLATION_LOCAL_SECONDARY_MODEL=your-secondary-model
```

支援 provider：
- `mock`
- `gemini`
- `google`
- `openai`
- `external`
- `ollama`

沒有正式 API key 時，可使用 mock 或 Ollama 地端模型進行最小流程測試。

## 8. 投影片文字翻譯範圍

需逐頁處理 PowerPoint。

翻譯內容：
- 一般文字方塊
- 標題 Placeholder
- 本文 Placeholder
- 內容 Placeholder 中的文字
- 具有文字框架且未被排除的 AutoShape 文字

不翻譯內容：
- 圖片內文字
- 表格文字
- SmartArt
- 圖表文字
- WordArt
- 群組物件
- 嵌入式 Excel 或其他嵌入物件
- 音訊
- 影片
- 頁碼
- 日期
- 頁尾

不送翻譯服務的文字：
- 空白文字
- 只有數字
- 只有符號
- 純網址
- 純電子郵件地址

## 9. 格式保留要求

投影片文字必須以段落為單位翻譯，不可用整個文字方塊覆蓋。

需盡量保留：
- 文字方塊位置
- 文字方塊寬度與高度
- 段落順序
- 條列符號
- 條列層級
- 對齊方式
- 字型
- 字體大小
- 粗體
- 斜體
- 字體顏色
- 行距
- 段落間距

若段落內有多個不同格式 run：
- 第一版保留第一個 run 的格式。
- 將完整翻譯結果寫入第一個 run。
- 清空其餘 run。
- 保留段落格式、條列層級與對齊方式。

文字可能溢出時：
- 每次縮小 1 pt。
- 最低不得小於 14 pt。
- 若仍可能溢出，保留文字並加入 warning，標記投影片頁碼與文字方塊名稱。

## 10. 講者備註翻譯與語音

若投影片有有效講者備註：
- 將備註正文視為單一翻譯單位。
- 翻譯成適合朗讀的自然口語。
- 不可摘要、延伸或加入原文沒有的內容。
- 翻譯結果寫回該張投影片的講者備註區。
- 翻譯後備註交給 TTS 產生語音。

若投影片沒有講者備註：
- 不自動建立備註。
- 不使用投影片文字代替講稿。
- 不產生語音。

若備註為空白、只有數字、只有符號或沒有可朗讀內容：
- 不產生語音。

## 11. 文字轉語音

目前主要 TTS provider：
- `sapi`：Windows 本機 SAPI
- `mock`：測試模式
- `external`：保留正式服務接口

Windows SAPI 要求：
- 後端需在互動式使用者桌面環境中執行。
- 目標語言需安裝對應 Windows 語音包。
- 前端需透過 API 取得語音包狀態。
- 若沒有對應語音包，前端需顯示警訊並禁止送出。

語音檔規則：
- 每張有有效講者備註的投影片產生一個獨立音訊檔。
- 檔名使用三位數頁碼，例如 `slide_001.wav`。
- 若某頁語音產生失敗，整個 job 失敗，不提供下載。

## 12. PowerPoint 音訊嵌入

使用 pywin32 與 Microsoft PowerPoint COM Automation 將音訊嵌入 `.pptx`。

嵌入要求：
- 音訊必須真正存入 `.pptx`，不可只建立連結。
- 每張有有效備註的投影片只嵌入一個翻譯旁白。
- 物件名稱格式：`TranslatedNarration_###`。
- 若已存在 `TranslatedNarration_` 開頭物件，先移除再嵌入。
- 音訊物件放在投影片角落，尺寸小，不遮住主要內容。

播放設定：
- 進入投影片時自動播放。
- 只播放一次。
- 不循環。
- 不跨投影片播放。
- 放映時隱藏音訊圖示。
- 不自動切換下一頁。

COM 安全要求：
- 必須有完整例外處理。
- 即使發生錯誤，也要關閉簡報。
- PowerPoint 程式需結束，不留下背景 PowerPoint process。

## 13. 工作狀態與進度

每次上傳建立不可預測 UUID job id。

每個 job 獨立資料夾：

```text
storage/
  {job_id}/
    upload.pptx
    working.pptx
    audio/
      slide_001.wav
      slide_002.wav
    output.pptx
    status.json
```

狀態欄位至少包含：
- job id
- 原始檔名
- 輸出檔名
- 原始語言
- 目標語言
- 翻譯 profile
- 翻譯 provider
- 翻譯 model
- 工作狀態
- 進度百分比
- 目前階段
- 目前頁數
- 總頁數
- 建立時間
- 完成時間
- 過期時間
- warning
- error code
- error message
- cancel requested
- output validated
- 統計資料

工作狀態：
- `pending`
- `running`
- `completed`
- `failed`
- `canceled`
- `expired`

進度階段：
- 驗證上傳檔案
- 解析簡報
- 擷取投影片文字與講者備註
- 翻譯投影片文字
- 翻譯講者備註
- 將翻譯內容寫回簡報
- 產生語音
- 將語音嵌入投影片
- 驗證輸出簡報
- 處理完成
- 處理失敗

## 14. 即時停止翻譯

前端在 job `pending` 或 `running` 時顯示「停止翻譯」按鈕。

停止流程：
1. 使用者按下「停止翻譯」。
2. 前端呼叫 `POST /api/jobs/{job_id}/cancel`。
3. 後端將 `cancel_requested` 設為 `true`。
4. 前端按鈕顯示「停止中」並持續輪詢 job 狀態。
5. 後端處理流程在檢查點偵測取消請求後停止。
6. job 狀態改為 `canceled`。
7. 前端顯示停止訊息。
8. 停止後不提供下載。

取消檢查點：
- 開始解析前
- 解析後
- 每個投影片文字段落翻譯前
- 每個投影片文字段落翻譯後、寫回前
- 每頁講者備註翻譯前
- 每頁講者備註翻譯後、寫回前
- 每頁語音產生前
- 每頁語音產生後
- 音訊嵌入前
- 輸出驗證前

限制：
- 若正在等待單次 Ollama、Gemini 或其他模型 HTTP 回應，無法硬中斷該次推理。
- 該次模型回應結束後，系統會在下一個檢查點停止。
- 停止後不會繼續處理後續頁面、語音或輸出驗證。

## 15. 下載與保存期限

完成後前端顯示：
- 翻譯完成
- 輸出檔名
- 投影片總頁數
- 已處理文字頁數
- 成功產生語音頁數
- 沒有講者備註頁數
- warning 數量
- 下載按鈕
- 翻譯其他檔案按鈕
- 檔案到期時間

下載前後端需確認：
- job id 有效
- job 狀態為 `completed`
- 輸出檔案存在
- 檔案未過期
- 輸出簡報已通過驗證

以下狀態不可下載：
- `pending`
- `running`
- `failed`
- `canceled`
- `expired`

工作完成、失敗或停止後，檔案保留 30 分鐘。超過保存期限後，自動刪除整個 job 資料夾。

## 16. 輸出驗證

完成後需驗證：
- 輸出 `.pptx` 存在。
- 檔案大小大於 0。
- 可由 python-pptx 成功開啟。
- 投影片數量與原始簡報相同。
- 原有圖片和圖形未消失。
- 需要語音的頁面都有對應語音。
- 音訊嵌入流程成功完成。

驗證失敗時：
- job 標示為 failed。
- 不提供下載。

## 17. 前端介面要求

既有版面需保留：
- 大型上傳區
- 語言與語音區
- 淡色說明區塊
- 備註與語音包說明區塊

新增功能呈現方式：
- 翻譯模型選單嵌入既有「語言與語音」區，不新增新的大型版面區塊。
- 停止翻譯按鈕顯示於既有進度卡右上角。
- 處理期間鎖定上傳、移除檔案、語言選單、模型選單與送出按鈕。

錯誤顯示：
- 不顯示 API key。
- 不顯示伺服器完整本機路徑。
- 不顯示 stack trace。
- 詳細技術錯誤寫入後端 log。
- 前端輪詢工作狀態時，若單次 `GET /api/jobs/{job_id}` 因暫時性網路或連線問題失敗，不得立即顯示「處理失敗」。
- 真正的處理失敗只能由後端 job 狀態 `failed`、`canceled` 或下載 API 的明確錯誤回應決定。
- 若任務仍為 `pending` 或 `running`，前端需保留進度畫面並等待下一次輪詢恢復。

## 18. 後端 API

| Method | Path | 說明 |
| --- | --- | --- |
| `GET` | `/health` | 健康檢查 |
| `GET` | `/api/translation/options` | 取得前端可選翻譯模型 |
| `GET` | `/api/tts/voices/{language}` | 檢查 Windows SAPI 語音包 |
| `POST` | `/api/jobs` | 建立 PowerPoint 翻譯工作 |
| `GET` | `/api/jobs/{job_id}` | 查詢工作狀態 |
| `POST` | `/api/jobs/{job_id}/cancel` | 請求停止翻譯 |
| `GET` | `/api/jobs/{job_id}/download` | 下載完成檔案 |

## 19. 啟動方式

後端：

```powershell
cd PROJECT_ROOT\backend
.\start-backend-interactive.ps1
```

後端啟動注意事項：
- 後端 PowerShell 視窗屬於必要執行元件，不是錯誤視窗。
- 視窗中出現 `Uvicorn running on http://0.0.0.0:8000` 代表 FastAPI 已正常啟動。
- 測試期間需保持此 PowerShell 視窗開啟；關閉視窗或按下 `CTRL+C` 會停止後端，前端將無法取得模型設定、語音包狀態、進度與下載檔案。
- 因 Windows SAPI 語音包與 Microsoft PowerPoint COM Automation 需要互動式使用者桌面環境，後端不建議改成 hidden background process 或 Windows Service。

前端：

```powershell
cd PROJECT_ROOT\frontend
pnpm dev
```

建議使用總啟動腳本，讓後端 watchdog 常駐並在 FastAPI 掛掉時自動重啟：

```powershell
PROJECT_ROOT\.runtime-logs\start-site.ps1
```

目前常用網址：

```text
前端：http://your-host-ip:3000
後端：http://your-host-ip:8000
後端文件：http://your-host-ip:8000/docs
```

服務穩定性要求：
- 前端需在模型設定或語音包狀態暫時無法取得時自動重試。
- 前端需避免把單次進度輪詢失敗誤判為整個翻譯工作失敗。
- 後端 watchdog 每 15 秒檢查 `http://127.0.0.1:8000/health`。
- 若後端健康檢查失敗，watchdog 需重新啟動互動式後端。
- watchdog 使用 Windows named mutex 保證單一實例，避免重複啟動多個看門程序。
- 若後端重啟後發現舊 job 停在 `pending` 或 `running` 但狀態檔長時間未更新，應視為殘留工作並透過取消流程釋放單工限制，不得讓使用者永遠無法重新上傳。

## 20. 測試與驗證

後端基本檢查：

```powershell
cd PROJECT_ROOT\backend
python -m py_compile app\core\config.py app\models\job.py app\services\translation.py app\api\routes.py app\services\processor.py app\pptx\processor.py
```

前端正式 build：

```powershell
cd PROJECT_ROOT\frontend
pnpm build
```

目前已驗證：
- 前端 production build 成功。
- 後端 health API 正常。
- 翻譯模型 options API 正常。
- 地端模型設定可完成最小短句翻譯測試。
- cancel API 已出現在 OpenAPI。

## 21. 目前限制

- 同一時間只允許處理一個 PowerPoint 檔案。
- 不支援 PDF、OCR、圖片文字翻譯。
- 不支援表格、圖表、SmartArt、WordArt 文字翻譯。
- Windows SAPI 輸出目前使用本機語音格式，非雲端高擬真語音。
- SAPI 與 PowerPoint COM 需互動式桌面環境。
- Ollama 大模型首次載入可能需要較久時間。
- 停止翻譯無法硬中斷正在等待中的單次模型 HTTP 回應。
