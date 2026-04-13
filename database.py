import json
import os
from typing import Any

import psycopg2
import requests

# Public Overpass endpoints are often slow or return 504; we try several mirrors.
_DEFAULT_OVERPASS_URLS = (
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.fr/api/interpreter",
    "https://overpass-api.de/api/interpreter",
)


def _overpass_urls() -> tuple[str, ...]:
    custom = os.environ.get("OVERPASS_URL", "").strip()
    if custom:
        return (custom,)
    return _DEFAULT_OVERPASS_URLS


def get_connection():
    return psycopg2.connect(
        host=os.environ.get("PGHOST", "localhost"),
        port=int(os.environ.get("PGPORT", "5432")),
        dbname=os.environ.get("PGDATABASE", "gis"),
        user=os.environ.get("PGUSER", "postgres"),
        password=os.environ.get("PGPASSWORD", "postgres"),
    )


def fetch_overpass(query: str) -> tuple[dict[str, Any], str]:
    """
    POST the Overpass QL string (raw body). Tries several public mirrors on
    timeouts / overload (504) so imports are more reliable than a single host.
    """
    headers = {"User-Agent": "postgis-site-selector/0.1 (https://github.com)"}
    errors: list[str] = []
    for url in _overpass_urls():
        try:
            response = requests.post(
                url,
                data=query.encode("utf-8"),
                timeout=120,
                headers=headers,
            )
            if response.status_code in (429, 502, 503, 504):
                errors.append(f"{url}: HTTP {response.status_code}")
                continue
            response.raise_for_status()
            try:
                data = response.json()
            except ValueError as e:
                errors.append(f"{url}: not JSON ({e})")
                continue
            if not isinstance(data, dict):
                errors.append(f"{url}: unexpected JSON type")
                continue
            return data, url
        except requests.RequestException as e:
            errors.append(f"{url}: {e}")
            continue
    msg = "; ".join(errors) if errors else "no Overpass endpoints configured"
    raise RuntimeError(f"Overpass request failed ({msg})")


def _ensure_substations_schema(cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS substations
        (
            id TEXT PRIMARY KEY,
            name TEXT,
            tags JSONB,
            geom GEOMETRY ( POINT, 4326)
        );
        """
    )
    cursor.execute(
        """
        SELECT data_type FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'substations'
          AND column_name = 'id';
        """
    )
    row = cursor.fetchone()
    if row and row[0] == "bigint":
        # Legacy importer only stored OSM nodes; remap to stable string ids.
        cursor.execute(
            """
            ALTER TABLE substations
            ALTER COLUMN id TYPE TEXT USING ('node/' || id::text);
            """
        )


def _element_pk(item: dict[str, Any]) -> str | None:
    t = item.get("type")
    oid = item.get("id")
    if t in ("node", "way", "relation") and oid is not None:
        return f"{t}/{oid}"
    return None


def _element_lon_lat(item: dict[str, Any]) -> tuple[float, float] | None:
    t = item.get("type")
    if t == "node":
        lon, lat = item.get("lon"), item.get("lat")
        if lon is not None and lat is not None:
            return float(lon), float(lat)
    if t in ("way", "relation"):
        c = item.get("center") or {}
        lon, lat = c.get("lon"), c.get("lat")
        if lon is not None and lat is not None:
            return float(lon), float(lat)
    return None


def save_substations(cursor, connection, bounding_box: str) -> dict[str, Any]:
    """
    Fetch substations from Overpass (nodes, ways, relations with power=substation),
    insert into PostGIS. Ways/relations use out center for a representative point.

    OSM ids are scoped by type in the primary key (e.g. node/123 vs way/123).
    """
    _ensure_substations_schema(cursor)

    query = f"""
    [out:json][timeout:60];
    (
      node["power"="substation"]{bounding_box};
      way["power"="substation"]{bounding_box};
      relation["power"="substation"]{bounding_box};
    );
    out center;
    """
    data, overpass_url = fetch_overpass(query)

    remark = data.get("remark")
    elements = data.get("elements") or []

    inserted = 0
    skipped_no_geom = 0
    for item in elements:
        pk = _element_pk(item)
        coords = _element_lon_lat(item)
        if not pk or not coords:
            skipped_no_geom += 1
            continue
        lon, lat = coords
        tags = item.get("tags") or {}
        cursor.execute(
            """
            INSERT INTO substations (id, name, tags, geom)
            VALUES (%s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326))
            ON CONFLICT (id) DO NOTHING;
            """,
            (
                pk,
                tags.get("name"),
                json.dumps(tags),
                lon,
                lat,
            ),
        )
        inserted += cursor.rowcount

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_substations_geom
        ON substations
        USING GIST (geom);
        """
    )

    connection.commit()
    return {
        "inserted_rows": inserted,
        "elements_from_overpass": len(elements),
        "skipped_without_point": skipped_no_geom,
        "overpass_remark": remark,
        "overpass_endpoint": overpass_url,
    }


def get_nearest_infrastructures(cursor, lon: float, lat: float, limit: int = 5) -> list[dict[str, Any]]:
    cursor.execute(
        """
        SELECT
            id,
            name,
            ST_X(geom) AS lon,
            ST_Y(geom) AS lat
        FROM substations
        ORDER BY geom <-> ST_SetSRID(ST_MakePoint(%s, %s), 4326)
        LIMIT %s;
        """,
        (lon, lat, limit),
    )
    rows = cursor.fetchall()
    return [
        {"id": r[0], "name": r[1], "lon": float(r[2]), "lat": float(r[3])}
        for r in rows
    ]
