# PostGIS site selector

Small full-stack app: import OpenStreetMap **power substations** into **PostGIS** for a bounding box, then query the **nearest** substations to a point and show them on a **Leaflet** map (React UI + FastAPI backend).

## Prerequisites

- **PostgreSQL** with **PostGIS** enabled, and a database your user can write to (default name below is `gis`).
- **Python 3.12+**
- **Node.js** (includes `npm`) for the frontend

## Project layout

| Path | Role |
|------|------|
| `api.py` | FastAPI app (`/api/...`) |
| `database.py` | DB connection, Overpass fetch, `substations` table, nearest-neighbor query |
| `main.py` | Optional CLI demo using the same helpers |
| `frontend/` | Vite + React + react-leaflet UI |

The **frontend** (`frontend/`) was built with [Cursor](https://cursor.com).

## Database configuration

Defaults match a typical local install. Override with environment variables if needed:

| Variable | Default |
|----------|---------|
| `PGHOST` | `localhost` |
| `PGPORT` | `5432` |
| `PGDATABASE` | `gis` |
| `PGUSER` | `postgres` |
| `PGPASSWORD` | `postgres` |

| `OVERPASS_URL` | (optional) Set to a single Overpass API base URL if you do not want the built-in mirror fallback (default: tries several public `…/api/interpreter` endpoints). |

Create the database and enable PostGIS once (example):

```sql
CREATE DATABASE gis;
\c gis
CREATE EXTENSION postgis;
```

## Run the backend

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn api:app --reload --host 127.0.0.1 --port 8000
```

Interactive API docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

## Run the frontend

In a **second** terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open the URL Vite prints (usually [http://localhost:5173](http://localhost:5173)). During development, `/api` is proxied to `http://127.0.0.1:8000` (see `frontend/vite.config.ts`), so keep the API running.

### Windows: `npm` and PowerShell

If you see *running scripts is disabled*, either:

- Use the batch shim: `npm.cmd install` and `npm.cmd run dev`, or  
- Allow scripts for your user:  
  `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`

## Using the UI

1. **Load substations** — Enter south, west, north, east (decimal degrees, Overpass order). The app queries the [Overpass API](https://overpass-api.de/) for `power=substation` **nodes, ways, and relations** (ways/relations use a center point) and inserts them into `substations`. Primary keys look like `node/123`, `way/456` so node and way ids never collide. Rows already in the table are skipped on re-import.
2. **Nearest to a point** — Enter longitude and latitude, then **Find 5 nearest**. The map shows your point and up to five nearest rows from the database.

## HTTP API

- `POST /api/substations/import`  
  JSON body: `{ "south": number, "west": number, "north": number, "east": number }`  
  Response includes `inserted_rows`, `elements_from_overpass` (how many OSM objects Overpass returned), and optional `overpass_remark` if the API left a note (e.g. load warnings).

- `GET /api/nearest?lon=...&lat=...&limit=5`  
  Response: `{ "point": { "lon", "lat" }, "nearest": [ { "id", "name", "lon", "lat" }, ... ] }`  
  `limit` is optional (1–50, default 5).

## Optional CLI

With the venv activated and `PG*` set as needed:

```powershell
python main.py
```

This uses the hard-coded bbox and sample coordinates in `main.py` for a quick smoke test.

## License

This project is licensed under the [MIT License](LICENSE).
