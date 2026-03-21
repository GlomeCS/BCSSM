import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Home from '../Home';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

function renderHome() {
  return render(
    <MemoryRouter>
      <Home />
    </MemoryRouter>
  );
}

function setupLoggedInUser(overrides: Record<string, string> = {}) {
  const defaults = {
    is_logged_in: 'true',
    currentUser: 'Alice',
    user_role: 'Team Member',
    is_leader: 'false',
  };
  Object.entries({ ...defaults, ...overrides }).forEach(([k, v]) =>
    localStorage.setItem(k, v)
  );
}

function mockValidateAuthSuccess(role = 'Team Member', isLeader = false) {
  vi.mocked(fetch).mockResolvedValueOnce(
    new Response(
      JSON.stringify({ is_valid: true, role, section: 'Seniors', is_leader: isLeader }),
      { headers: { 'Content-Type': 'application/json' } }
    )
  );
}

function mockDutyResponse(dutyMessage: string | null = null, role = 'Team Member') {
  vi.mocked(fetch).mockResolvedValueOnce(
    new Response(
      JSON.stringify({ user: 'Alice', duty_message: dutyMessage, role }),
      { headers: { 'Content-Type': 'application/json' } }
    )
  );
}

describe('Home', () => {
  beforeEach(() => {
    localStorage.clear();
    mockNavigate.mockClear();
    vi.stubGlobal('fetch', vi.fn());
  });
  afterEach(() => vi.unstubAllGlobals());

  it('redirects to /login when not logged in', async () => {
    renderHome();
    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith('/login'));
  });

  it('shows loading spinner initially', () => {
    setupLoggedInUser();
    // Keep fetch pending
    vi.mocked(fetch).mockReturnValue(new Promise(() => {}));
    renderHome();
    expect(screen.getByText(/loading your dashboard/i)).toBeInTheDocument();
  });

  it('redirects to /login when auth validation fails', async () => {
    setupLoggedInUser();
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ is_valid: false }), {
        headers: { 'Content-Type': 'application/json' },
      })
    );
    renderHome();
    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith('/login'));
  });

  it('shows the user name and welcome message after loading', async () => {
    setupLoggedInUser();
    mockValidateAuthSuccess();
    mockDutyResponse(null);
    renderHome();
    await waitFor(() => expect(screen.getByText(/good mae/i)).toBeInTheDocument());
    expect(screen.getByText('Alice')).toBeInTheDocument();
  });

  it('shows no duty message when none is assigned', async () => {
    setupLoggedInUser();
    mockValidateAuthSuccess();
    mockDutyResponse(null);
    renderHome();
    await waitFor(() =>
      expect(screen.getByText(/no duty assigned today/i)).toBeInTheDocument()
    );
  });

  it('shows the duty message when one is assigned', async () => {
    setupLoggedInUser();
    mockValidateAuthSuccess();
    mockDutyResponse('Setup');
    renderHome();
    await waitFor(() =>
      expect(screen.getByText(/your duty today is Setup/i)).toBeInTheDocument()
    );
  });

  it('shows bank details for regular team members', async () => {
    setupLoggedInUser({ user_role: 'Team Member' });
    mockValidateAuthSuccess('Team Member');
    mockDutyResponse();
    renderHome();
    await waitFor(() =>
      expect(screen.getByText(/Ballyholme CSSM Bank Account/i)).toBeInTheDocument()
    );
    expect(screen.getByText('Scripture Union Northern Ireland')).toBeInTheDocument();
  });

  it('shows Receipts & Expenses link for Section Leaders', async () => {
    setupLoggedInUser({ user_role: 'Section Leader' });
    mockValidateAuthSuccess('Section Leader');
    mockDutyResponse(null, 'Section Leader');
    renderHome();
    await waitFor(() =>
      expect(screen.getByText(/Receipts & Expenses/i)).toBeInTheDocument()
    );
    expect(screen.getByRole('link', { name: /submit receipt/i })).toBeInTheDocument();
  });

  it('shows Receipts & Expenses link for Admins', async () => {
    setupLoggedInUser({ user_role: 'Admin' });
    mockValidateAuthSuccess('Admin');
    mockDutyResponse(null, 'Admin');
    renderHome();
    await waitFor(() =>
      expect(screen.getByText(/Receipts & Expenses/i)).toBeInTheDocument()
    );
  });
});
