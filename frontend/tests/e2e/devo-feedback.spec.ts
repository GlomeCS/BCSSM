import { test, expect, Page } from '@playwright/test';

const SECTIONS = ['Seniors', 'Juniors', 'Minis'];

const FEEDBACK_RESPONSE = {
  date: '2026-03-21',
  feedback: {
    Seniors: 'Great session today! Lots of energy and enthusiasm from the kids.',
    Juniors: null,
    Minis: 'Wonderful morning, everyone engaged well.',
  },
  user: { section: 'Seniors' },
  can_edit_all: true,
};

async function setupDevoFeedbackPage(page: Page, isLeader = true, path = '/react/devos-feedback') {
  await page.addInitScript(({ leader }: { leader: boolean }) => {
    localStorage.setItem('is_logged_in', 'true');
    localStorage.setItem('currentUser', 'Alice');
    localStorage.setItem('user_role', leader ? 'Section Leader' : 'Leader');
    localStorage.setItem('can_edit_all', leader ? 'true' : 'false');
  }, { leader: isLeader });
  await page.route('**/api/auth/validate*', route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ is_valid: true, user_name: 'Alice', role: isLeader ? 'Section Leader' : 'Leader', section: 'Seniors', can_edit_all: isLeader }),
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
      body: JSON.stringify({ ...FEEDBACK_RESPONSE, can_edit_all: isLeader }),
    })
  );
  await page.goto(path);
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

// ── Focus mode ────────────────────────────────────────────────────────────

test('clicking a card body enters focus mode', async ({ page }) => {
  await setupDevoFeedbackPage(page);
  const seniorsCard = page.locator('.feedback-card').filter({ hasText: 'Seniors' });
  await seniorsCard.locator('.feedback-card-body').click();
  await expect(page.locator('.focus-overlay')).toBeVisible();
  await expect(page.locator('.focus-section-title')).toHaveText('Seniors');
});

test('close button exits focus mode', async ({ page }) => {
  await setupDevoFeedbackPage(page);
  const seniorsCard = page.locator('.feedback-card').filter({ hasText: 'Seniors' });
  await seniorsCard.locator('.feedback-card-body').click();
  await expect(page.locator('.focus-overlay')).toBeVisible();
  await page.locator('.focus-close-btn').click();
  await expect(page.locator('.focus-overlay')).not.toBeVisible();
});

test('next button navigates to next section in focus mode', async ({ page }) => {
  await setupDevoFeedbackPage(page);
  const seniorsCard = page.locator('.feedback-card').filter({ hasText: 'Seniors' });
  await seniorsCard.locator('.feedback-card-body').click();
  await expect(page.locator('.focus-section-title')).toHaveText('Seniors');
  await page.locator('button[aria-label="Next section"]').click();
  await expect(page.locator('.focus-section-title')).toHaveText('Juniors');
});

test('prev button navigates to prev section in focus mode', async ({ page }) => {
  await setupDevoFeedbackPage(page);
  const juniorsCard = page.locator('.feedback-card').filter({ hasText: 'Juniors' });
  await juniorsCard.locator('.feedback-card-body').click();
  await expect(page.locator('.focus-section-title')).toHaveText('Juniors');
  await page.locator('button[aria-label="Previous section"]').click();
  await expect(page.locator('.focus-section-title')).toHaveText('Seniors');
});

test('direct URL with section param opens focus mode', async ({ page }) => {
  await setupDevoFeedbackPage(page);
  await page.goto('/react/devos-feedback?section=Minis');
  await expect(page.locator('.focus-overlay')).toBeVisible();
  await expect(page.locator('.focus-section-title')).toHaveText('Minis');
});

test('empty section card is expandable in focus mode', async ({ page }) => {
  await setupDevoFeedbackPage(page);
  const juniorsCard = page.locator('.feedback-card').filter({ hasText: 'Juniors' });
  await juniorsCard.locator('.feedback-card-body').click();
  await expect(page.locator('.focus-overlay')).toBeVisible();
  await expect(page.locator('.focus-overlay')).toContainText('No feedback submitted yet.');
});

test('focus mode visual snapshot', async ({ page }) => {
  await setupDevoFeedbackPage(page, true);
  const seniorsCard = page.locator('.feedback-card').filter({ hasText: 'Seniors' });
  await seniorsCard.locator('.feedback-card-body').click();
  await expect(page.locator('.focus-overlay')).toBeVisible();
  await expect(page).toHaveScreenshot('devo-feedback-focus.png', { fullPage: true });
});

// ── Split view ─────────────────────────────────────────────────────────────

test('+ Split button appears in single-section focus mode', async ({ page }) => {
  await setupDevoFeedbackPage(page);
  const seniorsCard = page.locator('.feedback-card').filter({ hasText: 'Seniors' });
  await seniorsCard.locator('.feedback-card-body').click();
  await expect(page.locator('.focus-overlay')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Split view' })).toBeVisible();
});

test('clicking + Split opens a section picker', async ({ page }) => {
  await setupDevoFeedbackPage(page);
  const seniorsCard = page.locator('.feedback-card').filter({ hasText: 'Seniors' });
  await seniorsCard.locator('.feedback-card-body').click();
  await page.getByRole('button', { name: 'Split view' }).click();
  await expect(page.getByRole('listbox', { name: /add section to split view/i })).toBeVisible();
});

test('picker lists only sections not already in the view', async ({ page }) => {
  await setupDevoFeedbackPage(page);
  const seniorsCard = page.locator('.feedback-card').filter({ hasText: 'Seniors' });
  await seniorsCard.locator('.feedback-card-body').click();
  await page.getByRole('button', { name: 'Split view' }).click();
  const picker = page.getByRole('listbox', { name: /add section to split view/i });
  await expect(picker.getByRole('option', { name: 'Juniors' })).toBeVisible();
  await expect(picker.getByRole('option', { name: 'Minis' })).toBeVisible();
  await expect(picker.getByRole('option', { name: 'Seniors' })).not.toBeVisible();
});

test('selecting a section from the picker enters 2-column split view', async ({ page }) => {
  await setupDevoFeedbackPage(page);
  const seniorsCard = page.locator('.feedback-card').filter({ hasText: 'Seniors' });
  await seniorsCard.locator('.feedback-card-body').click();
  await page.getByRole('button', { name: 'Split view' }).click();
  await page.getByRole('option', { name: 'Juniors' }).click();
  await expect(page.getByRole('dialog')).toHaveAttribute('aria-label', 'Comparing Seniors, Juniors');
});

test('2-column split view shows both sections content', async ({ page }) => {
  await setupDevoFeedbackPage(page, true, '/react/devos-feedback?section=Seniors,Juniors');
  await expect(page.getByRole('dialog')).toBeVisible();
  await expect(page.locator('.focus-column-body').filter({ hasText: /great session today/i })).toBeVisible();
  await expect(page.locator('.focus-column-body').filter({ hasText: /no feedback submitted yet/i })).toBeVisible();
});

test('2-column split view shows breadcrumb with section names', async ({ page }) => {
  await setupDevoFeedbackPage(page, true, '/react/devos-feedback?section=Seniors,Juniors');
  await expect(page.getByRole('dialog')).toBeVisible();
  await expect(page.locator('.focus-split-breadcrumb')).toHaveText('Seniors · Juniors');
});

test('nav slides the window in 2-column split view', async ({ page }) => {
  await setupDevoFeedbackPage(page, true, '/react/devos-feedback?section=Seniors,Juniors');
  await expect(page.getByRole('dialog')).toHaveAttribute('aria-label', 'Comparing Seniors, Juniors');
  await page.getByRole('button', { name: 'Next section' }).click();
  await expect(page.getByRole('dialog')).toHaveAttribute('aria-label', 'Comparing Juniors, Minis');
});

test('close button exits split view', async ({ page }) => {
  await setupDevoFeedbackPage(page, true, '/react/devos-feedback?section=Seniors,Juniors');
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.getByRole('button', { name: 'Close focus view' }).click();
  await expect(page.getByRole('dialog')).not.toBeVisible();
});

test('direct URL with comma-separated sections opens split view', async ({ page }) => {
  await setupDevoFeedbackPage(page);
  await page.goto('/react/devos-feedback?section=Seniors,Minis');
  await expect(page.getByRole('dialog')).toHaveAttribute('aria-label', 'Comparing Seniors, Minis');
  await expect(page.locator('.focus-column')).toHaveCount(2);
});

test('picker in 2-column view only shows the remaining section', async ({ page }) => {
  await setupDevoFeedbackPage(page, true, '/react/devos-feedback?section=Seniors,Juniors');
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.getByRole('button', { name: 'Split view' }).click();
  const picker = page.getByRole('listbox', { name: /add section to split view/i });
  await expect(picker.getByRole('option', { name: 'Minis' })).toBeVisible();
  await expect(picker.getByRole('option', { name: 'Seniors' })).not.toBeVisible();
  await expect(picker.getByRole('option', { name: 'Juniors' })).not.toBeVisible();
});

test('selecting from picker in 2-column view enters 3-column view', async ({ page }) => {
  await setupDevoFeedbackPage(page, true, '/react/devos-feedback?section=Seniors,Juniors');
  await page.getByRole('button', { name: 'Split view' }).click();
  await page.getByRole('option', { name: 'Minis' }).click();
  await expect(page.getByRole('dialog')).toHaveAttribute('aria-label', 'Comparing Seniors, Juniors, Minis');
  await expect(page.locator('.focus-column')).toHaveCount(3);
});

test('+ Split button is hidden when 3 columns are shown', async ({ page }) => {
  await setupDevoFeedbackPage(page, true, '/react/devos-feedback?section=Seniors,Juniors,Minis');
  await expect(page.getByRole('dialog')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Split view' })).not.toBeVisible();
});

test('clicking + Split again toggles the picker closed', async ({ page }) => {
  await setupDevoFeedbackPage(page);
  const seniorsCard = page.locator('.feedback-card').filter({ hasText: 'Seniors' });
  await seniorsCard.locator('.feedback-card-body').click();
  await page.getByRole('button', { name: 'Split view' }).click();
  await expect(page.getByRole('listbox', { name: /add section to split view/i })).toBeVisible();
  await page.getByRole('button', { name: 'Split view' }).click();
  await expect(page.getByRole('listbox', { name: /add section to split view/i })).not.toBeVisible();
});

test('Escape closes picker first, then overlay on second press', async ({ page }) => {
  await setupDevoFeedbackPage(page);
  const seniorsCard = page.locator('.feedback-card').filter({ hasText: 'Seniors' });
  await seniorsCard.locator('.feedback-card-body').click();
  await page.getByRole('button', { name: 'Split view' }).click();
  await expect(page.getByRole('listbox', { name: /add section to split view/i })).toBeVisible();

  await page.keyboard.press('Escape');
  await expect(page.getByRole('listbox', { name: /add section to split view/i })).not.toBeVisible();
  await expect(page.getByRole('dialog')).toBeVisible();

  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).not.toBeVisible();
});

test('nav button closes picker when open', async ({ page }) => {
  await setupDevoFeedbackPage(page);
  const seniorsCard = page.locator('.feedback-card').filter({ hasText: 'Seniors' });
  await seniorsCard.locator('.feedback-card-body').click();
  await page.getByRole('button', { name: 'Split view' }).click();
  await expect(page.getByRole('listbox', { name: /add section to split view/i })).toBeVisible();

  await page.getByRole('button', { name: 'Next section' }).click();
  await expect(page.getByRole('listbox', { name: /add section to split view/i })).not.toBeVisible();
});

test('clicking outside picker closes it without exiting the overlay', async ({ page }) => {
  await setupDevoFeedbackPage(page);
  const seniorsCard = page.locator('.feedback-card').filter({ hasText: 'Seniors' });
  await seniorsCard.locator('.feedback-card-body').click();
  await page.getByRole('button', { name: 'Split view' }).click();
  await expect(page.getByRole('listbox', { name: /add section to split view/i })).toBeVisible();

  await page.locator('.focus-body').click();
  await expect(page.getByRole('listbox', { name: /add section to split view/i })).not.toBeVisible();
  await expect(page.getByRole('dialog')).toBeVisible();
});

test('column text is larger than card grid text in 2-column split view', async ({ page, isMobile }) => {
  // On mobile the columns stack vertically (full-width), testing side-by-side sizing only makes
  // sense on desktop where the container-query scaling is in effect.
  test.skip(isMobile, 'Desktop-only — columns stack on mobile');
  await setupDevoFeedbackPage(page, true, '/react/devos-feedback?section=Seniors,Juniors');
  await expect(page.locator('.focus-column-body .focus-text').first()).toBeVisible();
  const splitFontSize = await page.locator('.focus-column-body .focus-text').first().evaluate(
    el => parseFloat(getComputedStyle(el).fontSize)
  );
  // card grid uses --font-size-base = 1rem = 16px; 2-column split hits 1.5rem max = 24px on 1280px viewport
  expect(splitFontSize).toBeGreaterThan(20);
});

test('column text is larger than card grid text in 3-column split view', async ({ page, isMobile }) => {
  test.skip(isMobile, 'Desktop-only — columns stack on mobile');
  await setupDevoFeedbackPage(page, true, '/react/devos-feedback?section=Seniors,Juniors,Minis');
  await expect(page.locator('.focus-column-body .focus-text').first()).toBeVisible();
  const splitFontSize = await page.locator('.focus-column-body .focus-text').first().evaluate(
    el => parseFloat(getComputedStyle(el).fontSize)
  );
  // 3-column containers are narrower; floor is 1.2rem = 19.2px, well above card grid's 16px
  expect(splitFontSize).toBeGreaterThan(17);
});

test('split view visual snapshot - 2 columns', async ({ page, isMobile }) => {
  test.skip(isMobile, 'Desktop-only snapshot');
  await setupDevoFeedbackPage(page, true, '/react/devos-feedback?section=Seniors,Minis');
  await expect(page.getByRole('dialog')).toBeVisible();
  await expect(page.locator('.focus-nav-indicator')).toBeVisible();
  await expect(page).toHaveScreenshot('devo-feedback-split-2col.png', { fullPage: true });
});

test('split view visual snapshot - 3 columns', async ({ page, isMobile }) => {
  test.skip(isMobile, 'Desktop-only snapshot');
  await setupDevoFeedbackPage(page, true, '/react/devos-feedback?section=Seniors,Juniors,Minis');
  await expect(page.getByRole('dialog')).toBeVisible();
  await expect(page.locator('.focus-nav-indicator')).toBeVisible();
  await expect(page).toHaveScreenshot('devo-feedback-split-3col.png', { fullPage: true });
});
