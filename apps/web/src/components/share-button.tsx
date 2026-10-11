'use client';

import { useState } from 'react';
import { ShareNetwork } from '@phosphor-icons/react';

export function ShareButton({ text }: { text: string }) {
  const [message, setMessage] = useState('');
  async function share() {
    try {
      if (navigator.share) await navigator.share({ title: 'Wildmon', text });
      else {
        await navigator.clipboard.writeText(text);
        setMessage('Summary copied.');
      }
    } catch {
      setMessage('Sharing is unavailable here.');
    }
  }
  return (
    <div className='flex items-center gap-3'>
      <button type='button' onClick={share} className='button-secondary'>
        <ShareNetwork size={18} /> Share summary
      </button>
      {message ? (
        <span role='status' className='text-sm text-muted'>
          {message}
        </span>
      ) : null}
    </div>
  );
}
