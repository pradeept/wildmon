'use client';

import { useState, type FormEvent } from 'react';
import useSWR from 'swr';
import { api, post } from '@/lib/api';
import { EmptyState, ErrorNote, PageHeader } from '@/components/ui';

interface Friend {
  id: string;
  user_id: string;
  username: string;
  status: string;
  requested_by_me: boolean;
}

export default function Friends() {
  const { data, mutate } = useSWR<Friend[]>('/friends', api);
  const [username, setUsername] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  async function invite(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');
    try {
      await post('/friends/requests', { username });
      setUsername('');
      setMessage('Request sent.');
      await mutate();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not send request.');
    }
  }
  async function resolve(id: string, action: 'accept' | 'reject') {
    try {
      await post(`/friends/requests/${id}/${action}`);
      await mutate();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not update request.');
    }
  }
  return (
    <>
      <PageHeader
        title='Friends'
        description='Explore together. Friend challenges are only available after both people connect.'
      />
      <div className='grid gap-7 lg:grid-cols-[.8fr_1.2fr]'>
        <form onSubmit={invite} className='surface h-fit p-6'>
          <h2 className='text-xl font-semibold'>Find an explorer</h2>
          <p className='mt-2 text-sm text-muted'>Enter their Wildmon username to send a request.</p>
          <label htmlFor='friend-name' className='label mt-6'>
            Username
          </label>
          <input
            id='friend-name'
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            className='field'
            required
          />
          <button className='button mt-4 w-full'>Send request</button>
          {message ? <p className='mt-3 text-sm text-muted'>{message}</p> : null}
          <div className='mt-3'>
            <ErrorNote message={error} />
          </div>
        </form>
        <section>
          <h2 className='mb-4 text-xl font-semibold'>Your connections</h2>
          {data?.length ? (
            <div className='surface divide-y divide-line'>
              {data.map((friend) => (
                <div
                  key={friend.id}
                  className='flex flex-wrap items-center justify-between gap-4 p-5'
                >
                  <div>
                    <h3 className='font-semibold'>{friend.username}</h3>
                    <p className='mt-1 text-xs text-muted'>
                      {friend.status === 'accepted'
                        ? 'Connected'
                        : friend.requested_by_me
                          ? 'Request sent'
                          : 'Wants to connect'}
                    </p>
                  </div>
                  {friend.status === 'pending' && !friend.requested_by_me ? (
                    <div className='flex gap-2'>
                      <button onClick={() => resolve(friend.id, 'accept')} className='button'>
                        Accept
                      </button>
                      <button
                        onClick={() => resolve(friend.id, 'reject')}
                        className='button-secondary'
                      >
                        Decline
                      </button>
                    </div>
                  ) : null}
                </div>
              ))}
            </div>
          ) : (
            <EmptyState
              title='No friends yet'
              detail='Send a request using a friend’s username to start exploring together.'
            />
          )}
        </section>
      </div>
    </>
  );
}
