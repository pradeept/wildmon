'use client';

import { useParams } from 'next/navigation';
import Link from 'next/link';
import { useEffect, useState } from 'react';
import { Camera, CheckCircle, Clock, Flag } from '@phosphor-icons/react';
import useSWR from 'swr';
import { api, post } from '@/lib/api';
import type { Challenge, Profile, Requirement } from '@/lib/types';
import { ErrorNote, PageHeader } from '@/components/ui';

function label(target: Requirement) {
  if (target.kind === 'species') return `Exact species: ${target.species_id.replaceAll('_', ' ')}`;
  if (target.kind === 'visual_trait')
    return `Visible trait: ${target.trait_code.replaceAll('_', ' ')}`;
  return `Any ${target.category.replaceAll('_', ' ')}`;
}

export default function ChallengeDetail() {
  const { id } = useParams<{ id: string }>();
  const { data: me } = useSWR<Profile>('/me', api);
  const { data: challenge, mutate } = useSWR<Challenge>(`/challenges/${id}`, api, {
    refreshInterval: 3000,
  });
  const [error, setError] = useState('');
  const [remaining, setRemaining] = useState('');
  useEffect(() => {
    if (!challenge?.deadline_at) return;
    const update = () => {
      const seconds = Math.max(
        0,
        Math.floor((new Date(challenge.deadline_at!).getTime() - Date.now()) / 1000),
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
  }, [challenge?.deadline_at]);
  async function action(name: 'accept' | 'decline' | 'ready' | 'done') {
    setError('');
    try {
      await post(`/challenges/${id}/${name}`);
      await mutate();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not update challenge.');
    }
  }
  const isInvitee = challenge?.invitee_id === me?.id;
  const done = Boolean(me && challenge?.done_ids.includes(me.id));
  const ready = Boolean(me && challenge?.ready_ids.includes(me.id));
  return (
    <>
      <PageHeader
        title='Friend challenge'
        description='Find the same targets before the shared clock runs out. Verified photos decide the result.'
        action={<span className='status'>{challenge?.state.replace('_', ' ') ?? 'Loading'}</span>}
      />
      <div className='grid gap-6 lg:grid-cols-[1fr_.7fr]'>
        <div className='surface p-6 md:p-8'>
          <h2 className='text-xl font-semibold'>Targets</h2>
          <p className='mt-1 text-sm text-muted'>Each photo can satisfy only one target.</p>
          <div className='mt-5 divide-y divide-line'>
            {challenge?.requirements.map((target) => (
              <div key={target.id} className='flex items-center justify-between gap-3 py-4'>
                <div>
                  <p className='font-semibold capitalize'>{label(target)}</p>
                  <p className='mt-1 text-xs text-muted'>
                    {target.kind === 'species'
                      ? 'Catalog species identification required'
                      : target.kind === 'visual_trait'
                        ? 'Separate visual feature check required'
                        : 'Verified category required'}
                  </p>
                </div>
                <span className='shrink-0 font-semibold text-accent'>
                  {target.kind === 'species' ? 3 : target.kind === 'taxon_category' ? 2 : 1} pts
                </span>
              </div>
            ))}
          </div>
        </div>
        <aside className='surface-soft h-fit p-6'>
          <Clock size={28} className='text-accent' />
          <h2 className='mt-4 text-xl font-semibold'>
            {challenge?.state === 'active'
              ? 'Hunt in progress'
              : challenge?.state === 'completed'
                ? 'Results are in'
                : 'Shared start'}
          </h2>
          <p className='mt-2 text-sm text-muted'>
            {challenge?.state === 'invited'
              ? 'Your friend needs to accept the invitation.'
              : challenge?.state === 'active'
                ? 'Take photos, then press Done when you have finished.'
                : 'Both explorers must tap Ready. The server starts the timer together.'}
          </p>
          {challenge?.state === 'active' ? (
            <p className='mt-6 font-mono text-5xl font-semibold tracking-tight'>
              {remaining || '--:--'}
            </p>
          ) : null}
          <div className='mt-6 grid gap-3'>
            {challenge?.state === 'invited' && isInvitee ? (
              <>
                <button className='button' onClick={() => action('accept')}>
                  Accept challenge
                </button>
                <button className='button-secondary' onClick={() => action('decline')}>
                  Decline
                </button>
              </>
            ) : null}
            {['accepted', 'ready_wait'].includes(challenge?.state ?? '') ? (
              <button className='button' disabled={ready} onClick={() => action('ready')}>
                {ready ? 'Ready, waiting for friend' : 'I am ready'}
              </button>
            ) : null}
            {challenge?.state === 'active' && !done ? (
              <>
                <Link href={`/capture?challenge=${id}`} className='button'>
                  <Camera size={18} /> Capture target
                </Link>
                <button onClick={() => action('done')} className='button-secondary'>
                  <Flag size={18} /> Done for now
                </button>
              </>
            ) : null}
            {challenge?.state === 'active' && done ? (
              <div className='flex items-center gap-2 text-sm font-semibold text-muted'>
                <CheckCircle size={20} className='text-accent' /> Your captures are locked. Waiting
                for your friend.
              </div>
            ) : null}
            {challenge?.state === 'verifying' ? (
              <p className='text-sm font-semibold text-muted'>
                Checking evidence. Results will appear soon.
              </p>
            ) : null}
            {challenge?.state === 'completed' ? (
              <Link href={`/challenges/${id}/results`} className='button'>
                See results
              </Link>
            ) : null}
            <ErrorNote message={error} />
          </div>
        </aside>
      </div>
    </>
  );
}
