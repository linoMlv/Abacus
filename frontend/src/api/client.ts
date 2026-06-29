/**
 * Thin fetch wrapper for the V3 API. Cookies carry the session, so every
 * request is credentialed; mutations send JSON and the same-origin Origin
 * header the server's CSRF check expects (dev proxies /api to the backend).
 */

const BASE = '/api';

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  // JSON by default; for FormData let the browser set the multipart boundary.
  const isForm = options.body instanceof FormData;
  let res: Response;
  try {
    res = await fetch(BASE + path, {
      credentials: 'include',
      headers: {
        ...(isForm ? {} : { 'Content-Type': 'application/json' }),
        ...options.headers,
      },
      ...options,
    });
  } catch {
    throw new ApiError(0, 'Connexion au serveur impossible.');
  }

  if (!res.ok) {
    let detail = 'Une erreur est survenue.';
    try {
      const body = await res.json();
      if (typeof body?.detail === 'string') detail = body.detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

/**
 * Message to show for a react-query mutation: the server's detail when the
 * failure is an {@link ApiError}, otherwise a caller-provided fallback (and
 * `null` while the mutation has not errored).
 */
export function apiErrorMessage(
  mutation: { error: unknown; isError: boolean },
  fallback: string
): string | null {
  if (mutation.error instanceof ApiError) return mutation.error.message;
  return mutation.isError ? fallback : null;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'POST', body: body ? JSON.stringify(body) : undefined }),
  // Multipart: the browser sets the Content-Type (with its boundary).
  postForm: <T>(path: string, form: FormData) => request<T>(path, { method: 'POST', body: form }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'PATCH', body: body ? JSON.stringify(body) : undefined }),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'PUT', body: body ? JSON.stringify(body) : undefined }),
  del: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
};

/** Same-origin URL of an API resource (e.g. for an attachment download link). */
export function apiUrl(path: string): string {
  return BASE + path;
}
