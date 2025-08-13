import os
import uuid
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from openai import OpenAI  # <--- 修正点 1: インポートを変更

# .envファイルから環境変数を読み込む
load_dotenv()

# OpenAIクライアントを初期化 (新しい作法)
# 環境変数 "OPENAI_API_KEY" が自動で読み込まれます
client = OpenAI() # <--- 修正点 2: クライアントを初期化

# FastAPIアプリケーションを初期化
app = FastAPI()

# 分析結果の履歴を保存するディレクトリ
HISTORY_DIR = "history"
os.makedirs(HISTORY_DIR, exist_ok=True)

@app.post("/analyze")
async def analyze_audio(file: UploadFile = File(...)):
    file_path = None
    try:
        file_path = f"/tmp/{uuid.uuid4()}_{file.filename}"
        with open(file_path, "wb") as buffer:
            buffer.write(file.file.read())

        with open(file_path, "rb") as audio_file:
            # --- 修正点 3: Whisper APIの呼び出し方を最新の書き方に変更 ---
            transcript_response = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )
            transcript_text = transcript_response.text
            # --- 修正完了 ---

        # --- ここからダミーのAI処理 ---
        summary_text = f"これは「{transcript_text[:20]}...」という発言で始まる会議のAI要約です。"
        todos_list = [
            "アクションアイテム1: プロジェクトの進捗を確認する",
            "アクションアイテム2: 次回の会議日程を調整する"
        ]
        # --- ダミーのAI処理ここまで ---

        result = {
            "id": str(uuid.uuid4()),
            "transcript": transcript_text,
            "summary": summary_text,
            "todos": todos_list,
            "speakers": "（話者分離の結果はここに表示されます）",
            "cost": 0.20,
            "reliability": 96.8
        }

        history_file_path = os.path.join(HISTORY_DIR, f"{result['id']}.json")
        with open(history_file_path, "w", encoding="utf-8") as f:
            import json
            json.dump(result, f, ensure_ascii=False, indent=4)

        return JSONResponse(content=result)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

@app.get("/history")
async def get_history_list():
    files = [f.replace(".json", "") for f in os.listdir(HISTORY_DIR) if f.endswith(".json")]
    return JSONResponse(content={"history": sorted(files, reverse=True)})

@app.get("/history/{file_id}")
async def get_history_detail(file_id: str):
    file_path = os.path.join(HISTORY_DIR, f"{file_id}.json")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Analysis history not found.")
    with open(file_path, "r", encoding="utf-8") as f:
        import json
        data = json.load(f)
    return JSONResponse(content=data)