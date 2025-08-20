import os
import sys
import json
import re # 正規表現ライブラリをインポート

# 親ディレクトリ（プロジェクトルート）をPythonのパスに追加
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.knowledge_base_manager import KnowledgeBaseManager

# 分析結果JSONが保存されているディレクトリのパス
RESULTS_DIR = "backend/history" 

def main():
    """
    指定されたディレクトリ内のすべてのJSONファイルを読み込み、
    その内容をナレッジベースに追加するメイン関数。
    """
    print("ナレッジベースへの一括インポート処理を開始します...")
    
    if not os.path.isdir(RESULTS_DIR):
        print(f"❌ エラー: 指定されたディレクトリが見つかりません: {RESULTS_DIR}")
        return

    kb_manager = KnowledgeBaseManager()
    
    # データベースを一度リセットして、常に最新の状態で再構築する
    kb_manager.reset_database()
    
    json_files = [f for f in os.listdir(RESULTS_DIR) if f.endswith('.json')]
    
    if not json_files:
        print("⚠️ インポート対象のJSONファイルが見つかりませんでした。")
        return

    print(f"{len(json_files)}個のJSONファイルをインポートします。")

    for file_name in json_files:
        file_path = os.path.join(RESULTS_DIR, file_name)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                # 話者分離済みの文字起こしテキストが格納されているキー
                transcript_text = data.get('speakers', '') 

                if transcript_text:
                    # --- ディープクリーニング処理 ---
                    # 1. 不自然なスペースを全て削除
                    temp_text = transcript_text.replace(" ", "")
                    # 2. 「**話者名:**」や「[*]」のような記号を正規表現で削除し、純粋な会話内容だけを抽出
                    cleaned_text = re.sub(r'\*\*[^:]+:\s*|\[\*\]', '', temp_text)

                    metadata = {"source_file": file_name}
                    # 掃除したテキストをデータベースに追加
                    kb_manager.add_text_to_knowledge_base(cleaned_text, metadata)
                else:
                    print(f"⚠️ ファイル: {file_name} に文字起こしテキストが見つかりませんでした。スキップします。")

        except json.JSONDecodeError:
            print(f"❌ エラー: ファイル: {file_name} は不正なJSON形式です。スキップします。")
        except Exception as e:
            print(f"❌ ファイル: {file_name} の処理中に予期せぬエラーが発生しました: {e}")

    print("\n🎉 全てのファイルのインポート処理が完了しました。")
    print(f"現在のナレッジ総数: {kb_manager.collection.count()}")


if __name__ == '__main__':
    main()