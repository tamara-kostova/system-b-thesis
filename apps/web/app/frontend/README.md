Frontend startup
=================

This document explains how to run the frontend development server for the Next.js app located in apps/web and how to use the repository Makefile to help start the backend services.

Prerequisites
-------------
- Node.js (16+) and npm installed
- A Python virtual environment with backend deps (see project README)

Install frontend dependencies
-----------------------------
From the repository root:

    make frontend-install

or manually:

    cd apps/web
    npm ci

Run the frontend dev server
--------------------------
To start the Next.js dev server:

From the repository root:

    make frontend

or manually:

    cd apps/web
    npm run dev

By default the frontend runs on port 3001 (see apps/web/package.json).

Start the backend (APIs)
------------------------
The repository provides a convenience Makefile target that starts the backend APIs and UIs (using the Python virtualenv). From the project root:

    make start

This runs start.sh, which launches the FastAPI services and Streamlit UIs as background processes (logs are written to logs/).

Typical development workflow
--------------------------
1. Ensure the database is available (Postgres):

    make db

The repository `Makefile` provides a `db` target which runs `docker compose up -d postgres`.

2. Start backend services in background:

       make start

3. Install frontend deps (one-time):

       make frontend-install

4. Run frontend dev server (in a separate terminal):

       make frontend

Now open the frontend at http://localhost:3001 and APIs at their respective ports (e.g. http://localhost:8002 for Permit Service).

Troubleshooting
---------------
- If the frontend doesn't start, run `cd apps/web && npm run dev` to see errors.
- If the backend can't connect to Postgres, run `docker compose up -d postgres` and re-run `make start`.
