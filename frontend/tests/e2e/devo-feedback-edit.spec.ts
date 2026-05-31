import { test, expect, Page } from '@playwright/test';

const EDIT_URL = '/react/devos-feedback/edit?date=2026-03-21&section=Seniors';

const EXISTING_FEEDBACK_RESPONSE = {
  date: '2026-03-21',
  feedback: {
    Seniors: 'Existing feedback text already here.',
  },
  user: { section: 'Seniors' },
  is_leader: true,
};

async function setupEditPage(page: Page, existingFeedback = 'Existing feedback text already here.') {
  await page.addInitScript(() => {
    localStorage.setItem('is_logged_in', 'true');
    localStorage.setItem('currentUser', 'Alice');
    localStorage.setItem('user_role', 'Section Leader');
    localStorage.setItem('is_leader', 'true');
  });
  await page.route('**/api/auth/validate*', route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ is_valid: true, role: 'Section Leader', section: 'Seniors', is_leader: true }),
    })
  );
  await page.route('**/api/devos-feedback/edit*', route => {
    if (route.request().method() === 'POST') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true }),
      });
    }
    return route.continue();
  });
  await page.route('**/api/devos-feedback*', route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ...EXISTING_FEEDBACK_RESPONSE,
        feedback: { Seniors: existingFeedback },
      }),
    })
  );
  await page.goto(EDIT_URL);
}

test('unauthenticated visit to edit page redirects to /login', async ({ page }) => {
  await page.route('**/api/auth/validate*', route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ is_valid: false }),
    })
  );
  await page.goto(EDIT_URL);
  await expect(page).toHaveURL('/login');
});

test('shows error when date or section params are missing', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('is_logged_in', 'true');
    localStorage.setItem('currentUser', 'Alice');
    localStorage.setItem('user_role', 'Section Leader');
    localStorage.setItem('is_leader', 'true');
  });
  await page.route('**/api/auth/validate*', route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ is_valid: true, role: 'Section Leader', section: 'Seniors', is_leader: true }),
    })
  );
  await page.goto('/react/devos-feedback/edit');
  await expect(page.getByText(/missing date or section parameters/i)).toBeVisible();
});

test('shows section and date info in the header', async ({ page }) => {
  await setupEditPage(page);
  await expect(page.getByText('Seniors')).toBeVisible();
  // Date is formatted e.g. "Saturday, 21 March 2026"
  await expect(page.getByText(/March 2026/i)).toBeVisible();
});

test('loads existing feedback into the textarea', async ({ page }) => {
  await setupEditPage(page);
  const textarea = page.locator('textarea#feedbackArea');
  await expect(textarea).toBeVisible();
  await expect(textarea).toHaveValue('Existing feedback text already here.');
});

test('character counter updates as the user types', async ({ page }) => {
  await setupEditPage(page);
  const textarea = page.locator('textarea#feedbackArea');
  await textarea.clear();
  await textarea.fill('Hello world');
  await expect(page.getByText('11 / 140')).toBeVisible();
});

test('Save button is disabled when textarea is empty', async ({ page }) => {
  await setupEditPage(page, '');
  const textarea = page.locator('textarea#feedbackArea');
  await textarea.clear();
  await expect(page.getByRole('button', { name: /save feedback/i })).toBeDisabled();
});

test('Save button is enabled when textarea has content', async ({ page }) => {
  await setupEditPage(page);
  await expect(page.getByRole('button', { name: /save feedback/i })).toBeEnabled();
});

test('Cancel button navigates back to the feedback view', async ({ page }) => {
  await page.route('**/api/sections*', route =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(['Seniors', 'Juniors']) })
  );
  await page.route('**/api/devos-feedback*', route => {
    if (route.request().url().includes('/edit')) return route.continue();
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ...EXISTING_FEEDBACK_RESPONSE, feedback: { Seniors: 'text' } }),
    });
  });
  await setupEditPage(page);
  await page.getByRole('button', { name: /cancel/i }).click();
  await expect(page).toHaveURL(/\/react\/devos-feedback/);
});

test('saving feedback navigates back to the feedback view', async ({ page }) => {
  // Mock sections and feedback GET for the view page after redirect
  await page.route('**/api/sections*', route =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(['Seniors', 'Juniors']) })
  );
  await setupEditPage(page);

  const textarea = page.locator('textarea#feedbackArea');
  await textarea.fill('Updated feedback content for today.');
  await page.getByRole('button', { name: /save feedback/i }).click();
  await expect(page).toHaveURL(/\/react\/devos-feedback/);
});

test('devo feedback edit page visual snapshot', async ({ page }) => {
  await setupEditPage(page);
  await expect(page.locator('textarea#feedbackArea')).toBeVisible();
  await expect(page).toHaveScreenshot('devo-feedback-edit.png', { fullPage: true });
});

test('devo feedback edit page visual snapshot - mobile', async ({ page, isMobile }) => {
  test.skip(!isMobile, 'Mobile-only test');
  await setupEditPage(page);
  await expect(page.locator('textarea#feedbackArea')).toBeVisible();
  await expect(page).toHaveScreenshot('devo-feedback-edit-mobile.png', { fullPage: true });
});
