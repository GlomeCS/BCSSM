import { test, expect, Page } from '@playwright/test';

const TODAY_DUTIES = [
  {
    id: '1',
    name: 'Setup',
    duty_description: 'Set up the hall and equipment before the session',
    members: [
      { name: 'Alice', week: 'Week A' },
      { name: 'Bob', week: 'Week B' },
    ],
    is_current_user: true,
    team_name: 'Duty Team 1',
  },
  {
    id: '2',
    name: 'Teardown',
    duty_description: 'Pack away equipment after the session',
    members: [{ name: 'Carol', week: 'Both' }],
    is_current_user: false,
    team_name: 'Duty Team 2',
  },
];

const SCHEDULE = {
  schedule: [
    {
      date: '2026-07-04',
      day_name: 'Saturday',
      week: 'Week A',
      duties: [
        { duty_name: 'Setup', duty_description: 'Set up', team_name: 'Duty Team 1', team_members: [] },
        { duty_name: 'Teardown', duty_description: 'Pack away', team_name: 'Duty Team 2', team_members: [] },
      ],
    },
    {
      date: '2026-07-06',
      day_name: 'Monday',
      week: 'Week A',
      duties: [
        { duty_name: 'Setup', duty_description: 'Set up', team_name: 'Duty Team 2', team_members: [] },
        { duty_name: 'Teardown', duty_description: 'Pack away', team_name: 'Duty Team 1', team_members: [] },
      ],
    },
    {
      date: '2026-07-13',
      day_name: 'Monday',
      week: 'Week B',
      duties: [
        { duty_name: 'Setup', duty_description: 'Set up', team_name: 'Duty Team 1', team_members: [] },
        { duty_name: 'Teardown', duty_description: 'Pack away', team_name: 'Duty Team 2', team_members: [] },
      ],
    },
  ],
};

async function setupDutiesPage(page: Page, duties = TODAY_DUTIES) {
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
      body: JSON.stringify({ is_valid: true, role: 'Team Member', section: 'Seniors', can_edit_all: false }),
    })
  );
  await page.route('**/api/duties/today*', route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(duties),
    })
  );
  await page.route('**/api/duties/schedule*', route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(SCHEDULE),
    })
  );
  await page.goto('/duties');
}

test('unauthenticated visit to /duties redirects to /login', async ({ page }) => {
  await page.route('**/api/auth/validate*', route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ is_valid: false }),
    })
  );
  await page.goto('/duties');
  await expect(page).toHaveURL('/login');
});

test('duties page shows the Today tab by default', async ({ page }) => {
  await setupDutiesPage(page);
  await expect(page.getByText("📋 Duties Dashboard")).toBeVisible();
  await expect(page.getByRole('button', { name: /today's duties/i })).toBeVisible();
  await expect(page.getByRole('button', { name: /2-week schedule/i })).toBeVisible();
});

test('shows current user duty card under "Your Duties"', async ({ page }) => {
  await setupDutiesPage(page);
  await expect(page.getByRole('heading', { name: /Your Duties/i })).toBeVisible();
  await expect(page.getByText('Setup')).toBeVisible();
  await expect(page.getByText('Set up the hall and equipment before the session')).toBeVisible();
  await expect(page.getByText('Team 1 Duty')).toBeVisible();
});

test('shows team members on duty card', async ({ page }) => {
  await setupDutiesPage(page);
  await expect(page.getByText('Alice')).toBeVisible();
  await expect(page.getByText('Bob')).toBeVisible();
});

test('shows other duties section', async ({ page }) => {
  await setupDutiesPage(page);
  await expect(page.getByRole('heading', { name: '👥Other Duties' })).toBeVisible();
  await expect(page.getByText('Teardown')).toBeVisible();
  await expect(page.getByText('Carol')).toBeVisible();
});

test('shows "No Duty Today" message when user has no duties', async ({ page }) => {
  const noDuties = TODAY_DUTIES.map(d => ({ ...d, is_current_user: false }));
  await setupDutiesPage(page, noDuties);
  await expect(page.getByText('No Duty Today!')).toBeVisible();
});

test('switching to Schedule tab shows the schedule table', async ({ page }) => {
  await setupDutiesPage(page);
  await page.getByRole('button', { name: /2-week schedule/i }).click();
  await expect(page.getByRole('table')).toBeVisible();
  // Column headers for duty names
  await expect(page.getByRole('columnheader', { name: 'Setup' })).toBeVisible();
  await expect(page.getByRole('columnheader', { name: 'Teardown' })).toBeVisible();
  // Date rows
  await expect(page.getByText(/Sat.*4.*Jul/i)).toBeVisible();
});

test('duties page visual snapshot - today tab', async ({ page }) => {
  await setupDutiesPage(page);
  await expect(page.getByRole('heading', { name: /your duties/i })).toBeVisible();
  await page.locator('.duties-date').evaluate(el => ((el as HTMLElement).style.visibility = 'hidden'));
  await expect(page).toHaveScreenshot('duties-today.png', { fullPage: true });
});

test('duties page visual snapshot - schedule tab', async ({ page }) => {
  await setupDutiesPage(page);
  await page.getByRole('button', { name: /2-week schedule/i }).click();
  await expect(page.getByRole('table')).toBeVisible();
  await page.locator('.duties-date').evaluate(el => ((el as HTMLElement).style.visibility = 'hidden'));
  await expect(page).toHaveScreenshot('duties-schedule.png', { fullPage: true });
});

test('duties page visual snapshot - mobile today tab', async ({ page, isMobile }) => {
  test.skip(!isMobile, 'Mobile-only test');
  await setupDutiesPage(page);
  await expect(page.getByRole('heading', { name: /your duties/i })).toBeVisible();
  await page.locator('.duties-date').evaluate(el => ((el as HTMLElement).style.visibility = 'hidden'));
  await expect(page).toHaveScreenshot('duties-today-mobile.png', { fullPage: true });
});
