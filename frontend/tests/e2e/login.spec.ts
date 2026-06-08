import { test, expect } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  // Mock the /get-users API so the page loads without a running backend
  await page.route('**/get-users*', route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ users: ['Alice', 'Bob', 'Carol'] }),
    })
  );
});

test('login page shows the user select and continue button', async ({ page }) => {
  await page.goto('/login');
  await expect(page.getByText('Welcome Back')).toBeVisible();
  await expect(page.getByRole('combobox')).toBeVisible();
  await expect(page.getByRole('button', { name: /continue/i })).toBeDisabled();
});

test('login page visual snapshot', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/login');
  await expect(page.getByRole('combobox')).toBeVisible();
  await expect(page).toHaveScreenshot('login-page.png', { fullPage: true, maxDiffPixels: 200 });
});

test('selecting a user and entering a password enables the continue button', async ({ page }) => {
  await page.goto('/login');
  await page.waitForSelector('select.user-select');
  await page.selectOption('select.user-select', 'Alice');
  // Button stays disabled until a password is also entered
  await expect(page.getByRole('button', { name: /continue/i })).toBeDisabled();
  await page.fill('input[type="password"]', 'secret123');
  await expect(page.getByRole('button', { name: /continue/i })).toBeEnabled();
});

test('redirects to home when already logged in', async ({ page }) => {
  // Pre-seed localStorage as if logged in
  await page.goto('/login');
  await page.evaluate(() => {
    localStorage.setItem('is_logged_in', 'true');
    localStorage.setItem('currentUser', 'Alice');
  });

  // Mock validate auth for Home page
  await page.route('**/api/auth/validate*', route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ is_valid: true, role: 'Team Member', section: 'Seniors', can_edit_all: false }),
    })
  );
  await page.route('**/duty-teams*', route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ user: 'Alice', duty_message: null, role: 'Team Member' }),
    })
  );

  await page.goto('/login');
  await expect(page).toHaveURL('/');
});
