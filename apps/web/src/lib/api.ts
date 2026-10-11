function csrfToken() {
  if (typeof document === 'undefined') return '';
  return document.cookie
    .split('; ')
    .find((cookie) => cookie.startsWith('wildmon_csrf='))
    ?.split('=')[1];
}

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public code: string,
  ) {
    super(message);
  }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    ...init,
    credentials: 'include',
    headers: {
      ...(init.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...(init.method && init.method !== 'GET' ? { 'X-CSRF-Token': csrfToken() ?? '' } : {}),
      ...init.headers,
    },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new ApiError(
      payload.error?.message ?? 'Something went wrong.',
      response.status,
      payload.error?.code ?? 'unknown',
    );
  }
  return response.json() as Promise<T>;
}

export function post<T>(path: string, body?: unknown) {
  return api<T>(path, {
    method: 'POST',
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}
