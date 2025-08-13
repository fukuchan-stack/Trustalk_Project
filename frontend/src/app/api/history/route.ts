// frontend/src/app/api/history/route.ts
import { NextResponse } from 'next/server';
const BACKEND_URL = 'http://localhost:8000';

export async function GET() {
  try {
    const response = await fetch(`${BACKEND_URL}/api/history`);
    if (!response.ok) {
      throw new Error(`Backend error: ${response.statusText}`);
    }
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    return NextResponse.json({ error: 'Failed to fetch history', details: errorMessage }, { status: 500 });
  }
}