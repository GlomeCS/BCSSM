import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import React from 'react';
import { useRequireAuth } from '../hooks/useRequireAuth';
import { AuthProvider } from '../AuthContext';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

function wrapper({ children }: { children: React.ReactNode }) {
  return (
    <MemoryRouter>
      <AuthProvider>{children}</AuthProvider>
    </MemoryRouter>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  vi.spyOn(globalThis, 'fetch').mockReset();
});

afterEach(() => {
  vi.restoreAllMocks();
});

function mockValidateAuth(isValid: boolean) {
  vi.mocked(fetch).mockResolvedValueOnce(
    new Response(
      JSON.stringify({ is_valid: isValid, role: 'Team Member', section: 'Seniors', can_edit_all: false }),
      { headers: { 'Content-Type': 'application/json' } }
    )
  );
}

describe('useRequireAuth', () => {
  it('sets currentUser and stops loading after successful auth', async () => {
    localStorage.setItem('is_logged_in', 'true');
    localStorage.setItem('currentUser', 'Alice');
    mockValidateAuth(true);

    const { result } = renderHook(() => useRequireAuth(), { wrapper });

    expect(result.current.loading).toBe(true);

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.currentUser).toBe('Alice');
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it('redirects to /login when not logged in', async () => {
    // no localStorage entries

    const { result } = renderHook(() => useRequireAuth(), { wrapper });

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/login');
    });

    expect(result.current.currentUser).toBe(null);
  });

  it('redirects to /login and clears storage when validateAuth returns false', async () => {
    localStorage.setItem('is_logged_in', 'true');
    localStorage.setItem('currentUser', 'Bob');
    mockValidateAuth(false);

    renderHook(() => useRequireAuth(), { wrapper });

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/login');
    });

    expect(localStorage.getItem('currentUser')).toBeNull();
  });

  it('keeps the user logged in on a transient network error', async () => {
    localStorage.setItem('is_logged_in', 'true');
    localStorage.setItem('currentUser', 'Charlie');
    vi.mocked(fetch).mockRejectedValueOnce(new TypeError('Network error'));

    const { result } = renderHook(() => useRequireAuth(), { wrapper });

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.currentUser).toBe('Charlie');
    expect(mockNavigate).not.toHaveBeenCalled();
    expect(localStorage.getItem('currentUser')).toBe('Charlie');
  });

  // Finding 1: cross-tab localStorage race — server says valid but storage was cleared mid-flight
  it('redirects to /login when localStorage is cleared while validateAuth is in flight', async () => {
    localStorage.setItem('is_logged_in', 'true');
    localStorage.setItem('currentUser', 'Alice');

    vi.mocked(fetch).mockImplementationOnce(async () => {
      // Simulate another tab calling localStorage.clear() mid-flight
      localStorage.clear();
      return new Response(
        JSON.stringify({ is_valid: true, role: 'Team Member', section: 'Seniors', can_edit_all: false }),
        { headers: { 'Content-Type': 'application/json' } }
      );
    });

    const { result } = renderHook(() => useRequireAuth(), { wrapper });

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/login');
    });

    expect(result.current.currentUser).toBeNull();
  });

  // Finding 1 (catch path): same race during a transient network error
  it('redirects to /login when localStorage is cleared during a transient error', async () => {
    localStorage.setItem('is_logged_in', 'true');
    localStorage.setItem('currentUser', 'Alice');

    vi.mocked(fetch).mockImplementationOnce(async () => {
      localStorage.clear();
      throw new TypeError('Network error');
    });

    renderHook(() => useRequireAuth(), { wrapper });

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/login');
    });
  });

  // A 5xx response throws from validateAuth, which useRequireAuth treats as transient —
  // the session is preserved rather than forcing the user to /login.
  it('preserves session when server returns a 5xx response (transient outage)', async () => {
    localStorage.setItem('is_logged_in', 'true');
    localStorage.setItem('currentUser', 'Dave');
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response('<html>Bad Gateway</html>', { status: 502 })
    );

    const { result } = renderHook(() => useRequireAuth(), { wrapper });

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.currentUser).toBe('Dave');
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  // Finding 4 (stale metadata trade-off): during an outage the hook keeps users logged in,
  // which means stale localStorage values like user_role/can_edit_all may persist.
  // This is a deliberate trade-off to avoid logging users out during transient outages.
  // Tracked in GitHub issue #135.
});
