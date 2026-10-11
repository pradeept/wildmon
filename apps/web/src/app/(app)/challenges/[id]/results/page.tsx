'use client';

import { useParams } from 'next/navigation';
import Link from 'next/link';
import useSWR from 'swr';
import { api } from '@/lib/api';
import type { Challenge, Profile } from '@/lib/types';
import { PageHeader } from '@/components/ui';
import { ShareButton } from '@/components/share-button';

export default function ChallengeResults() {
  const { id } = useParams<{ id: string }>();
  const { data: me } = useSWR<Profile>('/me', api);
  const { data: challenge } = useSWR<Challenge>(`/challenges/${id}`, api, {
    refreshInterval: 5000,
  });
  const result = challenge?.result;
  const mine = challenge?.inviter_id === me?.id ? 0 : 1;
  const headline = !result
    ? 'Checking discoveries'
    : result.winner_id === null
      ? 'It is a draw'
      : result.winner_id === me?.id
        ? 'You won this hunt'
        : 'Your friend won this hunt';
  return (
    <>
      <PageHeader
        title='Challenge results'
        description='The score comes from verified target matches. A photo can fill one target only.'
        action={
          <Link href='/challenges' className='button-secondary'>
            All challenges
          </Link>
        }
      />
      <div className='mx-auto max-w-2xl'>
        <div className='rounded-2xl bg-forest p-8 text-white md:p-10'>
          <h2 className='text-3xl font-semibold tracking-tight'>{headline}</h2>
          <p className='mt-3 text-sm text-white/70'>
            {result
              ? 'A shared clock, two paths through the world.'
              : 'Pending model checks can take a few minutes. This page will update.'}
          </p>
        </div>
        {result ? (
          <>
            <div className='mt-5 grid grid-cols-2 gap-4'>
              <div className='surface p-5'>
                <p className='text-sm text-muted'>Your target points</p>
                <strong className='mt-3 block text-4xl'>{result.scores[mine]}</strong>
                <p className='mt-2 text-xs text-muted'>
                  {Object.keys(result.matches[mine]).length} targets matched
                </p>
              </div>
              <div className='surface p-5'>
                <p className='text-sm text-muted'>Friend’s target points</p>
                <strong className='mt-3 block text-4xl'>{result.scores[1 - mine]}</strong>
                <p className='mt-2 text-xs text-muted'>
                  {Object.keys(result.matches[1 - mine]).length} targets matched
                </p>
              </div>
            </div>
            <div className='mt-5'>
              <ShareButton
                text={`Our Wildmon challenge is complete! We found ${Object.keys(result.matches[0]).length + Object.keys(result.matches[1]).length} verified targets together.`}
              />
            </div>
          </>
        ) : null}
      </div>
    </>
  );
}
