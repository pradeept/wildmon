import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  reactStrictMode: true,
  allowedDevOrigins: ['192.168.1.25'],
  async rewrites() {
    const apiOrigin = process.env.API_PROXY_TARGET ?? 'http://127.0.0.1:8000';
    return [{ source: '/api/v1/:path*', destination: `${apiOrigin}/api/v1/:path*` }];
  },
};

export default nextConfig;
