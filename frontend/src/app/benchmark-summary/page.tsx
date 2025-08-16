"use client";
import { useState } from 'react';
import Link from 'next/link';
import { ALL_MODELS } from '../models';
interface BenchmarkResult { model_name: string; summary: string; todos: string[]; reliability: { score: number; justification: string; }; cost: number; execution_time: number; }
const BENCHMARK_MODELS = ALL_MODELS;
export default function BenchmarkSummaryPage() {
  const [file, setFile] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<BenchmarkResult[]>([]);
  const [selectedModels, setSelectedModels] = useState<Record<string, boolean>>(() => { const initialState: Record<string, boolean> = {}; BENCHMARK_MODELS.forEach(model => { initialState[model.value] = false; }); return initialState; });
  const apiUrl = process.env.NEXT_PUBLIC_API_URL;
  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => { if (event.target.files) { setFile(event.target.files[0]); } };
  const handleCheckboxChange = (modelValue: string) => { setSelectedModels(prev => ({ ...prev, [modelValue]: !prev[modelValue] })); };
  const handleSelectAllChange = (event: React.ChangeEvent<HTMLInputElement>) => { const isChecked = event.target.checked; const newSelectedModels: Record<string, boolean> = {}; BENCHMARK_MODELS.forEach(model => { newSelectedModels[model.value] = isChecked; }); setSelectedModels(newSelectedModels); };
  const isAllSelected = BENCHMARK_MODELS.length > 0 && BENCHMARK_MODELS.every(model => selectedModels[model.value]);
  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => { event.preventDefault(); if (!file) { setError('分析する音声ファイルを選択してください。'); return; } if (!apiUrl) { setError('APIのURLが設定されていません。'); return; } const modelsToRun = Object.keys(selectedModels).filter(model => selectedModels[model]); if (modelsToRun.length === 0) { setError('少なくとも1つのモデルを選択してください。'); return; } setIsLoading(true); setError(null); setResults([]); const formData = new FormData(); formData.append('file', file); formData.append('models_to_benchmark', JSON.stringify(modelsToRun)); try { const response = await fetch(`${apiUrl}/benchmark-summary`, { method: 'POST', body: formData }); if (!response.ok) { const errorData = await response.json(); throw new Error(errorData.detail || 'サーバーでエラーが発生しました。'); } const data: BenchmarkResult[] = await response.json(); setResults(data); } catch (err: any) { setError(err.message || '分析中に不明なエラーが発生しました。'); } finally { setIsLoading(false); } };
  return (
    <main className="flex min-h-screen flex-col items-center p-4 sm:p-8 bg-gray-50">
      <div className="w-full max-w-6xl">
        <div className="text-center mb-8"><h1 className="text-4xl font-bold text-gray-800 mb-2">Trustalk</h1><p className="text-lg text-gray-600">AIによる音声ファイル分析プラットフォーム</p></div>
        <nav className="mb-8 flex justify-center border-b border-gray-300">
          <Link href="/" className="px-4 py-2 text-lg font-semibold text-gray-500 hover:text-blue-600">個別分析</Link>
          <Link href="/benchmark-summary" className="px-4 py-2 text-lg font-semibold text-blue-600 border-b-2 border-blue-600">モデル性能比較</Link>
          <Link href="/benchmark-rag" className="px-4 py-2 text-lg font-semibold text-gray-500 hover:text-blue-600">RAG評価</Link>
        </nav>
        <div className="bg-white p-8 rounded-lg shadow-md border border-gray-200 mb-12">
          <h2 className="text-2xl font-bold text-gray-800 mb-1">モデル性能比較ベンチマーク</h2><p className="text-gray-600 mb-6">一つの音声ファイルをアップロードすると、選択したAIモデルで分析を実行し、結果を比較します。</p>
          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">1. 分析するモデルを選択</label>
              <div className="mt-2 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 p-4 border rounded-md">
                <div className="sm:col-span-1 lg:col-span-3 flex items-center pb-2 border-b"><input id="select-all" type="checkbox" checked={isAllSelected} onChange={handleSelectAllChange} className="h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500" /><label htmlFor="select-all" className="ml-3 block text-sm font-medium text-gray-900">すべて選択 / 解除</label></div>
                {BENCHMARK_MODELS.map(model => ( <div key={model.value} className="flex items-center"><input id={model.value} type="checkbox" checked={selectedModels[model.value] || false} onChange={() => handleCheckboxChange(model.value)} className="h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500" /><label htmlFor={model.value} className="ml-3 block text-sm font-medium text-gray-700">{model.label}</label></div> ))}
              </div>
            </div>
            <div><label htmlFor="file-upload" className="block text-sm font-medium text-gray-700 mb-2">2. 音声ファイルを選択</label><input id="file-upload" type="file" onChange={handleFileChange} accept="audio/*" className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100" /></div>
            <button type="submit" disabled={isLoading || !file} className="w-full bg-green-600 text-white font-bold py-3 px-4 rounded-lg hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors duration-300">{isLoading ? '選択したモデルで分析中...' : 'ベンチマークを開始'}</button>
          </form>
          {error && ( <div className="mt-6 p-4 bg-red-100 border border-red-400 text-red-700 rounded-lg"><p className="font-bold">エラー</p><p>{error}</p></div> )}
        </div>
        {isLoading && ( <div className="text-center"><p className="text-lg text-gray-600">分析中です。複数のAIが動作しているため、しばらくお待ちください...</p></div> )}
        {results.length > 0 && (
          <div>
            <h2 className="text-3xl font-bold text-gray-800 mb-6 text-center">ベンチマーク結果</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {results.map((result) => {
                const reliabilityScore = Math.round(result.reliability.score * 100);
                const scoreColor = reliabilityScore > 80 ? 'text-green-600' : reliabilityScore > 60 ? 'text-yellow-600' : 'text-red-600';
                const todosText = result.todos && result.todos.length > 0 ? result.todos.map(todo => `- ${todo}`).join('\n') : 'なし';
                return (
                  <div key={result.model_name} className="bg-white shadow-lg rounded-lg p-6 flex flex-col border-t-4 border-blue-500">
                    <h3 className="text-xl font-bold text-gray-800 mb-3 font-mono text-center pb-3 border-b">{result.model_name}</h3>
                    <div className="space-y-4 flex-grow">
                      <div><h4 className="font-semibold text-gray-700 mb-2 text-center">性能評価</h4><div className="flex justify-between text-sm bg-gray-50 p-2 rounded"><span>信頼性スコア:</span><span className={`font-bold ${scoreColor}`}>{reliabilityScore} / 100</span></div><div className="flex justify-between text-sm bg-gray-50 p-2 rounded mt-1"><span>処理時間:</span><span className="font-bold">{result.execution_time.toFixed(2)} 秒</span></div><div className="flex justify-between text-sm bg-gray-50 p-2 rounded mt-1"><span>概算コスト:</span><span className="font-bold">{result.cost.toFixed(3)} 円</span></div></div>
                      <div><h4 className="font-semibold text-gray-700 mb-1">要約</h4><div className="prose prose-sm max-w-none whitespace-pre-wrap p-3 border rounded-md bg-gray-50 h-32 overflow-y-auto">{result.summary}</div></div>
                      <div><h4 className="font-semibold text-gray-700 mb-1">ToDo</h4><div className="prose prose-sm max-w-none whitespace-pre-wrap p-3 border rounded-md bg-gray-50 h-32 overflow-y-auto">{todosText}</div></div>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </div>
    </main>
  );
}