# CFA_intake

Simple Django + SQLite app for a donation receiving warehouse.

## Features

- Login page for staff users
- Main donation intake form
- Donation log table with search and site filter
- Quantitative report cards:
- filtered result count
- all-time donation count
- last 30 days count
- Site summary table (donations by site)
- Donor memory/autocomplete suggestions by typing donor name or email
- Required notes field on intake

## Tech

- Django 6
- SQLite (`db.sqlite3`)

## Run Locally

```bash
python3 -m pip install django
python3 manage.py migrate
python3 manage.py createsuperuser
python3 manage.py runserver
```

Open:

- `http://127.0.0.1:8000/accounts/login/`

## Configuration

Environment variables are read from a `.env` file next to `manage.py` (or from
the systemd unit's environment on the server).

- `DONATION_VALUE_PER_POUND` – dollar value per pound used to estimate the value
  of in-kind donations from their recorded weight. Defaults to `3.90` if unset.
  The value is computed on read, so changing it re-values every donation.

```
DONATION_VALUE_PER_POUND=3.90
```

## Main Routes

- Login: `/accounts/login/`
- New donation intake: `/donations/new/`
- Donation log and reports: `/donations/log/`
- Donor suggestion endpoint: `/api/donor-suggestions/?q=<text>`
