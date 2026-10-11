'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useEffect, useState } from 'react';
import useSWR from 'swr';
import { ArrowRight, CheckCircle, Circle, Clock, Leaf } from '@phosphor-icons/react';
import { api, post } from '@/lib/api';
import type { Pack, Requirement } from '@/lib/types';
import { ErrorNote, PageHeader } from '@/components/ui';

function label(slot: Requirement) {
  if (slot.kind === 'taxon_category') return slot.category.replaceAll('_', ' ');
  if (slot.kind === 'visual_trait') return slot.trait_code.replaceAll('_', ' ');
  return slot.species_id.replaceAll('_', ' ');
}

function stateLabel(state: string) {
  return (
    (
      {
        active: 'In progress',
        verifying: 'Checking photos',
        completed: 'Completed',
        partial: 'Partially completed',
        missed: "Couldn't complete",
      } as Record<string, string>
    )[state] ?? state
  );
}

function timeLeft(deadline: string, current: number) {
  const seconds = Math.max(0, Math.ceil((new Date(deadline).getTime() - current) / 1000));
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return `${hours}h ${minutes}m left`;
}

export default function EcosystemDetail() {
  const { slug } = useParams<{ slug: string }>();
  const { data: pack, mutate } = useSWR<Pack>(`/ecosystems/${slug}`, api, {
    refreshInterval: (current) =>
      current?.attempt?.state === 'active' || current?.attempt?.state === 'verifying' ? 10000 : 0,
  });
  const [duration, setDuration] = useState(24);
  const [current, setCurrent] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const attempt = pack?.attempt;
  useEffect(() => {
    const update = () => setCurrent(Date.now());
    update();
    const timer = setInterval(update, 30000);
    return () => clearInterval(timer);
  }, []);

  async function start() {
    setBusy(true);
    setError('');
    try {
      await post(`/ecosystems/${slug}/start`, { duration_hours: duration });
      await mutate();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not start ecosystem.');
    } finally {
      setBusy(false);
    }
  }

  async function finish() {
    if (
      !window.confirm('Finish this ecosystem now? You cannot upload more photos or try it again.')
    )
      return;
    setBusy(true);
    setError('');
    try {
      await post(`/ecosystems/${slug}/finish`);
      await mutate();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not finish ecosystem.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader title={pack?.title ?? 'Ecosystem'} description={pack?.description} />
      <div className='grid gap-6 lg:grid-cols-[minmax(0,1fr)_310px]'>
        <section className='surface p-6 md:p-8'>
          <div className='flex flex-wrap items-center justify-between gap-3'>
            <h2 className='text-xl font-semibold'>Your field checklist</h2>
            <span className='status'>{attempt ? stateLabel(attempt.state) : 'Ready to start'}</span>
          </div>
          <p className='mt-2 text-sm text-muted'>
            Each checked spot needs a new verified photo uploaded through this ecosystem.
          </p>
          <div className='mt-6 divide-y divide-line'>
            {pack?.slots.map((slot) => {
              const found = Array.from(
                { length: slot.count },
                (_, unit) => attempt?.assignments[`${slot.id}:${unit}`],
              ).filter(Boolean).length;
              return (
                <div key={slot.id} className='flex items-center gap-4 py-4'>
                  {found === slot.count ? (
                    <CheckCircle size={25} weight='fill' className='text-accent' />
                  ) : (
                    <Circle size={25} className='text-muted' />
                  )}
                  <div>
                    <p className='font-semibold capitalize'>{label(slot)}</p>
                    <p className='text-xs text-muted'>
                      {found} of {slot.count} photos matched
                    </p>
                    {Array.from(
                      { length: slot.count },
                      (_, unit) => attempt?.assignments[`${slot.id}:${unit}`],
                    )
                      .filter((id): id is string => Boolean(id))
                      .map((id, index) => (
                        <Link
                          key={id}
                          href={`/discoveries/${id}`}
                          className='mt-1 mr-3 inline-block text-xs font-semibold text-accent underline-offset-2 hover:underline'
                        >
                          View photo {index + 1}
                        </Link>
                      ))}
                  </div>
                </div>
              );
            })}
          </div>
          {attempt?.state === 'active' ? (
            <div className='mt-6 flex flex-wrap gap-3'>
              <Link
                href={`/capture?ecosystem=${attempt.id}&ecosystem_slug=${slug}`}
                className='button'
              >
                Add a discovery <ArrowRight size={18} />
              </Link>
              <button disabled={busy} onClick={finish} className='button-secondary'>
                Finish now
              </button>
            </div>
          ) : null}
          {attempt && ['completed', 'partial', 'missed'].includes(attempt.state) ? (
            <div className='mt-6 rounded-2xl bg-surface-alt p-5'>
              <p className='font-semibold'>{stateLabel(attempt.state)}</p>
              <p className='mt-1 text-sm text-muted'>
                {attempt.matched_units} of {attempt.total_units} matched · +{attempt.bonus_xp}{' '}
                milestone XP
              </p>
            </div>
          ) : null}
          <div className='mt-4'>
            <ErrorNote message={error} />
          </div>
        </section>
        <aside className='surface-soft h-fit p-6'>
          <Leaf size={30} weight='duotone' className='text-accent' />
          <h2 className='mt-5 text-xl font-semibold'>A little time outside</h2>
          {!attempt ? (
            <>
              <p className='mt-3 text-sm leading-relaxed text-muted'>
                Set your window and begin. You get one attempt at this ecosystem.
              </p>
              <label htmlFor='duration' className='mt-6 block text-sm font-semibold'>
                Duration
              </label>
              <input
                id='duration'
                type='number'
                min={1}
                max={168}
                step={1}
                value={duration}
                onChange={(event) => setDuration(Number(event.target.value))}
                className='mt-2 w-full rounded-xl border border-line bg-surface px-4 py-3'
              />
              <p className='mt-2 text-xs text-muted'>Choose 1–168 whole hours (up to 7 days).</p>
              <button
                disabled={busy || !Number.isInteger(duration) || duration < 1 || duration > 168}
                onClick={start}
                className='button mt-4 w-full'
              >
                Start ecosystem
              </button>
            </>
          ) : (
            <>
              <p className='mt-3 flex items-center gap-2 text-sm font-semibold'>
                <Clock size={18} />
                {attempt.state === 'active'
                  ? timeLeft(attempt.deadline_at, current)
                  : stateLabel(attempt.state)}
              </p>
              <p className='mt-3 text-sm leading-relaxed text-muted'>
                {attempt.state === 'verifying'
                  ? 'Checking photos submitted before the timer ended. Results settle within five minutes.'
                  : 'Only photos submitted through this ecosystem count toward this checklist.'}
              </p>
              <p className='mt-5 text-xs text-muted'>
                Started {new Date(attempt.started_at).toLocaleString()}
              </p>
            </>
          )}
          <div className='mt-6 border-t border-line pt-5 text-sm text-muted'>
            Milestone XP: +50 for some progress, +150 for at least half, +300 for all spots.
          </div>
          {pack?.legacy_progress ? (
            <div className='mt-5 rounded-xl border border-line p-4 text-xs text-muted'>
              <p className='font-semibold text-ink'>Earlier pack history</p>
              <p className='mt-1'>
                {pack.legacy_progress.state === 'completed' ? 'Completed' : 'In progress'} ·{' '}
                {Object.keys(pack.legacy_progress.assignments).length} slots matched
              </p>
              <p className='mt-1'>
                This history and its XP are saved. It does not count toward this timed attempt.
              </p>
            </div>
          ) : null}
        </aside>
      </div>
    </>
  );
}
