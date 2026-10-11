'use client';

import { useState } from 'react';
import { ArrowClockwise } from '@phosphor-icons/react';
import { post } from '@/lib/api';
import type { Discovery } from '@/lib/types';
import { ErrorNote } from '@/components/ui';

export function RetryDiscoveryButton({
  id,
  onRetried,
}: {
  id: string;
  onRetried: (discovery: Discovery) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function retry() {
    setBusy(true);
    setError('');
    try {
      onRetried(await post<Discovery>(`/discoveries/${id}/retry`));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not retry identification.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className='mt-6 grid gap-3'>
      <button type='button' onClick={retry} disabled={busy} className='button w-full'>
        <ArrowClockwise size={18} /> {busy ? 'Retrying…' : 'Retry identification'}
      </button>
      <ErrorNote message={error} />
    </div>
  );
}
