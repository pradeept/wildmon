'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useState, type FormEvent } from 'react';
import { post } from '@/lib/api';
import { ErrorNote } from '@/components/ui';

export default function Login() {
  const router = useRouter();
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError('');
    const data = new FormData(event.currentTarget);
    try {
      await post('/auth/login', { email: data.get('email'), password: data.get('password') });
      router.push('/dashboard');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not log in.');
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
          <h1 className='text-3xl font-bold tracking-tight'>Welcome back</h1>
          <p className='mt-2 text-sm text-muted'>Your next discovery starts outside.</p>
          <form onSubmit={submit} className='mt-7 grid gap-5'>
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
                autoComplete='current-password'
                required
                className='field'
              />
            </div>
            <ErrorNote message={error} />
            <button className='button w-full' disabled={busy}>
              {busy ? 'Logging in...' : 'Log in'}
            </button>
          </form>
          <p className='mt-6 text-sm text-muted'>
            New here?{' '}
            <Link
              href='/register'
              className='font-semibold text-accent underline underline-offset-4'
            >
              Create an account
            </Link>
          </p>
        </div>
      </div>
    </main>
  );
}
