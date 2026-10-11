'use client';

import { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import * as Dialog from '@radix-ui/react-dialog';
import { Camera, ImageSquare, X } from '@phosphor-icons/react';
import { api, post } from '@/lib/api';
import { createClientId } from '@/lib/client-id';
import type { Discovery } from '@/lib/types';
import { DiscoveryCard, ErrorNote, PageHeader } from '@/components/ui';

type UploadSign = { key: string; upload_url: string; method: 'PUT' };

async function prepareImage(file: File): Promise<File> {
  const image = new Image();
  const url = URL.createObjectURL(file);
  try {
    await new Promise<void>((resolve, reject) => {
      image.onload = () => resolve();
      image.onerror = () => reject(new Error('Could not read this photo.'));
      image.src = url;
    });
    const scale = Math.min(1, 1600 / Math.max(image.width, image.height));
    const canvas = document.createElement('canvas');
    canvas.width = Math.round(image.width * scale);
    canvas.height = Math.round(image.height * scale);
    canvas.getContext('2d')?.drawImage(image, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise<Blob>((resolve, reject) =>
      canvas.toBlob(
        (value) => (value ? resolve(value) : reject(new Error('Could not prepare photo.'))),
        'image/jpeg',
        0.84,
      ),
    );
    return new File([blob], 'wildmon-capture.jpg', { type: 'image/jpeg' });
  } finally {
    URL.revokeObjectURL(url);
  }
}

export function CaptureFlow() {
  const params = useSearchParams();
  const sessionId = params.get('session');
  const challengeId = params.get('challenge');
  const fileInput = useRef<HTMLInputElement>(null);
  const video = useRef<HTMLVideoElement>(null);
  const stream = useRef<MediaStream | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState('');
  const [result, setResult] = useState<Discovery | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [cameraOpen, setCameraOpen] = useState(false);

  useEffect(() => {
    if (!file) return;
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);
  useEffect(() => () => stream.current?.getTracks().forEach((track) => track.stop()), []);
  useEffect(() => {
    if (cameraOpen && video.current && stream.current) video.current.srcObject = stream.current;
  }, [cameraOpen]);
  useEffect(() => {
    if (!result || !['queued', 'processing'].includes(result.status)) return;
    const timer = setInterval(async () => {
      try {
        setResult(await api<Discovery>(`/discoveries/${result.id}`));
      } catch {
        /* Keep pending until next poll. */
      }
    }, 3000);
    return () => clearInterval(timer);
  }, [result]);

  async function openCamera() {
    setError('');
    try {
      const media = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment' },
        audio: false,
      });
      stream.current = media;
      setCameraOpen(true);
    } catch {
      setError('Camera permission was denied or unavailable. Choose a photo instead.');
    }
  }

  function closeCamera() {
    stream.current?.getTracks().forEach((track) => track.stop());
    stream.current = null;
    setCameraOpen(false);
  }

  function snapPhoto() {
    if (!video.current) return;
    const canvas = document.createElement('canvas');
    canvas.width = video.current.videoWidth;
    canvas.height = video.current.videoHeight;
    canvas.getContext('2d')?.drawImage(video.current, 0, 0);
    canvas.toBlob(
      (blob) => {
        if (blob) setFile(new File([blob], 'camera.jpg', { type: 'image/jpeg' }));
        closeCamera();
      },
      'image/jpeg',
      0.9,
    );
  }

  async function submit() {
    if (!file) return;
    setBusy(true);
    setError('');
    try {
      const captureId = createClientId();
      const prepared = await prepareImage(file);
      if (challengeId)
        await post(`/challenges/${challengeId}/captures`, { client_capture_id: captureId });
      const signed = await post<UploadSign>('/uploads/sign', { content_type: prepared.type });
      const local =
        new URL(signed.upload_url, window.location.origin).origin === window.location.origin;
      const uploaded = await fetch(signed.upload_url, {
        method: 'PUT',
        credentials: local ? 'include' : 'omit',
        headers: {
          'Content-Type': prepared.type,
          ...(local
            ? {
                'X-CSRF-Token':
                  document.cookie
                    .split('; ')
                    .find((item) => item.startsWith('wildmon_csrf='))
                    ?.split('=')[1] ?? '',
              }
            : {}),
        },
        body: prepared,
      });
      if (!uploaded.ok) throw new Error('Photo upload failed. Please retry.');
      const discovery = await post<Discovery>('/discoveries', {
        image_key: signed.key,
        client_capture_id: captureId,
        session_id: sessionId,
        challenge_id: challengeId,
      });
      setResult(discovery);
      setFile(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not submit photo.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        title={challengeId ? 'Challenge capture' : sessionId ? 'Hunt capture' : 'Quick capture'}
        description='Photograph one organism clearly. Keep a safe distance and leave wildlife undisturbed.'
        action={
          <Link
            href={
              challengeId
                ? `/challenges/${challengeId}`
                : sessionId
                  ? `/hunts/${sessionId}`
                  : '/dashboard'
            }
            className='button-secondary'
          >
            Back
          </Link>
        }
      />
      <div className='mx-auto max-w-2xl'>
        {result ? (
          <div className='grid gap-5'>
            <DiscoveryCard item={result} />
            <p className='text-sm text-muted'>
              {['queued', 'processing'].includes(result.status)
                ? 'Identification is running. You can put your phone away and return later.'
                : 'Your result is ready.'}
            </p>
            <button className='button' onClick={() => setResult(null)}>
              Capture another
            </button>
          </div>
        ) : (
          <div className='surface overflow-hidden'>
            <div className='relative grid min-h-85 place-items-center overflow-hidden bg-forest'>
              {preview ? (
                <img
                  src={preview}
                  alt='Your photo preview'
                  className='absolute inset-0 h-full w-full object-contain'
                />
              ) : (
                <div className='px-8 text-center text-white'>
                  <Camera size={48} weight='duotone' className='mx-auto text-[#ff9975]' />
                  <p className='mt-4 text-xl font-semibold'>What caught your eye?</p>
                  <p className='mt-2 text-sm text-white/70'>
                    Aim for one clear plant, bird, or insect.
                  </p>
                </div>
              )}
            </div>
            <div className='grid gap-4 p-5 md:p-7'>
              <input
                ref={fileInput}
                type='file'
                accept='image/*'
                capture='environment'
                className='sr-only'
                onChange={(event) => {
                  setFile(event.target.files?.[0] ?? null);
                  setError('');
                }}
              />
              <ErrorNote message={error} />
              {file ? (
                <div className='flex flex-wrap gap-3'>
                  <button className='button' disabled={busy} onClick={submit}>
                    {busy ? 'Submitting...' : 'Submit discovery'}
                  </button>
                  <button
                    className='button-secondary'
                    onClick={() => {
                      setFile(null);
                      fileInput.current?.click();
                    }}
                  >
                    Retake
                  </button>
                </div>
              ) : (
                <div className='flex flex-wrap gap-3'>
                  <button className='button' onClick={() => fileInput.current?.click()}>
                    <ImageSquare size={19} /> Take or choose photo
                  </button>
                  <button className='button-secondary' onClick={openCamera}>
                    <Camera size={19} /> Live camera
                  </button>
                </div>
              )}
              <p className='text-xs leading-relaxed text-muted'>
                Use a clear photo of one organism. Identification can be uncertain and may ask for a
                retake. Avoid nests and unsafe locations.
              </p>
            </div>
          </div>
        )}
      </div>
      <Dialog.Root
        open={cameraOpen}
        onOpenChange={(open) => {
          if (!open) closeCamera();
        }}
      >
        <Dialog.Portal>
          <Dialog.Overlay className='fixed inset-0 z-30 bg-black/80' />
          <Dialog.Content className='fixed inset-4 z-40 flex flex-col items-center justify-center gap-5 rounded-2xl bg-forest p-4 text-white md:inset-12'>
            <Dialog.Title className='text-xl font-semibold'>Frame one living thing</Dialog.Title>
            <video
              ref={video}
              autoPlay
              playsInline
              muted
              className='max-h-[70dvh] w-full rounded-xl bg-black object-contain'
            />
            <div className='flex gap-3'>
              <button className='button' onClick={snapPhoto}>
                <Camera size={19} /> Capture
              </button>
              <Dialog.Close className='button-secondary'>
                <X size={17} /> Close
              </Dialog.Close>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </>
  );
}
