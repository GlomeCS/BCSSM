import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import React from 'react';
import { useRequireAuth } from '../hooks/useRequireAuth';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

function wrapper({ children }: { children: React.ReactNode }) {
  return <MemoryRouter>{children}</MemoryRouter>;
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
      JSON.stringify({ is_valid: isValid, role: 'Team Member', section: 'Seniors', is_leader: false }),
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
});
