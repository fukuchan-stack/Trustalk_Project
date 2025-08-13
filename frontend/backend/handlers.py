# handlers.py
import pandas as pd
import io
import datetime
import chardet
import gradio as gr
from datasets import Dataset
from sqlalchemy.orm import Session

# LangChain & RAG
from langchain_community.vectorstores import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain.embeddings import SentenceTransformerEmbeddings

# Ragas
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall

# ローカルモジュール
import database
from rag_pipeline import run_rag_pipeline
from utils import tonic_similarity, cosine_sim, llm_evaluate, plot_3d_scores, plot_group_analysis
from config import DF_HEADERS, COSINE_THRESHOLD
from agent_setup import initialize_agent_executor
from agent_tools import AgentToolsManager

# --- DBセッション管理 ---
def get_db():
    db = database.SessionLocal()
    try: yield db
    finally: db.close()

# --- 最終判定ロジック ---
def determine_final_judgement(ragas_score, cosine_score):
    if ragas_score.get('faithfulness', 0) >= 0.8 and \
       ragas_score.get('answer_relevancy', 0) >= 0.8 and \
       cosine_score >= COSINE_THRESHOLD:
        return "O"
    return "X"

# --- ファイル読み込みとベクトルストア構築 ---
def handle_csv_qna_upload(state, f):
    if f is None: return gr.update(), gr.update(), "ファイルが選択されていません。"
    try:
        byte_data = f.read()
        encoding = chardet.detect(byte_data)['encoding']
        df = pd.read_csv(io.BytesIO(byte_data), encoding=encoding)
        df.columns = [col.strip() for col in df.columns]
        if not all(col in df.columns for col in ["質問", "正解"]): raise ValueError("CSVに『質問』『正解』列が必要です。")
        
        state.df_qna = df
        questions = df["質問"].dropna().astype(str).tolist()
        return gr.update(choices=questions, value=None), gr.update(choices=questions, value=[]), "質問CSVが正常にロードされました。"
    except Exception as e:
        return gr.update(choices=[], value=None), gr.update(choices=[], value=[]), f"エラー: {e}"

def handle_csv_docs_upload(state, f):
    if f is None: return "ファイルが選択されていません。"
    try:
        byte_data = f.read()
        encoding = chardet.detect(byte_data)['encoding']
        df = pd.read_csv(io.BytesIO(byte_data), encoding=encoding)
        documents = [row['内容'] for _, row in df.iterrows()]
        
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        splits = text_splitter.create_documents(documents)

        embedding_function = SentenceTransformerEmbeddings(model_name="intfloat/multilingual-e5-large")
        vectorstore = Chroma.from_documents(documents=splits, embedding=embedding_function)
        
        state.retriever = vectorstore.as_retriever()
        return f"文脈CSVがロードされ、ベクトルストアが構築されました ({len(splits)}チャンク)。"
    except Exception as e:
        return f"エラー: {e}"

# --- 評価実行 ---
def handle_single_evaluation(state, model_name, question):
    if state.df_qna is None: return "", "質問データがロードされていません。", "", "0"
    if state.retriever is None: return "", "文脈データがロードされていません。", "", "0"
    
    db = next(get_db())
    try:
        row = state.df_qna[state.df_qna["質問"] == question].iloc[0]
        ground_truth = row["正解"]

        answer, contexts, cost = run_rag_pipeline(state.retriever, model_name, question)
        
        data_samples = {'question': [question], 'answer': [answer], 'contexts': [[c.strip() for c in contexts.split('\n\n') if c]], 'ground_truth': [ground_truth]}
        dataset = Dataset.from_dict(data_samples)
        ragas_score = evaluate(dataset, metrics=[faithfulness, answer_relevancy, context_precision, context_recall])
        
        tonic_score = tonic_similarity(question, ground_truth, answer, model_name)
        cosine = cosine_sim(ground_truth, answer)
        mlflow_ox = llm_evaluate(model_name, [question], [answer], [ground_truth])[0]
        
        final_judgement = determine_final_judgement(ragas_score, cosine)

        new_log = database.EvaluationLog(
            model_name=model_name, rag_config=", ".join(state.current_rag_config),
            question=question, ground_truth=ground_truth, generated_answer=answer,
            retrieved_contexts=contexts, final_judgement=final_judgement,
            tonic_score=tonic_score, cosine_similarity=round(cosine, 3), mlflow_judgement=mlflow_ox,
            faithfulness=ragas_score.get('faithfulness', 0), answer_relevancy=ragas_score.get('answer_relevancy', 0),
            context_precision=ragas_score.get('context_precision', 0), context_recall=ragas_score.get('context_recall', 0),
            cost_usd=cost
        )
        db.add(new_log)
        db.commit()
        
        eval_count = db.query(database.EvaluationLog).count()
        detail_text = f"コスト: ${cost:.6f}, Faithfulness: {ragas_score.get('faithfulness', 0):.3f}, Answer Relevancy: {ragas_score.get('answer_relevancy', 0):.3f}"
        return answer, f"最終判定: {final_judgement}", detail_text, str(eval_count)
    except Exception as e:
        db.rollback()
        print(f"評価エラー: {e}")
        return "エラー発生", str(e), "", str(db.query(database.EvaluationLog).count())
    finally:
        db.close()

def handle_multi_evaluation(state, model_name, selected_questions, prog=gr.Progress()):
    db = next(get_db())
    count = db.query(database.EvaluationLog).count()
    db.close()
    if not selected_questions: return "評価する質問が選択されていません。", str(count)
        
    for i, question in enumerate(selected_questions):
        prog((i + 1) / len(selected_questions), desc=f"評価中: {question[:30]}...")
        handle_single_evaluation(state, model_name, question)
    
    db = next(get_db())
    eval_count = db.query(database.EvaluationLog).count()
    db.close()
    return f"{len(selected_questions)} 件を一括評価しました。", str(eval_count)

# --- 履歴の取得とクリア ---
def get_history_df(model_filter="All", config_filter="All", final_filter="All"):
    db = next(get_db())
    try:
        query = db.query(database.EvaluationLog)
        if model_filter != "All": query = query.filter(database.EvaluationLog.model_name == model_filter)
        if config_filter != "All": query = query.filter(database.EvaluationLog.rag_config == config_filter)
        if final_filter != "All": query = query.filter(database.EvaluationLog.final_judgement == final_filter)
        
        logs = query.order_by(database.EvaluationLog.id.desc()).all()
        if not logs: return pd.DataFrame(columns=DF_HEADERS)
        
        log_list = [{
            "ID": log.id, "タイムスタンプ": log.timestamp.strftime("%Y-%m-%d %H:%M"), "モデル": log.model_name,
            "構成": log.rag_config, "質問": log.question, "最終判定": log.final_judgement,
            "Faithfulness": f"{log.faithfulness:.3f}", "Answer Relevancy": f"{log.answer_relevancy:.3f}",
            "Context Precision": f"{log.context_precision:.3f}", "Context Recall": f"{log.context_recall:.3f}",
            "コスト(USD)": f"${log.cost_usd:.6f}", "正解": log.ground_truth,
            "生成回答": log.generated_answer, "検索された文脈": log.retrieved_contexts
        } for log in logs]
        return pd.DataFrame(log_list, columns=DF_HEADERS)
    finally:
        db.close()

def clear_all_history(state):
    db = next(get_db())
    try:
        db.query(database.EvaluationLog).delete()
        db.commit()
        state.df_qna = None
        state.retriever = None
        state.current_rag_config = []
        state.agent_executor = None
        state.agent_memory_messages.clear()
        state.agent_tools_manager = None
        status_message = "全履歴とデータをクリアしました。"
    except Exception as e:
        db.rollback()
        status_message = f"クリア中にエラーが発生しました: {e}"
    finally:
        db.close()
        
    return {
        "csv_qna_input": gr.update(value=None), "csv_docs_input": gr.update(value=None), "csv_load_status": status_message,
        "rag_config": gr.update(value=[]), "current_rag_config_label": gr.update(value="Simple"),
        "question_dropdown": gr.update(choices=[], value=None), "question_display": "", "answer_text": "",
        "generated_text": "", "eval_result": "", "eval_detail": "",
        "question_multi_dropdown": gr.update(choices=[], value=[]), "multi_eval_status": "",
        "eval_count": "0", "csv_save_file": gr.update(value=None, visible=False), "csv_save_status": "",
        "history_df_display": pd.DataFrame(columns=DF_HEADERS), "graph_3d_out": None,
        "group_model_plot_out": None, "group_config_plot_out": None,
        "agent_status_output": "エージェントは初期化されていません。", "agent_chat_history_display": [],
        "agent_query_input": gr.update(interactive=False, value="")
    }

# --- グラフ描画ハンドラ ---
def handle_plot_3d_scores():
    db = next(get_db())
    try:
        df = pd.read_sql(db.query(database.EvaluationLog).statement, db.bind)
        return plot_3d_scores(df)
    finally:
        db.close()

def handle_group_analysis():
    db = next(get_db())
    try:
        df = pd.read_sql(db.query(database.EvaluationLog).statement, db.bind)
        return plot_group_analysis(df)
    finally:
        db.close()

# --- その他UIハンドラ ---
def get_current_question_context(state, selected_question: str):
    if state.df_qna is None or selected_question is None: return "", ""
    try:
        row = state.df_qna[state.df_qna['質問'] == selected_question].iloc[0]
        return row['質問'], row['正解']
    except (IndexError, KeyError):
        return "", ""

def handle_set_rag_config(state, configs):
    state.current_rag_config = configs
    return ", ".join(state.current_rag_config) if state.current_rag_config else "Simple"

# --- エージェント関連 ---
def init_agent_for_chat(state, model_name: str):
    try:
        tools_manager = AgentToolsManager(state, database.SessionLocal, handle_single_evaluation)
        state.agent_tools_manager = tools_manager
        state.agent_executor = initialize_agent_executor(state, model_name, tools_manager.tools)
        state.agent_memory_messages.clear()
        return ([], f"AIアシスタントがモデル '{model_name}' で初期化されました。", gr.update(interactive=True))
    except Exception as e:
        return ([], f"AIアシスタントの初期化に失敗: {e}", gr.update(interactive=False))

def chat_with_agent(state, user_message: str, chat_history_list: list):
    if not state.agent_executor:
        chat_history_list.append((user_message, "AIアシスタントが初期化されていません。"))
        return chat_history_list, ""

    chat_history_list.append((user_message, None))
    yield chat_history_list, ""

    full_response = ""
    try:
        response_stream = state.agent_executor.stream({"input": user_message})
        for chunk in response_stream:
            if "output" in chunk:
                full_response += chunk["output"]
                chat_history_list[-1] = (user_message, full_response)
                yield chat_history_list, ""
    except Exception as e:
        error_message = f"分析中にエラーが発生しました: {e}"
        chat_history_list[-1] = (user_message, error_message)
    yield chat_history_list, ""

def clear_agent_chat_history(state):
    if state.agent_executor:
        state.agent_executor.memory.clear()
    state.agent_memory_messages.clear()
    return [], gr.update(value="")
