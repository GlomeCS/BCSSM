import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import Login from '../Login';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

function renderLogin() {
  return render(
    <MemoryRouter>
      <Login />
    </MemoryRouter>
  );
}

const USER_LIST = ['Alice', 'Bob', 'Carol'];

function mockFetchUsers() {
  vi.mocked(fetch).mockResolvedValueOnce(
    new Response(JSON.stringify({ users: USER_LIST }), {
      headers: { 'Content-Type': 'application/json' },
    })
  );
}

function mockLoginSuccess(user: string) {
  vi.mocked(fetch).mockResolvedValueOnce(
    new Response(
      JSON.stringify({
        is_logged_in: true,
        role: 'Team Member',
        user_section: 'Seniors',
        is_leader: false,
      }),
      { headers: { 'Content-Type': 'application/json' } }
    )
  );
  return user;
}

describe('Login', () => {
  beforeEach(() => {
    localStorage.clear();
    mockNavigate.mockClear();
    vi.stubGlobal('fetch', vi.fn());
  });
  afterEach(() => vi.unstubAllGlobals());

  it('redirects to / when already logged in', async () => {
    localStorage.setItem('is_logged_in', 'true');
    localStorage.setItem('currentUser', 'Alice');
    renderLogin();
    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith('/'));
  });

  it('shows a loading state while fetching users', () => {
    vi.mocked(fetch).mockReturnValueOnce(new Promise(() => {})); // never resolves
    renderLogin();
    expect(screen.getByText(/loading users/i)).toBeInTheDocument();
  });

  it('renders user list after fetching', async () => {
    mockFetchUsers();
    renderLogin();
    await waitFor(() => expect(screen.getByRole('combobox')).toBeInTheDocument());
    USER_LIST.forEach(user => {
      expect(screen.getByRole('option', { name: user })).toBeInTheDocument();
    });
  });

  it('shows an error when users fail to load', async () => {
    vi.mocked(fetch).mockRejectedValueOnce(new Error('Network error'));
    renderLogin();
    await waitFor(() =>
      expect(screen.getByText(/failed to load users/i)).toBeInTheDocument()
    );
  });

  it('shows an error when login is attempted without selecting a user', async () => {
    mockFetchUsers();
    renderLogin();
    await waitFor(() => screen.getByRole('button', { name: /continue/i }));
    // Button should be disabled until a user is selected
    expect(screen.getByRole('button', { name: /continue/i })).toBeDisabled();
  });

  it('enables the Continue button after selecting a user', async () => {
    mockFetchUsers();
    renderLogin();
    await waitFor(() => screen.getByRole('combobox'));
    await userEvent.selectOptions(screen.getByRole('combobox'), 'Alice');
    expect(screen.getByRole('button', { name: /continue/i })).not.toBeDisabled();
  });

  it('stores auth data and navigates to / on successful login', async () => {
    mockFetchUsers();
    renderLogin();
    await waitFor(() => screen.getByRole('combobox'));

    await userEvent.selectOptions(screen.getByRole('combobox'), 'Bob');
    mockLoginSuccess('Bob');
    fireEvent.click(screen.getByRole('button', { name: /continue/i }));

    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith('/'));
    expect(localStorage.getItem('currentUser')).toBe('Bob');
    expect(localStorage.getItem('is_logged_in')).toBe('true');
    expect(localStorage.getItem('user_role')).toBe('Team Member');
    expect(localStorage.getItem('user_section')).toBe('Seniors');
    expect(localStorage.getItem('is_leader')).toBe('false');
  });

  it('shows an error message on failed login request', async () => {
    mockFetchUsers();
    renderLogin();
    await waitFor(() => screen.getByRole('combobox'));

    await userEvent.selectOptions(screen.getByRole('combobox'), 'Alice');
    vi.mocked(fetch).mockResolvedValueOnce(new Response('', { status: 500 }));
    fireEvent.click(screen.getByRole('button', { name: /continue/i }));

    await waitFor(() =>
      expect(screen.getByText(/failed to select user/i)).toBeInTheDocument()
    );
  });
});
