"use client";

import Link from 'next/link';
import { useState, FormEvent, useRef, useEffect } from 'react';

// メッセージの型を定義
interface Message {
  role: 'user' | 'assistant' | 'error';
  content: string;
}

export default function KnowledgePage() {
  // ユーザーが入力中の質問を管理
  const [question, setQuestion] = useState('');
  // 会話の履歴を管理
  const [messages, setMessages] = useState<Message[]>([]);
  // ローディング状態を管理
  const [isLoading, setIsLoading] = useState(false);
  // APIのURLを取得
  const apiUrl = process.env.NEXT_PUBLIC_API_URL;
  // チャットの末尾に自動スクロールするための参照
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // messagesが更新されるたびに一番下にスクロールする
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // フォーム送信時の処理
  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!question.trim() || isLoading) return;

    // APIのURLが設定されていない場合はエラーを表示
    if (!apiUrl) {
      setMessages(prev => [...prev, { role: 'error', content: 'エラー: APIのURLが設定されていません。' }]);
      return;
    }

    setIsLoading(true);
    // ユーザーの質問を会話履歴に追加
    const userMessage: Message = { role: 'user', content: question };
    setMessages(prev => [...prev, userMessage]);
    setQuestion(''); // 入力欄をクリア

    try {
      // バックエンドのAPIを呼び出す
      const response = await fetch(`${apiUrl}/api/ask-knowledge-base`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: userMessage.content }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'サーバーでエラーが発生しました。');
      }

      const data = await response.json();
      // AIの回答を会話履歴に追加
      const assistantMessage: Message = { role: 'assistant', content: data.answer };
      setMessages(prev => [...prev, assistantMessage]);

    } catch (err: any) {
      // エラーが発生した場合、エラーメッセージを会話履歴に追加
      const errorMessage: Message = { role: 'error', content: `エラー: ${err.message}` };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      // ローディング状態を解除
      setIsLoading(false);
    }
  };

  return (
    <main className="flex min-h-screen flex-col items-center p-4 sm:p-8 bg-gray-50">
      <div className="w-full max-w-4xl flex flex-col h-[calc(100vh-4rem)]">
        <div className="text-center mb-6">
          <h1 className="text-4xl font-bold text-gray-800 mb-2">Trustalk</h1>
          <nav className="flex justify-center border-b border-gray-200">
            <Link href="/" className="px-4 py-2 text-lg font-semibold text-gray-500 hover:text-blue-600">個別分析</Link>
            <Link href="/benchmark-summary" className="px-4 py-2 text-lg font-semibold text-gray-500 hover:text-blue-600">モデル性能比較</Link>
            <Link href="/benchmark-rag" className="px-4 py-2 text-lg font-semibold text-gray-500 hover:text-blue-600">RAG評価</Link>
            <Link href="/knowledge" className="px-4 py-2 text-lg font-semibold text-blue-600 border-b-2 border-blue-600">ナレッジ検索</Link>
          </nav>
        </div>

        <div className="bg-white flex-grow rounded-lg shadow-md border border-gray-200 flex flex-col">
            <div className="p-4 border-b">
              <h2 className="text-xl font-bold text-gray-800">AIナレッジアシスタント</h2>
              <p className="text-sm text-gray-600">過去のミーティング議事録から、必要な情報をAIが探し出して回答します。</p>
            </div>
            
            {/* チャットメッセージ表示エリア */}
            <div className="flex-grow p-6 overflow-y-auto space-y-4">
              {messages.map((msg, index) => (
                <div key={index} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-lg px-4 py-2 rounded-lg shadow ${
                      msg.role === 'user' ? 'bg-blue-500 text-white' :
                      msg.role === 'assistant' ? 'bg-gray-200 text-gray-800' :
                      'bg-red-100 text-red-700'
                    }`}
                  >
                    <p className="whitespace-pre-wrap">{msg.content}</p>
                  </div>
                </div>
              ))}
              {/* スクロール用のアンカー */}
              <div ref={messagesEndRef} />
            </div>

            {/* 質問入力フォーム */}
            <div className="p-4 border-t bg-white">
              <form onSubmit={handleSubmit} className="flex items-center space-x-2">
                <input
                  type="text"
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  placeholder={isLoading ? "AIが回答を考えています..." : "質問を入力してください..."}
                  className="flex-grow px-4 py-2 border border-gray-300 rounded-full focus:outline-none focus:ring-2 focus:ring-blue-500"
                  disabled={isLoading}
                />
                <button 
                  type="submit" 
                  disabled={isLoading || !question.trim()}
                  className="bg-blue-600 text-white font-bold p-2 rounded-full hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-all duration-200"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/></svg>
                </button>
              </form>
            </div>
        </div>
      </div>
    </main>
  );
}