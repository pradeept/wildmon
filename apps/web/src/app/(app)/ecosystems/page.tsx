'use client';

import Link from 'next/link';
import { ArrowRight, Leaf } from '@phosphor-icons/react';
import useSWR from 'swr';
import { api } from '@/lib/api';
import type { Pack } from '@/lib/types';
import { PageHeader } from '@/components/ui';

export default function Ecosystems() {
  const { data } = useSWR<Pack[]>('/ecosystems', api);
  return (
    <>
      <PageHeader
        title='Ecosystem challenges'
        description='Choose a place to explore, set your time, and add new discoveries to its field checklist.'
      />
      <div className='grid gap-4 md:grid-cols-3'>
        {data?.map((pack, index) => (
          <Link
            href={`/ecosystems/${pack.slug}`}
            key={pack.slug}
            className={`group flex min-h-70 flex-col justify-between rounded-2xl p-6 ${index === 0 ? 'bg-forest text-white' : 'surface'}`}
          >
            <div>
              <Leaf size={29} weight='duotone' className='text-accent' />
              <h2 className='mt-6 text-2xl font-semibold tracking-tight'>{pack.title}</h2>
              <p className={`mt-2 text-sm ${index === 0 ? 'text-white/75' : 'text-muted'}`}>
                {pack.description}
              </p>
            </div>
            <div className='flex items-center justify-between'>
              <span className='text-sm font-semibold'>
                {pack.attempt?.state === 'completed'
                  ? 'Completed'
                  : pack.attempt?.state === 'partial'
                    ? 'Partially completed'
                    : pack.attempt?.state === 'missed'
                      ? "Couldn't complete"
                      : pack.attempt
                        ? `${pack.attempt.matched_units} of ${pack.attempt.total_units} matched`
                        : 'Start challenge'}
              </span>
              <ArrowRight size={20} className='transition-transform group-hover:translate-x-1' />
            </div>
          </Link>
        ))}
      </div>
    </>
  );
}
