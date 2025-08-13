# gradio_ui.py
import gradio as gr
from config import RAG_CONFIG_OPTIONS, EVAL_MODEL_OPTIONS, AGENT_MODEL_OPTIONS, DF_HEADERS
import japanize_matplotlib

def create_ui_tabs():
    """Gradio UIのタブ構成とコンポーネントを定義する"""
    japanize_matplotlib.japanize()
    ui_components = {}

    with gr.Blocks(theme=gr.themes.Base()) as ui_tabs_block:
        gr.Markdown("# LLM RAG 評価・検証 & AIエージェント Playground")
        gr.Markdown("このアプリケーションは、RAG (Retrieval-Augmented Generation) パイプラインの性能を評価・検証し、AIアシスタントと対話するための統合ツールです。")

        with gr.Tab("RAG評価"):
            gr.Markdown("## RAGパイプラインの評価")
            with gr.Row():
                with gr.Column(scale=1):
                    with gr.Accordion("質問と文脈データのロード", open=True):
                        ui_components["csv_qna_input"] = gr.File(label="評価用CSV (qna.csv) をアップロード", file_types=[".csv"])
                        ui_components["csv_docs_input"] = gr.File(label="ドキュメントCSV (docs.csv) をアップロード", file_types=[".csv"])
                        ui_components["csv_load_status"] = gr.Textbox(label="ステータス", interactive=False)
                    ui_components["reset_btn"] = gr.Button("全履歴とデータをクリア", variant="secondary")

                with gr.Column(scale=2):
                    with gr.Accordion("評価設定と実行", open=True):
                        gr.Markdown("### 評価設定")
                        ui_components["model_dropdown"] = gr.Dropdown(label="モデルを選択", choices=EVAL_MODEL_OPTIONS, interactive=True)
                        with gr.Row():
                            ui_components["rag_config"] = gr.CheckboxGroup(label="RAG構成オプションを選択", choices=RAG_CONFIG_OPTIONS, value=[], interactive=True)
                            ui_components["select_all_rag_btn"] = gr.Button("全RAG構成を選択/選択解除")
                        ui_components["set_rag_config_btn"] = gr.Button("RAG構成を確定", variant="primary")
                        ui_components["current_rag_config_label"] = gr.Textbox(label="現在のRAG構成", interactive=False, value="Simple")
                        
            gr.Markdown("### 単体評価")
            with gr.Row():
                ui_components["question_dropdown"] = gr.Dropdown(label="評価したい質問を選択", interactive=True)
                ui_components["eval_btn"] = gr.Button("単体評価を実行", variant="primary")
            with gr.Row():
                ui_components["question_display"] = gr.Textbox(label="質問文", interactive=False)
                ui_components["answer_text"] = gr.Textbox(label="正解", interactive=False)
            with gr.Row():
                ui_components["generated_text"] = gr.Textbox(label="生成された回答", interactive=False, lines=5)
            with gr.Row():
                ui_components["eval_result"] = gr.Textbox(label="最終評価", interactive=False)
                ui_components["eval_detail"] = gr.Textbox(label="詳細スコア", interactive=False)

            gr.Markdown("### 一括評価")
            with gr.Row():
                ui_components["question_multi_dropdown"] = gr.CheckboxGroup(label="評価対象の質問を選択", interactive=True)
            with gr.Row():
                ui_components["select_all_questions_btn"] = gr.Button("全質問を選択/選択解除")
                ui_components["multi_eval_btn"] = gr.Button("一括評価を実行", variant="primary")
            ui_components["multi_eval_status"] = gr.Textbox(label="一括評価ステータス", interactive=False)

        with gr.Tab("評価履歴と分析"):
            gr.Markdown("## 評価結果の分析")
            with gr.Row():
                gr.Markdown("### 評価履歴")
                ui_components["eval_count"] = gr.Textbox(label="評価数", interactive=False, value="0")
            with gr.Row():
                ui_components["save_csv_btn"] = gr.Button("履歴をCSVで保存", variant="secondary")
                ui_components["csv_save_file"] = gr.File(label="保存されたファイル", visible=False)
                ui_components["csv_save_status"] = gr.Textbox(label="保存ステータス", interactive=False)

            ui_components["history_df_display"] = gr.DataFrame(headers=DF_HEADERS, interactive=False, wrap=True)

            gr.Markdown("### フィルタリング")
            with gr.Row():
                ui_components["filter_model"] = gr.Dropdown(label="モデル", choices=["All"] + EVAL_MODEL_OPTIONS, value="All", interactive=True)
                ui_components["filter_config"] = gr.Dropdown(label="RAG構成", choices=["All"] + RAG_CONFIG_OPTIONS, value="All", interactive=True)
                ui_components["filter_final"] = gr.Dropdown(label="最終判定", choices=["All", "O", "X"], value="All", interactive=True)

            gr.Markdown("### グラフ分析")
            with gr.Row():
                ui_components["graph_3d_btn"] = gr.Button("3Dスコアプロットを生成", variant="primary")
                ui_components["graph_3d_out"] = gr.Plot()
            with gr.Row():
                ui_components["group_analysis_btn"] = gr.Button("グループ別分析グラフを生成", variant="primary")
                ui_components["group_model_plot_out"] = gr.Plot()
                ui_components["group_config_plot_out"] = gr.Plot()

        with gr.Tab("AIアシスタント"):
            gr.Markdown("## 評価データと対話するAIアシスタント")
            with gr.Row():
                ui_components["agent_model_dropdown"] = gr.Dropdown(label="エージェントモデルを選択", choices=AGENT_MODEL_OPTIONS, interactive=True)
                ui_components["init_agent_btn"] = gr.Button("エージェントを初期化", variant="primary")
            ui_components["agent_status_output"] = gr.Textbox(label="エージェントステータス", interactive=False, value="エージェントは初期化されていません。")
            ui_components["agent_chat_history_display"] = gr.Chatbot(label="対話履歴", type='messages', height=400)
            with gr.Row():
                ui_components["agent_query_input"] = gr.Textbox(label="質問を送信", interactive=True)
                ui_components["send_agent_btn"] = gr.Button("送信", variant="primary")
            ui_components["clear_agent_chat_btn"] = gr.Button("チャットをクリア")

    ui_components["ui_tabs_block"] = ui_tabs_block
    return ui_components
