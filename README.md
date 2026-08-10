# ScratchGrader

> 系統改寫來源：[makishi-ops/scratch-ai-grader](https://github.com/makishi-ops/scratch-ai-grader)

ScratchGrader 是供 Scratch 教學使用的 AI 輔助批改系統。教師建立作業規則與參考解答後，學生可上傳自己的 `.sb3` 專案進行自評，系統會依教師規則產生分數、邏輯分析與可改進建議。

## 系統目的

它適合在課堂、社團或自學情境中，協助教師快速檢視學生是否完成指定的 Scratch 功能，同時讓學生在繳交前取得具體回饋。系統不取代教師判斷；教師仍可依課程目標調整題目、評分規則與 AI 回饋。

## 核心特色

- 教師可設定作業主題、評分規則、初始範本與參考解答。
- 學生以瀏覽器上傳 `.sb3`，不需安裝額外軟體。
- 直接解析 Scratch 專案結構、角色、背景、音效、變數與積木流程，再交由 Gemini 依規則評量。
- 積木名稱使用 Scratch 官方繁體中文詞彙；未知的第三方擴充會被標示，不讓 AI 任意猜測。
- 可選擇使用 Firestore 保存教師設定與學生自評紀錄；未啟用時只儲存在目前後端環境。
- 教師端由 `ADMIN_TOKEN` 保護；公開專案不含任何帳號、金鑰或既有學生資料。

## 操作方式

1. **部署者**：依「第一次設定」與「外部服務設定指南」建立自己的 ngrok、Gemini、`ADMIN_TOKEN`，以及選用的 Firestore 設定。
2. **教師**：開啟 `ScratchGrader_teacher.html`，輸入教師管理密碼，填入 Gemini API key、作業主題與評分規則；可上傳範本／參考解答 `.sb3`，先做單檔試評，再按「儲存設定」。
3. **學生**：開啟 `ScratchGrader_student.html`，輸入學號並上傳 `.sb3`，取得分數（若教師開啟）、邏輯分析與改善建議。
4. **教師追蹤**：啟用 Firestore 時，可在教師頁讀取學生自評紀錄；未啟用時，資料會隨目前的本機或 Colab 工作階段保存。

### 班級同時評分與排隊

學生可以同時開啟與送出學生頁面；後端會以 FIFO（先送先處理）佇列執行 AI 評分，預設同時處理 3 份，其餘等待。此設定讓約 15 位學生同時繳交時，不會同時大量佔用 Colab 與模型免費額度。

- `MAX_CONCURRENT_GRADES=3`：同時進行的 AI 評分數。免費 Colab 建議維持 2～3；效能與額度充足時才提高。
- `MAX_QUEUED_GRADES=24`：最多可等待的評分數；佇列已滿時，學生會收到稍後再試的訊息。
- 評分工作仍受模型回應時間與帳號額度影響；此佇列控制併發，不保證固定完成時間。

## 系統架構與檔案

後端在 Google Colab 執行 Flask，再以 ngrok 提供 HTTPS 網址；前端是兩個獨立 HTML：

| 檔案 | 用途 |
| --- | --- |
| `scratch_grader_core.py` | `.sb3` 解析、Gemini 評分、設定與 Firestore 存取 |
| `colab_server.py` | Flask API、教師端驗證、ngrok 連線 |
| `grading_queue.py` | 限制同時 AI 評分數並依送出順序排隊，保護 Colab 與模型額度 |
| `ScratchGrader_teacher.html` | 教師設定與試評頁面 |
| `ScratchGrader_student.html` | 學生自評頁面 |
| `app-config.js` | 前端唯一需調整的公開 API 網址 |
| `.env.example` | 所有伺服器端設定的清單 |
| `scratch_official_zh_tw.json` | Scratch Foundation 官方繁中詞彙快照 |
| `scratch_translation.py` | 積木名稱渲染與專案覆蓋率檢查 |

請使用 `ScratchGrader_Secure_Colab.ipynb` 啟動；兩個 Python 原始檔是唯一的後端來源。

## Scratch 官方繁中積木詞彙

批改前會將 `.sb3` 的 opcode 轉為 Scratch 官方繁體中文積木名稱，再提供給 AI。例如 `motion_movesteps` 會輸出為「移動 10 點」，不會把英文技術代號當成學生可見用語。

詞彙快照來自 Scratch Foundation 的 `scratch-l10n`（`zh-tw`）與 `scratch-vm`，並固定記錄來源提交版本。目前涵蓋 218 個 Scratch VM 官方核心與官方擴充 opcode；常見的 project.json 內部輸入積木也有中文處理。

若學生使用未收錄的第三方／自訂擴充，系統會標出「積木詞彙覆蓋警告」。AI 被要求不得猜測這些積木的功能或因此扣分；教師可在自訂擴充規則中補充其用途。

更新官方詞彙快照時，使用 `tools/sync_official_scratch_zh_tw.py` 對照官方來源後重新產生 JSON。提交前請執行：

```bash
python -m unittest discover -s tests -v
```

## 第一次設定（必要）

此公開專案**不含** ngrok authtoken、Gemini／Google API key、Firebase API key、服務帳戶或任何既有資料。每位使用者都必須建立並使用自己的設定：

1. 在 ngrok 建立自己的 authtoken 與靜態網域。
2. 為教師端產生一組長且隨機的 `ADMIN_TOKEN`。它只存在 Colab Secrets，不要寫進 HTML 或程式碼。
3. 若要使用 Firestore，建立自己的服務帳戶並授予該帳戶 Firestore 存取權。把其完整 JSON 放入 Colab Secret `FIREBASE_SERVICE_ACCOUNT_JSON`。
4. 將 Firestore 規則改為拒絕公開讀寫。此專案的瀏覽器不會直接讀取 Firestore，所有資料應只透過後端服務帳戶存取。

> 若你曾在早期的私人測試版本使用過自己的憑證，請自行到 ngrok／Google Cloud 撤銷並重建那些憑證；這與目前公開專案的內容無關。

建議的 Firestore 規則：

```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /{document=**} { allow read, write: if false; }
  }
}
```

## 外部服務設定指南

以下帳號、專案與金鑰都應由**每位部署者自行建立**；不要共用、不要上傳到 GitHub，也不要貼在學生端網頁。

### 1. Gemini API（必要）

1. 開啟 [Google AI Studio](https://aistudio.google.com/) 的 API key 頁面，使用自己的 Google 帳號／Google Cloud 專案建立 Gemini API key。
2. 依 [Gemini API key 官方說明](https://ai.google.dev/gemini-api/docs/api-key) 管理、限制與輪替 key。
3. 啟動系統後，在**教師頁面**輸入 key 並按「儲存設定」；key 只會送到後端，不會寫入 `app-config.js`、`.env` 或 GitHub。

> API key 會依部署方式保存在 Firestore 或目前的後端設定檔。若是共用教學環境，建議為每個班級或測試環境建立獨立 key，以便停用與用量管理。

#### 免費額度優先：建議使用 Gemma

如果帳號提供的 Gemma 免費額度高於 Gemini，建議在教師頁面的模型清單中優先選擇可用的 Gemma 模型。ScratchGrader 的評分內容以文字分析、規準比對與繁中回饋為主，先以 Gemma 維持免費使用是合理的部署策略。

- 請以教師頁面載入的模型清單為準；系統只會列出這把 API key 可用、且支援文字生成的 `gemma`／`gemini` 模型。
- 請用 10～20 份具代表性的 `.sb3` 作業，確認分數、官方繁中用語與改善建議符合教師規準後，再固定該模型。
- 若目標是零成本運作，請不要設定「Gemma 失敗時自動改用 Gemini」的備援，避免超出免費額度而產生費用。
- 模型與免費額度會隨帳號、地區及供應商方案變動；若清單中沒有 Gemma，請改用當下可用的免費模型或調整部署方案。

### 2. ngrok 公開網址（必要）

1. 註冊並登入 [ngrok Dashboard](https://dashboard.ngrok.com/)。
2. 在 Dashboard 取得自己的 authtoken；ngrok 將此視為可讓 agent 代表帳號連線的**祕密**，不可公開。[官方說明](https://ngrok.com/docs/agent/cli/)
3. 在你的方案可用範圍內建立或保留一個靜態網域（static domain）。
4. 將值填入環境變數／Colab Secrets：

```text
NGROK_AUTHTOKEN=你的_ngrok_authtoken
NGROK_STATIC_DOMAIN=你的靜態網域
```

啟動後，程式會印出 `https://...` API 網址。將該網址填入 `app-config.js`，供教師端與學生端連線。靜態網域本身可以公開；authtoken 不可以。

#### 避免「網域已被 Agent 使用」

若 Colab 非正常中斷，舊 agent 可能還在線並佔用同一靜態網域，導致 `ERR_NGROK_334`。本專案會先清除目前 Colab runtime 的 ngrok 程序；若要連**其他** runtime／裝置的舊 tunnel 一併安全釋放，請在 ngrok Dashboard 建立 API key，並額外設定：

```text
NGROK_API_KEY=你的_ngrok_API_key
NGROK_REMOTE_RECOVERY=true
```

啟動器會透過 ngrok API 列出 active endpoints，僅比對 `NGROK_STATIC_DOMAIN` 完全相符的項目，然後停止其 tunnel session；不會停止帳號下其他網域的 agent。ngrok 的 API key 是管理 API 用途，與 agent 連線所需的 authtoken 不同。[ngrok Agent 設定說明](https://ngrok.com/docs/agent/config/v3) [ERR_NGROK_334 官方說明](https://ngrok.com/docs/errors/err_ngrok_334)

若你正確在另一個 runtime 執行同一個正式服務，請把 `NGROK_REMOTE_RECOVERY=false`，避免新啟動的 Colab 中斷那個服務。

### 3. Firebase Firestore（選用，但建議用於保留設定與紀錄）

1. 到 [Firebase Console](https://console.firebase.google.com/) 建立自己的 Firebase 專案，並建立 Firestore 資料庫。請選擇**正式／Production mode**，不要使用允許公開讀寫的 Test mode。
2. 到 [Google Cloud Service Accounts](https://console.cloud.google.com/iam-admin/serviceaccounts) 為同一專案建立服務帳戶，僅授予可讀寫 Firestore 所需的角色（例如 **Cloud Datastore User**）。採用最小權限原則。[Firestore IAM 官方說明](https://firebase.google.com/docs/firestore/security/iam)
3. 為該服務帳戶建立 JSON 私鑰。此檔案等同後端身分憑證，不能上傳 GitHub、不能寄給學生。
4. 在 Colab 將完整 JSON 放入 `FIREBASE_SERVICE_ACCOUNT_JSON` Secret；在自己的電腦／伺服器則將 JSON 存在未被版控的檔案，並設定：

```text
FIREBASE_ENABLED=true
FIREBASE_PROJECT_ID=你的_firebase_專案_ID
FIREBASE_SERVICE_ACCOUNT_FILE=service-account.json
```

5. 將 Firestore Rules 保持為上方的 `allow read, write: if false;`。本系統後端使用服務帳戶 OAuth 存取，權限由 IAM 控制；瀏覽器不會直接讀取 Firestore。[Firestore REST 驗證官方說明](https://firebase.google.com/docs/firestore/use-rest-api)

> 本專案不需要 Firebase Web API key。請不要建立或填寫 `FIREBASE_API_KEY`。

### 4. Google Colab Secrets（Colab 部署時必要）

開啟 [Google Colab](https://colab.research.google.com/) 後，在左側 **Secrets** 面板建立下列項目，並允許此 notebook 存取它們：

| Secret 名稱 | 必要性 | 填入內容 |
| --- | --- | --- |
| `NGROK_AUTHTOKEN` | 必要 | ngrok 的祕密 authtoken |
| `NGROK_STATIC_DOMAIN` | 必要 | 你的 ngrok 靜態網域 |
| `NGROK_API_KEY` | 建議 | 自動釋放同網域舊 tunnel session 的管理 API key |
| `NGROK_REMOTE_RECOVERY` | 選用 | `true` 時啟用精準的遠端復原，預設為 `true` |
| `ADMIN_TOKEN` | 必要 | 自行產生的長隨機教師管理密碼 |
| `FIREBASE_ENABLED` | 選用 | 使用 Firestore 時填 `true` |
| `FIREBASE_PROJECT_ID` | Firestore 時必要 | Firebase 專案 ID |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | Firestore 時必要 | 完整服務帳戶 JSON 內容 |
| `CORS_ALLOWED_ORIGINS` | 正式網站建議 | 前端網址，例如 `https://example.github.io` |
| `MAX_CONCURRENT_GRADES` | 選用 | 同時評分數，預設 `3` |
| `MAX_QUEUED_GRADES` | 選用 | 最多等待中的評分數，預設 `24` |

將 `ScratchGrader_Secure_Colab.ipynb`、`scratch_grader_core.py` 與 `colab_server.py` 上傳到同一個 Colab 工作階段，依序執行 notebook 儲存格。缺少必要 Secret 時，啟動器會直接提示缺少的名稱，不會使用預設祕密值。

### 5. 前端網址與 CORS

在 `app-config.js` 填入 ngrok 啟動後顯示的網址：

```js
window.SCRATCH_GRADER_API_URL = 'https://你的靜態網域.ngrok-free.app';
```

- 直接以本機檔案開啟 HTML（`file://`）時，`CORS_ALLOWED_ORIGINS=*` 可供測試使用。
- 正式將 HTML 放到 GitHub Pages、學校網站等 HTTPS 網域時，請將 `CORS_ALLOWED_ORIGINS` 改成該確切來源；多個來源以半形逗號分隔。
- `app-config.js` 只能放公開 API 網址，不能放 `ADMIN_TOKEN`、Gemini key、ngrok authtoken 或服務帳戶 JSON。

## Colab 啟動

先將 `scratch_grader_core.py` 與 `colab_server.py` 上傳到同一個 Colab 工作階段，並安裝相依套件：

```python
!pip install -q flask flask-cors pyngrok pandas google-genai google-auth python-dotenv
```

在 Colab 的 Secrets 設定下列值：

```python
import os
from google.colab import userdata

for name in [
    'NGROK_AUTHTOKEN', 'NGROK_STATIC_DOMAIN', 'ADMIN_TOKEN',
    'FIREBASE_ENABLED', 'FIREBASE_PROJECT_ID',
    'FIREBASE_SERVICE_ACCOUNT_JSON',
]:
    try:
        value = userdata.get(name)
        if value:
            os.environ[name] = value
    except Exception:
        pass

```

接著啟動：

```python
import colab_server
colab_server.serve_background()
```

## 前端連線

只需編輯 `app-config.js` 的一行，把空字串改成此次 Colab 顯示的 HTTPS 網址。兩個 HTML 會自動讀取它：

```js
window.SCRATCH_GRADER_API_URL = 'https://your-domain.ngrok-free.app';
```

此檔可隨前端一起公開，因為它只能包含 API 網址；絕不可放入 Gemini key、Firebase key 或 `ADMIN_TOKEN`。

也可在開啟 HTML 時帶入網址，例如：

```
ScratchGrader_teacher.html?api=https://your-domain.ngrok-free.app
```

首次開啟教師端會要求輸入 `ADMIN_TOKEN`；只保存在該瀏覽器分頁的工作階段內。學生端不需要也不會取得這個密碼。

## 環境變數

完整清單見 `.env.example`。在一般電腦或伺服器上，將它複製成 `.env` 並填入值即可；程式會自動讀取。Colab 請使用 Secrets 與安全啟動 notebook，不要上傳 `.env`。

```bash
copy .env.example .env
```

每次修改環境變數或 Colab Secret 後，都要重新啟動 Colab 後端；不要把 `.env`、服務帳戶 JSON 或任何 token 上傳到 GitHub。

### 後端與部署參數

| 參數 | 預設值 | 放置位置／如何調整 | 用途與建議 |
| --- | --- | --- | --- |
| `NGROK_AUTHTOKEN` | 無 | `.env` 或 Colab Secret | 必填。ngrok 帳號的 agent 認證，不可公開。 |
| `NGROK_STATIC_DOMAIN` | 無 | `.env` 或 Colab Secret | 必填。ngrok 指派的固定 HTTPS 網域。更換網域後，也要更新 `app-config.js`。 |
| `NGROK_API_KEY` | 空白 | `.env` 或 Colab Secret | 選用。只用於解除同一靜態網域被舊 Colab Agent 佔用的狀況。 |
| `NGROK_REMOTE_RECOVERY` | `true` | `.env` 或 Colab Secret | 設為 `false` 可避免新啟動的 Colab 停止另一個正在使用相同網域的部署。 |
| `PORT` | `5000` | `.env` | Flask 本機連接埠；通常不必改。若已被其他程式占用才改，ngrok 會自動跟隨。 |
| `ADMIN_TOKEN` | 無 | `.env` 或 Colab Secret | 必填。教師端管理密碼，請使用長且隨機的值；更換後需在教師頁重新輸入。 |
| `CORS_ALLOWED_ORIGINS` | `*` | `.env` 或 Colab Secret | 可呼叫 API 的前端網址，多個網址以逗號分隔。正式發布務必填入確切的 HTTPS 網址；本機 `file://` 測試才使用 `*`。 |
| `MAX_CONCURRENT_GRADES` | `3` | `.env` 或 Colab Secret | 同時 AI 評分數。15 人班級和免費 Colab 建議 `2`～`3`；提高會加快處理，但更容易碰到模型額度與 Colab 資源限制。 |
| `MAX_QUEUED_GRADES` | `24` | `.env` 或 Colab Secret | 最多等待中的 AI 評分數。15 人班級可維持 `24`；超過時學生會收到稍後再試。 |
| `CONFIG_PATH` | `grader_config.json` | `.env` | 未使用或無法連線 Firestore 時的本機設定檔位置。此模式隨 Colab 重啟可能遺失。 |

### Firestore 資料保存參數

| 參數 | 預設值 | 放置位置／如何調整 | 用途與建議 |
| --- | --- | --- | --- |
| `FIREBASE_ENABLED` | `false` | `.env` 或 Colab Secret | 設為 `true` 才保存教師設定與學生紀錄到 Firestore。未啟用時僅保存在當前工作階段。 |
| `FIREBASE_PROJECT_ID` | 空白 | `.env` 或 Colab Secret | 啟用 Firestore 時必填，填入自己的 Firebase／Google Cloud 專案 ID。 |
| `FIREBASE_CONFIG_COLLECTION` | `scratchgrader` | `.env` | 教師共用設定所在集合名稱。多班級共用同一個 Firestore 時可改為不同名稱以隔離資料。 |
| `FIREBASE_CONFIG_DOCUMENT` | `config` | `.env` | 教師共用設定文件名稱。不同班級應使用不同名稱，避免最後儲存者覆蓋其他班級設定。 |
| `FIREBASE_SUBMISSIONS_COLLECTION` | `scratchgrader_submissions` | `.env` | 學生自評紀錄集合名稱；可依班級改名隔離。 |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | 空白 | **僅 Colab Secret** | 完整服務帳戶 JSON。不可寫入 `.env`、HTML 或 GitHub。 |
| `FIREBASE_SERVICE_ACCOUNT_FILE` | 空白 | 本機 `.env` | 服務帳戶 JSON 的本機路徑；檔案必須保留在版控之外。 |
| `GOOGLE_APPLICATION_CREDENTIALS` | 空白 | 本機 `.env` | `FIREBASE_SERVICE_ACCOUNT_FILE` 的替代方案，填入服務帳戶 JSON 路徑。 |

### 教師頁面可調整的評分設定

這些不是環境變數；由教師登入教師頁填寫並儲存。FireStore 可用時會永久保存，否則僅保留目前 Colab 工作階段。

| 設定 | 如何調整 | 影響範圍 |
| --- | --- | --- |
| API Key 1／2 | 在教師頁輸入自己的 Generative AI API key | 用於取得 Gemini／Gemma 模型清單與進行評分。使用免費 Gemma 時，請在模型清單選擇帳號實際可用的 Gemma。 |
| 評分模型 | 按「載入可用模型」後選擇 | 預設為 `gemini-2.5-flash`；免費額度優先時可選擇清單中的 Gemma。不要設定自動切換到付費模型。 |
| 每份冷卻秒數 | 教師頁調整，預設 `13` 秒 | 全系統每次開始呼叫 AI 前至少間隔的秒數。免費 Gemma 建議維持 `10`～`15`；額度充足且模型穩定時才降低。 |
| 作業主題與評分規則 | 直接編輯，或用參考解答產生後再審閱 | 決定 AI 依據什麼標準評分；教師修改後必須按「儲存設定」才會提供給學生。 |
| 初始範本與參考解答 `.sb3` | 上傳後轉成虛擬碼並儲存 | 可讓評分依指定範本／解答比較。 |
| 是否依標準答案評分 | 教師頁勾選 | 勾選時重視是否符合參考解答；取消時較著重教師規則與創意。 |
| 是否向學生顯示分數 | 教師頁勾選 | 取消後仍會記錄真實分數（Firestore 啟用時），但學生只看到分析與建議。 |
| 最大 `.sb3` 解析大小 | 教師頁調整，預設 `10 MB` | 限制 Scratch 專案內 `project.json` 的解析大小；一般作業維持預設即可。 |

Gemini／Gemma API key 不放在 `.env`，而是由教師登入教師頁面後輸入並保存於後端設定。請使用新的 key，並在 Google Cloud Console 限制其 API 與使用來源。

### 前端網址參數

`app-config.js` 只調整下列公開網址，不得放入任何密碼或 API key：

```js
window.SCRATCH_GRADER_API_URL = 'https://你的-ngrok-靜態網域.ngrok-free.app';
```

也可在開啟教師／學生 HTML 時附加 `?api=https://你的網域` 暫時覆蓋網址，適合測試；正式發布時仍建議修改 `app-config.js`。

## 轉移給其他使用者

1. 複製整個專案資料夾。
2. 新使用者自行建立 ngrok、Firebase／服務帳戶及 Gemini 憑證，絕不沿用你的憑證。
3. 填寫他自己的 `.env`，或在 Colab 建立同名 Secrets。
4. 只修改 `app-config.js` 中的公開 API 網址。
5. 使用 `ScratchGrader_Secure_Colab.ipynb` 啟動並測試教師、學生兩個頁面。

## 授權與開源宣言 (License)

本專案基於「共創共好」的教育精神，採用 **GNU GPLv3** 授權條款。

**開放與自由**：我們歡迎任何人、學校或商業機構自由使用、複製與修改本專案。我們相信，只要能讓這個教育工具變得更好，就不該限制它的發展。

**開源傳染性限制**：若您修改了本系統並重新發布（包含將其包裝為付費服務或商業軟體），您必須以相同的 GPLv3 授權，公開您修改後的完整原始碼。我們期盼取之於社群的成果，最終能回饋給所有的第一線教師。

**免責聲明**：本系統批改之評語與分數由 AI 自動生成，僅供教學輔助參考。請教師於正式登錄成績前，務必進行最終之確認與人工抽測。
