import Image from 'next/image';
import Link from 'next/link';
import { ArrowRight, Camera, Compass, Leaf, Trophy } from '@phosphor-icons/react/ssr';

export default function Home() {
  return (
    <main>
      <header className='app-width flex h-18 items-center justify-between gap-4'>
        <Link href='/' className='text-2xl font-black tracking-[-.08em] text-forest dark:text-ink'>
          wildmon<span className='text-accent'>.</span>
        </Link>
        <nav className='flex items-center gap-3 text-sm font-semibold'>
          <Link
            href='/leaderboard'
            className='hidden rounded-lg px-3 py-2 hover:bg-surface-alt sm:block'
          >
            Leaderboard
          </Link>
          <Link href='/login' className='rounded-lg px-3 py-2 hover:bg-surface-alt'>
            Log in
          </Link>
          <Link href='/register' className='button'>
            Start exploring <ArrowRight size={16} weight='bold' />
          </Link>
        </nav>
      </header>

      <section className='app-width grid min-h-[min(760px,calc(100dvh-72px))] items-center gap-8 py-6 md:grid-cols-[.92fr_1.08fr] md:gap-10'>
        <div className='max-w-xl py-8 md:py-12'>
          <div className='mb-8 inline-flex items-center gap-2 rounded-full border border-line bg-surface px-3 py-1.5 text-sm font-semibold text-muted'>
            <Leaf size={18} className='text-accent' /> Your world is alive
          </div>
          <h1 className='text-[clamp(3.25rem,6.4vw,6.5rem)] leading-[.98] font-bold tracking-[-.075em] text-forest dark:text-ink'>
            Step out.
            <br />
            <span className='text-accent'>Look closer.</span>
          </h1>
          <p className='mt-7 max-w-md text-lg leading-relaxed text-muted'>
            Photograph wildlife, build your collection, and challenge friends to discover more
            outside.
          </p>
          <div className='mt-9 flex flex-wrap gap-3'>
            <Link href='/register' className='button px-5 py-3.5'>
              Start exploring <ArrowRight size={18} weight='bold' />
            </Link>
            <Link href='/login' className='button-secondary px-5 py-3.5'>
              I have an account
            </Link>
          </div>
        </div>
        <div className='relative min-h-[360px] overflow-hidden rounded-[22px] bg-forest md:min-h-[580px]'>
          <Image
            src='/wildmon-hero.jpg'
            alt='Orange butterfly resting on white flowers among sunlit leaves'
            fill
            priority
            sizes='(max-width: 768px) 100vw, 55vw'
            className='object-cover'
          />
          <div className='absolute inset-0 bg-gradient-to-t from-[#103b2a]/55 via-transparent to-transparent' />
          <div className='absolute right-6 bottom-6 left-6 flex items-end justify-between text-white'>
            <p className='max-w-[16rem] text-2xl leading-tight font-semibold tracking-tight'>
              A tiny adventure is waiting right outside.
            </p>
            <span className='flex h-11 w-11 items-center justify-center rounded-full border border-white/50 bg-white/20 backdrop-blur-sm'>
              <Compass size={22} />
            </span>
          </div>
        </div>
      </section>

      <section className='app-width grid gap-0 border-t border-line py-10 md:grid-cols-[1.15fr_.85fr]'>
        {[
          {
            icon: Camera,
            title: 'Catch a moment',
            copy: 'One photo starts a discovery. Keep the interaction short and return to the outdoors.',
          },
          {
            icon: Leaf,
            title: 'Grow a collection',
            copy: 'Verified finds fill your personal collection and persistent ecosystem checklists.',
          },
          {
            icon: Trophy,
            title: 'Explore together',
            copy: 'Invite a friend to a timed hunt with the same targets and a fair shared clock.',
          },
        ].map(({ icon: Icon, title, copy }) => (
          <div
            key={title}
            className='border-b border-line py-7 md:px-7 first:md:row-span-2 first:md:border-r first:md:pl-0 last:border-b-0'
          >
            <Icon size={27} weight='duotone' className='mb-5 text-accent' />
            <h2 className='text-xl font-semibold tracking-tight'>{title}</h2>
            <p className='mt-2 max-w-sm text-sm leading-relaxed text-muted'>{copy}</p>
          </div>
        ))}
      </section>
      <footer className='app-width flex flex-wrap justify-between gap-3 border-t border-line py-7 text-sm text-muted'>
        <span>Wildmon. Photograph respectfully and leave wildlife undisturbed.</span>
        <span>Find more outside.</span>
      </footer>
    </main>
  );
}
