# Project Meridian

> A self-hosted household task and rewards app where completing chores earns points you can spend on rewards, wishlist items, and shared group goals.

Project Meridian is built for small households that want a lightweight, fun way to make everyday contributions visible and rewarding. It is not a workplace productivity tool or a school behaviour system — it is a simple household motivation and reward system with admin-controlled approvals and a configurable points economy.

**The core loop:**

1. Admin creates users, tasks, rewards, and goals.
2. Users log in with their avatar card and PIN.
3. Users complete tasks and submit them for approval.
4. Admin approves completions — points are awarded.
5. Users spend points in the reward shop, save toward wishlist items, or contribute to shared group goals.

---

## Tech stack

- Python / Flask
- SQLite (via Flask-SQLAlchemy and Flask-Migrate)
- Gunicorn
- Docker / Docker Compose
- Jinja2 templates
- Bootstrap + custom CSS

---

## Requirements

- Docker and Docker Compose (recommended), **or**
- Python 3.10+

---

## Quick start with Docker

**Linux / macOS:**

```bash
git clone https://github.com/Moose151/project-meridian.git
cd project-meridian
cp .env.example .env
```

Edit `.env` with a strong secret key and your chosen admin credentials (see [Configuration](#configuration)), then:

```bash
docker compose up -d --build
```

Open [http://localhost:8000](http://localhost:8000) and log in with the credentials you set.

**Windows:**

Install [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/) and ensure it is running, then open PowerShell:

```powershell
git clone https://github.com/Moose151/project-meridian.git
cd project-meridian
copy .env.example .env
notepad .env
docker compose up -d --build
```

Open [http://localhost:8000](http://localhost:8000).

To stop:

```powershell
docker compose down
```

---

## Local development

### Linux / macOS

```bash
git clone https://github.com/Moose151/project-meridian.git
cd project-meridian
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env`, then run:

```bash
python run.py
```

Open [http://localhost:8000](http://localhost:8000).

### Windows

Install [Python 3](https://www.python.org/downloads/windows/) (tick **Add Python to PATH**) and [Git for Windows](https://git-scm.com/download/win), then open PowerShell:

```powershell
git clone https://github.com/Moose151/project-meridian.git
cd project-meridian
python -m venv .venv
.venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
notepad .env
python run.py
```

Open [http://localhost:8000](http://localhost:8000).

To deactivate the virtual environment when done:

```powershell
.venv\Scripts\deactivate
```

---

## Configuration

Copy `.env.example` to `.env` and fill in your values. The real `.env` must never be committed — only `.env.example` (with placeholders) is tracked by Git.

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | Yes | Random string for session signing. Generate with `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `ADMIN_USERNAME` | Yes | Username for the initial admin account |
| `ADMIN_PASSWORD` | Yes | Password / PIN for the initial admin account |
| `DATABASE_URL` | Yes | `sqlite:////app/instance/meridian.db` for Docker · `sqlite:///instance/meridian.db` for local dev |
| `FLASK_DEBUG` | No | `true` for local dev · `false` (default) for production |

On a fresh install, a default admin account is seeded automatically if no users exist. Change the default credentials immediately after first login.

---

## Updating

Back up your data first (see [Backups](#backups)), then:

```bash
git pull origin main
docker compose down
docker compose build --no-cache
docker compose up -d
```

---

## SELinux hosts (Fedora / RHEL)

The `docker-compose.yml` volume mount uses `:Z` for SELinux relabelling. Do not remove it on SELinux-enforcing hosts.

If you see permission errors on the `instance/` folder after updating:

```bash
sudo chown -R 1000:1000 instance
```

---

## Backups

Download a backup of the database from **Admin → Reports → Download Database Backup** in the app, or copy the SQLite file directly:

```bash
cp instance/meridian.db meridian-backup-$(date +%F).db
```

Always back up before pulling a new version or making database changes.

---

## Features

### Users and login

- Avatar card and PIN login — tap your card, enter your PIN
- Admin and standard user roles
- Admin can create, edit, disable, restore, and delete users
- Admin can reset user PINs and manually adjust point balances

### Tasks

- Admin creates tasks with a point value, category, and completion behaviour (persistent or one-time)
- Hot Tasks — flagged tasks with a bonus point value and a custom label
- Users submit task completions for admin approval
- Users can cancel pending submissions
- Admin can approve, reject (with a reason), or complete tasks on behalf of users
- Points are only awarded after approval

### Reward shop

- Admin creates rewards with a point cost, category, and visibility toggle
- Users browse the shop and request rewards
- Points are reserved immediately on request
- Admin approves or rejects requests — rejected requests refund the reserved points
- Users can cancel pending requests

### Points economy

- Point ledger is the source of truth for balances
- Points are earned through approved task completions
- Points are spent or contributed via rewards, wishlist items, and group goals
- Rejected or cancelled requests refund reserved points
- Admin can make manual balance adjustments
- Point history page shows all transactions

### Wishlist

- Users request new wishlist items for admin approval
- Admin can add, edit, and fulfil wishlist items
- Users save points toward their wishlist items over time
- Items are marked funded when saved points reach the target

### Group goals

- Admin creates shared household goals with a point target
- Any user can contribute points toward a group goal
- Admin marks goals as fulfilled or cancelled

### Leaderboard

- Rankings by current balance, total points earned, and tasks completed
- Total earned is not reduced by spending — it is a record of contribution

### Badges

Seven badges are awarded automatically when milestones are reached:

| Badge | Condition |
|---|---|
| First Task | First approved task completion |
| Task Starter | 5 approved task completions |
| Task Champion | 10 approved task completions |
| Wishlist Saver | Contributed toward a wishlist item |
| Goal Reached | Fully funded a wishlist item |
| Team Player | Contributed toward a group goal |
| Big Earner | 100 total points earned |

### Admin tools

- Approval queues for task completions, reward requests, and wishlist requests
- Unified request archive (completed, rejected, and cancelled)
- User management
- Task and reward management with categories
- Household settings including a configurable points label
- Reports: point history, task activity, reward requests, user list
- CSV exports for all report types
- Database backup download

---

## License

Project Meridian is personal/hobbyist software shared publicly. No formal license is currently attached. If you intend to fork or redistribute it, please open an issue to discuss.
