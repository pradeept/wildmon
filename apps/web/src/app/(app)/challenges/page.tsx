'use client';

import Link from 'next/link';
import { ArrowRight, Trophy } from '@phosphor-icons/react';
import useSWR from 'swr';
import { api } from '@/lib/api';
import type { Challenge } from '@/lib/types';
import { EmptyState, PageHeader } from '@/components/ui';

export default function Challenges() {
  const { data } = useSWR<Challenge[]>('/challenges', api, { refreshInterval: 5000 });
  return (
    <>
      <PageHeader
        title='Friend challenges'
        description='Go after the same targets with a shared clock. Both explorers must be ready before the hunt begins.'
        action={
          <Link href='/challenges/new' className='button'>
            Create challenge
          </Link>
        }
      />
      {data?.length ? (
        <div className='grid gap-4 md:grid-cols-2'>
          {data.map((challenge) => (
            <Link
              key={challenge.id}
              href={`/challenges/${challenge.id}`}
              className='surface group flex min-h-45 flex-col justify-between p-6 hover:bg-surface-alt'
            >
              <div className='flex items-start justify-between gap-4'>
                <Trophy size={27} weight='duotone' className='text-accent' />
                <span className='status'>{challenge.state.replace('_', ' ')}</span>
              </div>
              <div>
                <h2 className='text-xl font-semibold'>
                  {challenge.requirements.length} targets to find
                </h2>
                <p className='mt-1 text-sm text-muted'>
                  {challenge.duration_minutes} minute shared hunt
                </p>
              </div>
              <ArrowRight
                size={20}
                className='self-end transition-transform group-hover:translate-x-1'
              />
            </Link>
          ))}
        </div>
      ) : (
        <EmptyState
          title='No challenges yet'
          detail='Connect with a friend, choose targets, and start exploring together.'
          action={{ href: '/challenges/new', label: 'Create challenge' }}
        />
      )}
    </>
  );
}
