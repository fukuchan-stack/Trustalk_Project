# backend/main.py
# --- ★★★ 必要なインポートを追加 ★★★ ---
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import database
import whisper
import os
import uuid
# from models import invoke_model # invoke_modelは使わなくなるので削除またはコメントアウト
from models import get_llm_instance # ★ 代わりにこちらをインポート
from config import MODEL_COSTS      # ★ configからコスト情報をインポート
from langchain.callbacks import get_openai_callback # ★ コスト計算のためにインポート
from langchain_core.prompts import ChatPromptTemplate # ★ チェーン構築のためにインポート
from langchain_core.output_parsers import StrOutputParser # ★ チェーン構築のためにインポート
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import faithfulness
import nest_asyncio
nest_asyncio.apply()

database.init_db()
app = FastAPI()

# ... (CORSミドルウェアやWhisperモデルロードは変更なし)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
UPLOAD_DIR = "temp_audio"
os.makedirs(UPLOAD_DIR, exist_ok=True)
print("Whisperモデルをロード中...")
whisper_model = whisper.load_model("base")
print("Whisperモデルのロード完了。")

# ... (@app.get("/") と @app.get("/api/history") の部分は変更なし)
@app.get("/")
def read_root(): return {"message": "Backend is running!"}
@app.get("/api/history")
def get_history():
    db = database.SessionLocal()
    try:
        query = db.query(database.EvaluationLog).statement
        df = pd.read_sql(query, db.bind)
        return df.to_dict(orient='records')
    finally:
        db.close()

@app.post("/api/analyze")
async def analyze_audio(file: UploadFile = File(...)):
    db = database.SessionLocal()
    try:
        # ... (ファイル受信、文字起こしまでは変更なし)
        file_extension = os.path.splitext(file.filename)[1]
        temp_filename = f"{uuid.uuid4()}{file_extension}"
        temp_filepath = os.path.join(UPLOAD_DIR, temp_filename)
        with open(temp_filepath, "wb") as buffer:
            buffer.write(await file.read())
        result = whisper_model.transcribe(temp_filepath, language="ja")
        transcribed_text = result["text"]

        # --- ★★★ ここからが要約＆コスト計算の処理 ★★★ ---
        print("要約を生成し、コストを計算中...")
        model_name_for_summary = "gpt-4o-mini" # 要約に使うモデル
        llm = get_llm_instance(model_name_for_summary)

        prompt = ChatPromptTemplate.from_template(
            "以下の会議の文字起こしを、重要なポイントを箇条書きで簡潔に要約してください。\n\n文字起こし:\n---\n{text}\n---"
        )
        chain = prompt | llm | StrOutputParser()

        summary = ""
        cost = 0.0

        with get_openai_callback() as cb:
            summary = chain.invoke({"text": transcribed_text})
            model_cost_info = MODEL_COSTS.get(model_name_for_summary, {"input": 0, "output": 0})
            cost = (cb.prompt_tokens * model_cost_info["input"] / 1000) + \
                   (cb.completion_tokens * model_cost_info["output"] / 1000)

        print(f"生成された要約: {summary}")
        print(f"概算コスト: ${cost:.6f}")
        # --- ★★★ ここまで ★★★ ---

        # ... (Ragasでの評価部分は変更なし)
        data_samples = { 'question': ["N/A"], 'answer': [summary], 'contexts': [[transcribed_text]] }
        dataset = Dataset.from_dict(data_samples)
        score = evaluate(dataset, metrics=[faithfulness])
        faithfulness_score = score["faithfulness"][0]

        # 5. 評価結果をデータベースに保存 (cost_usdを更新)
        new_log = database.EvaluationLog(
            model_name=model_name_for_summary,
            rag_config="Audio-Summarization",
            question=f"Audio file: {file.filename}",
            ground_truth=transcribed_text,
            generated_answer=summary,
            retrieved_contexts=transcribed_text,
            final_judgement="O" if faithfulness_score > 0.8 else "X",
            faithfulness=faithfulness_score,
            cost_usd=cost, # ★ 計算したコストを保存
            answer_relevancy=0, context_precision=0, context_recall=0,
            tonic_score=0, cosine_similarity=0, mlflow_judgement=""
        )
        db.add(new_log)
        db.commit()

        # ... (一時ファイル削除は変更なし)
        os.remove(temp_filepath)

        # 7. フロントエンドに結果を返す (cost_usdを追加)
        return {
            "filename": file.filename,
            "transcribed_text": transcribed_text,
            "summary": summary,
            "faithfulness_score": faithfulness_score,
            "cost_usd": cost # ★ コスト情報を追加
        }
    except Exception as e:
        db.rollback()
        if 'temp_filepath' in locals() and os.path.exists(temp_filepath):
            os.remove(temp_filepath)
        print(f"エラーが発生しました: {e}")
        return {"error": str(e)}
    finally:
        db.close()
        # backend/main.py の一番下に追記

from fastapi import HTTPException # ★ エラーハンドリングのためにインポート

@app.get("/api/history/{log_id}")
def get_history_detail(log_id: int):
    """
    指定されたIDの評価履歴を1件だけ取得するAPI
    """
    db = database.SessionLocal()
    try:
        # 指定されたIDでデータベースを検索
        log = db.query(database.EvaluationLog).filter(database.EvaluationLog.id == log_id).first()

        # データが見つからなかった場合、404エラーを返す
        if log is None:
            raise HTTPException(status_code=404, detail="Log not found")

        # データが見つかったら、それを返す
        return log
    finally:
        db.close()