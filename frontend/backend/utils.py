# utils.py
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib import cm
from sentence_transformers import SentenceTransformer, util
from models import invoke_model

# --- モデルのキャッシュ ---
sentence_model = SentenceTransformer("intfloat/multilingual-e5-large")

# --- 評価関数 ---
def tonic_similarity(question, target_answer, generated_answer, model_name):
    try:
        prompt_template = f"""
        以下の質問と正解に対する生成回答の関連性を5点満点で評価してください。
        1点: 全く関連性がない
        2点: 部分的に関連するが、多くの間違いがある
        3点: 関連性は高いが、重要な情報が欠けているか不正確
        4点: 正確で関連性が非常に高いが、完璧ではない
        5点: 完全に正確で、正解とほぼ同等である
        評価の点数のみを出力してください。

        質問: {question}
        正解: {target_answer}
        生成回答: {generated_answer}
        """
        response = invoke_model(model_name, prompt_template, {})
        score_str = response.splitlines()[0].strip()
        return float(score_str)
    except Exception as e:
        print(f"Tonic評価シミュレーションエラー: {e}")
        return 0.0

def cosine_sim(text1, text2):
    embeddings = sentence_model.encode([text1, text2], convert_to_tensor=True)
    cosine_scores = util.cos_sim(embeddings[0], embeddings[1])
    return cosine_scores.item()

def score_to_ox(score, threshold):
    return "O" if score >= threshold else "X"

def llm_evaluate(model_name, questions, generated_answers, target_answers):
    results = []
    for q, g, t in zip(questions, generated_answers, target_answers):
        try:
            prompt_template = f"""
            以下の質問に対する生成回答は、正解として適切ですか？
            「O」（適切）または「X」（不適切）で答えてください。
            評価理由の説明は不要です。

            質問: {q}
            正解: {t}
            生成回答: {g}
            """
            response = invoke_model(model_name, prompt_template, {})
            results.append("O" if "O" in response else "X")
        except Exception as e:
            print(f"LLM評価エラー: {e}")
            results.append("X")
    return results

# --- グラフ描画関数 ---
def plot_3d_scores(df: pd.DataFrame):
    """DataFrameを受け取り、3Dスコアグラフを生成する"""
    if df.empty or 'tonic_score' not in df.columns or 'cosine_similarity' not in df.columns:
        return None
    
    fig = plt.figure(figsize=(12, 8))
    ax = fig.add_subplot(111, projection='3d')
    
    colors = cm.rainbow(np.linspace(0, 1, len(df['model_name'].unique())))
    color_map = dict(zip(df['model_name'].unique(), colors))
    
    for model_name, color in color_map.items():
        sub_df = df[df['model_name'] == model_name]
        ax.scatter(sub_df['tonic_score'], sub_df['cosine_similarity'], sub_df['final_judgement'].apply(lambda x: 1 if x == 'O' else 0),
                   c=[color], label=model_name, s=50, alpha=0.7)
                   
    ax.set_xlabel('TONICスコア')
    ax.set_ylabel('コサイン類似度')
    ax.set_zlabel('最終判定 (O=1, X=0)')
    ax.set_title('RAG評価スコア 3Dプロット')
    ax.legend()
    
    return fig

def plot_group_analysis(df: pd.DataFrame):
    """DataFrameを受け取り、グループ別分析グラフを生成する"""
    if df.empty:
        return None, None
    
    # モデル別分析
    model_summary = df.groupby('model_name')['final_judgement'].apply(lambda x: (x == 'O').mean()).sort_values(ascending=False)
    fig1, ax1 = plt.subplots(figsize=(10, 6))
    model_summary.plot(kind='bar', ax=ax1, color='skyblue')
    ax1.set_title('モデル別成功率 (最終判定: Oの割合)')
    ax1.set_ylabel('成功率')
    ax1.set_xlabel('モデル')
    ax1.tick_params(axis='x', rotation=45)
    plt.tight_layout()

    # RAG構成別分析
    config_summary = df.groupby('rag_config')['final_judgement'].apply(lambda x: (x == 'O').mean()).sort_values(ascending=False)
    fig2, ax2 = plt.subplots(figsize=(10, 6))
    config_summary.plot(kind='bar', ax=ax2, color='lightgreen')
    ax2.set_title('RAG構成別成功率 (最終判定: Oの割合)')
    ax2.set_ylabel('成功率')
    ax2.set_xlabel('RAG構成')
    ax2.tick_params(axis='x', rotation=45)
    plt.tight_layout()
    
    return fig1, fig2
