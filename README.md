# ScratchGrader

以 Gemini 協助批改 Scratch `.sb3` 作業的教學原型。教師端設定作業主題與評分規則；學生端上傳作業進行自評；後端可選擇將設定與繳交紀錄儲存在 Firestore。

## 專案現況

目前後端設計為在 Google Colab 執行 Flask，再以 ngrok 提供 HTTPS 網址。前端是兩個獨立 HTML：

| 檔案 | 用途 |
| --- | --- |
| `scratch_grader_core.py` | `.sb3` 解析、Gemini 評分、設定與 Firestore 存取 |
| `colab_server.py` | Flask API、教師端驗證、ngrok 連線 |
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
| `ADMIN_TOKEN` | 必要 | 自行產生的長隨機教師管理密碼 |
| `FIREBASE_ENABLED` | 選用 | 使用 Firestore 時填 `true` |
| `FIREBASE_PROJECT_ID` | Firestore 時必要 | Firebase 專案 ID |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | Firestore 時必要 | 完整服務帳戶 JSON 內容 |
| `CORS_ALLOWED_ORIGINS` | 正式網站建議 | 前端網址，例如 `https://example.github.io` |

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

最重要的變數如下：

| 變數 | 必要性 | 說明 |
| --- | --- | --- |
| `NGROK_AUTHTOKEN` | 必要 | 新的 ngrok authtoken |
| `NGROK_STATIC_DOMAIN` | 必要 | 新的靜態網域 |
| `ADMIN_TOKEN` | 必要 | 保護所有 `/api/teacher/*` 端點 |
| `FIREBASE_ENABLED` | 選用 | `true` 才啟用 Firestore |
| `FIREBASE_PROJECT_ID` | Firestore 時必要 | 新的 Firebase/Google Cloud 專案 ID |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | Colab 時必要 | Firestore 服務帳戶 JSON（Colab Secret） |
| `FIREBASE_SERVICE_ACCOUNT_FILE` | 本機時建議 | Firestore 服務帳戶 JSON 檔案的路徑 |
| `CORS_ALLOWED_ORIGINS` | 正式部署建議 | 允許呼叫 API 的前端來源，逗號分隔 |

Gemini API key 不放在 `.env`，而是由教師登入教師頁面後輸入並保存於後端設定。請使用新的 key，且在 Google Cloud Console 限制其 API 與使用來源。

## 轉移給其他使用者

1. 複製整個專案資料夾。
2. 新使用者自行建立 ngrok、Firebase／服務帳戶及 Gemini 憑證，絕不沿用你的憑證。
3. 填寫他自己的 `.env`，或在 Colab 建立同名 Secrets。
4. 只修改 `app-config.js` 中的公開 API 網址。
5. 使用 `ScratchGrader_Secure_Colab.ipynb` 啟動並測試教師、學生兩個頁面。
