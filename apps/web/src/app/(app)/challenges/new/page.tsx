'use client';

import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { Plus, Trash } from '@phosphor-icons/react';
import useSWR from 'swr';
import { api, post } from '@/lib/api';
import { createClientId } from '@/lib/client-id';
import type { Challenge, Requirement } from '@/lib/types';
import { ErrorNote, PageHeader } from '@/components/ui';

type Friend = { user_id: string; username: string; status: string };
type Species = { id: string; common_name: string; scientific_name: string };
type Draft = { id: string; kind: 'species' | 'taxon_category' | 'visual_trait'; value: string };
const categories = ['plant', 'bird', 'insect', 'butterfly', 'flowering_plant', 'tree'];
const traits = ['serrated_leaf', 'yellow_flower', 'five_petals', 'striped_wing'];
const points = { species: 3, taxon_category: 2, visual_trait: 1 };
const defaultTargets: Draft[] = [
  { id: 'target_a', kind: 'taxon_category', value: 'plant' },
  { id: 'target_b', kind: 'taxon_category', value: 'bird' },
  { id: 'target_c', kind: 'visual_trait', value: 'yellow_flower' },
];

export default function NewChallenge() {
  const router = useRouter();
  const { data: friends } = useSWR<Friend[]>('/friends', api);
  const { data: species } = useSWR<Species[]>('/species', api);
  const accepted = friends?.filter((friend) => friend.status === 'accepted') ?? [];
  const [friendId, setFriendId] = useState('');
  const [duration, setDuration] = useState<15 | 20 | 30>(20);
  const [targets, setTargets] = useState<Draft[]>(defaultTargets);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  function change(index: number, update: Partial<Draft>) {
    setTargets((current) =>
      current.map((item, at) => (at === index ? { ...item, ...update } : item)),
    );
  }
  async function submit() {
    if (!friendId) {
      setError('Choose a friend first.');
      return;
    }
    setBusy(true);
    setError('');
    const requirements: Requirement[] = targets.map((target) => {
      if (target.kind === 'species')
        return { id: target.id, kind: 'species', species_id: target.value, count: 1 };
      if (target.kind === 'visual_trait')
        return { id: target.id, kind: 'visual_trait', trait_code: target.value, count: 1 };
      return {
        id: target.id,
        kind: 'taxon_category',
        category: target.value,
        count: 1,
        distinct_species: 0,
      };
    });
    try {
      const challenge = await post<Challenge>('/challenges', {
        friend_id: friendId,
        duration_minutes: duration,
        requirements,
      });
      router.push(`/challenges/${challenge.id}`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not create challenge.');
      setBusy(false);
    }
  }
  return (
    <>
      <PageHeader
        title='Create a challenge'
        description='Pick one friend and 3 to 5 clear targets. Each target shows what evidence it needs and how many points it earns.'
      />
      <div className='grid gap-6 lg:grid-cols-[1fr_.65fr]'>
        <div className='surface p-6 md:p-8'>
          <label htmlFor='opponent' className='label'>
            Challenge a friend
          </label>
          <select
            id='opponent'
            value={friendId}
            onChange={(event) => setFriendId(event.target.value)}
            className='field'
          >
            <option value=''>Choose a friend</option>
            {accepted.map((friend) => (
              <option key={friend.user_id} value={friend.user_id}>
                {friend.username}
              </option>
            ))}
          </select>
          {!accepted.length ? (
            <p className='mt-2 text-sm text-muted'>
              No accepted friends yet.{' '}
              <a href='/friends' className='font-semibold text-accent underline'>
                Find a friend
              </a>
              .
            </p>
          ) : null}
          <label htmlFor='duration' className='label mt-6'>
            Shared duration
          </label>
          <select
            id='duration'
            value={duration}
            onChange={(event) => setDuration(Number(event.target.value) as 15 | 20 | 30)}
            className='field'
          >
            <option value={15}>15 minutes</option>
            <option value={20}>20 minutes</option>
            <option value={30}>30 minutes</option>
          </select>
          <h2 className='mt-8 text-xl font-semibold'>Targets</h2>
          <div className='mt-4 grid gap-3'>
            {targets.map((target, index) => {
              const options =
                target.kind === 'species'
                  ? (species ?? []).map((item) => ({ value: item.id, label: item.common_name }))
                  : (target.kind === 'visual_trait' ? traits : categories).map((item) => ({
                      value: item,
                      label: item.replaceAll('_', ' '),
                    }));
              return (
                <div
                  key={target.id}
                  className='surface-soft grid gap-3 p-4 sm:grid-cols-[.8fr_1fr_auto]'
                >
                  <div>
                    <label htmlFor={`kind-${index}`} className='label'>
                      Evidence type
                    </label>
                    <select
                      id={`kind-${index}`}
                      className='field'
                      value={target.kind}
                      onChange={(event) => {
                        const kind = event.target.value as Draft['kind'];
                        change(index, {
                          kind,
                          value:
                            kind === 'species'
                              ? (species?.[0]?.id ?? '')
                              : kind === 'visual_trait'
                                ? traits[0]
                                : categories[0],
                        });
                      }}
                    >
                      <option value='taxon_category'>Category</option>
                      <option value='visual_trait'>Visual trait</option>
                      <option value='species' disabled={!species?.length}>
                        Exact species
                      </option>
                    </select>
                  </div>
                  <div>
                    <label htmlFor={`value-${index}`} className='label'>
                      Find
                    </label>
                    <select
                      id={`value-${index}`}
                      className='field capitalize'
                      value={target.value}
                      onChange={(event) => change(index, { value: event.target.value })}
                    >
                      {options.map((item) => (
                        <option key={item.value} value={item.value}>
                          {item.label}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className='flex items-end justify-between gap-3 sm:flex-col sm:items-center sm:justify-end'>
                    <span className='text-sm font-semibold text-accent'>
                      {points[target.kind]} pts
                    </span>
                    <button
                      aria-label={`Remove target ${index + 1}`}
                      disabled={targets.length <= 3}
                      onClick={() =>
                        setTargets((current) => current.filter((_, at) => at !== index))
                      }
                      className='rounded-lg p-2 text-muted hover:bg-surface'
                    >
                      <Trash size={18} />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
          {targets.length < 5 ? (
            <button
              onClick={() =>
                setTargets((current) => [
                  ...current,
                  { id: createClientId(), kind: 'taxon_category', value: 'insect' },
                ])
              }
              className='button-secondary mt-4'
            >
              <Plus size={17} /> Add target
            </button>
          ) : null}
          <div className='mt-6'>
            <ErrorNote message={error} />
          </div>
          <button disabled={busy} onClick={submit} className='button mt-5 w-full'>
            {busy ? 'Sending invitation...' : 'Send invitation'}
          </button>
        </div>
        <aside className='surface-soft h-fit p-6'>
          <h2 className='text-xl font-semibold'>Fair from the start</h2>
          <p className='mt-3 text-sm leading-relaxed text-muted'>
            An exact species needs a supported catalog match. Categories need a verified category.
            Visual traits get a separate model check. One photo fills one target.
          </p>
          <p className='mt-5 text-sm leading-relaxed text-muted'>
            The timer begins only after your friend accepts and both of you tap Ready.
          </p>
        </aside>
      </div>
    </>
  );
}
