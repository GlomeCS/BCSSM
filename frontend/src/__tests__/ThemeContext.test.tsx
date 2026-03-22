import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { ThemeProvider } from '../ThemeContext';
import { useTheme } from '../useTheme';

// Helper to create a matchMedia mock that captures the 'change' listener
function mockMatchMediaWithListener(initialDark: boolean) {
  let changeHandler: ((e: Partial<MediaQueryListEvent>) => void) | null = null;
  const removeEventListenerMock = vi.fn();
  vi.spyOn(window, 'matchMedia').mockImplementation((query: string) => ({
    matches: query === '(prefers-color-scheme: dark)' ? initialDark : false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn().mockImplementation(
      (_event: string, handler: (e: Partial<MediaQueryListEvent>) => void) => {
        changeHandler = handler;
      }
    ),
    removeEventListener: removeEventListenerMock,
    dispatchEvent: vi.fn(),
  } as unknown as MediaQueryList));
  return {
    fireChange: (matches: boolean) => act(() => { changeHandler?.({ matches }); }),
    removeEventListenerMock,
    getHandler: () => changeHandler,
  };
}

// Helper component that exposes theme state
function ThemeDisplay() {
  const { theme, toggleTheme } = useTheme();
  return (
    <div>
      <span data-testid="theme">{theme}</span>
      <button onClick={toggleTheme}>Toggle</button>
    </div>
  );
}

function renderWithProvider() {
  return render(
    <ThemeProvider>
      <ThemeDisplay />
    </ThemeProvider>
  );
}

describe('ThemeContext', () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute('data-theme');
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('initial theme detection', () => {
    it('defaults to light when no localStorage value and system is light', () => {
      renderWithProvider();
      expect(screen.getByTestId('theme')).toHaveTextContent('light');
    });

    it('defaults to dark when no localStorage value and system prefers dark', () => {
      mockMatchMediaWithListener(true);
      renderWithProvider();
      expect(screen.getByTestId('theme')).toHaveTextContent('dark');
    });

    it('reads saved light theme from localStorage', () => {
      localStorage.setItem('theme', 'light');
      renderWithProvider();
      expect(screen.getByTestId('theme')).toHaveTextContent('light');
    });

    it('reads saved dark theme from localStorage', () => {
      localStorage.setItem('theme', 'dark');
      renderWithProvider();
      expect(screen.getByTestId('theme')).toHaveTextContent('dark');
    });

    it('ignores invalid localStorage values and falls back to system', () => {
      localStorage.setItem('theme', 'invalid');
      renderWithProvider();
      expect(screen.getByTestId('theme')).toHaveTextContent('light');
    });
  });

  describe('toggleTheme', () => {
    it('toggles from light to dark', () => {
      renderWithProvider();
      expect(screen.getByTestId('theme')).toHaveTextContent('light');
      fireEvent.click(screen.getByRole('button', { name: 'Toggle' }));
      expect(screen.getByTestId('theme')).toHaveTextContent('dark');
    });

    it('toggles from dark to light', () => {
      localStorage.setItem('theme', 'dark');
      renderWithProvider();
      expect(screen.getByTestId('theme')).toHaveTextContent('dark');
      fireEvent.click(screen.getByRole('button', { name: 'Toggle' }));
      expect(screen.getByTestId('theme')).toHaveTextContent('light');
    });

    it('can toggle multiple times', () => {
      renderWithProvider();
      const toggle = screen.getByRole('button', { name: 'Toggle' });
      fireEvent.click(toggle);
      expect(screen.getByTestId('theme')).toHaveTextContent('dark');
      fireEvent.click(toggle);
      expect(screen.getByTestId('theme')).toHaveTextContent('light');
      fireEvent.click(toggle);
      expect(screen.getByTestId('theme')).toHaveTextContent('dark');
    });
  });

  describe('DOM side effects', () => {
    it('sets data-theme attribute on documentElement', () => {
      renderWithProvider();
      expect(document.documentElement).toHaveAttribute('data-theme', 'light');
    });

    it('updates data-theme to dark after toggle', () => {
      renderWithProvider();
      fireEvent.click(screen.getByRole('button', { name: 'Toggle' }));
      expect(document.documentElement).toHaveAttribute('data-theme', 'dark');
    });

    it('sets data-theme to dark when starting in dark mode', () => {
      localStorage.setItem('theme', 'dark');
      renderWithProvider();
      expect(document.documentElement).toHaveAttribute('data-theme', 'dark');
    });
  });

  describe('localStorage persistence', () => {
    it('persists light theme to localStorage', () => {
      renderWithProvider();
      expect(localStorage.getItem('theme')).toBe('light');
    });

    it('persists dark theme to localStorage after toggle', () => {
      renderWithProvider();
      fireEvent.click(screen.getByRole('button', { name: 'Toggle' }));
      expect(localStorage.getItem('theme')).toBe('dark');
    });

    it('persists light theme to localStorage after toggling back', () => {
      localStorage.setItem('theme', 'dark');
      renderWithProvider();
      fireEvent.click(screen.getByRole('button', { name: 'Toggle' }));
      expect(localStorage.getItem('theme')).toBe('light');
    });
  });

  describe('default context value', () => {
    it('useTheme returns light theme when used outside provider', () => {
      render(<ThemeDisplay />);
      expect(screen.getByTestId('theme')).toHaveTextContent('light');
    });
  });

  describe('real-time OS preference sync', () => {
    it('switches to dark when OS changes to dark', () => {
      const { fireChange } = mockMatchMediaWithListener(false);
      renderWithProvider();
      expect(screen.getByTestId('theme')).toHaveTextContent('light');
      fireChange(true);
      expect(screen.getByTestId('theme')).toHaveTextContent('dark');
    });

    it('switches to light when OS changes to light', () => {
      const { fireChange } = mockMatchMediaWithListener(true);
      renderWithProvider();
      expect(screen.getByTestId('theme')).toHaveTextContent('dark');
      fireChange(false);
      expect(screen.getByTestId('theme')).toHaveTextContent('light');
    });

    it('OS change overrides a previous manual toggle', () => {
      const { fireChange } = mockMatchMediaWithListener(false);
      renderWithProvider();
      fireEvent.click(screen.getByRole('button', { name: 'Toggle' }));
      expect(screen.getByTestId('theme')).toHaveTextContent('dark');
      fireChange(false); // OS says light
      expect(screen.getByTestId('theme')).toHaveTextContent('light');
    });

    it('updates localStorage when OS changes theme', () => {
      const { fireChange } = mockMatchMediaWithListener(false);
      renderWithProvider();
      fireChange(true);
      expect(localStorage.getItem('theme')).toBe('dark');
    });

    it('updates data-theme attribute when OS changes', () => {
      const { fireChange } = mockMatchMediaWithListener(false);
      renderWithProvider();
      fireChange(true);
      expect(document.documentElement).toHaveAttribute('data-theme', 'dark');
    });

    it('removes the OS preference listener on unmount', () => {
      const { removeEventListenerMock, getHandler } = mockMatchMediaWithListener(false);
      const { unmount } = renderWithProvider();
      const handler = getHandler();
      expect(handler).not.toBeNull();
      unmount();
      expect(removeEventListenerMock).toHaveBeenCalledWith('change', handler);
    });
  });
});
