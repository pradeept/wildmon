'use client';

import Link from 'next/link';
import useSWR from 'swr';
import { api } from '@/lib/api';
import type { Discovery } from '@/lib/types';
import { DiscoveryCard, EmptyState, PageHeader } from '@/components/ui';

export default function Collection() {
  const { data } = useSWR<Discovery[]>('/collection', api);
  return (
    <>
      <PageHeader
        title='Your collection'
        description='Every verified discovery is a closer look at the living world.'
        action={
          <Link href='/capture' className='button'>
            Add discovery
          </Link>
        }
      />
      {data?.length ? (
        <div className='grid gap-4 sm:grid-cols-2 lg:grid-cols-3'>
          {data.map((item) => (
            <DiscoveryCard key={item.id} item={item} />
          ))}
        </div>
      ) : (
        <EmptyState
          title='Nothing collected yet'
          detail='Take a clear photo of one living thing. Verified results appear here.'
          action={{ href: '/capture', label: 'Open camera' }}
        />
      )}
    </>
  );
}
