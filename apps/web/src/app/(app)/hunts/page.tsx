'use client';

import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useState } from 'react';
import { ArrowUpRight, Clock, Footprints, Sparkle } from '@phosphor-icons/react';
import useSWR from 'swr';
import { api, post } from '@/lib/api';
import type { Hunt } from '@/lib/types';
import { ErrorNote, PageHeader } from '@/components/ui';

export default function Hunts() {
  const router = useRouter();
  const [duration, setDuration] = useState<10 | 20 | 30>(20);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const { data: hunts, error: historyError } = useSWR<Hunt[]>('/hunts', api);
  async function start() {
    setBusy(true);
    setError('');
    try {
      const hunt = await post<Hunt>('/hunts', { duration_minutes: duration });
      router.push(`/hunts/${hunt.id}`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not start hunt.');
      setBusy(false);
    }
  }
  return (
    <>
      <PageHeader
        title='Timed free hunt'
        description='Give yourself a little time outside. Capture discoveries along the way, then see what you found.'
      />
      <div className='grid gap-6 lg:grid-cols-[1.1fr_.9fr]'>
        <div className='surface p-6 md:p-8'>
          <Clock size={33} weight='duotone' className='text-accent' />
          <h2 className='mt-5 text-2xl font-semibold tracking-tight'>Choose your time</h2>
          <p className='mt-2 text-sm text-muted'>
            The timer starts on the server when you press Start.
          </p>
          <div role='group' aria-label='Hunt duration' className='mt-7 grid grid-cols-3 gap-3'>
            {([10, 20, 30] as const).map((minutes) => (
              <button
                key={minutes}
                onClick={() => setDuration(minutes)}
                aria-pressed={duration === minutes}
                className={`rounded-xl border px-3 py-5 text-center transition-colors ${duration === minutes ? 'border-accent bg-surface-alt' : 'border-line hover:bg-surface-alt'}`}
              >
                <strong className='block text-2xl'>{minutes}</strong>
                <span className='text-xs text-muted'>minutes</span>
              </button>
            ))}
          </div>
          <div className='mt-6'>
            <ErrorNote message={error} />
          </div>
          <button onClick={start} disabled={busy} className='button mt-6 w-full'>
            {busy ? 'Starting...' : 'Start hunt'}
          </button>
        </div>
        <div className='surface-soft p-6 md:p-8'>
          <h2 className='text-xl font-semibold'>How it works</h2>
          <div className='mt-6 grid gap-6'>
            <div className='flex gap-4'>
              <Footprints size={24} className='shrink-0 text-accent' />
              <div>
                <h3 className='font-semibold'>Walk and notice</h3>
                <p className='mt-1 text-sm text-muted'>There is no required route or target.</p>
              </div>
            </div>
            <div className='flex gap-4'>
              <Sparkle size={24} className='shrink-0 text-accent' />
              <div>
                <h3 className='font-semibold'>Capture one subject at a time</h3>
                <p className='mt-1 text-sm text-muted'>
                  Photos are identified after upload. Unclear results stay uncertain.
                </p>
              </div>
            </div>
            <div className='flex gap-4'>
              <Clock size={24} className='shrink-0 text-accent' />
              <div>
                <h3 className='font-semibold'>Finish and reveal</h3>
                <p className='mt-1 text-sm text-muted'>
                  Your summary updates as identification completes.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
      <section className='mt-10'>
        <h2 className='text-xl font-semibold tracking-tight'>Your hunts</h2>
        <p className='mt-1 text-sm text-muted'>Pick up an active walk or revisit what you found.</p>
        {historyError ? (
          <p className='mt-4 text-sm text-muted'>Your hunt history could not load right now.</p>
        ) : hunts?.length ? (
          <div className='mt-5 grid gap-3 sm:grid-cols-2'>
            {hunts.map((hunt) => {
              const active = hunt.state === 'active' && new Date(hunt.deadline_at) > new Date();
              return (
                <Link
                  key={hunt.id}
                  href={active ? `/hunts/${hunt.id}` : `/hunts/${hunt.id}/summary`}
                  className='surface group flex items-center justify-between gap-4 p-5 transition-colors hover:bg-surface-alt focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent'
                >
                  <div>
                    <span className='text-xs font-semibold uppercase tracking-wide text-accent'>
                      {active ? 'In progress' : 'Hunt summary'}
                    </span>
                    <p className='mt-1 font-semibold'>{hunt.duration_minutes}-minute nature walk</p>
                    <p className='mt-1 text-sm text-muted'>
                      {new Date(hunt.started_at).toLocaleDateString()}
                    </p>
                  </div>
                  <ArrowUpRight size={20} className='shrink-0 text-accent' />
                </Link>
              );
            })}
          </div>
        ) : hunts ? (
          <p className='mt-4 text-sm text-muted'>Your first hunt will appear here.</p>
        ) : (
          <p className='mt-4 text-sm text-muted'>Loading hunts…</p>
        )}
      </section>
    </>
  );
}
