import { test, expect, Page } from '@playwright/test';

async function loginAs(page: Page, role = 'Team Member', isLeader = false) {
  await page.route('**/api/auth/validate*', route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ is_valid: true, role, section: 'Seniors', can_edit_all: isLeader }),
    })
  );
  await page.route('**/duty-teams*', route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ user: 'Alice', duty_message: 'Setup', role }),
    })
  );

  await page.goto('/');
  await page.evaluate(
    ({ r, leader }) => {
      localStorage.setItem('is_logged_in', 'true');
      localStorage.setItem('currentUser', 'Alice');
      localStorage.setItem('user_role', r);
      localStorage.setItem('can_edit_all', leader ? 'true' : 'false');
    },
    { r: role, leader: isLeader }
  );
  await page.reload();
}

test('unauthenticated visit to / redirects to /login', async ({ page }) => {
  // Intercept validate to return invalid so any stale storage gets cleared
  await page.route('**/api/auth/validate*', route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ is_valid: false }),
    })
  );
  await page.goto('/');
  await expect(page).toHaveURL('/login');
});

test('home page shows duty message for logged-in user', async ({ page }) => {
  await loginAs(page);
  await expect(page.getByText(/your duty today is Setup/i)).toBeVisible();
});

test('home page shows bank details for regular team members', async ({ page }) => {
  await loginAs(page, 'Team Member');
  await expect(page.getByText(/Ballyholme CSSM Bank Account/i)).toBeVisible();
  await expect(page.getByText('98-00-30')).toBeVisible();
});

test('home page shows receipt link for section leaders', async ({ page }) => {
  await loginAs(page, 'Section Leader', true);
  await expect(page.getByText(/Receipts & Expenses/i)).toBeVisible();
  await expect(page.getByRole('link', { name: /submit receipt/i })).toBeVisible();
});

test('home page visual snapshot - team member', async ({ page }) => {
  await loginAs(page, 'Team Member');
  await expect(page.getByText(/Good mae/i)).toBeVisible();
  await expect(page).toHaveScreenshot('home-team-member.png', { fullPage: true });
});

test('home page visual snapshot - section leader', async ({ page }) => {
  await loginAs(page, 'Section Leader', true);
  await expect(page.getByText(/Receipts & Expenses/i)).toBeVisible();
  await expect(page).toHaveScreenshot('home-section-leader.png', { fullPage: true });
});

test('navbar brand link is visible', async ({ page }) => {
  await loginAs(page);
  await expect(page.getByRole('link', { name: 'Ballyholme CSSM Helper' })).toBeVisible();
});

test('navbar contains correct links (desktop)', async ({ page, isMobile }) => {
  test.skip(isMobile ?? false, 'Desktop nav links hidden on mobile');
  await loginAs(page);
  await expect(page.getByRole('link', { name: 'Duties' })).toHaveAttribute('href', '/duties');
  await expect(page.getByRole('link', { name: 'Sections' })).toHaveAttribute('href', '/sections');
});

test('logout clears session and redirects to login', async ({ page, isMobile }) => {
  await loginAs(page);
  await page.route('**/get-users*', route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ users: ['Alice'] }),
    })
  );
  // On mobile the logout button is inside the hamburger menu
  if (isMobile) {
    await page.getByRole('button', { name: /toggle navigation menu/i }).click();
    await page.getByRole('button', { name: /logout/i }).click();
  } else {
    await page.getByRole('button', { name: /logout/i }).first().click();
  }
  await expect(page).toHaveURL('/login');
  const currentUser = await page.evaluate(() => localStorage.getItem('currentUser'));
  expect(currentUser).toBeNull();
});
