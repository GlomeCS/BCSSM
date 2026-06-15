# CONTEXT.md — BCSSM Domain Glossary

Single source of truth for domain terminology. Use these exact terms in code, issues, PRs, and architecture discussions. When a new concept is named during a grill or ADR session, add it here.

---

## Core domain concepts

**User**
A person in the system. Has a name, role, section, and duty team assignment. Stored in the `users` table.

**Role**
A user's organisational rank. Stored in the DB as `"Admin"` or `"Section Leader"`; `"Admin"` is displayed as `"Section Leader"` in all user-facing contexts. See #162 — consolidating this display mapping.

**Section**
An organisational grouping of users (e.g. a platoon sub-unit). Users belong to at most one section. The special value `"Unassigned"` covers users with no `section_id`.

**Section Leader**
The display role for users whose DB role is `"Admin"`. Sections typically have one Section Leader.

**Duty team**
A named group of users assigned to perform specific duties on a rotating schedule. Users belong to at most one duty team. Stored in `duty_teams`.

**Duty**
A named task (e.g. "Security") that a duty team is assigned to perform. Stored in `duties`.

**Duty schedule**
The 14-day rolling assignment of duties to duty teams, keyed from a fixed cycle anchor date (`CYCLE_ANCHOR = 2026-07-04`). Rendered on the `/duties` page as today's duties and a 14-day schedule.

**Duty cycle**
A bi-weekly rotation tracked as cycle week 0 or 1. Computed relative to `CYCLE_ANCHOR` by `_cycle_week_for_date()`. Determines which duty team is on for a given week.

**DevOs feedback**
Daily written feedback records keyed by section and date. Stored in `feedback_records`. Viewable by all users; editable by Section Leaders (own section) or users with `can_edit_all`.

---

## Infrastructure concepts

**Cache registry**
A centralised definition of cache key templates, TTLs, error TTLs, and invalidation groups. Introduced in #160 to replace scattered inline cache metadata. Lives in `cache_utils.py` as `CACHE_REGISTRY`.

**Invalidation group**
A named category (e.g. `"duties"`, `"users"`, `"feedback"`) that groups related cache entries for bulk clearing. Used by `clear_group(group_name)` in #165.

**Auth context** (frontend)
A React context that owns all client-side auth state (`currentUser`, `userSection`, `userRole`, `canEditAll`). Introduced in #161 to replace scattered `localStorage` reads across components.
