import { Suspense } from 'react';
import { CaptureFlow } from '@/components/capture-flow';

export default function CapturePage() {
  return (
    <Suspense fallback={<div className='surface h-96 animate-pulse bg-surface-alt' />}>
      <CaptureFlow />
    </Suspense>
  );
}
