// frontend/src/app/rag-history/[id]/page.tsx

"use client";

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';

// 型定義（将来的には共通ファイルにまとめるのが望ましい）
interface RagResultByQuestion { question: string; ground_truth: string; generated_answer: string; retrieved_contexts: string[]; faithfulness_score: number; relevancy_score: number; }
interface RagFinalScores { average_faithfulness: number; average_answer_relevancy: number; }
interface RagBenchmarkResult { model_name: string; results_by_question: RagResultByQuestion[]; final_scores: RagFinalScores; total_cost: number; }
interface RagHistoryDetail {
  id: string;
  createdAt: string;
  models_tested: string[];
  advanced_options: { chunking: boolean; hybridSearch: boolean; promptTuning: boolean; };
  num_questions: number;
  results: RagBenchmarkResult[];
}

export default function RagHistoryDetailPage() {
    const params = useParams();
    const id = params.id as string;
    const [historyDetail, setHistoryDetail] = useState<RagHistoryDetail | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [activeDetailModel, setActiveDetailModel] = useState<string | null>(null);
    
    const apiUrl = process.env.NEXT_PUBLIC_API_URL;

    useEffect(() => {
        if (id && apiUrl) {
            const fetchHistoryDetail = async () => {
                try {
                    setLoading(true);
                    const res = await fetch(`${apiUrl}/history-rag/${id}`);
                    if (!res.ok) throw new Error("RAG評価履歴の取得に失敗しました。");
                    const data: RagHistoryDetail = await res.json();
                    setHistoryDetail(data);
                    if (data.results && data.results.length > 0) {
                        setActiveDetailModel(data.results[0].model_name);
                    }
                } catch (err: any) {
                    setError(err.message);
                } finally {
                    setLoading(false);
                }
            };
            fetchHistoryDetail();
        }
    }, [id, apiUrl]);
    
    const getScoreColor = (score: number) => { if (score > 0.8) return 'text-green-600'; if (score > 0.6) return 'text-yellow-600'; return 'text-red-600'; };
    
    const activeResultDetails = historyDetail?.results.find(r => r.model_name === activeDetailModel);

    if (loading) return <div className="flex items-center justify-center min-h-screen text-xl">読み込み中...</div>;
    if (error) return <div className="p-8 max-w-4xl mx-auto text-red-600"><h1 className="text-2xl font-bold mb-4">エラー</h1><p>{error}</p></div>;
    if (!historyDetail) return <div className="p-8 max-w-4xl mx-auto"><h1 className="text-2xl font-bold">履歴が見つかりません</h1></div>;

    return (
        <main className="flex min-h-screen flex-col items-center p-4 sm:p-8 bg-gray-50">
            <div className="w-full max-w-6xl">
                <div className="mb-8">
                    <Link href="/benchmark-rag" className="text-blue-600 hover:underline">
                        &larr; RAG評価ページに戻る
                    </Link>
                </div>

                <h1 className="text-3xl font-bold text-gray-800 mb-2">RAG評価履歴 詳細</h1>
                <p className="text-gray-500 mb-6 text-xs">ID: {historyDetail.id}</p>

                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
                    <div className="bg-white shadow-md rounded-lg p-4">
                        <h3 className="font-semibold text-gray-700">実行日時</h3>
                        <p className="text-gray-900">{new Date(historyDetail.createdAt).toLocaleString('ja-JP')}</p>
                    </div>
                    <div className="bg-white shadow-md rounded-lg p-4">
                        <h3 className="font-semibold text-gray-700">テスト対象モデル</h3>
                        <div className="flex flex-wrap gap-1 mt-1">
                            {historyDetail.models_tested.map(m => <span key={m} className="font-mono bg-gray-100 text-gray-700 px-2 py-0.5 rounded-md text-xs">{m}</span>)}
                        </div>
                    </div>
                    <div className="bg-white shadow-md rounded-lg p-4">
                        <h3 className="font-semibold text-gray-700">Advanced RAG オプション</h3>
                        <div className="flex flex-wrap gap-x-4 gap-y-1 mt-1 text-sm">
                            <span>チャンキング: {historyDetail.advanced_options.chunking ? '✅' : '❌'}</span>
                            <span>ハイブリッド検索: {historyDetail.advanced_options.hybridSearch ? '✅' : '❌'}</span>
                            <span>プロンプト最適化: {historyDetail.advanced_options.promptTuning ? '✅' : '❌'}</span>
                        </div>
                    </div>
                </div>

                <h2 className="text-3xl font-bold text-gray-800 mb-6 text-center">ベンチマーク結果</h2>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8 mb-12">
                    {historyDetail.results.map(result => (
                        <div key={result.model_name} className="bg-white shadow-lg rounded-lg p-6 flex flex-col border-t-4 border-purple-500">
                        <h3 className="text-xl font-bold text-gray-800 mb-4 text-center font-mono">{result.model_name}</h3>
                        <div className="space-y-2">
                            <div className="flex justify-between text-lg"><span className="font-medium text-gray-600">忠実性スコア:</span> <span className={`font-bold ${getScoreColor(result.final_scores.average_faithfulness)}`}>{(result.final_scores.average_faithfulness * 100).toFixed(1)}</span></div>
                            <div className="flex justify-between text-lg"><span className="font-medium text-gray-600">関連性スコア:</span> <span className={`font-bold ${getScoreColor(result.final_scores.average_answer_relevancy)}`}>{(result.final_scores.average_answer_relevancy * 100).toFixed(1)}</span></div>
                            <div className="flex justify-between text-lg"><span className="font-medium text-gray-600">概算コスト:</span> <span className="font-bold">{result.total_cost.toFixed(3)} 円</span></div>
                        </div>
                        </div>
                    ))}
                </div>
                
                <div>
                    <h3 className="text-2xl font-bold text-gray-800 mb-4 text-center">質問ごとの詳細結果</h3>
                    <div className="flex justify-center border-b border-gray-200 mb-4">
                        {historyDetail.results.map(result => (
                        <button key={result.model_name} onClick={() => setActiveDetailModel(result.model_name)} className={`px-4 py-2 font-medium text-sm rounded-t-lg ${activeDetailModel === result.model_name ? 'bg-white border-t border-l border-r border-gray-200 text-purple-600' : 'text-gray-500 hover:bg-gray-100'}`}>
                            {result.model_name}
                        </button>
                        ))}
                    </div>
                    
                    {activeResultDetails && (
                        <div className="bg-white shadow-md rounded-lg overflow-hidden">
                        <table className="min-w-full leading-normal">
                            <thead><tr><th className="px-5 py-3 border-b-2 border-gray-200 bg-gray-100 text-left text-sm font-semibold text-gray-700 uppercase tracking-wider">質問</th><th className="px-5 py-3 border-b-2 border-gray-200 bg-gray-100 text-left text-sm font-semibold text-gray-700 uppercase tracking-wider">AIの回答</th><th className="px-5 py-3 border-b-2 border-gray-200 bg-gray-100 text-left text-sm font-semibold text-gray-700 uppercase tracking-wider">正解の回答</th><th className="px-5 py-3 border-b-2 border-gray-200 bg-gray-100 text-center text-sm font-semibold text-gray-700 uppercase tracking-wider">評価</th></tr></thead>
                            <tbody>{activeResultDetails.results_by_question.map((item, index) => ( <tr key={index}><td className="px-5 py-4 border-b border-gray-200 bg-white text-base w-3/12"><p className="text-gray-900 font-medium">{item.question}</p></td><td className="px-5 py-4 border-b border-gray-200 bg-white text-base w-4/12"><p className="text-gray-800 font-medium">{item.generated_answer}</p></td><td className="px-5 py-4 border-b border-gray-200 bg-white text-base w-3/12"><p className="text-green-800 bg-green-50 p-2 rounded font-medium">{item.ground_truth}</p></td><td className="px-5 py-4 border-b border-gray-200 bg-white text-base text-right w-2/12"><div className={`font-bold ${getScoreColor(item.faithfulness_score)}`}>忠実性: {(item.faithfulness_score * 100).toFixed(0)}</div><div className={`font-bold mt-2 ${getScoreColor(item.relevancy_score)}`}>関連性: {(item.relevancy_score * 100).toFixed(0)}</div></td></tr> ))}</tbody>
                        </table>
                        </div>
                    )}
                </div>
            </div>
        </main>
    );
}