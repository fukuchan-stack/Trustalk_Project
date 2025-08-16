"use client";
import { useState } from 'react';
import Link from 'next/link';
import { ALL_MODELS } from '../models';
import Papa from 'papaparse';

interface RagResultByQuestion { question: string; ground_truth: string; generated_answer: string; retrieved_contexts: string[]; faithfulness_score: number; relevancy_score: number; }
interface RagFinalScores { average_faithfulness: number; average_answer_relevancy: number; }
interface RagBenchmarkResult { results_by_question: RagResultByQuestion[]; final_scores: RagFinalScores; total_cost: number; }
interface QaPair { question: string; ground_truth: string; }

export default function BenchmarkRagPage() {
  const [qaFile, setQaFile] = useState<File | null>(null);
  const [contextFile, setContextFile] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<RagBenchmarkResult | null>(null);
  const [selectedModel, setSelectedModel] = useState(ALL_MODELS[0].value);
  const [qaPairs, setQaPairs] = useState<QaPair[]>([]);
  const [selectedQuestions, setSelectedQuestions] = useState<Record<number, boolean>>({});
  const apiUrl = process.env.NEXT_PUBLIC_API_URL;
  const handleQaFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setQaFile(file);
    setQaPairs([]);
    setSelectedQuestions({});
    setError(null);
    Papa.parse<QaPair>(file, {
      header: true, skipEmptyLines: true, encoding: 'sjis',
      complete: (result) => {
        if (result.errors.length > 0) { setError(`CSVの解析に失敗しました: ${result.errors[0].message}`); return; }
        if (result.data.length > 0 && ('question' in result.data[0]) && ('ground_truth' in result.data[0])) {
          const validQaPairs = result.data.filter(pair => pair.question && pair.question.trim() !== '');
          setQaPairs(validQaPairs);
          const initialSelection: Record<number, boolean> = {};
          validQaPairs.forEach((_, index) => { initialSelection[index] = false; });
          setSelectedQuestions(initialSelection);
        } else {
          setError("CSVファイルに 'question' と 'ground_truth' のカラムが必要です。");
        }
      }
    });
  };
  const handleCheckboxChange = (index: number) => { setSelectedQuestions(prev => ({ ...prev, [index]: !prev[index] })); };
  const handleSelectAllQuestionsChange = (event: React.ChangeEvent<HTMLInputElement>) => { const isChecked = event.target.checked; const newSelection: Record<number, boolean> = {}; qaPairs.forEach((_, index) => { newSelection[index] = isChecked; }); setSelectedQuestions(newSelection); };
  const isAllQuestionsSelected = qaPairs.length > 0 && qaPairs.every((_, index) => selectedQuestions[index]);
  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!qaFile || !contextFile) { setError('2つのCSVファイルを両方選択してください。'); return; }
    if (!apiUrl) { setError('APIのURLが設定されていません。'); return; }
    const selectedIndices = Object.keys(selectedQuestions).filter(index => selectedQuestions[parseInt(index)]).map(index => parseInt(index));
    if (selectedIndices.length === 0) { setError('少なくとも1つの質問を選択してください。'); return; }
    setIsLoading(true); setError(null); setResults(null);
    const formData = new FormData();
    formData.append('qa_file', qaFile);
    formData.append('context_file', contextFile);
    formData.append('model_name', selectedModel);
    formData.append('selected_indices_json', JSON.stringify(selectedIndices));
    try {
      const response = await fetch(`${apiUrl}/benchmark-rag`, { method: 'POST', body: formData });
      if (!response.ok) { const errorData = await response.json(); throw new Error(errorData.detail || 'サーバーでエラーが発生しました。'); }
      const data: RagBenchmarkResult = await response.json();
      setResults(data);
    } catch (err: any) {
      setError(err.message || '分析中に不明なエラーが発生しました。');
    } finally {
      setIsLoading(false);
    }
  };
  const getScoreColor = (score: number) => { if (score > 0.8) return 'text-green-600'; if (score > 0.6) return 'text-yellow-600'; return 'text-red-600'; };
  return (
    <main className="flex min-h-screen flex-col items-center p-4 sm:p-8 bg-gray-50">
      <div className="w-full max-w-6xl">
        <div className="text-center mb-8"><h1 className="text-4xl font-bold text-gray-800 mb-2">Trustalk</h1><p className="text-lg text-gray-600">AIによる音声ファイル分析プラットフォーム</p></div>
        <nav className="mb-8 flex justify-center border-b border-gray-300">
          <Link href="/" className="px-4 py-2 text-lg font-semibold text-gray-500 hover:text-blue-600">個別分析</Link>
          <Link href="/benchmark-summary" className="px-4 py-2 text-lg font-semibold text-gray-500 hover:text-blue-600">モデル性能比較</Link>
          <Link href="/benchmark-rag" className="px-4 py-2 text-lg font-semibold text-blue-600 border-b-2 border-blue-600">RAG評価</Link>
        </nav>
        <div className="bg-white p-8 rounded-lg shadow-md border border-gray-200 mb-12">
          <h2 className="text-2xl font-bold text-gray-800 mb-1">RAG性能評価ベンチマーク</h2>
          <p className="text-gray-700 mb-6">質問応答データセットとコンテキスト（知識源）のCSVファイルをアップロードし、選択したモデルのRAG性能を評価します。</p>
          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label htmlFor="model-select" className="block text-sm font-medium text-gray-700 mb-2">1. 評価するAIモデルを選択</label>
              <select id="model-select" value={selectedModel} onChange={(e) => setSelectedModel(e.target.value)} className="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm rounded-md">
                {ALL_MODELS.map((option) => ( <option key={option.value} value={option.value}>{option.label}</option> ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">2. 文脈CSVファイルを選択</label>
              <label htmlFor="context-file-upload" className="w-full cursor-pointer bg-gray-50 border-2 border-dashed border-gray-300 rounded-lg p-2 flex items-center justify-center hover:bg-gray-100 transition-colors">
                <span className="text-gray-800 font-medium text-sm">{contextFile ? contextFile.name : "ファイルを選択"}</span>
              </label>
              <input id="context-file-upload" type="file" onChange={(e) => e.target.files && setContextFile(e.target.files[0])} accept=".csv" className="hidden" />
              <p className="mt-2 text-xs text-gray-700 p-2 bg-gray-100 rounded-md">必須カラム: <code className="font-semibold">context</code></p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">3. 質問・回答CSVファイルを選択</label>
              <label htmlFor="qa-file-upload" className="w-full cursor-pointer bg-gray-50 border-2 border-dashed border-gray-300 rounded-lg p-2 flex items-center justify-center hover:bg-gray-100 transition-colors">
                <span className="text-gray-800 font-medium text-sm">{qaFile ? qaFile.name : "ファイルを選択"}</span>
              </label>
              <input id="qa-file-upload" type="file" onChange={handleQaFileChange} accept=".csv" className="hidden" />
              <p className="mt-2 text-xs text-gray-700 p-2 bg-gray-100 rounded-md">必須カラム: <code className="font-semibold">question</code>, <code className="font-semibold">ground_truth</code></p>
            </div>
            {qaPairs.length > 0 && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">4. 評価する質問を選択</label>
                <div className="w-full lg:w-3/4 mx-auto">
                  <div className="mt-2 space-y-2 p-4 border rounded-md max-h-60 overflow-y-auto bg-white">
                  <div className="flex items-center pb-2 border-b"><input id="select-all-questions" type="checkbox" checked={isAllQuestionsSelected} onChange={handleSelectAllQuestionsChange} className="h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500" /><label htmlFor="select-all-questions" className="ml-3 block text-sm font-medium text-gray-900">すべて選択 / 解除</label></div>
                  {qaPairs.map((pair, index) => ( <div key={index} className="flex items-center"><input id={`q-${index}`} type="checkbox" checked={selectedQuestions[index] || false} onChange={() => handleCheckboxChange(index)} className="h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500" /><label htmlFor={`q-${index}`} className="ml-3 block text-sm text-gray-800 truncate" title={pair.question}>{pair.question}</label></div> ))}
                  </div>
                </div>
              </div>
            )}
            <button type="submit" disabled={isLoading || !qaFile || !contextFile} className="w-full bg-purple-600 text-white font-bold py-3 px-4 rounded-lg hover:bg-purple-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-purple-500 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors duration-300">
              {isLoading ? 'RAG性能を評価中...' : 'RAG評価を開始'}
            </button>
          </form>
          {error && ( <div className="mt-6 p-4 bg-red-100 border border-red-400 text-red-700 rounded-lg"><p className="font-bold">エラー</p><p>{error}</p></div> )}
        </div>
        {isLoading && ( <div className="text-center"><p className="text-lg text-gray-600">RAG評価を実行中です。データ量に応じて数分かかることがあります...</p></div> )}
        {results && (
          <div>
            <h2 className="text-3xl font-bold text-gray-800 mb-6 text-center">RAG評価ベンチマーク結果</h2>
            <div className="bg-white shadow-lg rounded-lg p-6 mb-8">
              <h3 className="text-xl font-bold text-gray-800 mb-4 text-center">総合評価</h3>
              <div className="flex justify-around items-center">
                <div className="text-center"><p className="text-base font-medium text-gray-600">忠実性</p><p className={`text-4xl font-bold ${getScoreColor(results.final_scores.average_faithfulness)}`}>{(results.final_scores.average_faithfulness * 100).toFixed(1)}</p></div>
                <div className="text-center"><p className="text-base font-medium text-gray-600">関連性</p><p className={`text-4xl font-bold ${getScoreColor(results.final_scores.average_answer_relevancy)}`}>{(results.final_scores.average_answer_relevancy * 100).toFixed(1)}</p></div>
                <div className="text-center border-l-2 border-gray-200 pl-6 ml-6">
                  <p className="text-base font-medium text-gray-600">概算コスト</p>
                  <p className="text-4xl font-bold text-gray-800">{results.total_cost.toFixed(3)}<span className="text-2xl font-normal"> 円</span></p>
                </div>
              </div>
            </div>
            <div className="bg-white shadow-md rounded-lg overflow-hidden">
                <table className="min-w-full leading-normal">
                    <thead><tr><th className="px-5 py-3 border-b-2 border-gray-200 bg-gray-100 text-left text-sm font-semibold text-gray-700 uppercase tracking-wider">質問</th><th className="px-5 py-3 border-b-2 border-gray-200 bg-gray-100 text-left text-sm font-semibold text-gray-700 uppercase tracking-wider">AIの回答</th><th className="px-5 py-3 border-b-2 border-gray-200 bg-gray-100 text-left text-sm font-semibold text-gray-700 uppercase tracking-wider">正解の回答</th><th className="px-5 py-3 border-b-2 border-gray-200 bg-gray-100 text-center text-sm font-semibold text-gray-700 uppercase tracking-wider">評価</th></tr></thead>
                    <tbody>{results.results_by_question.map((item, index) => ( <tr key={index}><td className="px-5 py-4 border-b border-gray-200 bg-white text-base w-3/12"><p className="text-gray-900 font-medium">{item.question}</p></td><td className="px-5 py-4 border-b border-gray-200 bg-white text-base w-4/12"><p className="text-gray-800 font-medium">{item.generated_answer}</p></td><td className="px-5 py-4 border-b border-gray-200 bg-white text-base w-3/12"><p className="text-green-800 bg-green-50 p-2 rounded font-medium">{item.ground_truth}</p></td><td className="px-5 py-4 border-b border-gray-200 bg-white text-base text-right w-2/12"><div className={`font-bold ${getScoreColor(item.faithfulness_score)}`}>忠実性: {(item.faithfulness_score * 100).toFixed(0)}</div><div className={`font-bold mt-2 ${getScoreColor(item.relevancy_score)}`}>関連性: {(item.relevancy_score * 100).toFixed(0)}</div></td></tr> ))}</tbody>
                </table>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}