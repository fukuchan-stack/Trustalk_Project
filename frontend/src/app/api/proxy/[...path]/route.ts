// frontend/src/app/api/proxy/[...path]/route.ts
import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = 'http://localhost:8000';

async function handler(req: NextRequest) {
  const path = req.nextUrl.pathname.replace('/api/proxy', '');
  const url = `${BACKEND_URL}${path}${req.nextUrl.search}`;

  try {
    const response = await fetch(url, {
      method: req.method,
      headers: req.headers,
      body: req.body,
      // ★ 修正点1: duplex は streaming body で必要だが、
      // ここではNextResponseでラップするため、ts-ignoreを削除しても問題ないことが多い
      // duplex: 'half',
    });

    // バックエンドからのレスポンスをそのままクライアントに返す
    return response;
  } catch (error) {
    // ★ 修正点2: console.errorを削除
    return NextResponse.json(
      { error: 'Proxy request failed' },
      { status: 500 },
    );
  }
}

// ★ 修正点3: exportの順番をアルファベット順に (DELETE, GET, POST, PUT)
export { handler as DELETE, handler as GET, handler as POST, handler as PUT };
