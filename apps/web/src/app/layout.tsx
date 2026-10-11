import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import { GeistSans } from 'geist/font/sans';
import './globals.css';

export const metadata: Metadata = {
  title: { default: 'Wildmon', template: '%s | Wildmon' },
  description: 'Collect nature discoveries, challenge friends, and explore the world around you.',
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang='en' className={GeistSans.variable}>
      <body className='font-sans antialiased'>{children}</body>
    </html>
  );
}
