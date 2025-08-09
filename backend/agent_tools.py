# agent_tools.py
import pandas as pd
from langchain.tools import tool
from sqlalchemy.orm import Session
import database
from models import invoke_model
from config import RAG_CONFIG_OPTIONS

class AgentToolsManager:
    """AIアシスタントが使用するツールを管理するクラス"""
    def __init__(self, state, db_session_factory, single_eval_func):
        self.state = state
        self.db_session_factory = db_session_factory
        self._single_eval_func = single_eval_func
        
        # ツールをリストとして保持
        self.tools = [
            self.summarize_model_performance,
            self.analyze_failed_questions,
            self.compare_models_configs,
            self.update_rag_config,
            self.run_evaluation_for_agent,
        ]

    def _get_df_from_db(self) -> pd.DataFrame:
        """データベースから評価履歴をDataFrameとして読み込むヘルパー関数"""
        db = self.db_session_factory()
        try:
            query = db.query(database.EvaluationLog).statement
            df = pd.read_sql(query, db.bind)
            return df
        finally:
            db.close()

    @tool
    def summarize_model_performance(self) -> str:
        """評価履歴データに基づき、各モデルの性能を要約します。"""
        df = self._get_df_from_db()
        if df.empty:
            return "評価履歴データがありません。"
        
        summary = df.groupby('model_name')['final_judgement'].apply(
            lambda x: (x == 'O').mean()
        ).sort_values(ascending=False)
        
        summary_text = "【モデル別性能サマリー】\n"
        for model, success_rate in summary.items():
            count = len(df[df['model_name'] == model])
            summary_text += f"- {model}: 成功率 {success_rate:.2%} ({count}件中)\n"
        return summary_text

    @tool
    def analyze_failed_questions(self) -> str:
        """最終判定が「X」となった質問を抽出し、その原因をAIで分析します。"""
        df = self._get_df_from_db()
        if df.empty:
            return "評価履歴データがありません。"

        failed_df = df[df['final_judgement'] == 'X']
        if failed_df.empty:
            return "最終判定が「X」の質問はありませんでした。"
        
        # 最新3件に絞って分析
        recent_failed_df = failed_df.tail(3)
        analysis_results = []
        for _, row in recent_failed_df.iterrows():
            try:
                analysis_prompt = f"""
                以下の質問に対する生成回答は、正解と比べてなぜ「X」と判定されたのでしょうか？
                簡潔に理由を分析してください。
                質問: {row['question']}
                正解: {row['ground_truth']}
                生成回答: {row['generated_answer']}
                """
                analysis = invoke_model(row['model_name'], analysis_prompt, {})
                analysis_results.append(f"【質問: {row['question']}】\n原因分析: {analysis}\n")
            except Exception as e:
                analysis_results.append(f"【質問: {row['question']}】\n分析中にエラーが発生しました: {e}\n")
        return "「X」と判定された質問の原因分析:\n\n" + "\n".join(analysis_results)

    @tool
    def compare_models_configs(self, query: str) -> str:
        """ "gpt-4o vs claude-3-sonnet" のように、2つのモデルの性能を比較します。"""
        df = self._get_df_from_db()
        if df.empty:
            return "評価履歴データがありません。"

        parts = query.lower().split(" vs ")
        if len(parts) != 2:
            return "比較するには「A vs B」の形式でモデル名を指定してください。"
        item1, item2 = parts[0].strip(), parts[1].strip()

        def get_summary(item_name, df_group):
            filtered_df = df_group[df_group['model_name'].str.lower() == item_name]
            if filtered_df.empty:
                return f"'{item_name}'のデータが見つかりません。"
            success_rate = (filtered_df['final_judgement'] == 'O').mean()
            avg_faithfulness = filtered_df['faithfulness'].mean()
            avg_cost = filtered_df['cost_usd'].mean()
            return f"- {item_name}:\n  - 成功率: {success_rate:.2%}\n  - 忠実性 (Faithfulness): {avg_faithfulness:.3f}\n  - 平均コスト: ${avg_cost:.6f}"
        
        summary1 = get_summary(item1, df)
        summary2 = get_summary(item2, df)
        return f"【モデル性能比較レポート】\n{summary1}\n\n{summary2}"

    @tool
    def update_rag_config(self, new_config_list_str: str) -> str:
        """RAG評価に使用する構成要素を更新します。例: "Chanking,Hybrid Search" """
        new_configs = [c.strip() for c in new_config_list_str.split(',') if c.strip()]
        valid_configs = set(RAG_CONFIG_OPTIONS)
        
        if not all(c in valid_configs for c in new_configs):
            invalid_configs = [c for c in new_configs if c not in valid_configs]
            return f"無効な構成要素: {', '.join(invalid_configs)}。有効なオプション: {', '.join(valid_configs)}"
        
        self.state.current_rag_config = new_configs
        config_str = ", ".join(new_configs) if new_configs else "Simple"
        return f"RAG構成を「{config_str}」に更新しました。"

    @tool
    def run_evaluation_for_agent(self, model_name: str, question: str) -> str:
        """指定されたモデルと質問でRAG評価を実行します。"""
        if self.state.df_qna is None or self.state.df_qna.empty:
            return "質問データ（qna.csv）がアップロードされていません。"
        if self.state.retriever is None:
            return "文脈データ（docs.csv）がアップロードされていません。"
        try:
            _, final_ox, _, _ = self._single_eval_func(self.state, model_name, question)
            return f"質問「{question}」の評価が完了しました。モデル: {model_name}, 最終判定: {final_ox}"
        except Exception as e:
            return f"評価中にエラーが発生しました: {e}"
