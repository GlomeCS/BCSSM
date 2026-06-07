import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import AdminPasswords from '../AdminPasswords';

function renderAdminPasswords() {
  return render(<AdminPasswords />);
}

const USER_STATUS = [
  { name: 'Alice', has_password: true },
  { name: 'Bob', has_password: false },
];

function mockStatusOk() {
  vi.mocked(fetch).mockResolvedValueOnce(
    new Response(JSON.stringify({ users: USER_STATUS }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })
  );
}

function mock403() {
  vi.mocked(fetch).mockResolvedValueOnce(new Response('{"error":"Unauthorized"}', { status: 403 }));
}

function mockSetPasswordOk(userName: string) {
  vi.mocked(fetch).mockResolvedValueOnce(
    new Response(JSON.stringify({ ok: true, user_name: userName }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })
  );
}

describe('AdminPasswords — session validation on mount', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.stubGlobal('fetch', vi.fn());
  });
  afterEach(() => vi.unstubAllGlobals());

  it('shows a verifying state while the session probe is in flight', async () => {
    localStorage.setItem('user_role', 'Admin');
    vi.mocked(fetch).mockReturnValueOnce(new Promise(() => {})); // never resolves
    renderAdminPasswords();
    expect(screen.getByText(/verifying session/i)).toBeInTheDocument();
  });

  it('skips the probe and shows secret form when user_role is not Admin', async () => {
    localStorage.setItem('user_role', 'Team Member');
    renderAdminPasswords();
    await waitFor(() => expect(screen.getByPlaceholderText(/enter admin_secret/i)).toBeInTheDocument());
    expect(fetch).not.toHaveBeenCalled();
  });

  it('shows user list without secret form when session probe succeeds', async () => {
    localStorage.setItem('user_role', 'Admin');
    mockStatusOk();
    renderAdminPasswords();
    await waitFor(() => expect(screen.getByText('Password set')).toBeInTheDocument());
    expect(screen.getByText('No password')).toBeInTheDocument();
    expect(screen.queryByPlaceholderText(/enter admin_secret/i)).not.toBeInTheDocument();
  });

  it('falls back to secret form when session probe returns 403', async () => {
    localStorage.setItem('user_role', 'Admin');
    mock403();
    renderAdminPasswords();
    await waitFor(() => expect(screen.getByPlaceholderText(/enter admin_secret/i)).toBeInTheDocument());
  });
});

describe('AdminPasswords — secret form', () => {
  beforeEach(() => {
    localStorage.clear(); // no Admin role → goes straight to secret form
    vi.stubGlobal('fetch', vi.fn());
  });
  afterEach(() => vi.unstubAllGlobals());

  it('shows an error when Load Users is clicked with an empty secret', async () => {
    renderAdminPasswords();
    await waitFor(() => screen.getByRole('button', { name: /load users/i }));
    fireEvent.click(screen.getByRole('button', { name: /load users/i }));
    expect(screen.getByText(/admin secret is required/i)).toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalled();
  });

  it('renders the user list after a successful load', async () => {
    mockStatusOk();
    renderAdminPasswords();
    await waitFor(() => screen.getByPlaceholderText(/enter admin_secret/i));
    await userEvent.type(screen.getByPlaceholderText(/enter admin_secret/i), 'mysecret');
    fireEvent.click(screen.getByRole('button', { name: /load users/i }));
    await waitFor(() => expect(screen.getByText('Password set')).toBeInTheDocument());
    expect(screen.getByText('No password')).toBeInTheDocument();
  });

  it('shows an error on 403', async () => {
    mock403();
    renderAdminPasswords();
    await waitFor(() => screen.getByPlaceholderText(/enter admin_secret/i));
    await userEvent.type(screen.getByPlaceholderText(/enter admin_secret/i), 'wrongsecret');
    fireEvent.click(screen.getByRole('button', { name: /load users/i }));
    await waitFor(() => expect(screen.getByText(/unauthorized/i)).toBeInTheDocument());
  });

  it('shows a network error message on fetch failure', async () => {
    vi.mocked(fetch).mockRejectedValueOnce(new Error('Network error'));
    renderAdminPasswords();
    await waitFor(() => screen.getByPlaceholderText(/enter admin_secret/i));
    await userEvent.type(screen.getByPlaceholderText(/enter admin_secret/i), 'mysecret');
    fireEvent.click(screen.getByRole('button', { name: /load users/i }));
    await waitFor(() => expect(screen.getByText(/network error/i)).toBeInTheDocument());
  });
});

describe('AdminPasswords — set password form', () => {
  beforeEach(async () => {
    localStorage.clear();
    vi.stubGlobal('fetch', vi.fn());
    // Render with the session-probe path: Admin in localStorage, probe succeeds
    localStorage.setItem('user_role', 'Admin');
  });
  afterEach(() => vi.unstubAllGlobals());

  async function renderWithUsers() {
    mockStatusOk();
    renderAdminPasswords();
    await waitFor(() => expect(screen.getByText('Password set')).toBeInTheDocument());
  }

  it('Set Password button is disabled until both a user and password are provided', async () => {
    await renderWithUsers();
    expect(screen.getByRole('button', { name: /set password/i })).toBeDisabled();
    await userEvent.selectOptions(screen.getByRole('combobox'), 'Bob');
    expect(screen.getByRole('button', { name: /set password/i })).toBeDisabled();
    await userEvent.type(screen.getByPlaceholderText(/new password/i), 'validpassword');
    expect(screen.getByRole('button', { name: /set password/i })).not.toBeDisabled();
  });

  it('shows an error when the password is too short', async () => {
    await renderWithUsers();
    await userEvent.selectOptions(screen.getByRole('combobox'), 'Bob');
    await userEvent.type(screen.getByPlaceholderText(/new password/i), 'short');
    await userEvent.click(screen.getByRole('button', { name: /set password/i }));
    await waitFor(() => expect(screen.getByText(/at least 8 characters/i)).toBeInTheDocument());
  });

  it('shows success and refreshes the list on a successful password set', async () => {
    await renderWithUsers();
    await userEvent.selectOptions(screen.getByRole('combobox'), 'Bob');
    await userEvent.type(screen.getByPlaceholderText(/new password/i), 'validpassword');
    mockSetPasswordOk('Bob');
    mockStatusOk(); // refresh after set
    await userEvent.click(screen.getByRole('button', { name: /set password/i }));
    await waitFor(() => expect(screen.getByText(/password set for bob/i)).toBeInTheDocument());
  });

  it('shows an error on 403 from set-password', async () => {
    await renderWithUsers();
    await userEvent.selectOptions(screen.getByRole('combobox'), 'Alice');
    await userEvent.type(screen.getByPlaceholderText(/new password/i), 'validpassword');
    mock403();
    await userEvent.click(screen.getByRole('button', { name: /set password/i }));
    await waitFor(() => expect(screen.getByText(/unauthorized/i)).toBeInTheDocument());
  });
});
