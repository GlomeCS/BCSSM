import { test, expect, Page } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  await page.route('**/get-users*', route =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ users: [] }) })
  );
});

const SECTIONS = ['Seniors', 'Juniors', 'Minis'];

const FEEDBACK_RESPONSE = {
  date: '2026-03-21',
  feedback: {
    Seniors: 'Great session today! Lots of energy and enthusiasm from the kids.',
    Juniors: null,
    Minis: 'Wonderful morning, everyone engaged well.',
  },
  user: { section: 'Seniors' },
  is_leader: true,
};

async function setupDevoFeedbackPage(page: Page, isLeader = true) {
  await page.addInitScript(({ leader }: { leader: boolean }) => {
    localStorage.setItem('is_logged_in', 'true');
    localStorage.setItem('currentUser', 'Alice');
    localStorage.setItem('user_role', leader ? 'Section Leader' : 'Leader');
    localStorage.setItem('is_leader', leader ? 'true' : 'false');
  }, { leader: isLeader });
  await page.route('**/api/auth/validate*', route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ is_valid: true, role: 'Section Leader', section: 'Seniors', is_leader: isLeader }),
    })
  );
  await page.route('**/api/sections*', route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(SECTIONS),
    })
  );
  await page.route('**/api/devos-feedback*', route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ...FEEDBACK_RESPONSE, is_leader: isLeader }),
    })
  );
  await page.goto('/react/devos-feedback');
}

test('unauthenticated visit to /react/devos-feedback redirects to /login', async ({ page }) => {
  await page.route('**/api/auth/validate*', route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ is_valid: false }),
    })
  );
  await page.goto('/react/devos-feedback');
  await expect(page).toHaveURL('/login');
});

test('shows page title and subtitle', async ({ page }) => {
  await setupDevoFeedbackPage(page);
  await expect(page.getByText("Devo's Feedback")).toBeVisible();
  await expect(page.getByText(/share your praise and prayer points/i)).toBeVisible();
});

test('shows a feedback card for each section', async ({ page }) => {
  await setupDevoFeedbackPage(page);
  for (const section of SECTIONS) {
    await expect(page.getByText(section)).toBeVisible();
  }
});

test('shows feedback text for sections that have it', async ({ page }) => {
  await setupDevoFeedbackPage(page);
  await expect(page.getByText('Great session today! Lots of energy and enthusiasm from the kids.')).toBeVisible();
  await expect(page.getByText('Wonderful morning, everyone engaged well.')).toBeVisible();
});

test('shows "No feedback submitted yet" for sections without feedback', async ({ page }) => {
  await setupDevoFeedbackPage(page);
  // Juniors has null feedback
  const juniorCard = page.locator('.feedback-card').filter({ hasText: 'Juniors' });
  await expect(juniorCard.getByText('No feedback submitted yet.')).toBeVisible();
});

test('shows Edit button on cards with existing feedback (for leader)', async ({ page }) => {
  await setupDevoFeedbackPage(page, true);
  const seniorsCard = page.locator('.feedback-card').filter({ hasText: 'Seniors' });
  await expect(seniorsCard.getByRole('link', { name: /edit/i })).toBeVisible();
});

test('shows Add button on cards without feedback (for leader)', async ({ page }) => {
  await setupDevoFeedbackPage(page, true);
  const juniorsCard = page.locator('.feedback-card').filter({ hasText: 'Juniors' });
  await expect(juniorsCard.getByRole('link', { name: /add/i })).toBeVisible();
});

test('Edit link points to the edit page with correct params', async ({ page }) => {
  await setupDevoFeedbackPage(page, true);
  const seniorsCard = page.locator('.feedback-card').filter({ hasText: 'Seniors' });
  const editLink = seniorsCard.getByRole('link', { name: /edit/i });
  const href = await editLink.getAttribute('href');
  expect(href).toContain('/react/devos-feedback/edit');
  expect(href).toContain('section=Seniors');
});

test('date input is visible and pre-filled', async ({ page }) => {
  await setupDevoFeedbackPage(page);
  const dateInput = page.locator('input[type="date"]');
  await expect(dateInput).toBeVisible();
  const value = await dateInput.inputValue();
  expect(value).toMatch(/^\d{4}-\d{2}-\d{2}$/);
});

test('Return to Home link is present', async ({ page }) => {
  await setupDevoFeedbackPage(page);
  await expect(page.getByRole('link', { name: /return to home/i })).toBeVisible();
});

test('devo feedback page visual snapshot - leader view', async ({ page }) => {
  await setupDevoFeedbackPage(page, true);
  await expect(page.getByText("Devo's Feedback")).toBeVisible();
  await expect(page).toHaveScreenshot('devo-feedback-leader.png', { fullPage: true });
});

test('devo feedback page visual snapshot - non-leader view', async ({ page }) => {
  await setupDevoFeedbackPage(page, false);
  await expect(page.getByText("Devo's Feedback")).toBeVisible();
  await expect(page).toHaveScreenshot('devo-feedback-non-leader.png', { fullPage: true });
});

test('devo feedback visual snapshot - mobile', async ({ page, isMobile }) => {
  test.skip(!isMobile, 'Mobile-only test');
  await setupDevoFeedbackPage(page, true);
  await expect(page.getByText("Devo's Feedback")).toBeVisible();
  await expect(page).toHaveScreenshot('devo-feedback-mobile.png', { fullPage: true });
});
