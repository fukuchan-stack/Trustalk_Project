"use client";

import { useState, useEffect, useMemo } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { ALL_MODELS } from '../models';
import Papa from 'papaparse';

// 型定義
interface RagResultByQuestion { question: string; ground_truth: string; generated_answer: string; retrieved_contexts: string[]; faithfulness_score: number; relevancy_score: number; }
interface RagFinalScores { average_faithfulness: number; average_answer_relevancy: number; }
interface RagBenchmarkResult { model_name: string; results_by_question: RagResultByQuestion[]; final_scores: RagFinalScores; total_cost: number; }
interface RagHistoryDetail { id: string; createdAt: string; models_tested: string[]; advanced_options: { chunking: boolean; hybridSearch: boolean; promptTuning: boolean; }; num_questions: number; results: RagBenchmarkResult[]; }
interface QaPair { question: string; ground_truth: string; }
interface RagHistoryItem {
    id: string;
    createdAt: string;
    models_tested: string[];
    num_questions: number;
    qa_filename: string;
    context_filename: string;
}

const RAG_BENCHMARK_MODELS = ALL_MODELS;
const ITEMS_PER_PAGE = 10;

export default function BenchmarkRagPage() {
  const [qaFile, setQaFile] = useState<File | null>(null);
  const [contextFile, setContextFile] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<RagBenchmarkResult[]>([]);
  const [selectedModels, setSelectedModels] = useState<Record<string, boolean>>(() => { const i: Record<string, boolean> = {}; RAG_BENCHMARK_MODELS.forEach(m => { i[m.value] = false; }); return i; });
  const [advancedRagOptions, setAdvancedRagOptions] = useState({ chunking: false, hybridSearch: false, promptTuning: false });
  const [qaPairs, setQaPairs] = useState<QaPair[]>([]);
  const [selectedQuestions, setSelectedQuestions] = useState<Record<number, boolean>>({});
  const [ragHistory, setRagHistory] = useState<RagHistoryItem[]>([]);
  const [activeDetailModel, setActiveDetailModel] = useState<string | null>(null);
  const [visibleHistoryCount, setVisibleHistoryCount] = useState(ITEMS_PER_PAGE);
  const [selectedForDeletion, setSelectedForDeletion] = useState<Record<string, boolean>>({});
  const router = useRouter();
  const apiUrl = process.env.NEXT_PUBLIC_API_URL;

  const fetchRagHistory = async () => {
      if (!apiUrl) return;
      try {
          const res = await fetch(`${apiUrl}/history-rag`);
          if (!res.ok) throw new Error("RAG履歴の取得に失敗しました。");
          const data = await res.json();
          setRagHistory(data);
      } catch (err: any) {
          console.error("RAG History fetch error:", err.message);
      }
  };

  useEffect(() => {
      fetchRagHistory();
  }, []);

  const handleModelCheckboxChange = (modelValue: string) => { setSelectedModels(prev => ({ ...prev, [modelValue]: !prev[modelValue] })); };
  const handleSelectAllModelsChange = (e: React.ChangeEvent<HTMLInputElement>) => { const c = e.target.checked; const n: Record<string, boolean> = {}; RAG_BENCHMARK_MODELS.forEach(m => { n[m.value] = c; }); setSelectedModels(n); };
  const isAllModelsSelected = RAG_BENCHMARK_MODELS.length > 0 && RAG_BENCHMARK_MODELS.every(m => selectedModels[m.value]);
  const handleAdvancedRagChange = (option: keyof typeof advancedRagOptions) => { setAdvancedRagOptions(prev => ({...prev, [option]: !prev[option]})); };
  const handleSelectAllAdvancedChange = (e: React.ChangeEvent<HTMLInputElement>) => { const c = e.target.checked; setAdvancedRagOptions({ chunking: c, hybridSearch: c, promptTuning: c }); };
  const isAllAdvancedSelected = Object.values(advancedRagOptions).every(Boolean);
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
        if (result.errors.length > 0) { setError(`CSV解析失敗: ${result.errors[0].message}`); return; }
        if (result.data.length > 0 && ('question' in result.data[0]) && ('ground_truth' in result.data[0])) {
          const validQaPairs = result.data.filter(p => p.question && p.question.trim() !== '');
          setQaPairs(validQaPairs);
          const initialSelection: Record<number, boolean> = {};
          validQaPairs.forEach((_, idx) => { initialSelection[idx] = false; });
          setSelectedQuestions(initialSelection);
        } else {
          setError("CSVに 'question' と 'ground_truth' カラムが必要です。");
        }
      }
    });
  };
  const handleQuestionCheckboxChange = (index: number) => { setSelectedQuestions(prev => ({ ...prev, [index]: !prev[index] })); };
  const handleSelectAllQuestionsChange = (e: React.ChangeEvent<HTMLInputElement>) => { const c = e.target.checked; const n: Record<number, boolean> = {}; qaPairs.forEach((_, idx) => { n[idx] = c; }); setSelectedQuestions(n); };
  const isAllQuestionsSelected = qaPairs.length > 0 && qaPairs.every((_, idx) => selectedQuestions[idx]);
  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!qaFile || !contextFile) { setError('2つのCSVファイルを両方選択してください。'); return; }
    const modelsToRun = Object.keys(selectedModels).filter(m => selectedModels[m]);
    if (modelsToRun.length === 0) { setError('少なくとも1つの評価モデルを選択してください。'); return; }
    const selectedIndices = Object.keys(selectedQuestions).filter(i => selectedQuestions[parseInt(i)]).map(i => parseInt(i));
    if (selectedIndices.length === 0) { setError('少なくとも1つの質問を選択してください。'); return; }
    
    setIsLoading(true); setError(null); setResults([]); setActiveDetailModel(null);
    const formData = new FormData();
    formData.append('qa_file', qaFile);
    formData.append('context_file', contextFile);
    formData.append('models_to_run_json', JSON.stringify(modelsToRun));
    formData.append('selected_indices_json', JSON.stringify(selectedIndices));
    formData.append('advanced_rag_options_json', JSON.stringify(advancedRagOptions));
    try {
      const response = await fetch(`${apiUrl}/benchmark-rag`, { method: 'POST', body: formData });
      if (!response.ok) { const errorData = await response.json(); throw new Error(errorData.detail || 'サーバーエラー'); }
      const data: RagHistoryDetail = await response.json();
      setResults(data.results);
      if (data.results && data.results.length > 0) {
        setActiveDetailModel(data.results[0].model_name);
      }
      await fetchRagHistory();
    } catch (err: any) {
      setError(err.message || '不明なエラー');
    } finally {
      setIsLoading(false);
    }
  };
  const getScoreColor = (score: number) => { if (score > 0.8) return 'text-green-600'; if (score > 0.6) return 'text-yellow-600'; return 'text-red-600'; };
  const activeResultDetails = results.find(r => r.model_name === activeDetailModel);
  const visibleHistory = useMemo(() => ragHistory.slice(0, visibleHistoryCount), [ragHistory, visibleHistoryCount]);
  const handleDeletionCheckboxChange = (id: string) => {
    setSelectedForDeletion(prev => ({...prev, [id]: !prev[id]}));
  };
  const handleSelectAllDeletionChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const isChecked = event.target.checked;
    const newSelection: Record<string, boolean> = {};
    visibleHistory.forEach(item => { newSelection[item.id] = isChecked; });
    setSelectedForDeletion(newSelection);
  };
  const handleDeleteSelected = async () => {
    const idsToDelete = Object.keys(selectedForDeletion).filter(id => selectedForDeletion[id]);
    if (idsToDelete.length === 0) { alert('削除する項目を選択してください。'); return; }
    if (window.confirm(`${idsToDelete.length}件の履歴を本当に削除しますか？`)) {
      try {
        const response = await fetch(`${apiUrl}/history-rag/delete`, {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ ids: idsToDelete }),
        });
        if (!response.ok) throw new Error('削除中にエラーが発生しました。');
        await fetchRagHistory();
        setSelectedForDeletion({});
      } catch (err: any) { alert(`エラー: ${err.message}`); }
    }
  };
  const selectedCount = Object.values(selectedForDeletion).filter(Boolean).length;
  const isAllVisibleSelected = visibleHistory.length > 0 && visibleHistory.every(item => selectedForDeletion[item.id]);

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
          <p className="text-gray-700 mb-6">質問応答データセットとコンテキスト（知識源）のCSVファイルをアップロードし、選択した複数モデルと技術のRAG性能を一度に評価・比較します。</p>
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                    <label htmlFor="qa-file-upload" className="block text-sm font-medium text-gray-700 mb-2">1. 質問・回答CSVファイル</label>
                    <label htmlFor="qa-file-upload" className="w-full cursor-pointer bg-gray-50 border-2 border-dashed border-gray-300 rounded-lg p-4 flex flex-col items-center justify-center hover:bg-gray-100 transition-colors">
                        <span className="text-purple-600 font-semibold">ファイルを選択</span>
                        <span className="text-gray-800 font-medium text-sm mt-1">{qaFile ? qaFile.name : "選択されていません"}</span>
                    </label>
                    <input id="qa-file-upload" type="file" onChange={handleQaFileChange} accept=".csv" className="hidden" />
                    <p className="mt-2 text-xs text-gray-700 p-2 bg-gray-100 rounded-md">必須カラム: <code className="font-semibold">question</code>, <code className="font-semibold">ground_truth</code></p>
                </div>
                <div>
                    <label htmlFor="context-file-upload" className="block text-sm font-medium text-gray-700 mb-2">2. 文脈CSVファイル</label>
                    <label htmlFor="context-file-upload" className="w-full cursor-pointer bg-gray-50 border-2 border-dashed border-gray-300 rounded-lg p-4 flex flex-col items-center justify-center hover:bg-gray-100 transition-colors">
                        <span className="text-purple-600 font-semibold">ファイルを選択</span>
                        <span className="text-gray-800 font-medium text-sm mt-1">{contextFile ? contextFile.name : "選択されていません"}</span>
                    </label>
                    <input id="context-file-upload" type="file" onChange={(e) => e.target.files && setContextFile(e.target.files[0])} accept=".csv" className="hidden" />
                    <p className="mt-2 text-xs text-gray-700 p-2 bg-gray-100 rounded-md">必須カラム: <code className="font-semibold">context</code></p>
                </div>
            </div>
            {qaPairs.length > 0 && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">3. 評価する質問を選択</label>
                <div className="w-full lg:w-3/4 mx-auto">
                    <div className="mt-2 space-y-2 p-4 border rounded-md max-h-60 overflow-y-auto bg-white">
                    <div className="flex items-center pb-2 border-b"><input id="select-all-questions" type="checkbox" checked={isAllQuestionsSelected} onChange={handleSelectAllQuestionsChange} className="h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500" /><label htmlFor="select-all-questions" className="ml-3 block text-sm font-medium text-gray-900">すべて選択 / 解除</label></div>
                    {qaPairs.map((pair, index) => ( <div key={index} className="flex items-center"><input id={`q-${index}`} type="checkbox" checked={selectedQuestions[index] || false} onChange={() => handleQuestionCheckboxChange(index)} className="h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500" /><label htmlFor={`q-${index}`} className="ml-3 block text-sm text-gray-800 truncate" title={pair.question}>{pair.question}</label></div> ))}
                    </div>
                </div>
              </div>
            )}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">4. 評価するAIモデルを選択</label>
              <div className="mt-2 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 p-4 border rounded-md">
                <div className="sm:col-span-1 lg:col-span-3 flex items-center pb-2 border-b"><input id="select-all-models" type="checkbox" checked={isAllModelsSelected} onChange={handleSelectAllModelsChange} className="h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500" /><label htmlFor="select-all-models" className="ml-3 block text-sm font-medium text-gray-900">すべて選択 / 解除</label></div>
                {RAG_BENCHMARK_MODELS.map(model => ( <div key={model.value} className="flex items-center"><input id={model.value} type="checkbox" checked={selectedModels[model.value] || false} onChange={() => handleModelCheckboxChange(model.value)} className="h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500" /><label htmlFor={model.value} className="ml-3 block text-sm font-medium text-gray-700">{model.label}</label></div> ))}
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">5. Advanced RAG 技術を選択</label>
              <div className="mt-2 space-y-3 p-4 border rounded-md bg-gray-50">
                <div className="flex items-center pb-2 border-b"><input id="select-all-advanced" type="checkbox" checked={isAllAdvancedSelected} onChange={handleSelectAllAdvancedChange} className="h-4 w-4 text-purple-600 border-gray-300 rounded focus:ring-purple-500" /><label htmlFor="select-all-advanced" className="ml-3 block text-sm font-medium text-gray-900">すべて選択 / 解除</label></div>
                <div className="flex items-start"><div className="flex items-center h-5"><input id="chunking" type="checkbox" checked={advancedRagOptions.chunking} onChange={() => handleAdvancedRagChange('chunking')} className="h-4 w-4 text-purple-600 border-gray-300 rounded focus:ring-purple-500" /></div><div className="ml-3 text-sm"><label htmlFor="chunking" className="font-medium text-gray-700">チャンキング</label></div></div>
                <div className="flex items-start"><div className="flex items-center h-5"><input id="hybrid-search" type="checkbox" checked={advancedRagOptions.hybridSearch} onChange={() => handleAdvancedRagChange('hybridSearch')} className="h-4 w-4 text-purple-600 border-gray-300 rounded focus:ring-purple-500" /></div><div className="ml-3 text-sm"><label htmlFor="hybrid-search" className="font-medium text-gray-700">ハイブリッド検索</label></div></div>
                <div className="flex items-start"><div className="flex items-center h-5"><input id="prompt-tuning" type="checkbox" checked={advancedRagOptions.promptTuning} onChange={() => handleAdvancedRagChange('promptTuning')} className="h-4 w-4 text-purple-600 border-gray-300 rounded focus:ring-purple-500" /></div><div className="ml-3 text-sm"><label htmlFor="prompt-tuning" className="font-medium text-gray-700">プロンプト最適化</label></div></div>
              </div>
            </div>
            <button type="submit" disabled={isLoading || !qaFile || !contextFile} className="w-full bg-purple-600 text-white font-bold py-3 px-4 rounded-lg hover:bg-purple-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-purple-500 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors duration-300">
              {isLoading ? 'RAG性能を評価中...' : 'RAG評価を開始'}
            </button>
          </form>
          {error && ( <div className="mt-6 p-4 bg-red-100 border border-red-400 text-red-700 rounded-lg"><p className="font-bold">エラー</p><p>{error}</p></div> )}
        </div>
        
        {isLoading && ( <div className="text-center"><p className="text-lg text-gray-600">RAG評価を実行中です...</p></div> )}
        
        {results.length > 0 && (
          <div>
            <h2 className="text-3xl font-bold text-gray-800 mb-6 text-center">RAG評価ベンチマーク結果</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8 mb-12">
              {results.map(result => (
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
                {results.map(result => (
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
        )}
        <div className="mt-12">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-2xl font-bold text-gray-800">RAG評価の履歴</h2>
            {selectedCount > 0 && (
              <button onClick={handleDeleteSelected} className="bg-red-600 text-white font-bold py-2 px-4 rounded-lg hover:bg-red-700 text-sm transition-colors">
                選択した{selectedCount}件を削除
              </button>
            )}
          </div>
          <div className="bg-white shadow-md rounded-lg overflow-hidden">
            <table className="min-w-full leading-normal">
              <thead>
                <tr>
                  <th className="px-5 py-3 border-b-2 border-gray-200 bg-gray-100 w-12 text-center"><input type="checkbox" checked={isAllVisibleSelected} onChange={handleSelectAllDeletionChange} /></th>
                  <th className="px-5 py-3 border-b-2 border-gray-200 bg-gray-100 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">No.</th>
                  <th className="px-5 py-3 border-b-2 border-gray-200 bg-gray-100 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">実行日時</th>
                  <th className="px-5 py-3 border-b-2 border-gray-200 bg-gray-100 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">Q&Aファイル</th>
                  <th className="px-5 py-3 border-b-2 border-gray-200 bg-gray-100 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">文脈ファイル</th>
                  <th className="px-5 py-3 border-b-2 border-gray-200 bg-gray-100 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">評価モデル</th>
                  <th className="px-5 py-3 border-b-2 border-gray-200 bg-gray-100 text-center text-xs font-semibold text-gray-600 uppercase tracking-wider">質問数</th>
                </tr>
              </thead>
              <tbody>
                {visibleHistory.length > 0 ? (
                  visibleHistory.map((item, index) => (
                    <tr key={item.id} className={`${selectedForDeletion[item.id] ? 'bg-blue-50' : 'hover:bg-gray-50'}`}>
                      <td className="px-5 py-4 border-b border-gray-200 text-center"><input type="checkbox" checked={selectedForDeletion[item.id] || false} onChange={() => handleDeletionCheckboxChange(item.id)} /></td>
                      <td className="px-5 py-4 border-b border-gray-200"><Link href={`/rag-history/${item.id}`} className="text-blue-600 font-semibold hover:underline">{index + 1}</Link></td>
                      <td className="px-5 py-4 border-b border-gray-200 text-sm"><p className="text-gray-900 whitespace-no-wrap">{new Date(item.createdAt).toLocaleString('ja-JP')}</p></td>
                      <td className="px-5 py-4 border-b border-gray-200 text-sm"><p className="text-gray-900 whitespace-no-wrap">{item.qa_filename}</p></td>
                      <td className="px-5 py-4 border-b border-gray-200 text-sm"><p className="text-gray-900 whitespace-no-wrap">{item.context_filename}</p></td>
                      <td className="px-5 py-4 border-b border-gray-200 text-sm"><div className="flex flex-wrap gap-1">{item.models_tested.map(m => <span key={m} className="font-mono bg-gray-100 text-gray-700 px-2 py-0.5 rounded-md text-xs">{m}</span>)}</div></td>
                      <td className="px-5 py-4 border-b border-gray-200 text-sm text-center"><p className="text-gray-900 whitespace-no-wrap">{item.num_questions}</p></td>
                    </tr>
                  ))
                ) : (
                  <tr><td colSpan={7} className="text-center py-5 text-gray-500">RAG評価の履歴はまだありません。</td></tr>
                )}
              </tbody>
            </table>
          </div>
          {ragHistory.length > visibleHistoryCount && (
            <div className="mt-6 text-center">
              <button onClick={() => setVisibleHistoryCount(prev => prev + 10)} className="bg-gray-200 text-gray-800 font-bold py-2 px-6 rounded-lg hover:bg-gray-300">もっと見る</button>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}