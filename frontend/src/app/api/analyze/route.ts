import { NextRequest, NextResponse } from 'next/server';

export async function POST(req: NextRequest) {
  try {
    const formData = await req.formData();
    const backendUrl = 'http://localhost:8000/analyze';

    const response = await fetch(backendUrl, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const errorText = await response.text();
      // バックエンドからのエラーをフロントエンドに中継する
      return new NextResponse(errorText || response.statusText, { status: response.status });
    }

    const data = await response.json();
    return NextResponse.json(data);

  } catch (error) {
    console.error('BFF Error in /api/analyze:', error);
    return new NextResponse('Internal Server Error in BFF', { status: 500 });
  }
}