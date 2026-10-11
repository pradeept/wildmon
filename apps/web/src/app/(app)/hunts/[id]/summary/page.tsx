'use client';

import { useParams } from 'next/navigation';
import Link from 'next/link';
import useSWR from 'swr';
import { api } from '@/lib/api';
import type { Discovery, Hunt } from '@/lib/types';
import { DiscoveryCard, EmptyState, PageHeader } from '@/components/ui';
import { ShareButton } from '@/components/share-button';

interface Summary extends Hunt {
  pending: boolean;
  estimated_in_app_focus_seconds: number;
  discoveries: Discovery[];
  xp_awarded: number;
}

export default function HuntSummary() {
  const { id } = useParams<{ id: string }>();
  const { data } = useSWR<Summary>(`/hunts/${id}/summary`, api, {
    refreshInterval: (summary) => (summary?.pending ? 4000 : 0),
  });
  return (
    <>
      <PageHeader
        title='Hunt summary'
        description={
          data?.pending
            ? 'Some photographs are still being identified. This page will update.'
            : 'Take a look at what you noticed.'
        }
        action={
          <Link href='/dashboard' className='button-secondary'>
            Explore dashboard
          </Link>
        }
      />
      <div className='mb-8 grid gap-3 sm:grid-cols-3'>
        <div className='surface p-5'>
          <span className='text-sm text-muted'>Discoveries</span>
          <strong className='mt-2 block text-3xl'>{data?.discoveries.length ?? '...'}</strong>
        </div>
        <div className='surface p-5'>
          <span className='text-sm text-muted'>Discovery XP</span>
          <strong className='mt-2 block text-3xl'>{data?.xp_awarded ?? '...'}</strong>
        </div>
        <div className='surface p-5'>
          <span className='text-sm text-muted'>Estimated in-app focus</span>
          <strong className='mt-2 block text-3xl'>
            {data ? `${Math.floor(data.estimated_in_app_focus_seconds / 60)} min` : '...'}
          </strong>
        </div>
      </div>
      {data && !data.pending ? (
        <div className='mb-7'>
          <ShareButton
            text={`I found ${data.discoveries.filter((item) => item.status === 'verified').length} verified nature discoveries on my Wildmon hunt!`}
          />
        </div>
      ) : null}
      {data?.discoveries.length ? (
        <div className='grid gap-4 sm:grid-cols-2 lg:grid-cols-3'>
          {data.discoveries.map((item) => (
            <DiscoveryCard key={item.id} item={item} />
          ))}
        </div>
      ) : (
        <EmptyState
          title='No photos yet'
          detail='Your discoveries will appear here after you submit them.'
        />
      )}
    </>
  );
}
