'use client';

import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { useEffect, useState } from 'react';
import { Camera, Clock } from '@phosphor-icons/react';
import useSWR from 'swr';
import { api, post } from '@/lib/api';
import type { Hunt } from '@/lib/types';
import { ErrorNote, PageHeader } from '@/components/ui';

export default function HuntPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { data: hunt, mutate } = useSWR<Hunt>(`/hunts/${id}`, api);
  const [remaining, setRemaining] = useState('');
  const [error, setError] = useState('');
  useEffect(() => {
    if (!hunt) return;
    const update = () => {
      const seconds = Math.max(
        0,
        Math.floor((new Date(hunt.deadline_at).getTime() - Date.now()) / 1000),
      );
      setRemaining(
        `${Math.floor(seconds / 60)
          .toString()
          .padStart(2, '0')}:${(seconds % 60).toString().padStart(2, '0')}`,
      );
    };
    update();
    const timer = setInterval(update, 1000);
    return () => clearInterval(timer);
  }, [hunt]);
  useEffect(() => {
    if (!hunt) return;
    if (hunt.state !== 'active' && Date.now() > new Date(hunt.deadline_at).getTime() + 120000) {
      return;
    }
    const visibility = () => {
      void api(`/hunts/${id}/visibility`, {
        method: 'POST',
        keepalive: true,
        body: JSON.stringify({
          kind: document.hidden ? 'hidden' : 'visible',
          client_at: new Date().toISOString(),
        }),
      }).catch(() => {});
    };
    if (!document.hidden) visibility();
    const pagehide = () => {
      const csrf =
        document.cookie
          .split('; ')
          .find((item) => item.startsWith('wildmon_csrf='))
          ?.split('=')[1] ?? '';
      fetch(`/api/v1/hunts/${id}/visibility`, {
        method: 'POST',
        credentials: 'include',
        keepalive: true,
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
        body: JSON.stringify({ kind: 'pagehide', client_at: new Date().toISOString() }),
      }).catch(() => {});
    };
    document.addEventListener('visibilitychange', visibility);
    window.addEventListener('pagehide', pagehide);
    return () => {
      document.removeEventListener('visibilitychange', visibility);
      window.removeEventListener('pagehide', pagehide);
    };
  }, [hunt?.state, id]);
  async function finish() {
    try {
      await post(`/hunts/${id}/finish`);
      await mutate();
      router.push(`/hunts/${id}/summary`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not finish hunt.');
    }
  }
  return (
    <>
      <PageHeader
        title='Your hunt is on'
        description='Look around, take a photo when something catches your eye, then put your phone away.'
      />
      <div className='mx-auto max-w-xl'>
        <div className='rounded-2xl bg-forest p-8 text-center text-white'>
          <Clock size={28} className='mx-auto text-[#ff9975]' />
          <p className='mt-3 text-sm text-white/70'>Time remaining</p>
          <p className='mt-2 font-mono text-6xl font-semibold tracking-tight'>
            {remaining || '--:--'}
          </p>
          <p className='mt-3 text-sm text-white/70'>
            Estimated in-app focus appears in your summary.
          </p>
        </div>
        <div className='mt-5 grid gap-3'>
          <Link href={`/capture?session=${id}`} className='button w-full py-4'>
            <Camera size={20} /> Capture discovery
          </Link>
          <button onClick={finish} className='button-secondary w-full'>
            Finish hunt
          </button>
          <ErrorNote message={error} />
        </div>
      </div>
    </>
  );
}
