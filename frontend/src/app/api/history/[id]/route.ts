// frontend/src/app/api/history/[id]/route.ts
import { NextResponse } from 'next/server';
const BACKEND_URL = 'http://localhost:8000';

export async function GET(
  _req: Request,
  { params }: { params: { id: string } },
) {
  const id = params.id;
  try {
    const response = await fetch(`${BACKEND_URL}/api/history/${id}`);
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json(
      { error: 'Failed to fetch history detail' },
      { status: 500 },
    );
  }
}
