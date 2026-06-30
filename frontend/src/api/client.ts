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

const REFRESH_PATH = '/auth/refresh';
// Endpoints where a 401 is terminal: the auth flows themselves (refreshing on a
// failed login would loop). Every other path — including /auth/session — may
// refresh and replay, so a returning user with a valid refresh cookie stays in.
const NO_REFRESH_PATHS = ['/auth/login', '/auth/register', '/auth/logout', REFRESH_PATH];

let refreshInFlight: Promise<boolean> | null = null;

/**
 * Refresh the session once, shared across concurrent callers (single-flight): a
 * burst of requests that all 401 at once funnels through a single rotating
 * refresh, never a stampede. Resolves to whether the session was renewed.
 */
function refreshSession(): Promise<boolean> {
  if (!refreshInFlight) {
    refreshInFlight = fetch(BASE + REFRESH_PATH, {
      method: 'POST',
      credentials: 'include',
      cache: 'no-store',
      headers: { 'Content-Type': 'application/json' },
    })
      .then((res) => res.ok)
      .catch(() => false)
      .finally(() => {
        refreshInFlight = null;
      });
  }
  return refreshInFlight;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  // JSON by default; for FormData let the browser set the multipart boundary.
  const isForm = options.body instanceof FormData;
  const send = (): Promise<Response> =>
    fetch(BASE + path, {
      credentials: 'include',
      // Never let the browser serve a heuristically-cached prior response for a
      // credentialed API GET — accounting figures must reflect the latest state.
      cache: 'no-store',
      headers: {
        ...(isForm ? {} : { 'Content-Type': 'application/json' }),
        ...options.headers,
      },
      ...options,
    });

  let res: Response;
  try {
    res = await send();
    // A 401 means the access token is missing or expired: refresh the session
    // once (rotating refresh cookie) and replay the original request, so an
    // otherwise-valid session survives access-token expiry transparently.
    if (res.status === 401 && !NO_REFRESH_PATHS.some((p) => path.startsWith(p))) {
      if (await refreshSession()) res = await send();
    }
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
