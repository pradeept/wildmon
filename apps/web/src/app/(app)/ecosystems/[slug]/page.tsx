'use client';

import { useParams } from 'next/navigation';
import { useState } from 'react';
import useSWR from 'swr';
import { CheckCircle, Circle } from '@phosphor-icons/react';
import { api, post } from '@/lib/api';
import type { Pack, Requirement } from '@/lib/types';
import { ErrorNote, PageHeader } from '@/components/ui';

function label(slot: Requirement) {
  if (slot.kind === 'taxon_category') return slot.category.replaceAll('_', ' ');
  if (slot.kind === 'visual_trait') return slot.trait_code.replaceAll('_', ' ');
  return slot.species_id.replaceAll('_', ' ');
}

export default function EcosystemDetail() {
  const { slug } = useParams<{ slug: string }>();
  const { data: pack, mutate } = useSWR<Pack>(`/ecosystems/${slug}`, api);
  const [error, setError] = useState('');
  async function join() {
    try {
      await post(`/ecosystems/${slug}/join`);
      await mutate();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not join pack.');
    }
  }
  return (
    <>
      <PageHeader title={pack?.title ?? 'Ecosystem'} description={pack?.description} />
      <div className='grid gap-6 lg:grid-cols-[1fr_.7fr]'>
        <section className='surface p-6 md:p-8'>
          <div className='flex flex-wrap items-center justify-between gap-3'>
            <h2 className='text-xl font-semibold'>Your checklist</h2>
            <span className='status'>
              {pack?.progress?.state.replace('_', ' ') ?? 'Not joined'}
            </span>
          </div>
          <div className='mt-6 divide-y divide-line'>
            {pack?.slots.map((slot, index) => {
              const found = Array.from(
                { length: slot.count },
                (_, unit) => pack.progress?.assignments[`${slot.id}:${unit}`],
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
                      {slot.count > 1
                        ? `${found} of ${slot.count} distinct species verified`
                        : 'Photograph a clear, verified observation'}
                    </p>
                  </div>
                  <span className='ml-auto text-xs text-muted'>
                    {index + 1}/{pack.slots.length}
                  </span>
                </div>
              );
            })}
          </div>
          {!pack?.progress ? (
            <button onClick={join} className='button mt-6'>
              Join this pack
            </button>
          ) : null}
          <div className='mt-4'>
            <ErrorNote message={error} />
          </div>
        </section>
        <aside className='surface-soft h-fit p-6'>
          <h2 className='text-xl font-semibold'>Explore over time</h2>
          <p className='mt-3 text-sm leading-relaxed text-muted'>
            A pack has no timer. Verified photos from quick captures and hunts can count, including
            earlier discoveries when you join.
          </p>
          <p className='mt-5 text-sm font-semibold text-accent'>Complete the pack for 300 XP</p>
        </aside>
      </div>
    </>
  );
}
