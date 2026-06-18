# Project Meridian — Handover Notes

## 1. Project overview

Project Meridian is a self-hosted household task, reward, and points-management web application. It is built for a household where users complete tasks, earn points, spend those points on rewards, contribute toward wishlist items, and contribute toward shared group goals.

The app is intended to make household contribution visible and rewarding without becoming a formal workplace productivity system. It is not a project-management app, not a school behaviour-management platform, not a finance app, and not a surveillance or punishment system. It is a household motivation and reward system with admin-controlled approvals and a configurable points economy.

The core product loop is:

1. Admin creates users, tasks, rewards, categories, wishlist items, and group goals.
2. Standard users log in using an avatar/user-card and PIN.
3. Users complete tasks and submit them for approval.
4. Admin approves or rejects task completions.
5. Approved tasks award points.
6. Users spend or contribute points through rewards, wishlist items, and group goals.
7. Admin manages approvals, point adjustments, users, reports, and settings.

The app is currently still called **Project Meridian**. Alternative names and logos were explored, including HomeQuest-style family/progress branding, but the current decision is to keep the Project Meridian name.

## 2. Intended household use case

Project Meridian is intended for a small household, with roughly four user accounts as the initial target.

There are two main user types:

- **Admin users**: manage the household system, users, tasks, rewards, categories, approvals, reports, and settings.
- **Standard users**: complete tasks, earn points, view progress, request rewards, and contribute toward goals.

Expected daily use:

- A user opens the app on desktop, phone, or possibly a future home touchscreen hub.
- They select their avatar/user card on the login page.
- They enter a 4-digit PIN.
- They choose tasks to complete.
- They submit completions for approval.
- Admin reviews and approves/rejects requests.
- Users use their points in the reward shop, wishlist, or group goals.

A future kiosk/home-hub use case has been discussed. The idea is to run Project Meridian on a Raspberry Pi with a touchscreen as a central household hub. This means the UI should remain touch-friendly, simple, and mobile/kiosk-compatible.

## 3. Technical stack

Project Meridian is a Python Flask application.

Known stack:

- **Backend language:** Python
- **Web framework:** Flask
- **Templates:** Jinja2 server-rendered HTML
- **Database:** SQLite
- **ORM:** SQLAlchemy / Flask-SQLAlchemy
- **Migrations:** Flask-Migrate / Alembic
- **Authentication/session handling:** Flask-Login
- **Forms:** Flask-WTF / WTForms style form classes
- **Frontend:** HTML templates, CSS, Bootstrap, small JavaScript snippets
- **CSS files:** `app/static/css/styles.css` and `app/static/css/homestack.css`
- **Deployment:** Docker Compose
- **Host OS preference:** Fedora Server
- **Container name:** `project-meridian`
- **Local browser URL commonly used:** `http://localhost:8000`

The app is intended to be a small self-hosted household app, not a public SaaS product.

## 4. Repository and branch context

Known repo state from recent work:

- Main branch: `main`
- UI refresh branch used: `ui-homestack-refresh-v2`
- Important tag after service-layer work: `stable-service-layer`
- Important tag after UI refresh: `stable-homestack-ui`

A repository cleanup was previously completed using `git filter-repo`. Sensitive and local runtime files were removed from tracked history, including `.env`, SQLite databases, backups, pycache files, generated/local files, and accidental local artifacts.

The `.gitignore` was replaced with a cleaner version that ignores secrets, databases, runtime files, backups, generated docs, and Python cache files.

Important: `.env` must stay untracked. If any old `.env` existed in Git history before cleanup, the local `SECRET_KEY` should be treated as exposed and rotated.

GitHub may classify the repo as HTML because the app has many large Jinja templates after the UI refresh. This is normal. It is still a Python/Flask app.

## 5. Deployment workflow

Typical local development workflow:

```bash
cd <local-project-meridian-directory>

python -m py_compile app/routes.py app/models.py app/forms.py app/__init__.py
python -m py_compile app/services/*.py

docker compose down
docker compose up -d --build
docker logs project-meridian --tail=100
```

Typical commit workflow:

```bash
git status
git add <changed files>
git commit -m "<clear commit message>"
git push origin main
```

Typical server deployment workflow:

```bash
cd /opt/docker/project-meridian/app

git pull
docker compose down
docker compose up -d --build
docker compose ps
docker logs project-meridian --tail=100
```

Before any database-affecting change, back up the SQLite database.

## 6. Database and source-of-truth decisions

The database is SQLite.

The most important architectural decision is:

> The point transaction ledger is the source of truth for user balances.

Do not treat a user's current points as a static manually edited field unless the current model explicitly stores a cache. Balances should be calculated from point transactions.

Known core models and concepts include:

### User

Known fields/concepts:

- `username`
- `display_name`
- `avatar_emoji`
- `password_hash`
- `role`
- `is_active_account`
- `created_at`
- `set_password()`
- `check_password()`
- `is_admin()`
- `point_balance()` — calculates current balance from point transactions
- admin vs standard user roles
- user can be active/disabled/restored/deleted depending on admin workflows
- current point balance is calculated from point transactions

Admins should not normally receive task points.

### HouseholdSettings

Known fields/defaults:

```python
household_name="Project Meridian"
points_label="points"
wishlist_requests_enabled=True
group_goals_enabled=True
updated_at=<timestamp>
```

`points_label` is important. Visible UI text should use the configured household points label where practical rather than hardcoded "points". Internal variable names like `point_cost`, `point_value`, and `points_label` are acceptable and should not be renamed casually.

This table should normally only have one row.

### Task

Known fields/concepts:

- `title`
- `description`
- `point_value`
- `category`
- `completion_behavior` — `"stay_active"` (persistent) or similar for one-time tasks
- `is_active`
- `is_hot`
- `hot_bonus_points`
- `hot_label`
- `created_at`
- `total_point_value()` — returns `point_value + hot_bonus_points` when `is_hot` is true
- Hot Tasks are already implemented — do not treat as a missing dependency
- admin can create/edit/manage/delete/hide tasks
- admin can complete a task for a user
- standard users submit task completions for approval

### TaskCompletion

Known fields/concepts:

- `task_id`, `user_id`
- `status` — `"submitted"`, `"approved"`, `"rejected"`, `"cancelled"`
- `submitted_at`, `reviewed_at`, `reviewed_by_id`
- `rejection_reason`
- user submits a completion request
- admin approves or rejects
- points are not awarded until approval
- task history exists
- rejection workflow exists
- users can cancel their own pending submissions

### PointTransaction

Known fields/concepts:

- `user_id`, `amount`, `transaction_type`, `reason`
- `related_task_completion_id`
- `related_reward_purchase_id`
- `created_by_id`, `created_at`
- stores every point change
- point ledger is the source of truth
- positive transactions award points
- negative transactions reserve, spend, or contribute points
- linked to task completions, reward purchases, wishlist contributions, or group-goal contributions depending on context
- current balance and total earned can be calculated separately

Known routes:

- `/points`
- `/admin/reports/points.csv`
- `/admin/users/<int:user_id>/adjust-points`

### Reward

Known fields/concepts:

- `name`, `description`, `category`, `point_cost`
- `is_active`, `created_at`
- admin can create/edit/manage rewards
- users can request rewards

### RewardPurchase / reward request

Known fields/behaviour:

- `reward_id`, `user_id`
- `status` — `"requested"`, `"approved"`, `"rejected"`, `"cancelled"`, `"fulfilled"`
- `requested_at`, `reviewed_at`, `reviewed_by_id`
- `rejection_reason`
- a user requests a reward
- points are reserved/deducted immediately
- admin approves or rejects the request
- if rejected or cancelled, reserved points are refunded
- service layer should prevent double deductions/refunds

### TaskCategory / RewardCategory

Two separate category models exist:

- `TaskCategory` — admin-managed categories for tasks (`task_categories` table)
- `RewardCategory` — admin-managed categories for rewards/shop (`reward_categories` table)

Both have `name`, `is_active`, and `created_at` fields. Categories are managed via `/admin/categories`.

### Notification

Known fields/concepts:

- `user_id`, `title`, `message`
- `action_url`, `action_label`
- `notification_type` — `"info"`, `"success"`, etc.
- `is_read`, `created_at`
- notifications are created by services (e.g. badge awards)
- users can mark notifications as read via `/notifications/<id>/read`
- notifications surface on the dashboard

### WishlistRequest

Known fields/concepts:

- `user_id`, `requested_name`, `requested_description`
- `status` — `"requested"`, `"approved"`, `"rejected"`, `"cancelled"`
- `rejection_reason`, `reviewed_at`, `reviewed_by_id`
- users submit requests for new wishlist items
- admin can approve (which creates a WishlistItem) or reject

### WishlistItem

Known fields/concepts:

- `user_id`, `name`, `description`, `point_cost`
- `status` — `"active"`, `"funded"`, `"fulfilled"`
- `is_active`, `created_by_id`, `created_at`
- `total_saved()`, `remaining_points()`, `progress_percentage()`, `is_funded()`
- wishlist items belong to one user
- admin controls or finalises the item name/description/cost
- users contribute points toward wishlist items over time
- item can be considered funded when saved points reach the point cost
- admin can fulfil funded items via `/admin/wishlist/items/<id>/fulfil`
- archive workflow exists

### WishlistContribution

Known fields/concepts:

- `item_id`, `user_id`, `amount`
- `status` — `"active"`
- `created_at`
- stores user point contributions toward wishlist items
- creates point transactions
- contributes to point history

### GroupGoal

Known fields/concepts:

- `title`, `description`, `target_points`
- `status` — `"active"`, `"fulfilled"`, `"cancelled"`
- `is_active`, `created_at`
- `total_contributed()`, `remaining_points()`, `progress_percentage()`, `is_funded()`
- shared household goals
- users contribute points toward a common target
- admins do not normally contribute
- admin can fulfil a funded goal via `/group-goals/<id>/fulfil`
- admin can cancel a goal via `/group-goals/<id>/cancel`

### GroupGoalContribution

Known fields/concepts:

- `goal_id`, `user_id`, `amount`
- `status` — `"active"`
- `created_at`

### Badge / UserBadge

Known badge codes (seeded automatically):

```text
first_task          — First Task (✅) — completed first approved task
five_tasks          — Task Starter (⭐) — completed 5 approved tasks
ten_tasks           — Task Champion (🏆) — completed 10 approved tasks
wishlist_saver      — Wishlist Saver (🎁) — saved toward a wishlist item
wishlist_funded     — Goal Reached (🎯) — fully funded a wishlist item
group_contributor   — Team Player (🤝) — contributed to a group goal
hundred_points_earned — Big Earner (💰) — reached 100 total points earned
```

`UserBadge` stores user-badge links with `earned_at` timestamps. Badge notifications are created automatically on award.

## 7. Current feature set

### Authentication and login

Built/expected:

- avatar/user-card login
- PIN/password entry
- Flask-Login session handling
- admin and standard user roles
- default admin seeded on fresh install (idempotent, only if zero users exist)
- desired UX: selecting a user should automatically focus the PIN input
- desired mobile UX: PIN field should show numeric keypad, not full keyboard

Default fresh-install admin:

```text
Display name: Admin
Username: admin
PIN/password: 1234
Role: admin
Avatar: 🛡️
```

This is a public first-login default for brand-new empty databases only. Change it immediately after first login.

**Note:** Login PIN autofocus/numeric keypad is not yet implemented. The current `login.html` JS selects the user card and updates a hidden field, but does not focus the PIN input or add `inputmode="numeric"`. See section 10 for the implementation plan.

### User dashboard

Built/expected:

- current balance
- recent point activity
- available task/reward/wishlist/group-goal navigation
- HomeStack-style cards and layout
- notifications surfaced from service layer

### Admin dashboard

Built/expected:

- admin centre
- approval queues
- user management
- task management
- reward management
- category management
- reports
- request archive
- household settings
- quick actions

### User management

Admin can create users, edit users, disable users, restore users, delete users, change/reset user PIN/password, manually adjust balance/points, and manage account status.

Relevant templates:

```text
users.html
create_user.html
edit_user.html
change_user_password.html
adjust_points.html
user_profile.html
```

### Task management

Admin can create tasks, edit tasks, manage tasks, hide/delete tasks, configure persistent or one-time tasks, use Hot Tasks, and complete tasks on behalf of users.

Users can view tasks, submit task completions, cancel pending submissions, and view task history.

Relevant templates:

```text
tasks.html
create_task.html
edit_task.html
manage_tasks.html
admin_complete_task.html
task_history.html
reject_task_completion.html
```

### Approvals

Admin can approve task completions, reject task completions, approve reward purchases, reject reward purchases, and view archived requests.

Relevant templates:

```text
admin_approvals.html
request_archive.html
reject_task_completion.html
reject_reward_purchase.html
```

### Reward shop

Admin can create rewards, edit rewards, manage rewards, set cost/category/visibility, and approve/reject purchases.

Users can browse the reward shop, request rewards, cancel pending requests, spend/reserve points, and view reward history.

Relevant templates:

```text
shop.html
create_reward.html
edit_reward.html
manage_rewards.html
reward_history.html
reject_reward_purchase.html
```

### Point system

Built/expected:

- point ledger
- current balance
- total earned
- manual balance adjustment
- points awarded through approved task completions
- points reserved for reward requests
- refunds on rejected/cancelled reward requests
- wishlist contributions
- group-goal contributions
- point history page
- point CSV export

Relevant templates/routes:

```text
point_history.html
/points
/admin/reports/points.csv
/admin/users/<int:user_id>/adjust-points
```

### Reports and CSV exports

Four CSV exports are available via the admin reports page:

```text
/admin/reports/users.csv    — user list
/admin/reports/points.csv   — point transaction history
/admin/reports/tasks.csv    — task activity
/admin/reports/rewards.csv  — reward requests
```

Relevant template:

```text
admin_reports.html
```

### Database backup

A database download backup route exists:

```text
/admin/backup
```

Admin only. Downloads the SQLite database file as a timestamped `.db` attachment (e.g. `project-meridian-backup-20260618-123000.db`). This is the current backup mechanism for the local MVP.

### Wishlist

Built/expected:

- wishlist page
- request wishlist item
- cancel pending wishlist request
- admin add wishlist item
- approve/reject wishlist request
- edit wishlist item
- contribute to wishlist item
- admin fulfil funded wishlist item (`/admin/wishlist/items/<id>/fulfil`)
- admin remove wishlist item
- wishlist archive
- funded status based on saved points meeting item cost

Relevant templates:

```text
wishlist.html
request_wishlist_item.html
admin_add_wishlist_item.html
edit_wishlist_item.html
contribute_wishlist_item.html
approve_wishlist_request.html
reject_wishlist_request.html
wishlist_archive.html
```

### Group goals

Built/expected:

- group goals page
- create group goal
- contribute to group goal
- shared goal progress tracking
- contribution point deductions
- admin fulfil funded goal (`/group-goals/<id>/fulfil`) — marks goal as fulfilled
- admin cancel goal (`/group-goals/<id>/cancel`)

Relevant templates:

```text
group_goals.html
create_group_goal.html
contribute_group_goal.html
```

### Leaderboard

A leaderboard page exists at `/leaderboard`. Shows rankings for active standard users by:

- Current points (from point balance)
- Total points earned (from positive earning transactions returned by `points_service.get_earning_transaction_types()`; spending does not reduce this score)
- Tasks completed (from approved task completion records)

### Request archive

A unified request archive exists at `/requests/archive`. Shows completed/rejected/cancelled requests for all request types (task completions, reward requests, wishlist requests). Admins see all users; standard users see their own records.

### Categories

Built/expected:

- manage task and reward categories separately
- `TaskCategory` and `RewardCategory` are distinct models
- categories apply to tasks and rewards
- admin can add, restore, and remove categories
- future filtering/grouping should be category-aware

Relevant template:

```text
manage_categories.html
```

### Badges

Badge awarding is fully implemented via the service layer.

Seven default badges are seeded automatically (see section 6 for codes). Badges are awarded when task approvals, wishlist contributions, group contributions, and point milestones are reached. A notification is created for the user on badge award.

Relevant file:

```text
app/services/badge_service.py
```

## 8. Service layer and architecture

A service-layer refactor was introduced to move business logic out of `routes.py`.

Known service files:

```text
app/services/settings_service.py
app/services/notification_service.py
app/services/points_service.py
app/services/badge_service.py
app/services/report_service.py
app/services/task_service.py
app/services/reward_service.py
app/services/seed_service.py
```

### `settings_service.py`

Known functions:

```python
get_household_settings()
get_points_label()
```

Purpose: centralise household settings access and avoid repeated fallback/default settings logic.

### `points_service.py`

Purpose: calculate point totals, format point-related text, and support current balance and total earned calculations.

Current total-earned transaction types:

```text
task_approved
manual_adjustment
admin_adjustment
point_adjustment
```

Only positive transactions of those types count toward total earned. Reward spending, wishlist saving, group-goal contributions, refunds, and negative adjustments should not reduce total earned.

### `notification_service.py`

Purpose: centralise notification creation/handling.

### `badge_service.py`

Purpose: badge award/evaluation logic. Includes `seed_badges()`, `award_badge()`, and `check_and_award_badges()`.

### `report_service.py`

Purpose: build report rows, especially point transaction reports.

### `task_service.py`

Purpose: task approval/rejection logic, positive point transaction creation, and task-related visibility/approval handling.

### `reward_service.py`

Purpose: reserve points for pending reward request, approve reward purchase, reject/cancel reward request and refund points, and prevent duplicate deductions/refunds.

### `seed_service.py`

Purpose: seed required default data, ensure household settings exist, create default admin only if no users exist, and be safe to run repeatedly.

Correct startup pattern in `app/__init__.py`:

```python
with app.app_context():
    db.create_all()

    from app.services.seed_service import seed_default_data
    seed_default_data()
```

The seed call must run inside the app context.

## 9. UI design and UX decisions

Project Meridian has been refreshed with a HomeStack-style design, adapted from Project Solace.

Design direction:

- soft warm colours
- beige/warm neutral palette
- clean household-friendly feel
- minimal but not overly minimal
- mobile-first emphasis
- desktop and mobile support
- large cards and clear sections
- friendly but not childish
- consistent design direction with Project Solace and the future home server dashboard

Main CSS files:

```text
app/static/css/styles.css
app/static/css/homestack.css
```

UI refresh was applied in batches:

- Batch 1: `login.html`, `dashboard.html`, `tasks.html`, `shop.html`, `wishlist.html`
- Batch 2: `point_history.html`, `task_history.html`, `reward_history.html`, `user_profile.html`, `leaderboard.html`, `group_goals.html`
- Batch 3: `admin_home.html`, `admin_approvals.html`, `users.html`, `manage_tasks.html`, `manage_rewards.html`, `manage_categories.html`, `admin_reports.html`, `request_archive.html`
- Batch 4: `create_task.html`, `edit_task.html`, `create_reward.html`, `edit_reward.html`, `create_user.html`, `edit_user.html`, `change_user_password.html`, `adjust_points.html`, `household_settings.html`, `admin_complete_task.html`
- Batch 5: `request_wishlist_item.html`, `admin_add_wishlist_item.html`, `edit_wishlist_item.html`, `contribute_wishlist_item.html`, `approve_wishlist_request.html`, `reject_wishlist_request.html`, `wishlist_archive.html`, `create_group_goal.html`, `contribute_group_goal.html`
- Batch 6: `reject_task_completion.html`, `reject_reward_purchase.html`

### Navbar dropdown layering fix

A bug was found where navbar dropdowns appeared behind cards. This fix is committed. Keep this patch at the bottom of `homestack.css`:

```css
/* =========================================================
   Navbar / dropdown layering fix
   ========================================================= */

.navbar {
    position: relative;
    z-index: 2000;
}

.navbar .dropdown-menu {
    z-index: 2050;
}

.page-shell,
.card {
    position: relative;
    z-index: 1;
}
```

If dropdowns still appear behind cards, check for parent stacking contexts from `transform`, `filter`, `opacity`, or `overflow`.

## 10. Login UX improvement to implement

**Status: Not yet implemented.**

Desired feature:

When a user is selected at login, the cursor should automatically go to the PIN input. On mobile, tapping the user should bring up the numeric keypad instead of the full keyboard.

Current state: `login.html` has JS that sets the hidden `selected_user_id` field and updates the selected-user display text when a card is clicked, but does not focus the PIN input and the password field does not yet have `inputmode="numeric"`.

Implementation direction:

In `login.html`, the PIN/password field should include:

```html
inputmode="numeric"
pattern="[0-9]*"
autocomplete="one-time-code"
maxlength="4"
```

WTForms/Jinja example:

```jinja
{{ form.password(
    class="form-control",
    id="pin-input",
    inputmode="numeric",
    pattern="[0-9]*",
    autocomplete="one-time-code",
    maxlength="4"
) }}
```

Then add JavaScript to focus `#pin-input` when the user radio/card changes or is clicked.

Suggested commit message:

```text
Focus PIN input after user selection
```

## 11. Economy design baseline

The household points economy is being created.

Baseline principle:

```text
1 point = small effort
5 points = normal useful chore
10 points = meaningful household contribution
20+ points = large, unpleasant, or high-value task
```

Suggested weekly earning targets:

```text
Casual participation: 30–50 points/week
Normal active user: 60–100 points/week
Very active user: 120–160 points/week
Exceptional week: 180+ points/week
```

Suggested task values:

```text
Tiny task: 1–3 points
Small task: 5 points
Standard chore: 8–12 points
Larger chore: 15–20 points
Major chore: 25–40 points
One-off project: 40–80 points
Hot task bonus: +5 to +15 points
```

Example task values:

```text
Take rubbish/recycling out: 5
Empty dishwasher: 5
Load dishwasher / clean kitchen after meal: 8
Wipe kitchen benches: 5
Vacuum living area: 10
Vacuum bedroom: 8
Mop kitchen/living area: 15
Clean toilet: 8
Clean bathroom sink/mirror: 8
Full bathroom clean: 20
Fold laundry: 10
Put laundry away: 8
Change bedsheets: 15
Feed pets: 3
Walk dog / longer pet care: 10
Tidy bedroom/common area: 10
Clean car interior: 25
Mow lawn: 30
Weed garden / outdoor tidy: 20
Big declutter task: 30–50
```

Suggested reward tiers:

```text
Tiny reward: 50–80 points
Small reward: 100–160 points
Medium reward: 200–350 points
Large reward: 400–700 points
Major reward: 800–1500+ points
```

Money-like conversion guide:

```text
$1 equivalent ≈ 30 points
$5 equivalent ≈ 150 points
$10 equivalent ≈ 300 points
$25 equivalent ≈ 750 points
$50 equivalent ≈ 1500 points
```

Suggested first reward shop:

```text
3 small rewards: 100–160
3 medium rewards: 200–400
2 large rewards: 600–1000
1–2 group goals: 1500+
```

Economy rule: a normal active user should not be able to buy meaningful rewards every day. Meaningful rewards should generally take 1–4 weeks of normal effort.

Adjustment rule after two weeks:

- If rewards are being bought too often, raise reward costs by 20–30%.
- If users are stuck and never redeem anything, add more small rewards around 100–150.
- If one task is being farmed, reduce its value, limit it, or make it one-time/hidden.

## 12. Features added recently

Recent major work completed:

- Repository cleanup and `.gitignore` hardening.
- Sensitive/local runtime files removed from Git history.
- Service layer added/refined.
- Database indexes added for common queries.
- HomeStack UI refresh ported across the app in batches.
- Final CSS/mobile polish applied.
- Navbar dropdown layering fix committed.
- Dynamic wording cleanup for visible "points" labels.
- Default admin seed feature added — solves fresh-install lockout.
- Database backup download route added (`/admin/backup`).
- Four CSV export routes added (users, points, tasks, rewards).
- Group goal fulfil and cancel admin routes added.
- Wishlist item fulfil admin route added.
- Badge system implemented with seven default badges.
- Unified request archive page implemented.

Repository hygiene:

- Remove personal names, account URLs, secrets, database files, backups, and machine-specific paths from documentation before committing.
- Keep `.env`, SQLite database files, backup files, generated exports, and runtime artifacts untracked.
- After each completed code or documentation change, run the relevant checks, commit with a clear message, and push to GitHub.

Recent tag context:

```text
stable-service-layer
stable-homestack-ui
```

## 13. Features yet to implement

The following items remain to be done. After each change, commit with a clear message and push to the repository.

### Priority items

1. **Login PIN autofocus and numeric keypad** — add `inputmode="numeric"`, `pattern`, `autocomplete`, `maxlength` to the PIN field in `login.html` and add JS to focus it when a user card is clicked. (See section 10.)
2. **Populate the starting task and reward economy** — use the economy baseline in section 11. Create categories first, then tasks, then rewards.
3. **Smoke test mobile layout** — test all main pages on a phone-sized viewport.
4. **Continue service-layer refactoring** — gradually extract remaining inline logic from `routes.py` into service files. Avoid a risky full rewrite.

### Possible future features

- Kiosk/touchscreen mode for Raspberry Pi home hub.
- More badges and milestone logic (e.g. streaks, 25/50-task milestones, higher earning tiers).
- Better leaderboard options (weekly view, opt-out toggle).
- More group goal lifecycle states (funded milestone notification).
- More wishlist lifecycle states.
- Reward stock/quantity handling if the household needs limited-availability rewards.
- Backup/restore page (currently download-only; no restore UI).
- More modular dashboard widgets.
- More mobile-specific navigation improvements.
- Reverse proxy/domain setup for local network access.
- Optional household-specific points label such as stars or credits (partially supported via `points_label`).

### Future task customisation

Recurring tasks should be more configurable. They may be always available, or only available during configured time windows such as morning, afternoon, evening, weekdays, weekends, or specific times of day.

Recurring task completion scope needs to be configurable. Options to consider:

- Once per recurrence for the whole household, then hidden until the next recurrence.
- Once per assigned user for each recurrence.
- Once per user for each recurrence, where completing it hides it only for that user.

Tasks should support assignment to one user. Assigned tasks need a visibility setting so admins can choose whether the task is visible only to the assigned user, or visible to other users but only actionable by the assigned user.

### Future admin participation mode

Admins should be able to opt in or out of household participation at any time.

When opted in, admins can act like standard users where appropriate: complete tasks, earn points, appear on leaderboards, create wishlist items, contribute to wishlist items, contribute to group goals, and otherwise participate in the household economy.

When opted out, admins remain management-only. They should not earn task points, appear on normal user leaderboards, or distort household economy stats.

### Future routines and habit tracking

Add routines as a separate feature from tasks. Routines are repeated habits or personal-care flows created by admins for users, such as shower, brush teeth, or similar daily habits.

Routines should grant small point amounts and track streaks, including how many days in a row the user completed the routine. Add milestone bonuses for streaks or consistency targets.

Routines should have their own views and leaderboard options separate from general task and point leaderboards, so habit consistency can be celebrated without being mixed into normal chore/task rankings.

## 14. Known issues and technical debt

### Large `routes.py`

`routes.py` is still large. Some logic has been moved into services, but more gradual extraction is warranted. Avoid a risky full rewrite.

Refactor goal:

```text
Keep the existing main blueprint and main.<endpoint> URL names stable,
but move route groups into smaller modules by feature area.
```

Preferred shape:

```text
app/routes.py
app/route_sections/
    __init__.py
    admin_exports.py
    activity.py
    auth.py
    dashboard.py
    tasks.py
    rewards.py
    users.py
    points.py
    categories.py
    notifications.py
    profiles.py
    group_goals.py
    wishlist.py
    request_archive.py
```

Do not rename the existing `main` blueprint casually. Many templates call endpoints such as `url_for("main.dashboard")`, so the first phase should register smaller route modules against the existing blueprint instead of changing endpoint names.

Refactor steps:

1. Move low-risk, self-contained routes first: reports, CSV exports, database backup, notifications, points/history.
2. Move simple admin CRUD groups next: categories, users, task/reward management pages.
3. Move complex workflow groups last: task approval, reward reservation/refund, wishlist, and group goals.
4. As each route group moves, keep behaviour unchanged, run syntax checks, smoke test affected pages, then commit and push.
5. After route groups are separated, continue moving business logic into services so route files mostly validate input, call a service, flash a result, and redirect/render.

Current first extraction target:

```text
app/route_sections/admin_exports.py
```

This module should own:

```text
/admin/reports
/admin/reports/users.csv
/admin/reports/points.csv
/admin/reports/tasks.csv
/admin/reports/rewards.csv
/admin/backup
```

This keeps the report/backup code together and removes CSV/download concerns from the main route file.

Status: initial extraction completed. `admin_exports.py` now owns the admin reports page, CSV report downloads, and database backup route while preserving the existing `main.admin_reports`, `main.export_*_csv`, and `main.backup_database` endpoint names.

Second extraction completed:

```text
app/route_sections/activity.py
```

This module now owns:

```text
/points
/history/tasks
/history/rewards
/notifications/<id>/read
```

The existing `main.point_history`, `main.task_history`, `main.reward_history`, and `main.mark_notification_read` endpoint names were preserved.

Third extraction completed:

```text
app/route_sections/categories.py
```

This module now owns:

```text
/admin/categories
/admin/categories/task/add
/admin/categories/reward/add
/admin/categories/task/<id>/remove
/admin/categories/reward/<id>/remove
/admin/categories/task/<id>/restore
/admin/categories/reward/<id>/restore
```

The existing `main.manage_categories`, `main.add_task_category`, `main.add_reward_category`, `main.remove_task_category`, `main.remove_reward_category`, `main.restore_task_category`, and `main.restore_reward_category` endpoint names were preserved.

Fourth extraction completed:

```text
app/route_sections/auth.py
```

This module now owns:

```text
/
/login
/logout
```

The existing `main.index`, `main.login`, and `main.logout` endpoint names were preserved.

Fifth extraction completed:

```text
app/route_sections/dashboard.py
```

This module now owns:

```text
/dashboard
```

The existing `main.dashboard` endpoint name was preserved.

Sixth extraction completed:

```text
app/route_sections/profiles.py
```

This module now owns:

```text
/profile
/users/<id>/profile
```

The existing `main.my_profile` and `main.user_profile` endpoint names were preserved.

Seventh extraction completed:

```text
app/route_sections/group_goals.py
```

This module now owns:

```text
/group-goals
/group-goals/create
/group-goals/<id>/contribute
/group-goals/<id>/fulfil
/group-goals/<id>/cancel
```

The existing `main.group_goals`, `main.create_group_goal`, `main.contribute_group_goal`, `main.fulfil_group_goal`, and `main.cancel_group_goal` endpoint names were preserved.

Eighth extraction completed:

```text
app/route_sections/leaderboard.py
```

This module now owns:

```text
/leaderboard
```

The existing `main.leaderboard` endpoint name was preserved.

Ninth extraction completed:

```text
app/route_sections/wishlist.py
```

This module now owns:

```text
/wishlist
/wishlist/request
/wishlist/requests/<id>/cancel
/admin/wishlist/add
/admin/wishlist/requests/<id>/approve
/admin/wishlist/requests/<id>/reject
/admin/wishlist/items/<id>/remove
/wishlist/items/<id>/contribute
/admin/wishlist/items/<id>/fulfil
/admin/wishlist/items/<id>/edit
/wishlist/archive
```

The existing `main.wishlist`, `main.request_wishlist_item`, `main.cancel_wishlist_request`, `main.admin_add_wishlist_item`, `main.approve_wishlist_request`, `main.reject_wishlist_request`, `main.remove_wishlist_item`, `main.contribute_wishlist_item`, `main.fulfil_wishlist_item`, `main.edit_wishlist_item`, and `main.wishlist_archive` endpoint names were preserved.

Tenth extraction completed:

```text
app/route_sections/request_archive.py
```

This module now owns:

```text
/requests/archive
```

The existing `main.request_archive` endpoint name was preserved.

### Visible "points" wording

Some internal names still use `point`/`points`. This is acceptable for fields, routes, comments, docstrings, and services. Visible UI text should use the household label where practical.

Visible wording already changed includes:

```text
Point Value -> Value
Point Cost -> Cost
Point Adjustment -> Balance Adjustment
Target Points -> Target Amount
Complete Task and Award Points -> Complete Task and Award
Contribute Points -> Contribute
Add Points to Wishlist Item -> Add to Wishlist Item
Points Label -> Balance Label
```

Do not rename internal database fields casually.

### Hardcoded SECRET_KEY fallback

`config.py` contains `SECRET_KEY = "change-this-later"` and `app/__init__.py` has a fallback of `"dev-secret-key-change-later"`. Production deployments must set `SECRET_KEY` in `.env`. Never use the fallback value on a real install.

### Seed logic

Default seed logic must remain idempotent and must run inside an app context.

### SQLite

SQLite is acceptable for the small self-hosted household use case. Avoid overengineering into PostgreSQL unless there is a real need.

### CSS caching

After CSS changes, hard refresh may be required:

```text
Ctrl + F5
```

or test in a private/incognito window.

## 15. Decisions already made

Do not relitigate unless the user explicitly asks:

- The app is called Project Meridian for now.
- It is a self-hosted household task/reward app.
- It uses Flask and SQLite.
- It is deployed through Docker Compose.
- It runs on the home server.
- The point ledger is the balance source of truth.
- Avatar/PIN login is the preferred login style.
- Admin and standard user roles are required.
- Hot Tasks already exist.
- Reward requests reserve points immediately.
- Cancelled/rejected rewards refund reserved points.
- Admins should not receive task points by default. A future opt-in participation mode may allow admins to earn points and join user-facing leaderboards when explicitly enabled.
- `household_settings.points_label` controls the visible points label where practical.
- HomeStack-style UI is the chosen design direction.
- Mobile compatibility matters.
- `.env`, databases, backups, and runtime files must not be tracked.
- Default admin should only be seeded if the database has zero users.
- Keep changes incremental, tested, and committed.

## 16. Working preferences

The developer prefers:

- direct, practical guidance
- copy-pasteable commands
- step-by-step instructions
- explanations of why steps matter
- full-file replacements or replacement ZIPs when practical
- small batches instead of risky large rewrites
- clear test commands after changes
- clear commit messages
- rollback/safety guidance when modifying production-like systems
- code comments that explain sections
- mobile-first design
- consistent UI across Project Meridian, Project Solace, and the home server dashboard
- Fedora/Docker Compose-compatible instructions
- careful handling of persistent data and secrets

When continuing work, give exact files to edit, exact commands to run, and what output to paste back if something fails.

## 17. Recommended handoff workflow for the next assistant

Start by checking the repo state:

```bash
cd <local-project-meridian-directory>

git status
git log --oneline --decorate -8
git branch -vv
git tag --list
```

Check app syntax:

```bash
python -m py_compile app/routes.py app/models.py app/forms.py app/__init__.py
python -m py_compile app/services/*.py
```

Check Docker locally:

```bash
docker compose down
docker compose up -d --build
docker logs project-meridian --tail=100
```

Check server state:

```bash
cd /opt/docker/project-meridian/app

git status
git log --oneline --decorate -8
docker compose ps
docker logs project-meridian --tail=100
```

Before database-affecting work, back up the SQLite database.

Continue work in this order:

1. Continue the `routes.py` modularisation in small route groups (section 14, Large `routes.py`).
2. Implement login PIN autofocus and numeric keypad (section 10).
3. Populate starting task and reward economy (section 11).
4. Smoke test mobile UI across all main pages.
5. Continue service-layer cleanup.

After each change: commit with a clear message and push to the repository.

## 18. One-sentence product definition

Project Meridian is a self-hosted Flask/SQLite household task and rewards app where users complete approved tasks to earn points, then spend or contribute those points toward rewards, wishlist items, and group goals while admins manage users, approvals, tasks, rewards, categories, reports, and the household points economy.
