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

請使用 `ScratchGrader_Secure_Colab.ipynb` 啟動；兩個 Python 原始檔是唯一的後端來源。

## 第一次設定（必要）

1. 立即撤銷舊的 ngrok authtoken 與 Google/Firebase API key。它們曾經出現在舊版原始碼，刪除檔案中的字串並不會使憑證失效。
2. 在 ngrok 建立新的 authtoken 與靜態網域。
3. 為教師端產生一組長且隨機的 `ADMIN_TOKEN`。它只存在 Colab Secrets，不要寫進 HTML 或程式碼。
4. 若要使用 Firestore，建立服務帳戶並授予該帳戶 Firestore 存取權。把其完整 JSON 放入 Colab Secret `FIREBASE_SERVICE_ACCOUNT_JSON`。
5. 將 Firestore 規則改為拒絕公開讀寫。此專案的瀏覽器不會直接讀取 Firestore，所有資料應只透過後端服務帳戶存取。

建議的 Firestore 規則：

```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /{document=**} { allow read, write: if false; }
  }
}
```

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

os.environ.setdefault('FIREBASE_ENABLED', 'true')
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
