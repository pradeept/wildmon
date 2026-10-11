'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { Binoculars, Camera, Leaf, Medal, Trophy, UserCircle, Users } from '@phosphor-icons/react';
import useSWR from 'swr';
import { api } from '@/lib/api';
import type { Profile } from '@/lib/types';
import { useEffect, type ReactNode } from 'react';
import { ErrorNote } from '@/components/ui';

const links = [
  { href: '/dashboard', label: 'Explore', icon: Binoculars },
  { href: '/collection', label: 'Collection', icon: Leaf },
  { href: '/challenges', label: 'Challenges', icon: Medal },
  { href: '/leaderboard', label: 'Leaderboard', icon: Trophy },
  { href: '/friends', label: 'Friends', icon: Users },
];
const mobileLinks = [
  ...links.slice(0, 4),
  { href: '/settings', label: 'Profile', icon: UserCircle },
];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { data: me, error } = useSWR<Profile>('/me', api);

  useEffect(() => {
    if (error?.status === 401) router.replace('/login');
  }, [error, router]);

  if (error && error.status !== 401)
    return (
      <div className='app-width py-12'>
        <ErrorNote message={error.message} />
      </div>
    );
  if (!me)
    return (
      <div className='app-width py-12'>
        <div className='surface h-36 animate-pulse bg-surface-alt' />
        <span className='sr-only'>Loading Wildmon</span>
      </div>
    );

  return (
    <div className='min-h-[100dvh] lg:grid lg:grid-cols-[250px_minmax(0,1fr)]'>
      <aside className='hidden min-h-[100dvh] flex-col bg-forest px-6 py-7 text-white lg:flex'>
        <Link href='/dashboard' className='text-3xl font-black tracking-[-.08em]'>
          wildmon<span className='text-[#ff9370]'>.</span>
        </Link>
        <p className='mt-2 text-xs text-white/65'>Your outdoor world, collected.</p>
        <nav className='mt-12 grid gap-1'>
          {links.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              aria-current={pathname.startsWith(href) ? 'page' : undefined}
              className={`flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-semibold transition-colors ${pathname.startsWith(href) ? 'bg-white/16 text-white' : 'text-white/70 hover:bg-white/10 hover:text-white'}`}
            >
              <Icon size={21} weight={pathname.startsWith(href) ? 'fill' : 'regular'} />
              {label}
            </Link>
          ))}
        </nav>
        <Link
          href='/badges'
          className='mt-2 flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-semibold text-white/70 hover:bg-white/10 hover:text-white'
        >
          <Medal size={21} /> Badges
        </Link>
        <Link href='/capture' className='button mt-8 w-full'>
          <Camera size={19} weight='bold' /> Quick capture
        </Link>
        <Link
          href='/settings'
          className='mt-auto flex items-center gap-3 rounded-xl px-4 py-3 text-sm text-white/75 hover:bg-white/10'
        >
          <UserCircle size={21} /> {me.username}
        </Link>
      </aside>
      <div className='min-w-0 pb-22 lg:pb-0'>
        <header className='flex h-17 items-center justify-between border-b border-line bg-surface px-5 lg:px-10'>
          <Link
            href='/dashboard'
            className='text-2xl font-black tracking-[-.08em] text-forest dark:text-ink lg:hidden'
          >
            wildmon<span className='text-accent'>.</span>
          </Link>
          <span className='hidden text-sm font-medium text-muted lg:block'>
            Go outside. Come back with a story.
          </span>
          <div className='flex items-center gap-3'>
            <span className='status'>+ {me.xp} XP</span>
            <Link
              href='/settings'
              aria-label='Profile settings'
              className='rounded-full p-1 hover:bg-surface-alt'
            >
              <UserCircle size={28} />
            </Link>
          </div>
        </header>
        <main className='mx-auto w-full max-w-6xl px-5 py-7 md:px-10 md:py-10'>{children}</main>
      </div>
      <nav className='fixed right-0 bottom-0 left-0 z-20 grid h-18 grid-cols-5 border-t border-line bg-surface/95 backdrop-blur-sm lg:hidden'>
        {mobileLinks.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            aria-current={pathname.startsWith(href) ? 'page' : undefined}
            className={`flex flex-col items-center justify-center gap-1 text-[10px] font-semibold ${pathname.startsWith(href) ? 'text-accent' : 'text-muted'}`}
          >
            <Icon size={23} weight={pathname.startsWith(href) ? 'fill' : 'regular'} />
            {label}
          </Link>
        ))}
      </nav>
      <Link
        href='/capture'
        aria-label='Quick capture'
        className='button fixed right-5 bottom-22 z-20 h-14 w-14 rounded-full p-0 shadow-[0_10px_28px_rgba(89,40,22,.23)] lg:hidden'
      >
        <Camera size={25} weight='bold' />
      </Link>
    </div>
  );
}
