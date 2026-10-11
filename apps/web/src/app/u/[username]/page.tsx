'use client';

import { useParams } from 'next/navigation';
import Link from 'next/link';
import useSWR from 'swr';
import { api } from '@/lib/api';
import type { Profile } from '@/lib/types';

export default function PublicProfile() {
  const { username } = useParams<{ username: string }>();
  const { data, error } = useSWR<Profile>(`/users/${username}`, api);
  return (
    <main className='app-width py-8'>
      <Link href='/leaderboard' className='text-sm font-semibold text-accent'>
        Back to leaderboard
      </Link>
      <div className='surface mt-8 max-w-xl p-8'>
        <h1 className='text-3xl font-bold tracking-tight'>
          {data?.username ?? (error ? 'Explorer not found' : 'Loading...')}
        </h1>
        {data ? <p className='mt-3 text-muted'>{data.xp} XP earned</p> : null}
      </div>
    </main>
  );
}
