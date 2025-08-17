import os
import uuid
import json
import torch
import traceback
import subprocess
import re
import threading
import pandas as pd
from datetime import datetime, timezone
from typing import List
from pydantic import BaseModel
from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pyannote.audio import Pipeline
import whisper_timestamped as whisper
from ai_pipelines import run_self_improvement_pipeline, run_benchmark_pipeline
from rag_pipelines import run_rag_benchmark_pipeline, _parse_csv_to_records
from cost_calculator import calculate_cost_in_jpy
from io import BytesIO

# --- 環境変数 ---
HF_TOKEN = os.getenv("HF_TOKEN")
if not HF_TOKEN:
    raise ValueError("環境変数 HF_TOKEN が設定されていません。")

# --- AIモデルのグローバル変数 (遅延読み込み) ---
device = "cuda" if torch.cuda.is_available() else "cpu"
whisper_model = None
diarization_pipeline = None
whisper_lock = threading.Lock()
pyannote_lock = threading.Lock()

# --- モデル読み込み関数 ---
def load_whisper_model():
    global whisper_model
    with whisper_lock:
        if whisper_model is None:
            print("Whisper: Loading 'base' model for the first time...")
            whisper_model = whisper.load_model("base", device=device)
            print("Whisper: Model loaded successfully.")

def load_pyannote_pipeline():
    global diarization_pipeline
    with pyannote_lock:
        if diarization_pipeline is None:
            print("Pyannote: Loading diarization pipeline for the first time...")
            diarization_pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1", use_auth_token=HF_TOKEN).to(torch.device(device))
            print("Pyannote: Diarization pipeline loaded successfully.")

# --- FastAPIアプリケーションのセットアップ ---
app = FastAPI(title="Trustalk API", version="2.5.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
HISTORY_DIR = "history"
RAG_HISTORY_DIR = "rag_history"
os.makedirs(HISTORY_DIR, exist_ok=True)
os.makedirs(RAG_HISTORY_DIR, exist_ok=True)

# --- ヘルパー関数 ---
def merge_results(diarization, transcription):
    if not diarization: return "話者分離パイプラインが利用できません。", transcription.get("text", "")
    word_speakers, current_speaker, current_speech = [], None, ""
    for segment in transcription.get("segments", []):
        for word in segment.get("words", []):
            speaker_label = "UNKNOWN"
            try:
                cropped_annotation = diarization.crop(word)
                if cropped_annotation:
                    speaker_turn = cropped_annotation.get_timeline().support().pop(0)
                    speaker_label = speaker_turn[2]
            except (IndexError, KeyError): speaker_label = "UNKNOWN"
            word_speakers.append({'word': word.get('text', ''), 'speaker': speaker_label})
    if not word_speakers: return "発言が見つかりませんでした。", transcription.get("text", "")
    full_transcript_with_speakers, current_speaker, current_speech = "", word_speakers[0]['speaker'], ""
    for item in word_speakers:
        word, speaker = item['word'], item['speaker']
        if speaker != current_speaker:
            full_transcript_with_speakers += f"**{current_speaker}**: {current_speech.strip()}\n\n"; current_speech = ""
        current_speech += word + " "; current_speaker = speaker
    if current_speech: full_transcript_with_speakers += f"**{current_speaker}**: {current_speech.strip()}\n"
    return full_transcript_with_speakers.strip(), transcription.get("text", "")

# --- APIエンドポイント ---
@app.get("/", summary="APIのヘルスチェック")
def read_root(): return {"status": "ok"}

@app.post("/analyze", summary="音声ファイルの分析")
async def analyze_audio(file: UploadFile = File(...), model_name: str = Form("gpt-4o-mini")):
    load_whisper_model(); load_pyannote_pipeline()
    original_filename, temp_file_path = file.filename, f"/tmp/{uuid.uuid4()}_{file.filename}"
    wav_file_path = f"{os.path.splitext(temp_file_path)[0]}.wav"
    try:
        with open(temp_file_path, "wb") as buffer: contents = await file.read(); buffer.write(contents)
        command = ["ffmpeg", "-i", temp_file_path, "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", wav_file_path]; subprocess.run(command, check=True, capture_output=True, text=True)
        audio = whisper.load_audio(wav_file_path)
        audio_duration_seconds = len(audio) / whisper.audio.SAMPLE_RATE
        transcription_result = whisper.transcribe(whisper_model, audio, language="ja", detect_disfluencies=True)
        diarization_result = diarization_pipeline(wav_file_path)
        speakers_text, transcript_text = merge_results(diarization_result, transcription_result)
        cleaned_text = re.sub(r'[\(\[].*?[\)\]]', '', transcript_text or "").strip()
        if len(cleaned_text) < 10:
            summary_text, todos_list, reliability_info, token_usage = "- 音声が短すぎるため要約できません。", [], {"score": 0.0, "justification": "評価できません。"}, {"input_tokens": 0, "output_tokens": 0}
        else:
            summary_text, todos_list, reliability_info, token_usage = run_self_improvement_pipeline(model_name, transcript_text)
        calculated_cost_jpy = calculate_cost_in_jpy(model_name=model_name, total_input_tokens=token_usage.get("input_tokens", 0), total_output_tokens=token_usage.get("output_tokens", 0), audio_duration_seconds=audio_duration_seconds)
        result = { "id": str(uuid.uuid4()), "createdAt": datetime.now(timezone.utc).isoformat(), "originalFilename": original_filename, "model_name": model_name, "transcript": transcript_text if transcript_text and transcript_text.strip() else "有効な音声が検出されませんでした。", "summary": summary_text, "todos": todos_list, "speakers": speakers_text, "cost": calculated_cost_jpy, "reliability": reliability_info }
        history_file_path = os.path.join(HISTORY_DIR, f"{result['id']}.json")
        with open(history_file_path, "w", encoding="utf-8") as f: json.dump(result, f, ensure_ascii=False, indent=4)
        return JSONResponse(content=result)
    except Exception as e:
        print(traceback.format_exc()); raise HTTPException(status_code=500, detail=f"分析中に予期せぬエラー: {str(e)}")
    finally:
        if os.path.exists(temp_file_path): os.remove(temp_file_path)
        if os.path.exists(wav_file_path): os.remove(wav_file_path)

@app.post("/benchmark-summary", summary="単一の音声ファイルで、複数のモデルの性能を比較する")
async def benchmark_summary_audio(file: UploadFile = File(...), models_to_benchmark: str = Form(...)):
    load_whisper_model()
    try: models_to_run = json.loads(models_to_benchmark)
    except Exception: raise HTTPException(status_code=400, detail="無効なモデルリストが送信されました。")
    original_filename, temp_file_path = file.filename, f"/tmp/{uuid.uuid4()}_{file.filename}"
    wav_file_path = f"{os.path.splitext(temp_file_path)[0]}.wav"
    try:
        with open(temp_file_path, "wb") as buffer: contents = await file.read(); buffer.write(contents)
        command = ["ffmpeg", "-i", temp_file_path, "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", wav_file_path]; subprocess.run(command, check=True, capture_output=True, text=True)
        audio = whisper.load_audio(wav_file_path)
        audio_duration_seconds = len(audio) / whisper.audio.SAMPLE_RATE
        transcription_result = whisper.transcribe(whisper_model, audio, language="ja", detect_disfluencies=True)
        transcript_text = transcription_result.get("text", "")
        cleaned_text = re.sub(r'[\(\[].*?[\)\]]', '', transcript_text or "").strip()
        if len(cleaned_text) < 10: raise HTTPException(status_code=400, detail="内容が短すぎるためベンチマークを実行できません。")
        benchmark_results = run_benchmark_pipeline(transcript_text, models_to_run)
        for result in benchmark_results:
            result["cost"] = calculate_cost_in_jpy(model_name=result["model_name"], total_input_tokens=result["token_usage"].get("input_tokens", 0), total_output_tokens=result["token_usage"].get("output_tokens", 0), audio_duration_seconds=audio_duration_seconds)
        return JSONResponse(content=benchmark_results)
    except Exception as e:
        print(traceback.format_exc()); raise HTTPException(status_code=500, detail=f"ベンチマーク中に予期せぬエラー: {str(e)}")
    finally:
        if os.path.exists(temp_file_path): os.remove(temp_file_path)
        if os.path.exists(wav_file_path): os.remove(wav_file_path)

@app.post("/benchmark-rag", summary="CSVデータセットで、複数のモデルと技術のRAG性能を一度に評価する")
async def benchmark_rag_multi(qa_file: UploadFile = File(...), context_file: UploadFile = File(...), models_to_run_json: str = Form(...), selected_indices_json: str = Form(...), advanced_rag_options_json: str = Form(...)):
    try:
        models_to_run, selected_indices, advanced_options = json.loads(models_to_run_json), json.loads(selected_indices_json), json.loads(advanced_rag_options_json)
        qa_file_content = await qa_file.read(); context_file_content = await context_file.read()
        all_qa_records = _parse_csv_to_records(BytesIO(qa_file_content), required_columns=["question", "ground_truth"])
        selected_qa_records = [all_qa_records[i] for i in selected_indices]
        if not selected_qa_records: raise HTTPException(status_code=400, detail="評価対象の質問が選択されていません。")
        benchmark_results = []
        for model_name in models_to_run:
            context_file_stream = BytesIO(context_file_content)
            results_data = run_rag_benchmark_pipeline(qa_dataset=selected_qa_records, context_file=context_file_stream, model_name=model_name, advanced_options=advanced_options)
            token_usage = results_data.get("token_usage", {})
            calculated_cost = calculate_cost_in_jpy(model_name=model_name, total_input_tokens=token_usage.get("input_tokens", 0), total_output_tokens=token_usage.get("output_tokens", 0), audio_duration_seconds=0)
            results_data["total_cost"] = calculated_cost
            results_data["model_name"] = model_name
            benchmark_results.append(results_data)
        rag_run_id = str(uuid.uuid4())
        final_data_to_save = { "id": rag_run_id, "createdAt": datetime.now(timezone.utc).isoformat(), "qa_filename": qa_file.filename, "context_filename": context_file.filename, "models_tested": models_to_run, "advanced_options": advanced_options, "num_questions": len(selected_qa_records), "results": benchmark_results }
        history_file_path = os.path.join(RAG_HISTORY_DIR, f"{rag_run_id}.json")
        with open(history_file_path, "w", encoding="utf-8") as f: json.dump(final_data_to_save, f, ensure_ascii=False, indent=4)
        return JSONResponse(content=final_data_to_save)
    except Exception as e:
        print(traceback.format_exc()); raise HTTPException(status_code=500, detail=f"RAGベンチマーク中にエラー: {str(e)}")

@app.get("/history", summary="分析履歴の一覧を取得")
async def get_history_list():
    try:
        history_summary = []
        files = [f for f in os.listdir(HISTORY_DIR) if f.endswith(".json")]
        for filename in files:
            file_path = os.path.join(HISTORY_DIR, filename)
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                reliability_data = data.get("reliability", {})
                score = reliability_data.get("score", 0.0) if isinstance(reliability_data, dict) else 0.0
                history_summary.append({
                    "id": data.get("id"), "createdAt": data.get("createdAt"),
                    "originalFilename": data.get("originalFilename", "ファイル名不明"), "cost": data.get("cost", 0.0),
                    "model_name": data.get("model_name", "不明"), "reliability_score": score
                })
        valid_history = [h for h in history_summary if h.get("createdAt")]
        sorted_history = sorted(valid_history, key=lambda x: x["createdAt"], reverse=True)
        return sorted_history
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"履歴の読み込み中にエラーが発生しました: {str(e)}")

@app.get("/history/{file_id}", summary="特定の分析履歴を取得")
async def get_history_detail(file_id: str):
    file_path = os.path.join(HISTORY_DIR, f"{file_id}.json")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="指定された分析履歴が見つかりません。")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class DeleteHistoryRequest(BaseModel):
    ids: List[str]

@app.post("/history/delete", summary="指定された分析履歴を削除する")
async def delete_history(request: DeleteHistoryRequest):
    deleted_count = 0; errors = []
    for file_id in request.ids:
        if ".." in file_id or "/" in file_id or "\\" in file_id:
            errors.append(f"不正なID形式: {file_id}"); continue
        file_path = os.path.join(HISTORY_DIR, f"{file_id}.json")
        if os.path.exists(file_path):
            try:
                os.remove(file_path); deleted_count += 1
            except Exception as e:
                errors.append(f"{file_id}の削除中にエラー: {e}")
        else:
            errors.append(f"ファイルが見つかりません: {file_id}")
    if errors:
        raise HTTPException(status_code=500, detail={"message": "一部のファイルの削除に失敗しました。", "errors": errors})
    return {"message": f"{deleted_count}件の履歴を削除しました。", "deleted_count": deleted_count}

@app.get("/history-rag", summary="RAG評価履歴の一覧を取得")
async def get_rag_history_list():
    try:
        history_summary = []
        files = [f for f in os.listdir(RAG_HISTORY_DIR) if f.endswith(".json")]
        for filename in files:
            file_path = os.path.join(RAG_HISTORY_DIR, filename)
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                history_summary.append({
                    "id": data.get("id"), "createdAt": data.get("createdAt"),
                    "qa_filename": data.get("qa_filename", "不明"),
                    "context_filename": data.get("context_filename", "不明"),
                    "models_tested": data.get("models_tested", []),
                    "num_questions": data.get("num_questions", 0),
                })
        valid_history = [h for h in history_summary if h.get("createdAt")]
        sorted_history = sorted(valid_history, key=lambda x: x["createdAt"], reverse=True)
        return sorted_history
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RAG履歴の読み込み中にエラーが発生しました: {str(e)}")

@app.get("/history-rag/{file_id}", summary="特定のRAG評価履歴を取得")
async def get_rag_history_detail(file_id: str):
    if ".." in file_id or "/" in file_id or "\\" in file_id:
        raise HTTPException(status_code=400, detail="不正なファイルIDです。")
    file_path = os.path.join(RAG_HISTORY_DIR, f"{file_id}.json")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="指定されたRAG評価履歴が見つかりません。")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/history-rag/delete", summary="指定されたRAG評価履歴を削除する")
async def delete_rag_history(request: DeleteHistoryRequest):
    deleted_count = 0; errors = []
    for file_id in request.ids:
        if ".." in file_id or "/" in file_id or "\\" in file_id:
            errors.append(f"不正なID形式: {file_id}"); continue
        file_path = os.path.join(RAG_HISTORY_DIR, f"{file_id}.json")
        if os.path.exists(file_path):
            try: os.remove(file_path); deleted_count += 1
            except Exception as e: errors.append(f"{file_id}の削除中エラー: {e}")
        else: errors.append(f"ファイルが見つかりません: {file_id}")
    if errors: raise HTTPException(status_code=500, detail={"message": "一部削除失敗。", "errors": errors})
    return {"message": f"{deleted_count}件のRAG履歴を削除しました。", "deleted_count": deleted_count}