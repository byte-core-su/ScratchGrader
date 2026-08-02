# -*- coding: utf-8 -*-
"""
colab_server.py
================
Scratch 作業 AI 批改系統 — 後端 API 伺服器（在 Google Colab 執行）

架構：
    前端網頁 (ScratchGrader_teacher.html / ScratchGrader_student.html)
            │  fetch  (https://<你的 ngrok 靜態網域>)
            ▼
    Flask API  ── 呼叫 ──►  scratch_grader_core.py（解析 + Gemini 評分）
                                    │
                                    ▼
                    grader_config.json（Colab 本機共用設定）

──────────────────────────────────────────────────────────────
在 Colab 使用步驟：
  1. 先執行安裝儲存格（見下方 SETUP 說明）。
  2. 把 scratch_grader_core.py 與本檔上傳到 Colab。
  3. 執行本檔 → 會取得固定網址，把它填進 ScratchGrader_teacher.html / ScratchGrader_student.html。
──────────────────────────────────────────────────────────────

# ===== SETUP（請在 Colab 另一個儲存格先跑一次）=====
# !pip install -q flask flask-cors pyngrok pandas google-genai
# ===================================================
# 說明：本版本不掛載 Google Drive。設定檔與批改報告皆存在 Colab 本機，
#       全班批改時請把學生作業資料夾直接上傳到 Colab（例：/content/作業）。
"""

import os
import tempfile
import traceback

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from flask import Flask, request, jsonify
from flask_cors import CORS

import scratch_grader_core as core

# ==========================================
# 1. 執行環境設定（請在 Colab Secrets 或環境變數中設定）
# ==========================================
NGROK_AUTHTOKEN = os.getenv("NGROK_AUTHTOKEN", "").strip()
NGROK_STATIC_DOMAIN = os.getenv("NGROK_STATIC_DOMAIN", "").strip()
PORT = int(os.getenv("PORT", "5000"))
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "").strip()
_cors_origins = [origin.strip() for origin in os.getenv("CORS_ALLOWED_ORIGINS", "*").split(",") if origin.strip()]

# 設定檔路徑（與 core 預設一致，可自行改成你的 Drive 路徑）
CONFIG_PATH = core.CONFIG_PATH

app = Flask(__name__)
# 允許前端網頁（file:// 或任何來源）跨域呼叫本 API
CORS(app, resources={r"/*": {"origins": _cors_origins}},
     methods=["GET", "POST", "OPTIONS"],
     allow_headers=["Content-Type", "X-Admin-Token", "ngrok-skip-browser-warning"])

# 背景執行緒（Colab 推薦啟動方式用）
_flask_thread = None

# 伺服器版本：用來確認 Colab 跑的是不是最新程式（開網址根目錄或 /api/health 可看到）
SERVER_VERSION = "2026-07-18-subcol"


# ==========================================
# 2. 小工具
# ==========================================
def _require_admin():
    """
    所有教師端操作都需要伺服器環境變數 ADMIN_TOKEN。
    回傳 None 代表通過，否則回傳 Flask response。
    """
    if not ADMIN_TOKEN:
        return jsonify({"ok": False, "error": "伺服器尚未設定 ADMIN_TOKEN"}), 503
    supplied = request.headers.get("X-Admin-Token", "")
    if not supplied or not __import__("hmac").compare_digest(supplied, ADMIN_TOKEN):
        return jsonify({"ok": False, "error": "教師端驗證失敗"}), 401
    return None


def _save_upload_to_temp(file_storage):
    """把上傳的檔案存到暫存檔，回傳路徑。呼叫端需自行刪除。"""
    suffix = os.path.splitext(file_storage.filename or "")[1] or ".sb3"
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    file_storage.save(path)
    return path


# ==========================================
# 3. 一般端點
# ==========================================
@app.route("/")
def index():
    return jsonify({
        "service": "Scratch AI Grader API",
        "status": "running",
        "version": SERVER_VERSION,
        "config_path": CONFIG_PATH,
        "endpoints": [
            "GET  /api/health",
            "GET  /api/teacher/config",
            "POST /api/teacher/config",
            "POST /api/teacher/models",
            "POST /api/teacher/suggest_rules",
            "POST /api/teacher/convert_sb3",
            "POST /api/teacher/test",
            "GET  /api/teacher/submissions",
            "GET  /api/student/config",
            "POST /api/student/grade",
        ],
    })


@app.route("/api/health")
def health():
    return jsonify({"ok": True, "version": SERVER_VERSION})


# ==========================================
# 4. 教師端：設定檔讀寫
# ==========================================
@app.route("/api/teacher/config", methods=["GET"])
def teacher_get_config():
    guard = _require_admin()
    if guard:
        return guard
    cfg = core.load_config(CONFIG_PATH)
    return jsonify({"ok": True, "config": cfg})


@app.route("/api/teacher/config", methods=["POST"])
def teacher_save_config():
    guard = _require_admin()
    if guard:
        return guard
    incoming = request.get_json(force=True, silent=True) or {}
    # 以現有設定為底，合併前端送來的欄位（前端可只傳有改動的部分）
    cfg = core.load_config(CONFIG_PATH)
    cfg.update(incoming)
    path = core.save_config(cfg, CONFIG_PATH)
    return jsonify({"ok": True, "saved_to": path, "updated_at": cfg.get("updated_at")})


# ==========================================
# 5. 教師端：把 .sb3 轉成虛擬碼（供設定範本 / 參考解答）
# ==========================================
@app.route("/api/teacher/convert_sb3", methods=["POST"])
def teacher_convert_sb3():
    guard = _require_admin()
    if guard:
        return guard
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "未收到檔案"}), 400
    max_mb = int(request.form.get("max_size_mb", 10))
    path = _save_upload_to_temp(request.files["file"])
    try:
        raw = core.extract_project_json(path, max_mb)
        if not raw:
            return jsonify({"ok": False, "error": "無法解析 .sb3，請確認檔案未損毀"}), 400
        clean_code = core.clean_json_for_ai(raw)
        return jsonify({"ok": True, "clean_code": clean_code})
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


# ==========================================
# 5a. 教師端：查詢可用模型清單
# ==========================================
@app.route("/api/teacher/models", methods=["POST"])
def teacher_models():
    guard = _require_admin()
    if guard:
        return guard
    body = request.get_json(force=True, silent=True) or {}
    api_keys = [body.get("api_key_1", ""), body.get("api_key_2", "")]
    return jsonify(core.list_available_models(api_keys))


# ==========================================
# 5b. 教師端：由參考解答 AI 自動生成主題與評分規則
# ==========================================
@app.route("/api/teacher/suggest_rules", methods=["POST"])
def teacher_suggest_rules():
    guard = _require_admin()
    if guard:
        return guard
    body = request.get_json(force=True, silent=True) or {}
    clean_code = body.get("clean_code", "")
    api_keys = [body.get("api_key_1", ""), body.get("api_key_2", "")]
    model_name = body.get("model_name", "gemini-2.5-flash")

    # 若前端沒帶 clean_code，改用設定檔內已存的參考解答虛擬碼
    if not clean_code:
        clean_code = core.load_config(CONFIG_PATH).get("example_code", "")

    result = core.suggest_theme_and_rules(clean_code, api_keys, model_name)
    if result.get("ok"):
        return jsonify(result)
    return jsonify(result), 400


# ==========================================
# 5c. 教師端：讀取學生成績紀錄
# ==========================================
@app.route("/api/teacher/submissions", methods=["GET"])
def teacher_submissions():
    guard = _require_admin()
    if guard:
        return guard
    return jsonify(core.list_submissions())


# ==========================================
# 6. 教師端：單檔試評
# ==========================================
@app.route("/api/teacher/test", methods=["POST"])
def teacher_test():
    guard = _require_admin()
    if guard:
        return guard
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "未收到檔案"}), 400

    cfg = core.load_config(CONFIG_PATH)
    # 允許前端在試評時臨時覆蓋部分欄位（例如尚未存檔的規則）
    overrides = request.form.get("overrides")
    if overrides:
        import json as _json
        try:
            cfg.update(_json.loads(overrides))
        except Exception:
            pass

    path = _save_upload_to_temp(request.files["file"])
    try:
        result = core.grade_project_file(path, cfg)
        return jsonify({"ok": True, "result": result})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e),
                        "trace": traceback.format_exc()[:800]}), 500
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


# ==========================================
# 8. 學生端：取得公開設定 + 自評
# ==========================================
@app.route("/api/student/config", methods=["GET"])
def student_config():
    cfg = core.load_config(CONFIG_PATH)
    return jsonify({"ok": True, "config": core.public_config(cfg)})


@app.route("/api/student/grade", methods=["POST"])
def student_grade():
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "未收到檔案"}), 400

    student_id = (request.form.get("student_id") or "").strip()
    if not student_id:
        return jsonify({"ok": False, "error": "請先輸入你的學號"}), 400

    cfg = core.load_config(CONFIG_PATH)
    if not (cfg.get("api_key_1") or cfg.get("api_key_2")):
        return jsonify({"ok": False, "error": "老師尚未設定 API Key，暫時無法自評"}), 400

    path = _save_upload_to_temp(request.files["file"])
    try:
        result = core.grade_project_file(path, cfg)
        # 先用「真實分數」記錄到 Firestore（不受學生端顯示設定影響）
        core.record_submission(student_id, result, theme=cfg.get("theme", ""))
        # 依老師設定決定是否對學生顯示分數
        if not cfg.get("student_show_score", True):
            result = dict(result)
            result["score"] = None
        # 學生端不需要看到內部虛擬碼，移除以精簡回傳
        result.pop("clean_code", None)
        return jsonify({"ok": True, "result": result,
                        "student_id": student_id,
                        "theme": cfg.get("theme", ""),
                        "show_score": cfg.get("student_show_score", True)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e),
                        "trace": traceback.format_exc()[:800]}), 500
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


# ==========================================
# 9. 啟動：連上 ngrok 靜態網域後執行 Flask
# ==========================================
def start():
    if not NGROK_AUTHTOKEN or not NGROK_STATIC_DOMAIN:
        raise RuntimeError("請先設定 NGROK_AUTHTOKEN 與 NGROK_STATIC_DOMAIN 環境變數")
    from pyngrok import ngrok, conf
    conf.get_default().auth_token = NGROK_AUTHTOKEN

    # 先強制殺掉本機殘留的 ngrok 程序（解決 ERR_NGROK_334：網域已在線）
    # 通常是上一次執行中斷後 ngrok agent 沒被關掉，仍佔用著靜態網域。
    try:
        for t in ngrok.get_tunnels():
            ngrok.disconnect(t.public_url)
    except Exception:
        pass
    try:
        ngrok.kill()          # 終止本 runtime 內所有 ngrok agent 程序
        import time as _t; _t.sleep(2)
    except Exception:
        pass

    try:
        public_url = ngrok.connect(PORT, domain=NGROK_STATIC_DOMAIN).public_url
    except Exception as e:
        msg = str(e)
        if "ERR_NGROK_334" in msg or "already online" in msg:
            print("=" * 60)
            print("❌ 靜態網域仍被佔用（ERR_NGROK_334）。")
            print("   代表有另一個 ngrok agent（可能是別的 Colab 分頁或舊 runtime）還在線。")
            print("   請擇一處理：")
            print("   1) 到 https://dashboard.ngrok.com/agents 把舊的 agent 按 Stop。")
            print("   2) 或在 Colab 選單『執行階段 → 中斷連線並刪除執行階段』後重開。")
            print("   3) 或另開一格執行： from pyngrok import ngrok; ngrok.kill()")
            print("=" * 60)
            raise
        raise
    print("=" * 60)
    print(f"✅ API 已上線：{public_url}")
    print(f"   健康檢查： {public_url}/api/health")
    print(f"   請把上面網址填入 ScratchGrader_teacher.html / ScratchGrader_student.html 的「伺服器網址」欄位。")
    print(f"   設定檔位置：{CONFIG_PATH}")
    print("=" * 60)
    app.run(host="0.0.0.0", port=PORT)


def serve_background():
    """
    【Colab 推薦啟動方式】以背景執行緒跑 Flask，cell 會立刻返回並持續服務。
    好處：中斷/重跑 cell 不會留下殺不掉的殭屍 ngrok 程序。

    用法（在 Colab 儲存格）：
        import colab_server
        colab_server.serve_background()
    重跑本函式可安全重連（會自動清掉舊 ngrok 通道）。
    """
    global _flask_thread
    if not NGROK_AUTHTOKEN or not NGROK_STATIC_DOMAIN:
        raise RuntimeError("請先設定 NGROK_AUTHTOKEN 與 NGROK_STATIC_DOMAIN 環境變數")
    import threading, time as _t, subprocess, sys
    from werkzeug.serving import make_server
    from pyngrok import ngrok, conf
    conf.get_default().auth_token = NGROK_AUTHTOKEN

    # 1) 關掉「上一次由本函式啟動的」Flask 伺服器（存在 sys 上，importlib.reload 清不掉），
    #    先釋放 port 5000，才能用最新程式重開 → 避免舊路由殘留造成 Failed to fetch。
    old_srv = getattr(sys, "_sg_server", None)
    if old_srv is not None:
        try:
            old_srv.shutdown()
            print("♻️ 已關閉舊的 Flask 伺服器，準備用最新程式重開…")
        except Exception:
            pass
        _t.sleep(1)

    # 2) 徹底清掉殘留的 ngrok（reload 也有效）：OS 層 pkill + pyngrok kill
    try:
        subprocess.run(["pkill", "-9", "-f", "ngrok"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass
    try:
        ngrok.kill()
    except Exception:
        pass
    _t.sleep(3)

    # 3) 用「目前最新的 app」啟動一台可被關閉的 werkzeug 伺服器；
    #    伺服器物件存到 sys._sg_server，下次重跑才能把它 shutdown 換新。
    srv = make_server("0.0.0.0", PORT, app, threaded=True)
    sys._sg_server = srv
    _flask_thread = threading.Thread(target=srv.serve_forever, daemon=True)
    _flask_thread.start()
    _t.sleep(2)

    # 3) 連 ngrok（遇 334 再多殺一次並重試）
    public_url = None
    for attempt in range(3):
        try:
            public_url = ngrok.connect(PORT, domain=NGROK_STATIC_DOMAIN).public_url
            break
        except Exception as e:
            msg = str(e)
            if ("ERR_NGROK_334" in msg or "already online" in msg) and attempt < 2:
                print(f"⚠️ 網域佔用中，第 {attempt+1} 次清除後重試…")
                try:
                    subprocess.run(["pkill", "-9", "-f", "ngrok"],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    ngrok.kill()
                except Exception:
                    pass
                _t.sleep(4)
                continue
            if "ERR_NGROK_334" in msg or "already online" in msg:
                print("❌ 靜態網域仍被佔用（ERR_NGROK_334）。")
                print("   多半是『另一個 Colab 分頁』或『別的舊 runtime』還連著同一個 ngrok 網域。")
                print("   → 最快解法：本 runtime『執行階段 → 中斷連線並刪除執行階段』後重開；")
                print("     或到 https://dashboard.ngrok.com/agents 停掉舊 agent。")
            raise

    print("=" * 60)
    print(f"✅ API 已上線（背景執行）：{public_url}")
    print(f"   健康檢查： {public_url}/api/health")
    print(f"   請把上面網址填入 ScratchGrader_teacher.html / ScratchGrader_student.html 的「伺服器網址」欄位。")
    print(f"   設定檔位置：{CONFIG_PATH}")
    print("=" * 60)
    return public_url


if __name__ == "__main__":
    start()
