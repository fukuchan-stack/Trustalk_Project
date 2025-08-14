// frontend/src/app/not-found.tsx

import { Metadata } from 'next';
import Link from 'next/link'; // Linkコンポーネントを使用
import * as React from 'react';
import { RiAlarmWarningFill } from 'react-icons/ri';

export const metadata: Metadata = {
  title: 'Not Found',
};

export default function NotFound() {
  return (
    <main>
      <section className='bg-white'>
        <div className='flex min-h-screen flex-col items-center justify-center text-center text-black'>
          <RiAlarmWarningFill
            size={60}
            className='drop-shadow-glow animate-flicker text-red-500'
          />
          <h1 className='mt-8 text-4xl md:text-6xl'>Page Not Found</h1>
          <Link href='/' className='mt-4 text-blue-600 hover:underline'>
            Back to home
          </Link>
        </div>
      </section>
    </main>
  );
}