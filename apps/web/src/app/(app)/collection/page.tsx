'use client';

import Link from 'next/link';
import useSWR from 'swr';
import { api } from '@/lib/api';
import type { Discovery } from '@/lib/types';
import { DiscoveryCard, EmptyState, ErrorNote, PageHeader } from '@/components/ui';

export default function Collection() {
  const { data: verified, error: verifiedError } = useSWR<Discovery[]>('/collection', api);
  const { data: recent, error: recentError } = useSWR<Discovery[]>('/discoveries?limit=100', api);
  const other = recent?.filter((item) => item.status !== 'verified');
  return (
    <>
      <PageHeader
        title='Your collection'
        description='Revisit your finds and follow photos still being identified.'
        action={
          <Link href='/capture' className='button'>
            Add discovery
          </Link>
        }
      />
      {verifiedError || recentError ? (
        <ErrorNote message='Your discoveries could not be loaded. Please try again.' />
      ) : null}
      {!verified && !recent && !verifiedError && !recentError ? (
        <p className='text-sm text-muted'>Loading discoveries…</p>
      ) : null}
      {other?.length ? (
        <section className='mb-9'>
          <h2 className='mb-4 text-xl font-semibold tracking-tight'>Recent submissions</h2>
          <div className='grid gap-4 sm:grid-cols-2 lg:grid-cols-3'>
            {other.map((item) => (
              <DiscoveryCard key={item.id} item={item} />
            ))}
          </div>
        </section>
      ) : null}
      {verified?.length ? (
        <section>
          <h2 className='mb-4 text-xl font-semibold tracking-tight'>Verified discoveries</h2>
          <div className='grid gap-4 sm:grid-cols-2 lg:grid-cols-3'>
            {verified.map((item) => (
              <DiscoveryCard key={item.id} item={item} />
            ))}
          </div>
        </section>
      ) : verified && recent && !other?.length ? (
        <EmptyState
          title='Nothing collected yet'
          detail='Take a clear photo of one living thing. Your submissions will appear here.'
          action={{ href: '/capture', label: 'Open camera' }}
        />
      ) : null}
    </>
  );
}
