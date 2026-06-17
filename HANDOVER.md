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
- **Repository:** `https://github.com/Moose151/project-meridian`
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
cd ~/Documents/project-meridian

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
- `set_password()`
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
```

`points_label` is important. Visible UI text should use the configured household points label where practical rather than hardcoded “points”. Internal variable names like `point_cost`, `point_value`, and `points_label` are acceptable and should not be renamed casually.

### Task

Known concepts:

- task name/title
- description
- category
- point value
- active/hidden state
- persistent vs one-time task
- Hot Tasks
- Hot Tasks can optionally add bonus points
- admin can create/edit/manage/delete/hide tasks
- admin can complete a task for a user
- standard users submit task completions for approval

Important: **Hot Tasks are already implemented**. Do not treat Hot Tasks as a missing dependency in future planning.

### TaskCompletion

Known concepts:

- user submits a completion request
- admin approves or rejects
- points are not awarded until approval
- task history exists
- rejection workflow exists

### PointTransaction

Known concepts:

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

Known concepts:

- reward name
- description
- point cost
- stock/availability
- category
- active/hidden state
- admin can create/edit/manage rewards
- users can request rewards

### RewardPurchase / reward request

Known behaviour:

- a user requests a reward
- points are reserved/deducted immediately
- admin approves or rejects the request
- if rejected or cancelled, reserved points are refunded
- service layer should prevent double deductions/refunds

### Category

Known concepts:

- categories are used for tasks and rewards
- admin can manage categories
- future filtering/grouping should use categories consistently

### WishlistItem

Known concepts:

- wishlist items belong to one user
- users can request wishlist items
- admin can add or approve wishlist items
- admin controls or finalises the item name/description/cost
- users contribute points toward wishlist items over time
- the app calculates active saved points
- the app calculates remaining points required
- item can be considered funded when saved points reach the point cost
- archive workflow exists

### WishlistContribution

Known concepts:

- stores user point contributions toward wishlist items
- creates point transactions
- contributes to point history

### GroupGoal

Known concepts:

- shared household goals
- users contribute points toward a common target
- app calculates contributed points and remaining points
- standard users can contribute
- admins do not normally contribute

## 7. Current feature set

### Authentication and login

Built/expected:

- avatar/user-card login
- PIN/password entry
- Flask-Login session handling
- admin and standard user roles
- default admin seeding for fresh installs has been added or is in progress
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

Default admin seeding must be idempotent and only create the default admin if the database has zero users.

### User dashboard

Built/expected:

- current balance
- recent point activity
- available task/reward/wishlist/group-goal navigation
- HomeStack-style cards and layout

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

Users can view tasks, submit task completions, and view task history.

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

Admin can create rewards, edit rewards, manage rewards, set cost/category/stock/visibility, and approve/reject purchases.

Users can browse the reward shop, request rewards, spend/reserve points, and view reward history.

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

### Wishlist

Built/expected:

- wishlist page
- request wishlist item
- admin add wishlist item
- approve/reject wishlist request
- edit wishlist item
- contribute to wishlist item
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

Relevant templates:

```text
group_goals.html
create_group_goal.html
contribute_group_goal.html
```

### Reports

Built/expected:

- admin reports page
- CSV exports
- point transaction report
- user/task/reward activity reporting

Relevant template:

```text
admin_reports.html
```

### Categories

Built/expected:

- manage categories
- categories apply to tasks and rewards
- future filtering/grouping should be category-aware

Relevant template:

```text
manage_categories.html
```

### Badges

A badge service exists.

Known badge concepts:

- saved toward wishlist item
- contributed to group goal
- total earned milestone

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

### `notification_service.py`

Purpose: centralise notification creation/handling.

### `badge_service.py`

Purpose: badge award/evaluation logic.

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

A bug was found where navbar dropdowns appeared behind cards. Add/keep this patch at the bottom of `homestack.css`:

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

Desired feature:

When a user is selected at login, the cursor should automatically go to the PIN input. On mobile, tapping the user should bring up the numeric keypad instead of the full keyboard.

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
- Navbar dropdown layering fix identified.
- Dynamic wording cleanup for visible “points” labels.
- Default admin seed feature planned/added to solve fresh-install lockout.
- Login numeric PIN autofocus feature identified as the next UX improvement.
- Economy baseline discussed.

Recent tag context:

```text
stable-service-layer
stable-homestack-ui
```

## 13. Features yet to implement or confirm

Priority items:

1. Confirm default admin seeding is committed and deployed.
2. Confirm fresh database creates default admin:
   - display name: Admin
   - username: admin
   - PIN/password: 1234
   - role: admin
3. Implement or confirm login user-card-to-PIN autofocus.
4. Confirm mobile numeric keypad appears on login.
5. Confirm navbar dropdown layering fix is committed.
6. Populate starting task and reward economy.
7. Smoke test mobile layout across all main pages.
8. Add or improve backup/export tooling if not present.
9. Continue gradual service-layer refactoring.
10. Consider kiosk/touchscreen mode after core household use is stable.

Possible future features:

- Kiosk/touchscreen mode for Raspberry Pi home hub.
- More badges and milestone logic.
- Better leaderboard options.
- More group goal lifecycle states: active, funded, completed, archived.
- More wishlist lifecycle states.
- More reward stock handling.
- More admin CSV/report exports.
- Backup/restore page.
- More modular dashboard widgets.
- More mobile-specific navigation improvements.
- Reverse proxy/domain setup.
- Optional household-specific points label such as stars or credits.

## 14. Known issues and technical debt

### Large `routes.py`

`routes.py` is still large. Some logic has been moved into services, but more gradual extraction is warranted. Avoid a risky full rewrite.

### Visible “points” wording

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

### Fresh install lockout

Fresh installs without users were unusable. The default admin seed is intended to solve this.

## 15. Decisions already made

Do not relitigate unless Nick explicitly asks:

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
- Admins should not normally receive task points.
- `household_settings.points_label` controls the visible points label where practical.
- HomeStack-style UI is the chosen design direction.
- Mobile compatibility matters.
- `.env`, databases, backups, and runtime files must not be tracked.
- Default admin should only be seeded if the database has zero users.
- Keep changes incremental, tested, and committed.

## 16. Nick’s working preferences

Nick prefers:

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
cd ~/Documents/project-meridian

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

1. Confirm seed/default admin behaviour.
2. Confirm login PIN autofocus/numeric keypad.
3. Confirm dropdown layering fix.
4. Add first stable task/reward economy.
5. Smoke test mobile UI.
6. Add backup/restore tooling.
7. Continue service-layer cleanup.

## 18. One-sentence product definition

Project Meridian is a self-hosted Flask/SQLite household task and rewards app where users complete approved tasks to earn points, then spend or contribute those points toward rewards, wishlist items, and group goals while admins manage users, approvals, tasks, rewards, categories, reports, and the household points economy.
