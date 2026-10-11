'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useState, type FormEvent } from 'react';
import { post } from '@/lib/api';
import { ErrorNote } from '@/components/ui';

export default function Register() {
  const router = useRouter();
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError('');
    const data = new FormData(event.currentTarget);
    try {
      await post('/auth/register', {
        username: data.get('username'),
        email: data.get('email'),
        password: data.get('password'),
      });
      router.push('/dashboard');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not create account.');
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className='grid min-h-[100dvh] place-items-center px-4 py-10'>
      <div className='w-full max-w-md'>
        <Link href='/' className='text-2xl font-black tracking-[-.08em]'>
          wildmon<span className='text-accent'>.</span>
        </Link>
        <div className='surface mt-7 p-7 md:p-9'>
          <h1 className='text-3xl font-bold tracking-tight'>Become an explorer</h1>
          <p className='mt-2 text-sm text-muted'>Find something wonderful near you.</p>
          <form onSubmit={submit} className='mt-7 grid gap-5'>
            <div>
              <label htmlFor='username' className='label'>
                Username
              </label>
              <input
                id='username'
                name='username'
                minLength={3}
                maxLength={24}
                pattern='[A-Za-z0-9_]+'
                autoComplete='username'
                required
                className='field'
              />
              <p className='mt-1 text-xs text-muted'>Letters, numbers, and underscores.</p>
            </div>
            <div>
              <label htmlFor='email' className='label'>
                Email
              </label>
              <input
                id='email'
                name='email'
                type='email'
                autoComplete='email'
                required
                className='field'
              />
            </div>
            <div>
              <label htmlFor='password' className='label'>
                Password
              </label>
              <input
                id='password'
                name='password'
                type='password'
                minLength={10}
                autoComplete='new-password'
                required
                className='field'
              />
              <p className='mt-1 text-xs text-muted'>Use at least 10 characters.</p>
            </div>
            <ErrorNote message={error} />
            <button className='button w-full' disabled={busy}>
              {busy ? 'Creating account...' : 'Create account'}
            </button>
          </form>
          <p className='mt-6 text-sm text-muted'>
            Already exploring?{' '}
            <Link href='/login' className='font-semibold text-accent underline underline-offset-4'>
              Log in
            </Link>
          </p>
        </div>
      </div>
    </main>
  );
}
