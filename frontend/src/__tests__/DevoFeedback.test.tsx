import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import DevoFeedback from '../DevoFeedback';

const SECTIONS = ['Seniors', 'Juniors', 'Minis'];

const FEEDBACK_RESPONSE = {
  date: '2026-03-21',
  feedback: {
    Seniors: 'Great session today! Lots of energy and enthusiasm.',
    Juniors: null,
    Minis: 'Wonderful morning, everyone engaged well.',
  },
  user: { section: 'Seniors' },
  is_leader: true,
};

const mockNavigate = vi.fn();

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

function setupMockFetch(isLeader = true) {
  vi.mocked(fetch).mockImplementation((input: RequestInfo | URL) => {
    const url = input.toString();
    if (url.includes('/api/auth/validate')) {
      return Promise.resolve(
        new Response(
          JSON.stringify({ is_valid: true, role: 'Section Leader', section: 'Seniors', is_leader: isLeader }),
          { headers: { 'Content-Type': 'application/json' } }
        )
      );
    }
    if (url.includes('/api/sections')) {
      return Promise.resolve(
        new Response(JSON.stringify(SECTIONS), { headers: { 'Content-Type': 'application/json' } })
      );
    }
    if (url.includes('/api/devos-feedback')) {
      return Promise.resolve(
        new Response(
          JSON.stringify({ ...FEEDBACK_RESPONSE, is_leader: isLeader }),
          { headers: { 'Content-Type': 'application/json' } }
        )
      );
    }
    return Promise.reject(new Error(`Unmocked fetch: ${url}`));
  });
}

function renderDevoFeedback(initialPath = '/react/devos-feedback') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <DevoFeedback />
    </MemoryRouter>
  );
}

async function waitForLoad() {
  await waitFor(() => expect(screen.getByText('Seniors')).toBeInTheDocument());
}

describe('DevoFeedback', () => {
  beforeEach(() => {
    localStorage.clear();
    localStorage.setItem('is_logged_in', 'true');
    localStorage.setItem('currentUser', 'Alice');
    localStorage.setItem('user_role', 'Section Leader');
    localStorage.setItem('is_leader', 'true');
    mockNavigate.mockClear();
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => vi.unstubAllGlobals());

  it('renders all section cards after loading', async () => {
    setupMockFetch();
    renderDevoFeedback();
    await waitForLoad();
    for (const section of SECTIONS) {
      expect(screen.getByText(section)).toBeInTheDocument();
    }
  });

  it('clicking a card body enters focus mode', async () => {
    setupMockFetch();
    renderDevoFeedback();
    await waitForLoad();

    fireEvent.click(screen.getByRole('button', { name: /view seniors feedback in focus mode/i }));

    await waitFor(() => expect(screen.getByRole('dialog')).toBeInTheDocument());
    expect(screen.getByRole('dialog')).toHaveAttribute('aria-label', 'Seniors feedback');
  });

  it('focus overlay shows section name and feedback text', async () => {
    setupMockFetch();
    renderDevoFeedback();
    await waitForLoad();

    fireEvent.click(screen.getByRole('button', { name: /view seniors feedback in focus mode/i }));

    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText('Great session today! Lots of energy and enthusiasm.')).toBeInTheDocument();
  });

  it('close button exits focus mode', async () => {
    setupMockFetch();
    renderDevoFeedback();
    await waitForLoad();

    fireEvent.click(screen.getByRole('button', { name: /view seniors feedback in focus mode/i }));
    await waitFor(() => expect(screen.getByRole('dialog')).toBeInTheDocument());

    fireEvent.click(screen.getByRole('button', { name: /close focus view/i }));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  });

  it('Escape key exits focus mode', async () => {
    setupMockFetch();
    renderDevoFeedback();
    await waitForLoad();

    fireEvent.click(screen.getByRole('button', { name: /view seniors feedback in focus mode/i }));
    await waitFor(() => expect(screen.getByRole('dialog')).toBeInTheDocument());

    fireEvent.keyDown(window, { key: 'Escape' });
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  });

  it('next button navigates to the next section', async () => {
    setupMockFetch();
    renderDevoFeedback();
    await waitForLoad();

    fireEvent.click(screen.getByRole('button', { name: /view seniors feedback in focus mode/i }));
    await waitFor(() => expect(screen.getByRole('dialog')).toHaveAttribute('aria-label', 'Seniors feedback'));

    fireEvent.click(screen.getByRole('button', { name: /next section/i }));
    await waitFor(() => expect(screen.getByRole('dialog')).toHaveAttribute('aria-label', 'Juniors feedback'));
  });

  it('prev button navigates to the previous section', async () => {
    setupMockFetch();
    renderDevoFeedback();
    await waitForLoad();

    fireEvent.click(screen.getByRole('button', { name: /view juniors feedback in focus mode/i }));
    await waitFor(() => expect(screen.getByRole('dialog')).toHaveAttribute('aria-label', 'Juniors feedback'));

    fireEvent.click(screen.getByRole('button', { name: /previous section/i }));
    await waitFor(() => expect(screen.getByRole('dialog')).toHaveAttribute('aria-label', 'Seniors feedback'));
  });

  it('prev button wraps to last section from first', async () => {
    setupMockFetch();
    renderDevoFeedback();
    await waitForLoad();

    fireEvent.click(screen.getByRole('button', { name: /view seniors feedback in focus mode/i }));
    await waitFor(() => expect(screen.getByRole('dialog')).toHaveAttribute('aria-label', 'Seniors feedback'));

    fireEvent.click(screen.getByRole('button', { name: /previous section/i }));
    await waitFor(() => expect(screen.getByRole('dialog')).toHaveAttribute('aria-label', 'Minis feedback'));
  });

  it('next button wraps to first section from last', async () => {
    setupMockFetch();
    renderDevoFeedback();
    await waitForLoad();

    fireEvent.click(screen.getByRole('button', { name: /view minis feedback in focus mode/i }));
    await waitFor(() => expect(screen.getByRole('dialog')).toHaveAttribute('aria-label', 'Minis feedback'));

    fireEvent.click(screen.getByRole('button', { name: /next section/i }));
    await waitFor(() => expect(screen.getByRole('dialog')).toHaveAttribute('aria-label', 'Seniors feedback'));
  });

  it('section URL param on mount restores focus mode', async () => {
    setupMockFetch();
    renderDevoFeedback('/react/devos-feedback?section=Minis');
    await waitForLoad();

    await waitFor(() => expect(screen.getByRole('dialog')).toHaveAttribute('aria-label', 'Minis feedback'));
  });

  it('empty section is expandable and shows empty state in focus mode', async () => {
    setupMockFetch();
    renderDevoFeedback();
    await waitForLoad();

    fireEvent.click(screen.getByRole('button', { name: /view juniors feedback in focus mode/i }));
    await waitFor(() => expect(screen.getByRole('dialog')).toBeInTheDocument());

    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveTextContent('No feedback submitted yet.');
  });

  it('shows position indicator in focus nav', async () => {
    setupMockFetch();
    renderDevoFeedback();
    await waitForLoad();

    fireEvent.click(screen.getByRole('button', { name: /view seniors feedback in focus mode/i }));
    await waitFor(() => expect(screen.getByRole('dialog')).toBeInTheDocument());

    expect(screen.getByText(`1 / ${SECTIONS.length}`)).toBeInTheDocument();
  });
});
