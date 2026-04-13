import json
import os
from typing import Any

import psycopg2
import requests


def get_connection():
    return psycopg2.connect(
        host=os.environ.get("PGHOST", "localhost"),
        port=int(os.environ.get("PGPORT", "5432")),
        dbname=os.environ.get("PGDATABASE", "gis"),
        user=os.environ.get("PGUSER", "postgres"),
        password=os.environ.get("PGPASSWORD", "postgres"),
    )


def get_geojson(query: str) -> dict[str, Any]:
    response = requests.post(
        "https://overpass-api.de/api/interpreter",
        data=query,
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


def save_substations(cursor, connection, bounding_box: str) -> int:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS substations
        (
            id BIGINT PRIMARY KEY,
            name TEXT,
            tags JSONB,
            geom GEOMETRY ( POINT, 4326)
        );
        """
    )

    query = f"""
    [out:json][timeout:25];
    node["power"="substation"]{bounding_box};
    out;
    """
    data = get_geojson(query)

    inserted = 0
    for item in data.get("elements", []):
        if item.get("type") != "node":
            continue
        cursor.execute(
            """
            INSERT INTO substations (id, name, tags, geom)
            VALUES (%s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326))
            ON CONFLICT (id) DO NOTHING;
            """,
            (
                item["id"],
                item.get("tags", {}).get("name"),
                json.dumps(item.get("tags", {})),
                item["lon"],
                item["lat"],
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
    return inserted


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
