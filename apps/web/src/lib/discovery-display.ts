import type { Discovery } from '@/lib/types';

export function discoveryStatusLabel(status: string): string {
  switch (status) {
    case 'queued':
      return 'Waiting to identify';
    case 'processing':
      return 'Identifying';
    case 'verified':
      return 'Verified';
    case 'needs_review':
      return 'Uncertain identification';
    case 'unidentified':
      return 'Could not identify';
    case 'rejected':
      return 'Photo not accepted';
    case 'failed':
      return 'Identification failed';
    default:
      return status.replaceAll('_', ' ');
  }
}

export function discoveryTitle(item: Discovery): string {
  if (item.status === 'failed') return 'Identification failed';
  if (item.status === 'unidentified') return 'Could not identify';
  if (item.status === 'rejected') return 'Photo not accepted';
  if (item.status === 'needs_review') {
    return item.common_name ? `Possible ${item.common_name}` : 'Uncertain identification';
  }
  if (item.common_name) return item.common_name;
  if (item.status === 'verified' && item.category) return item.category.replaceAll('_', ' ');
  return 'Finding out…';
}
