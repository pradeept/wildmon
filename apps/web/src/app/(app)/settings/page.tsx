'use client';

import { useRouter } from 'next/navigation';
import useSWR from 'swr';
import { api, post } from '@/lib/api';
import type { Profile } from '@/lib/types';
import { PageHeader } from '@/components/ui';

export default function Settings() {
  const router = useRouter();
  const { data: me, mutate } = useSWR<Profile>('/me', api);
  async function toggle() {
    await api('/me', {
      method: 'PATCH',
      body: JSON.stringify({ public_leaderboard: !me?.public_leaderboard }),
    });
    await mutate();
  }
  async function logout() {
    await post('/auth/logout');
    router.push('/');
  }
  return (
    <>
      <PageHeader
        title='Settings'
        description='Choose how your explorer profile appears in the community.'
      />
      <div className='max-w-2xl space-y-4'>
        <div className='surface flex items-center justify-between gap-5 p-6'>
          <div>
            <h2 className='font-semibold'>Global leaderboard</h2>
            <p className='mt-1 text-sm text-muted'>
              Show your username and XP in global rankings. Your photos and exact location stay
              private.
            </p>
          </div>
          <button
            role='switch'
            aria-checked={Boolean(me?.public_leaderboard)}
            aria-label='Global leaderboard visibility'
            onClick={toggle}
            className={`relative h-8 w-14 shrink-0 rounded-full ${me?.public_leaderboard ? 'bg-accent' : 'bg-surface-alt'}`}
          >
            <span
              className={`absolute top-1 left-1 h-6 w-6 rounded-full bg-white transition-transform ${me?.public_leaderboard ? 'translate-x-6' : ''}`}
            />
          </button>
        </div>
        <button onClick={logout} className='button-secondary'>
          Log out
        </button>
      </div>
    </>
  );
}
