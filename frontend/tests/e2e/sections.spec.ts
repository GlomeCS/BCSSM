import { test, expect, Page } from '@playwright/test';

const SECTIONS_DATA = {
  sections: [
    {
      name: 'Seniors',
      display_order: 1,
      users: [
        { name: 'Alice', role: 'Section Leader' },
        { name: 'Bob', role: 'Team Leader' },
        { name: 'Carol', role: 'Leader', week: 'Week A' },
        { name: 'Dave', role: 'Leader', week: 'Week B' },
      ],
      user_count: 4,
    },
    {
      name: 'Juniors',
      display_order: 2,
      users: [
        { name: 'Eve', role: 'Section Leader' },
        { name: 'Frank', role: 'Leader', week: 'Both' },
        { name: 'Grace', role: 'Leader', week: 'Week A' },
      ],
      user_count: 3,
    },
  ],
  total_users: 7,
  total_sections: 2,
};

async function setupSectionsPage(page: Page) {
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
  await page.route('**/api/users/by-section*', route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(SECTIONS_DATA),
    })
  );
  await page.goto('/sections');
}

test('unauthenticated visit to /sections redirects to /login', async ({ page }) => {
  await page.route('**/api/auth/validate*', route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ is_valid: false }),
    })
  );
  await page.goto('/sections');
  await expect(page).toHaveURL('/login');
});

test('sections page shows heading and total counts', async ({ page }) => {
  await setupSectionsPage(page);
  await expect(page.getByText(/Users by Section/i)).toBeVisible();
  await expect(page.getByText(/7 users across 2 sections/i)).toBeVisible();
});

test('shows all section cards', async ({ page }) => {
  await setupSectionsPage(page);
  await expect(page.getByText('Seniors')).toBeVisible();
  await expect(page.getByText('Juniors')).toBeVisible();
});

test('shows user count badge on each section card', async ({ page }) => {
  await setupSectionsPage(page);
  await expect(page.getByText('4 users')).toBeVisible();
  await expect(page.getByText('3 users')).toBeVisible();
});

test('lists users within each section', async ({ page }) => {
  await setupSectionsPage(page);
  await expect(page.getByText('Alice')).toBeVisible();
  await expect(page.getByText('Bob')).toBeVisible();
  await expect(page.getByText('Eve')).toBeVisible();
  await expect(page.getByText('Frank')).toBeVisible();
});

// ── Role filter ──────────────────────────────────────────────────────────────

test('role filter dropdown exists with correct options', async ({ page }) => {
  await setupSectionsPage(page);
  const select = page.locator('select#role-filter');
  await expect(select).toBeVisible();
  await expect(page.getByRole('option', { name: 'All Roles' })).toBeAttached();
  await expect(page.getByRole('option', { name: 'Section Leaders Only', exact: true })).toBeAttached();
  await expect(page.getByRole('option', { name: 'Team Leaders Only', exact: true })).toBeAttached();
  await expect(page.getByRole('option', { name: 'Leaders Only', exact: true })).toBeAttached();
});

test('filtering by Section Leader shows only section leaders', async ({ page }) => {
  await setupSectionsPage(page);
  await page.selectOption('select#role-filter', 'Section Leader');
  await expect(page.getByText('Alice')).toBeVisible();
  await expect(page.getByText('Eve')).toBeVisible();
  await expect(page.getByText('Bob')).not.toBeVisible();
  await expect(page.getByText('Carol')).not.toBeVisible();
});

test('filtering by Team Leader shows only team leaders', async ({ page }) => {
  await setupSectionsPage(page);
  await page.selectOption('select#role-filter', 'Team Leader');
  await expect(page.getByText('Bob')).toBeVisible();
  await expect(page.getByText('Alice')).not.toBeVisible();
});

test('filtering by Team Leader hides sections with no matching users', async ({ page }) => {
  await setupSectionsPage(page);
  await page.selectOption('select#role-filter', 'Team Leader');
  await expect(page.getByText('Juniors')).not.toBeVisible();
  await expect(page.getByText('Seniors')).toBeVisible();
});

// ── Week filter ──────────────────────────────────────────────────────────────

test('week filter dropdown exists with correct options', async ({ page }) => {
  await setupSectionsPage(page);
  const select = page.locator('select#week-filter');
  await expect(select).toBeVisible();
  await expect(page.getByRole('option', { name: 'All Weeks' })).toBeAttached();
  await expect(page.getByRole('option', { name: 'Week A', exact: true })).toBeAttached();
  await expect(page.getByRole('option', { name: 'Week B', exact: true })).toBeAttached();
});

test('filtering by Week A shows Week A and Both users', async ({ page }) => {
  await setupSectionsPage(page);
  await page.selectOption('select#week-filter', 'Week A');
  // Week A leader
  await expect(page.getByText('Carol')).toBeVisible();
  // Both leader — should appear in Week A filter
  await expect(page.getByText('Frank')).toBeVisible();
  // Week B leader — should be hidden
  await expect(page.getByText('Dave')).not.toBeVisible();
});

test('filtering by Week B shows Week B and Both users', async ({ page }) => {
  await setupSectionsPage(page);
  await page.selectOption('select#week-filter', 'Week B');
  // Week B leader
  await expect(page.getByText('Dave')).toBeVisible();
  // Both leader — should appear in Week B filter
  await expect(page.getByText('Frank')).toBeVisible();
  // Week A leader — should be hidden
  await expect(page.getByText('Carol')).not.toBeVisible();
  await expect(page.getByText('Grace')).not.toBeVisible();
});

test('week filter preserves users without week (including section leaders)', async ({ page }) => {
  await setupSectionsPage(page);
  await page.selectOption('select#week-filter', 'Week A');
  // Users with no week show alongside week-matched users for context
  await expect(page.getByText('Alice')).toBeVisible();
  await expect(page.getByText('Bob')).toBeVisible();
  await expect(page.getByText('Eve')).toBeVisible();
});

test('combined role and week filter shows only matching users', async ({ page }) => {
  await setupSectionsPage(page);
  await page.selectOption('select#role-filter', 'Leader');
  await page.selectOption('select#week-filter', 'Week B');
  await expect(page.getByText('Dave')).toBeVisible();
  await expect(page.getByText('Frank')).toBeVisible();
  await expect(page.getByText('Grace')).not.toBeVisible();
});

// ── Collapse / expand ────────────────────────────────────────────────────────

test('clicking a section header collapses and hides its users', async ({ page }) => {
  await setupSectionsPage(page);
  await expect(page.getByText('Alice')).toBeVisible();
  // Click the Seniors header button to collapse it
  await page.getByRole('button', { name: /Seniors/ }).click();
  await expect(page.getByText('Alice')).not.toBeVisible();
  await expect(page.getByText('Bob')).not.toBeVisible();
});

test('clicking a collapsed section header expands it again', async ({ page }) => {
  await setupSectionsPage(page);
  const seniorsHeader = page.getByRole('button', { name: /Seniors/ });
  await seniorsHeader.click();
  await expect(page.getByText('Alice')).not.toBeVisible();
  await seniorsHeader.click();
  await expect(page.getByText('Alice')).toBeVisible();
});

test('collapse all button hides all section bodies', async ({ page }) => {
  await setupSectionsPage(page);
  await page.getByRole('button', { name: /Collapse All/i }).click();
  await expect(page.getByText('Alice')).not.toBeVisible();
  await expect(page.getByText('Eve')).not.toBeVisible();
});

test('expand all button after collapse all restores all section bodies', async ({ page }) => {
  await setupSectionsPage(page);
  await page.getByRole('button', { name: /Collapse All/i }).click();
  await page.getByRole('button', { name: /Expand All/i }).click();
  await expect(page.getByText('Alice')).toBeVisible();
  await expect(page.getByText('Eve')).toBeVisible();
});

test('collapsing a section keeps other sections visible', async ({ page }) => {
  await setupSectionsPage(page);
  await page.getByRole('button', { name: /Seniors/ }).click();
  // Seniors collapsed, Juniors still expanded
  await expect(page.getByText('Alice')).not.toBeVisible();
  await expect(page.getByText('Eve')).toBeVisible();
  await expect(page.getByText('Frank')).toBeVisible();
});

// ── Visual snapshots ─────────────────────────────────────────────────────────

test('sections page visual snapshot - all roles', async ({ page }) => {
  await setupSectionsPage(page);
  await expect(page.getByText(/7 users across 2 sections/i)).toBeVisible();
  await expect(page).toHaveScreenshot('sections-all-roles.png', { fullPage: true });
});

test('sections page visual snapshot - section leaders only', async ({ page }) => {
  await setupSectionsPage(page);
  await page.selectOption('select#role-filter', 'Section Leader');
  await expect(page.getByText('Alice')).toBeVisible();
  await expect(page).toHaveScreenshot('sections-leaders-only.png', { fullPage: true });
});

test('sections page visual snapshot - week a filter', async ({ page }) => {
  await setupSectionsPage(page);
  await page.selectOption('select#week-filter', 'Week A');
  await expect(page.getByText('Carol')).toBeVisible();
  await expect(page).toHaveScreenshot('sections-week-a.png', { fullPage: true });
});

test('sections page visual snapshot - collapsed', async ({ page }) => {
  await setupSectionsPage(page);
  await page.getByRole('button', { name: /Collapse All/i }).click();
  await expect(page.getByText('Carol')).not.toBeVisible();
  await expect(page).toHaveScreenshot('sections-collapsed.png', { fullPage: true });
});

test('sections page visual snapshot - mobile', async ({ page, isMobile }) => {
  test.skip(!isMobile, 'Mobile-only test');
  await setupSectionsPage(page);
  await expect(page.getByText(/7 users across 2 sections/i)).toBeVisible();
  await expect(page).toHaveScreenshot('sections-mobile.png', { fullPage: true });
});
