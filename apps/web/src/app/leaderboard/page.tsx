'use client';

import Link from 'next/link';
import * as Tabs from '@radix-ui/react-tabs';
import { useState } from 'react';
import useSWR from 'swr';
import { api } from '@/lib/api';
import { EmptyState, ErrorNote, PageHeader } from '@/components/ui';

interface Entry {
  rank: number;
  user_id: string;
  username: string;
  xp: number;
  unique_species: number;
}
interface Board {
  scope: string;
  period: string;
  total: number;
  entries: Entry[];
}

export default function Leaderboard() {
  const [scope, setScope] = useState<'global' | 'friends'>('global');
  const [period, setPeriod] = useState<'weekly' | 'all-time'>('weekly');
  const { data, error } = useSWR<Board>(`/leaderboards?scope=${scope}&period=${period}`, api);
  return (
    <main className='min-h-[100dvh]'>
      <header className='app-width flex h-18 items-center justify-between gap-3'>
        <Link href='/' className='text-2xl font-black tracking-[-.08em]'>
          wildmon<span className='text-accent'>.</span>
        </Link>
        <Link href='/dashboard' className='button-secondary'>
          Explore
        </Link>
      </header>
      <div className='app-width py-10'>
        <PageHeader
          title='Leaderboard'
          description='Verified discoveries and server-awarded XP. Weekly rankings reset on Monday at 00:00 UTC.'
        />
        <div className='mb-6 flex flex-wrap gap-5'>
          <Tabs.Root
            value={scope}
            onValueChange={(value) => setScope(value as 'global' | 'friends')}
          >
            <Tabs.List
              aria-label='Leaderboard scope'
              className='inline-flex rounded-xl border border-line bg-surface p-1'
            >
              <Tabs.Trigger
                value='global'
                className='rounded-lg px-4 py-2 text-sm font-semibold data-[state=active]:bg-surface-alt'
              >
                Global
              </Tabs.Trigger>
              <Tabs.Trigger
                value='friends'
                className='rounded-lg px-4 py-2 text-sm font-semibold data-[state=active]:bg-surface-alt'
              >
                Friends
              </Tabs.Trigger>
            </Tabs.List>
          </Tabs.Root>
          <Tabs.Root
            value={period}
            onValueChange={(value) => setPeriod(value as 'weekly' | 'all-time')}
          >
            <Tabs.List
              aria-label='Leaderboard period'
              className='inline-flex rounded-xl border border-line bg-surface p-1'
            >
              <Tabs.Trigger
                value='weekly'
                className='rounded-lg px-4 py-2 text-sm font-semibold data-[state=active]:bg-surface-alt'
              >
                This week
              </Tabs.Trigger>
              <Tabs.Trigger
                value='all-time'
                className='rounded-lg px-4 py-2 text-sm font-semibold data-[state=active]:bg-surface-alt'
              >
                All time
              </Tabs.Trigger>
            </Tabs.List>
          </Tabs.Root>
        </div>
        <ErrorNote message={error?.message} />
        {data?.entries.length ? (
          <div className='surface overflow-hidden'>
            <div className='grid grid-cols-[3.5rem_1fr_5rem] gap-4 border-b border-line bg-surface-alt px-5 py-3 text-xs font-semibold text-muted sm:grid-cols-[4rem_1fr_7rem_8rem]'>
              <span>Rank</span>
              <span>Explorer</span>
              <span>XP</span>
              <span className='hidden sm:block'>Species</span>
            </div>
            {data.entries.map((entry) => (
              <div
                key={entry.user_id}
                className='grid grid-cols-[3.5rem_1fr_5rem] items-center gap-4 border-b border-line px-5 py-4 last:border-0 sm:grid-cols-[4rem_1fr_7rem_8rem]'
              >
                <span className='font-mono text-sm text-muted'>#{entry.rank}</span>
                <Link href={`/u/${entry.username}`} className='font-semibold hover:text-accent'>
                  {entry.username}
                </Link>
                <strong>{entry.xp}</strong>
                <span className='hidden text-sm text-muted sm:block'>{entry.unique_species}</span>
              </div>
            ))}
          </div>
        ) : data ? (
          <EmptyState
            title='No scores yet'
            detail='Verified discoveries will appear here after explorers opt in.'
          />
        ) : null}
      </div>
    </main>
  );
}
