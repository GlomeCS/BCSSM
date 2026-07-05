import { test, expect, Page } from '@playwright/test';

async function setupDevotionPage(page: Page) {
  // Set localStorage before any page JS runs so auth check passes immediately
  await page.addInitScript(() => {
    localStorage.setItem('is_logged_in', 'true');
    localStorage.setItem('currentUser', 'Alice');
    localStorage.setItem('user_role', 'Team Member');
    localStorage.setItem('can_edit_all', 'false');
  });
  await page.route('**/api/auth/validate*', route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ is_valid: true, user_name: 'Alice', role: 'Team Member', section: 'Seniors', can_edit_all: false }),
    })
  );
  await page.goto('/react/devotion');
}

test('unauthenticated visit to /react/devotion redirects to /login', async ({ page }) => {
  await page.route('**/api/auth/validate*', route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ is_valid: false }),
    })
  );
  await page.goto('/react/devotion');
  await expect(page).toHaveURL('/login');
});

test('shows the devotion page heading', async ({ page }) => {
  await setupDevotionPage(page);
  await expect(page.getByRole('heading', { name: 'Team Devotional Resource' })).toBeVisible();
  await expect(page.getByText('Live in the Light')).toBeVisible();
});

test('nav link to the devotion tab is present with the correct href', async ({ page, isMobile }) => {
  test.skip(isMobile ?? false, 'Desktop nav links hidden on mobile');
  await setupDevotionPage(page);
  await expect(page.getByRole('link', { name: 'Devotion' })).toHaveAttribute('href', '/react/devotion');
});

test('renders the PDF viewer with at least one page', async ({ page }) => {
  await setupDevotionPage(page);
  await expect(page.locator('.pdf-page').first()).toBeVisible({ timeout: 15000 });
  await expect(page.locator('.pdf-document canvas').first()).toBeVisible({ timeout: 15000 });
});
