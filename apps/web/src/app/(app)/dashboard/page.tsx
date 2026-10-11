'use client';

import Link from 'next/link';
import { ArrowRight, Camera, Clock, Leaf, Trophy } from '@phosphor-icons/react';
import useSWR from 'swr';
import { api } from '@/lib/api';
import type { Discovery, Pack, Profile } from '@/lib/types';
import { DiscoveryCard, EmptyState, PageHeader } from '@/components/ui';

export default function Dashboard() {
  const { data: me } = useSWR<Profile>('/me', api);
  const { data: discoveries } = useSWR<Discovery[]>('/discoveries?limit=6', api, {
    refreshInterval: (items) =>
      items?.some((item) => item.status === 'queued' || item.status === 'processing') ? 5000 : 0,
  });
  const { data: packs } = useSWR<Pack[]>('/ecosystems', api);
  return (
    <>
      <PageHeader
        title={me ? `Hello, ${me.username}.` : 'Your wild world'}
        description='There is more life nearby than you think. Head out, take one photo, and see what you find.'
      />
      <div className='grid gap-4 lg:grid-cols-[1.2fr_.8fr]'>
        <Link
          href='/capture'
          className='group relative flex min-h-60 flex-col justify-between overflow-hidden rounded-2xl bg-forest p-7 text-white'
        >
          <div className='absolute -top-30 -right-20 h-80 w-80 rounded-full border border-white/20 bg-white/5' />
          <Camera size={29} weight='duotone' className='relative text-[#ff9975]' />
          <div className='relative'>
            <h2 className='text-3xl font-semibold tracking-tight'>Catch a discovery</h2>
            <p className='mt-2 max-w-sm text-sm text-white/75'>
              One photo, one closer look. No timer needed.
            </p>
          </div>
          <ArrowRight
            size={23}
            className='relative self-end transition-transform group-hover:translate-x-1'
          />
        </Link>
        <div className='grid gap-4 sm:grid-cols-2 lg:grid-cols-1'>
          <Link
            href='/hunts'
            className='surface flex items-center justify-between gap-4 p-6 transition-colors hover:bg-surface-alt'
          >
            <div>
              <Clock size={25} className='text-accent' />
              <h2 className='mt-3 text-lg font-semibold'>Timed hunt</h2>
              <p className='mt-1 text-sm text-muted'>A focused walk, your pace.</p>
            </div>
            <ArrowRight size={21} />
          </Link>
          <Link
            href='/challenges'
            className='surface flex items-center justify-between gap-4 p-6 transition-colors hover:bg-surface-alt'
          >
            <div>
              <Trophy size={25} className='text-accent' />
              <h2 className='mt-3 text-lg font-semibold'>Challenge a friend</h2>
              <p className='mt-1 text-sm text-muted'>Same targets. Shared start.</p>
            </div>
            <ArrowRight size={21} />
          </Link>
        </div>
      </div>
      <div className='mt-10 grid gap-8 xl:grid-cols-[1.4fr_.6fr]'>
        <section>
          <div className='mb-4 flex items-center justify-between'>
            <h2 className='text-xl font-semibold tracking-tight'>Recent discoveries</h2>
            <Link href='/collection' className='text-sm font-semibold text-accent'>
              View collection
            </Link>
          </div>
          {discoveries?.length ? (
            <div className='grid gap-4 sm:grid-cols-2 lg:grid-cols-3'>
              {discoveries.map((item) => (
                <DiscoveryCard key={item.id} item={item} />
              ))}
            </div>
          ) : (
            <EmptyState
              title='Your collection starts here'
              detail='Take a clear photo of one plant, bird, or insect to begin.'
              action={{ href: '/capture', label: 'Open camera' }}
            />
          )}
        </section>
        <section>
          <div className='mb-4 flex items-center justify-between'>
            <h2 className='text-xl font-semibold tracking-tight'>Ecosystems</h2>
            <Leaf size={20} className='text-accent' />
          </div>
          <div className='surface divide-y divide-line overflow-hidden'>
            {packs?.map((pack) => (
              <Link
                key={pack.slug}
                href={`/ecosystems/${pack.slug}`}
                className='flex items-center justify-between gap-3 p-5 hover:bg-surface-alt'
              >
                <div>
                  <h3 className='font-semibold'>{pack.title}</h3>
                  <p className='mt-1 text-xs text-muted'>
                    {pack.progress?.state === 'completed'
                      ? 'Completed'
                      : pack.progress
                        ? `${Object.keys(pack.progress.assignments).length} of ${pack.slots.reduce((sum, slot) => sum + slot.count, 0)} found`
                        : 'Ready to join'}
                  </p>
                </div>
                <ArrowRight size={18} />
              </Link>
            ))}
          </div>
        </section>
      </div>
    </>
  );
}
