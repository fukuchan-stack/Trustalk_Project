import os
import uuid
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
import openai
import json

# .envファイルから環境変数を読み込む
load_dotenv()
# OpenAI APIキーを設定
# 環境変数 "OPENAI_API_KEY" にご自身のキーを設定してください
openai.api_key = os.getenv("OPENAI_API_KEY")

# FastAPIアプリケーションを初期化
app = FastAPI()

# 分析結果の履歴を保存するディレクトリ
HISTORY_DIR = "history"
os.makedirs(HISTORY_DIR, exist_ok=True)

@app.post("/analyze")
async def analyze_audio(file: UploadFile = File(...)):
    """
    アップロードされた音声ファイルを分析し、文字起こし、要約、ToDoなどを生成する。
    """
    file_path = None  # finallyブロックで参照するために事前に定義
    try:
        # 一意のファイル名で一時的に音声ファイルを保存
        file_path = f"/tmp/{uuid.uuid4()}_{file.filename}"
        with open(file_path, "wb") as buffer:
            buffer.write(file.file.read())

        # OpenAI Whisper APIを使用して文字起こしを実行
        with open(file_path, "rb") as audio_file:
            transcript_response = openai.Audio.transcribe(
                model="whisper-1",
                file=audio_file,
                response_format="json" # 応答形式をjsonに指定
            )
        
        transcript_text = transcript_response["text"]

        # --- ここからダミーのAI処理 ---
        # 実際にはここで、文字起こし結果(transcript_text)を基に
        # GPT-4などで要約やToDo抽出を行います。
        summary_text = f"これは「{transcript_text[:20]}...」という発言で始まる会議のAI要約です。"
        todos_list = [
            "アクションアイテム1: プロジェクトの進捗を確認する",
            "アクションアイテム2: 次回の会議日程を調整する"
        ]
        # --- ダミーのAI処理ここまで ---

        # クライアントに返す結果オブジェクトを作成
        result = {
            "id": str(uuid.uuid4()),
            "transcript": transcript_text,
            "summary": summary_text,
            "todos": todos_list,
            "speakers": "（話者分離の結果はここに表示されます）",
            "cost": 0.20,  # ダミーのコスト
            "reliability": 96.8  # ダミーの信頼性スコア
        }

        # 分析結果をJSONファイルとして履歴ディレクトリに保存
        history_file_path = os.path.join(HISTORY_DIR, f"{result['id']}.json")
        with open(history_file_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=4)

        return JSONResponse(content=result)

    except Exception as e:
        # エラーが発生した場合はHTTP 500エラーを返す
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

    finally:
        # 処理が終了したら、一時ファイルを確実に削除
        if file_path and os.path.exists(file_path):
            os.remove(file_path)


@app.get("/history")
async def get_history_list():
    """
    保存されている分析履歴のIDリストを返す。
    """
    try:
        history_files = [f.replace(".json", "") for f in os.listdir(HISTORY_DIR) if f.endswith(".json")]
        # ファイル名（ID）のリストを降順（新しいものが先）で返す
        return JSONResponse(content={"history": sorted(history_files, reverse=True)})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/history/{file_id}")
async def get_history_detail(file_id: str):
    """
    指定されたIDの分析結果詳細を返す。
    """
    file_path = os.path.join(HISTORY_DIR, f"{file_id}.json")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Analysis history not found.")
    
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    return JSONResponse(content=data)