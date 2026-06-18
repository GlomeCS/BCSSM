import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import {
  getCurrentUser,
  isLoggedIn,
  apiGet,
  apiPost,
  login,
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

  it('does not inject user_name into GET URL', async () => {
    localStorage.setItem('currentUser', 'Bob');
    vi.mocked(fetch).mockResolvedValueOnce(new Response('{}'));
    await apiGet('/api/test');
    const [url] = vi.mocked(fetch).mock.calls[0];
    expect(url).not.toContain('user_name');
  });

  it('does not set X-Current-User header', async () => {
    localStorage.setItem('currentUser', 'Bob');
    vi.mocked(fetch).mockResolvedValueOnce(new Response('{}'));
    await apiGet('/api/test');
    const [, options] = vi.mocked(fetch).mock.calls[0];
    const headers = options?.headers as Headers;
    expect(headers.get('X-Current-User')).toBeNull();
  });

  it('sets credentials: include', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(new Response('{}'));
    await apiGet('/api/test');
    const [, options] = vi.mocked(fetch).mock.calls[0];
    expect(options?.credentials).toBe('include');
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

  it('sends caller-supplied data without injecting user_name', async () => {
    localStorage.setItem('currentUser', 'Carol');
    vi.mocked(fetch).mockResolvedValueOnce(new Response('{}'));
    await apiPost('/api/test', { data: 1 });
    const [, options] = vi.mocked(fetch).mock.calls[0];
    const body = JSON.parse(options?.body as string);
    expect(body.user_name).toBeUndefined();
    expect(body.data).toBe(1);
  });
});

describe('login', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.stubGlobal('fetch', vi.fn());
  });
  afterEach(() => vi.unstubAllGlobals());

  it('POSTs to /api/auth/login with the supplied username and password', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(new Response('{}'));
    await login('Alice', 'secret123');
    const [url, options] = vi.mocked(fetch).mock.calls[0];
    expect(url).toBe('/api/auth/login');
    expect(options?.method).toBe('POST');
    const body = JSON.parse(options?.body as string);
    expect(body.user_name).toBe('Alice');
    expect(body.password).toBe('secret123');
  });

  it('sends credentials: include so the session cookie is accepted', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(new Response('{}'));
    await login('Alice', 'secret123');
    const [, options] = vi.mocked(fetch).mock.calls[0];
    expect(options?.credentials).toBe('include');
  });
});

describe('validateAuth', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.stubGlobal('fetch', vi.fn());
  });
  afterEach(() => vi.unstubAllGlobals());

  it('returns null when server returns 401 (no localStorage)', async () => {
    // localStorage is empty — server is still queried (cookie-based auth)
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: 'Unauthorized' }), { status: 401 })
    );
    const result = await validateAuth();
    expect(result).toBeNull();
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it('returns the AuthUser on valid response without touching localStorage', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(
        JSON.stringify({ is_valid: true, user_name: 'Dave', role: 'Admin', section: 'A', can_edit_all: true }),
        { headers: { 'Content-Type': 'application/json' } }
      )
    );
    const result = await validateAuth();
    expect(result).toEqual({ user_name: 'Dave', role: 'Admin', section: 'A', can_edit_all: true });
    expect(localStorage.getItem('user_role')).toBeNull();
    expect(localStorage.getItem('is_logged_in')).toBeNull();
  });

  it('returns null when is_valid is false', async () => {
    localStorage.setItem('currentUser', 'Dave');
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ is_valid: false }), {
        headers: { 'Content-Type': 'application/json' },
      })
    );
    const result = await validateAuth();
    expect(result).toBeNull();
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

  it('returns null when server responds with 401', async () => {
    localStorage.setItem('currentUser', 'Dave');
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: 'Unauthorized' }), { status: 401 })
    );
    const result = await validateAuth();
    expect(result).toBeNull();
  });

  it('returns null when server responds with 400 (no session)', async () => {
    localStorage.setItem('currentUser', 'Dave');
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ is_valid: false, error: 'No username provided' }), { status: 400 })
    );
    const result = await validateAuth();
    expect(result).toBeNull();
  });
});

describe('logout', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('POSTs to /api/auth/logout', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ ok: true }), { status: 200 })
    );
    await logout();
    expect(fetch).toHaveBeenCalledWith(
      '/api/auth/logout',
      expect.objectContaining({ method: 'POST', credentials: 'include' })
    );
  });

  it('propagates errors from the logout API call', async () => {
    vi.mocked(fetch).mockRejectedValueOnce(new Error('Network error'));
    await expect(logout()).rejects.toThrow('Network error');
  });
});
