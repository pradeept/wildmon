'use client';

import useSWR from 'swr';
import { Medal } from '@phosphor-icons/react';
import { api } from '@/lib/api';
import { PageHeader } from '@/components/ui';

interface Badge {
  code: string;
  title: string;
}
interface Earned {
  code: string;
  earned_at: string;
}

export default function Badges() {
  const { data: badges } = useSWR<Badge[]>('/badges', api);
  const { data: earned } = useSWR<Earned[]>('/me/badges', api);
  const earnedCodes = new Set(earned?.map((item) => item.code) ?? []);
  return (
    <>
      <PageHeader
        title='Badges'
        description='Small markers of the places you have noticed and the walks you have shared.'
      />
      <div className='grid gap-4 sm:grid-cols-2 lg:grid-cols-3'>
        {badges?.map((badge) => (
          <div
            key={badge.code}
            className={`surface p-6 ${earnedCodes.has(badge.code) ? '' : 'opacity-60'}`}
          >
            <Medal
              size={29}
              weight={earnedCodes.has(badge.code) ? 'fill' : 'regular'}
              className='text-accent'
            />
            <h2 className='mt-5 text-lg font-semibold'>{badge.title}</h2>
            <p className='mt-1 text-sm text-muted'>
              {earnedCodes.has(badge.code) ? 'Earned' : 'Still to discover'}
            </p>
          </div>
        ))}
      </div>
    </>
  );
}
