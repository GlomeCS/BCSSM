import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import {
  getCurrentUser,
  isLoggedIn,
  apiGet,
  apiPost,
  logout,
  validateAuth,
} from '../../api';

describe('getCurrentUser', () => {
  beforeEach(() => localStorage.clear());

  it('returns null when no user is stored', () => {
    expect(getCurrentUser()).toBeNull();
  });

  it('returns the stored username', () => {
    localStorage.setItem('currentUser', 'Alice');
    expect(getCurrentUser()).toBe('Alice');
  });
});

describe('isLoggedIn', () => {
  beforeEach(() => localStorage.clear());

  it('returns false when nothing is stored', () => {
    expect(isLoggedIn()).toBe(false);
  });

  it('returns false when is_logged_in is true but no currentUser', () => {
    localStorage.setItem('is_logged_in', 'true');
    expect(isLoggedIn()).toBe(false);
  });

  it('returns false when currentUser is set but is_logged_in is not true', () => {
    localStorage.setItem('currentUser', 'Alice');
    expect(isLoggedIn()).toBe(false);
  });

  it('returns true when both is_logged_in and currentUser are set', () => {
    localStorage.setItem('is_logged_in', 'true');
    localStorage.setItem('currentUser', 'Alice');
    expect(isLoggedIn()).toBe(true);
  });
});

describe('apiGet', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.stubGlobal('fetch', vi.fn());
  });
  afterEach(() => vi.unstubAllGlobals());

  it('calls fetch with GET method', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(new Response('{}'));
    await apiGet('/api/test');
    expect(fetch).toHaveBeenCalledWith(
      '/api/test',
      expect.objectContaining({ method: 'GET' })
    );
  });

  it('appends user_name query param when logged in', async () => {
    localStorage.setItem('currentUser', 'Bob');
    vi.mocked(fetch).mockResolvedValueOnce(new Response('{}'));
    await apiGet('/api/test');
    const [url] = vi.mocked(fetch).mock.calls[0];
    expect(url).toContain('user_name=Bob');
  });

  it('does not append user_name when no user', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(new Response('{}'));
    await apiGet('/api/test');
    const [url] = vi.mocked(fetch).mock.calls[0];
    expect(url).not.toContain('user_name');
  });

  it('sets X-Current-User header when logged in', async () => {
    localStorage.setItem('currentUser', 'Bob');
    vi.mocked(fetch).mockResolvedValueOnce(new Response('{}'));
    await apiGet('/api/test');
    const [, options] = vi.mocked(fetch).mock.calls[0];
    const headers = options?.headers as Headers;
    expect(headers.get('X-Current-User')).toBe('Bob');
  });

  it('does not duplicate user_name if already in URL', async () => {
    localStorage.setItem('currentUser', 'Bob');
    vi.mocked(fetch).mockResolvedValueOnce(new Response('{}'));
    await apiGet('/api/test?user_name=Bob');
    const [url] = vi.mocked(fetch).mock.calls[0];
    expect((url as string).split('user_name').length - 1).toBe(1);
  });
});

describe('apiPost', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.stubGlobal('fetch', vi.fn());
  });
  afterEach(() => vi.unstubAllGlobals());

  it('calls fetch with POST method and JSON content-type', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(new Response('{}'));
    await apiPost('/api/test', { key: 'value' });
    const [, options] = vi.mocked(fetch).mock.calls[0];
    expect(options?.method).toBe('POST');
    const headers = options?.headers as Headers;
    expect(headers.get('Content-Type')).toBe('application/json');
  });

  it('merges user_name into the request body', async () => {
    localStorage.setItem('currentUser', 'Carol');
    vi.mocked(fetch).mockResolvedValueOnce(new Response('{}'));
    await apiPost('/api/test', { data: 1 });
    const [, options] = vi.mocked(fetch).mock.calls[0];
    const body = JSON.parse(options?.body as string);
    expect(body.user_name).toBe('Carol');
    expect(body.data).toBe(1);
  });

  it('works without a currentUser', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(new Response('{}'));
    await apiPost('/api/test', { data: 2 });
    const [, options] = vi.mocked(fetch).mock.calls[0];
    const body = JSON.parse(options?.body as string);
    expect(body.user_name).toBeUndefined();
    expect(body.data).toBe(2);
  });
});

describe('validateAuth', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.stubGlobal('fetch', vi.fn());
  });
  afterEach(() => vi.unstubAllGlobals());

  it('returns false immediately when no currentUser', async () => {
    const result = await validateAuth();
    expect(result).toBe(false);
    expect(fetch).not.toHaveBeenCalled();
  });

  it('returns true and updates localStorage on valid response', async () => {
    localStorage.setItem('currentUser', 'Dave');
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ is_valid: true, role: 'Admin', section: 'A', is_leader: true }), {
        headers: { 'Content-Type': 'application/json' },
      })
    );
    const result = await validateAuth();
    expect(result).toBe(true);
    expect(localStorage.getItem('user_role')).toBe('Admin');
    expect(localStorage.getItem('user_section')).toBe('A');
    expect(localStorage.getItem('is_leader')).toBe('true');
    expect(localStorage.getItem('is_logged_in')).toBe('true');
  });

  it('returns false when is_valid is false', async () => {
    localStorage.setItem('currentUser', 'Dave');
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ is_valid: false }), {
        headers: { 'Content-Type': 'application/json' },
      })
    );
    const result = await validateAuth();
    expect(result).toBe(false);
  });

  it('throws on network/transport error', async () => {
    localStorage.setItem('currentUser', 'Dave');
    vi.mocked(fetch).mockRejectedValueOnce(new Error('Network error'));
    await expect(validateAuth()).rejects.toThrow('Network error');
  });

  it('throws when server responds with a non-auth error status (e.g. 502)', async () => {
    localStorage.setItem('currentUser', 'Dave');
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response('<html>Bad Gateway</html>', { status: 502 })
    );
    await expect(validateAuth()).rejects.toThrow('Auth check failed with status 502');
  });

  it('returns false when server responds with 401', async () => {
    localStorage.setItem('currentUser', 'Dave');
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: 'Unauthorized' }), { status: 401 })
    );
    const result = await validateAuth();
    expect(result).toBe(false);
  });

  it('returns false when server responds with 400 (no session)', async () => {
    localStorage.setItem('currentUser', 'Dave');
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ is_valid: false, error: 'No username provided' }), { status: 400 })
    );
    const result = await validateAuth();
    expect(result).toBe(false);
  });
});

describe('logout', () => {
  beforeEach(() => {
    localStorage.setItem('currentUser', 'Alice');
    localStorage.setItem('is_logged_in', 'true');
    localStorage.setItem('user_role', 'Team Member');
    localStorage.setItem('user_section', 'Seniors');
    localStorage.setItem('is_leader', 'false');
    vi.stubGlobal('fetch', vi.fn());
  });
  afterEach(() => {
    localStorage.clear();
    vi.unstubAllGlobals();
  });

  it('clears localStorage after a successful logout API call', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ ok: true }), { status: 200 })
    );
    await logout();
    expect(localStorage.getItem('currentUser')).toBeNull();
    expect(localStorage.getItem('is_logged_in')).toBeNull();
  });

  it('clears localStorage even when the logout API call throws', async () => {
    vi.mocked(fetch).mockRejectedValueOnce(new Error('Network error'));
    await expect(logout()).rejects.toThrow('Network error');
    expect(localStorage.getItem('currentUser')).toBeNull();
    expect(localStorage.getItem('is_logged_in')).toBeNull();
  });
});
