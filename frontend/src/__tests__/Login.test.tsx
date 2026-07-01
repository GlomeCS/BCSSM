import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import Login from '../Login';
import type { AuthUser } from '../../api';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

const mockAuth = vi.hoisted(() => ({
  currentUser: null as string | null,
  loading: false,
  setUser: vi.fn<(user: AuthUser) => void>(),
  logout: vi.fn(),
  refresh: vi.fn(),
  userRole: null as string | null,
  userSection: null as string | null,
  canEditAll: false,
}));

vi.mock('../AuthContext', () => ({
  useAuth: () => mockAuth,
}));

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
        ok: true,
        user_name: user,
        role: 'Team Member',
        section: 'Seniors',
        can_edit_all: false,
      }),
      { headers: { 'Content-Type': 'application/json' } }
    )
  );
  return user;
}

// Types in the combobox and clicks the matching dropdown option.
async function selectUser(username: string) {
  const input = screen.getByRole('combobox');
  await userEvent.type(input, username);
  await userEvent.click(screen.getByRole('option', { name: username }));
}

describe('Login', () => {
  beforeEach(() => {
    localStorage.clear();
    mockNavigate.mockClear();
    mockAuth.setUser.mockClear();
    mockAuth.currentUser = null;
    mockAuth.loading = false;
    vi.stubGlobal('fetch', vi.fn());
  });
  afterEach(() => vi.unstubAllGlobals());

  it('redirects to / when already logged in', async () => {
    mockAuth.currentUser = 'Alice';
    renderLogin();
    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith('/'));
  });

  it('shows a loading state while fetching users', () => {
    vi.mocked(fetch).mockReturnValueOnce(new Promise(() => {})); // never resolves
    renderLogin();
    expect(screen.getByText(/loading users/i)).toBeInTheDocument();
  });

  it('renders user list in dropdown after fetching', async () => {
    mockFetchUsers();
    renderLogin();
    const input = await waitFor(() => screen.getByRole('combobox'));
    await userEvent.click(input);
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

  it('disables the Continue button until a user is selected', async () => {
    mockFetchUsers();
    renderLogin();
    await waitFor(() => screen.getByRole('button', { name: /continue/i }));
    expect(screen.getByRole('button', { name: /continue/i })).toBeDisabled();
  });

  it('keeps Continue disabled after selecting a user but before entering a password', async () => {
    mockFetchUsers();
    renderLogin();
    await waitFor(() => screen.getByRole('combobox'));
    await selectUser('Alice');
    expect(screen.getByRole('button', { name: /continue/i })).toBeDisabled();
  });

  it('enables the Continue button after selecting a user and entering a password', async () => {
    mockFetchUsers();
    renderLogin();
    await waitFor(() => screen.getByRole('combobox'));
    await selectUser('Alice');
    await userEvent.type(screen.getByPlaceholderText(/enter your password/i), 'secret123');
    expect(screen.getByRole('button', { name: /continue/i })).not.toBeDisabled();
  });

  it('clears the password field when a different user is selected', async () => {
    mockFetchUsers();
    renderLogin();
    await waitFor(() => screen.getByRole('combobox'));
    await selectUser('Alice');
    await userEvent.type(screen.getByPlaceholderText(/enter your password/i), 'secret123');
    expect(screen.getByPlaceholderText(/enter your password/i)).toHaveValue('secret123');
    // Switch to Bob: clear the search input and pick Bob from the dropdown
    const input = screen.getByRole('combobox');
    await userEvent.clear(input);
    await userEvent.type(input, 'Bob');
    await userEvent.click(screen.getByRole('option', { name: 'Bob' }));
    expect(screen.getByPlaceholderText(/enter your password/i)).toHaveValue('');
    expect(screen.getByRole('button', { name: /continue/i })).toBeDisabled();
  });

  it('calls setUser with auth data and navigates to / on successful login', async () => {
    mockFetchUsers();
    renderLogin();
    await waitFor(() => screen.getByRole('combobox'));

    await selectUser('Bob');
    await userEvent.type(screen.getByPlaceholderText(/enter your password/i), 'secret123');
    mockLoginSuccess('Bob');
    fireEvent.click(screen.getByRole('button', { name: /continue/i }));

    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith('/'));
    expect(mockAuth.setUser).toHaveBeenCalledWith({
      user_name: 'Bob',
      role: 'Team Member',
      section: 'Seniors',
      can_edit_all: false,
    });
  });

  it('shows an error message on failed login request', async () => {
    mockFetchUsers();
    renderLogin();
    await waitFor(() => screen.getByRole('combobox'));

    await selectUser('Alice');
    await userEvent.type(screen.getByPlaceholderText(/enter your password/i), 'secret123');
    vi.mocked(fetch).mockResolvedValueOnce(new Response('', { status: 500 }));
    fireEvent.click(screen.getByRole('button', { name: /continue/i }));

    await waitFor(() =>
      expect(screen.getByText(/failed to select user/i)).toBeInTheDocument()
    );
  });
});
