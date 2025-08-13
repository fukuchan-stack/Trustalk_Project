// frontend/src/app/api/analyze/route.ts
import { NextRequest, NextResponse } from 'next/server';
const BACKEND_URL = 'http://localhost:8000';

export async function POST(req: NextRequest) {
  try {
    const formData = await req.formData();
    const response = await fetch(`${BACKEND_URL}/api/analyze`, {
      method: 'POST',
      body: formData,
    });
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json(
      { error: 'Failed to analyze audio' },
      { status: 500 },
    );
  }
}
