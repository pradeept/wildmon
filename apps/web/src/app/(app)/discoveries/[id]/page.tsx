'use client';

import { useParams } from 'next/navigation';
import Link from 'next/link';
import useSWR from 'swr';
import { ArrowLeft, ArrowUpRight } from '@phosphor-icons/react';
import { api } from '@/lib/api';
import { discoveryStatusLabel, discoveryTitle } from '@/lib/discovery-display';
import type { Discovery } from '@/lib/types';
import { ErrorNote, PageHeader } from '@/components/ui';
import { RetryDiscoveryButton } from '@/components/retry-discovery-button';

export default function DiscoveryPage() {
  const { id } = useParams<{ id: string }>();
  const {
    data: item,
    error,
    mutate,
  } = useSWR<Discovery>(`/discoveries/${id}`, api, {
    refreshInterval: (discovery) =>
      discovery && ['queued', 'processing'].includes(discovery.status) ? 3000 : 0,
  });
  const name = item ? discoveryTitle(item) : 'Your discovery';

  return (
    <>
      <PageHeader
        title={name}
        description='A closer look at this moment outside.'
        action={
          <Link href='/collection' className='button-secondary'>
            <ArrowLeft size={17} /> Collection
          </Link>
        }
      />
      {error ? <ErrorNote message='This discovery could not be loaded.' /> : null}
      {!item && !error ? <p className='text-sm text-muted'>Loading discovery…</p> : null}
      {item ? (
        <div className='grid gap-6 lg:grid-cols-[minmax(0,1.25fr)_minmax(20rem,.75fr)]'>
          <div className='surface overflow-hidden'>
            {item.image_url ? (
              <img
                src={item.image_url}
                alt={item.common_name ? `Photograph of ${item.common_name}` : 'Nature photograph'}
                className='max-h-[70vh] w-full bg-surface-alt object-contain'
              />
            ) : (
              <div className='grid min-h-80 place-items-center bg-surface-alt text-sm text-muted'>
                Photo unavailable
              </div>
            )}
          </div>
          <div className='self-start surface p-6 md:p-8'>
            <span className='status'>{discoveryStatusLabel(item.status)}</span>
            <h2 className='mt-5 text-2xl font-semibold tracking-tight'>{name}</h2>
            {item.scientific_name ? (
              <p className='mt-1 text-sm italic text-muted'>{item.scientific_name}</p>
            ) : null}
            <p className='mt-5 text-sm text-muted'>
              Captured {new Date(item.created_at).toLocaleString()}
            </p>
            {item.category ? (
              <p className='mt-3 text-sm text-muted'>Category: {item.category.replace('_', ' ')}</p>
            ) : null}
            {item.ecosystem_name && item.ecosystem_slug ? (
              <Link
                href={`/ecosystems/${item.ecosystem_slug}`}
                className='mt-3 inline-block text-sm font-semibold text-accent'
              >
                {item.ecosystem_name} <ArrowUpRight size={15} className='inline' />
              </Link>
            ) : null}
            {item.uncertainty ? (
              <div className='mt-6 rounded-xl bg-surface-alt p-4'>
                <h3 className='text-sm font-semibold'>Identification note</h3>
                <p className='mt-1 text-sm leading-relaxed text-muted'>{item.uncertainty}</p>
              </div>
            ) : null}
            {item.guidance ? (
              <p className='mt-5 text-sm leading-relaxed text-muted'>{item.guidance}</p>
            ) : null}
            {['queued', 'processing'].includes(item.status) ? (
              <p className='mt-5 text-sm text-muted'>
                Identification is running. This page updates automatically.
              </p>
            ) : null}
            {item.status === 'needs_review' && !item.uncertainty ? (
              <p className='mt-5 text-sm leading-relaxed text-muted'>
                The photo did not support a confident identification. Try a clearer view of one
                subject.
              </p>
            ) : null}
            {item.status === 'failed' ? (
              <RetryDiscoveryButton id={item.id} onRetried={(updated) => void mutate(updated)} />
            ) : null}
            {item.xp_awarded > 0 ? (
              <p className='mt-6 text-lg font-semibold text-accent'>+{item.xp_awarded} XP</p>
            ) : null}
            {item.session_id ? (
              <Link
                href={`/hunts/${item.session_id}/summary`}
                className='button-secondary mt-7 w-full'
              >
                View hunt summary <ArrowUpRight size={18} />
              </Link>
            ) : null}
          </div>
        </div>
      ) : null}
    </>
  );
}
