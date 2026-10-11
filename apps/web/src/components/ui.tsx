import Link from 'next/link';
import type { ReactNode } from 'react';
import type { Discovery } from '@/lib/types';
import { discoveryStatusLabel, discoveryTitle } from '@/lib/discovery-display';

export function PageHeader({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className='mb-7 flex flex-wrap items-end justify-between gap-4'>
      <div>
        <h1 className='text-3xl font-bold tracking-[-.055em] md:text-4xl'>{title}</h1>
        {description ? (
          <p className='mt-2 max-w-2xl text-sm leading-relaxed text-muted md:text-base'>
            {description}
          </p>
        ) : null}
      </div>
      {action}
    </div>
  );
}

export function EmptyState({
  title,
  detail,
  action,
}: {
  title: string;
  detail: string;
  action?: { href: string; label: string };
}) {
  return (
    <div className='surface flex min-h-56 flex-col items-center justify-center px-6 py-10 text-center'>
      <h2 className='text-lg font-semibold'>{title}</h2>
      <p className='mt-2 max-w-sm text-sm text-muted'>{detail}</p>
      {action ? (
        <Link href={action.href} className='button mt-5'>
          {action.label}
        </Link>
      ) : null}
    </div>
  );
}

export function ErrorNote({ message }: { message?: string }) {
  return message ? (
    <p
      role='alert'
      className='rounded-xl border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-900 dark:border-red-700 dark:bg-red-950 dark:text-red-100'
    >
      {message}
    </p>
  ) : null;
}

export function DiscoveryCard({ item }: { item: Discovery }) {
  return (
    <Link
      href={`/discoveries/${item.id}`}
      aria-label={`Open discovery: ${discoveryTitle(item)}`}
      className='surface group block overflow-hidden transition-transform hover:-translate-y-0.5 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent'
    >
      {item.image_url ? (
        <div className='aspect-[4/3] overflow-hidden bg-surface-alt'>
          <img
            src={item.image_url}
            alt={
              item.common_name
                ? `Photograph identified as ${item.common_name}`
                : 'Submitted nature photograph'
            }
            loading='lazy'
            className='h-full w-full object-cover transition-transform duration-300 group-hover:scale-[1.03]'
          />
        </div>
      ) : null}
      <div className='p-4'>
        <div className='flex items-start justify-between gap-3'>
          <div>
            <h3 className='font-semibold'>{discoveryTitle(item)}</h3>
            <p className='mt-1 text-xs text-muted'>
              {item.scientific_name ?? new Date(item.created_at).toLocaleDateString()}
            </p>
          </div>
          <span className='status'>{discoveryStatusLabel(item.status)}</span>
        </div>
        {item.uncertainty ? <p className='mt-3 text-sm text-muted'>{item.uncertainty}</p> : null}
        {item.guidance ? <p className='mt-3 text-sm text-muted'>{item.guidance}</p> : null}
        {item.xp_awarded > 0 ? (
          <p className='mt-3 text-sm font-semibold text-accent'>+{item.xp_awarded} XP</p>
        ) : null}
        <p className='mt-4 text-sm font-semibold text-accent'>Open discovery →</p>
      </div>
    </Link>
  );
}
