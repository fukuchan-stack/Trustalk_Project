// frontend/src/app/api/proxy/[...path]/route.ts
import { NextRequest, NextResponse } from 'next/server';

// バックエンドAPIのベースURL (localhost, Codespacesコンテナ内から見たアドレス)
const BACKEND_URL = 'http://localhost:8000';

async function handler(req: NextRequest) {
  // フロントエンドからのパスを取得 (例: /api/proxy/api/history -> /api/history)
  const path = req.nextUrl.pathname.replace('/api/proxy', '');
  const url = `${BACKEND_URL}${path}${req.nextUrl.search}`;

  try {
    // ★★★★★★★★★★★★★★★★★★★★★★★★★★★★
    // ★ 修正点：headersを書き換えず、そのまま転送する
    // ★★★★★★★★★★★★★★★★★★★★★★★★★★★★
    const response = await fetch(url, {
      method: req.method,
      headers: req.headers, // ブラウザからのヘッダーをそのまま使う
      body: req.body,
      // @ts-ignore
      duplex: 'half',
    });

    return response;

  } catch (error) {
    console.error('Proxy error:', error);
    return NextResponse.json({ error: 'Proxy request failed' }, { status: 500 });
  }
}

export { handler as GET, handler as POST, handler as PUT, handler as DELETE };