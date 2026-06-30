import { beforeEach, describe, expect, it, vi } from 'vitest';

import { api } from '@/api/client';

/** A minimal Response stand-in good enough for the client (ok/status/json). */
function jsonResponse(status: number, body: unknown = {}): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

describe('api client — 401 auto-refresh', () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('refreshes the session and replays the original request once on a 401', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(401, { detail: 'expired' })) // original
      .mockResolvedValueOnce(jsonResponse(200, {})) // /auth/refresh
      .mockResolvedValueOnce(jsonResponse(200, { ok: true })); // replay
    vi.stubGlobal('fetch', fetchMock);

    const data = await api.get<{ ok: boolean }>('/asso/x/ecritures');

    expect(data).toEqual({ ok: true });
    expect(fetchMock).toHaveBeenCalledTimes(3);
    const refreshCall = fetchMock.mock.calls.find(([url]) => String(url).endsWith('/auth/refresh'));
    expect(refreshCall).toBeTruthy();
    expect((refreshCall?.[1] as RequestInit | undefined)?.method).toBe('POST');
  });

  it('propagates the 401 (no replay) when the refresh fails', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(401, { detail: 'expired' })) // original
      .mockResolvedValueOnce(jsonResponse(401, { detail: 'no session' })); // refresh
    vi.stubGlobal('fetch', fetchMock);

    await expect(api.get('/asso/x/ecritures')).rejects.toMatchObject({ status: 401 });
    expect(fetchMock).toHaveBeenCalledTimes(2); // original + refresh, never replayed
  });

  it('never tries to refresh on the auth endpoints themselves', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(jsonResponse(401, { detail: 'bad creds' }));
    vi.stubGlobal('fetch', fetchMock);

    await expect(api.post('/auth/login', { email: 'a@b.c', password: 'x' })).rejects.toMatchObject({
      status: 401,
    });
    expect(fetchMock).toHaveBeenCalledTimes(1); // no refresh attempt
  });

  it('shares a single refresh across concurrent 401s (single-flight)', async () => {
    let refreshCount = 0;
    const seen: Record<string, number> = {};
    const fetchMock = vi.fn((url: string) => {
      const u = String(url);
      if (u.endsWith('/auth/refresh')) {
        refreshCount += 1;
        return Promise.resolve(jsonResponse(200, {}));
      }
      seen[u] = (seen[u] ?? 0) + 1;
      // Each data path 401s the first time, then succeeds on its replay.
      return Promise.resolve(seen[u] === 1 ? jsonResponse(401, {}) : jsonResponse(200, { u }));
    });
    vi.stubGlobal('fetch', fetchMock);

    const [a, b] = await Promise.all([
      api.get<{ u: string }>('/asso/x/ecritures'),
      api.get<{ u: string }>('/asso/x/comptes'),
    ]);

    expect(a.u).toBe('/api/asso/x/ecritures');
    expect(b.u).toBe('/api/asso/x/comptes');
    expect(refreshCount).toBe(1); // both 401s funnel through one refresh
  });
});
