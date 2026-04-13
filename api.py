from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from database import get_connection, get_nearest_infrastructures, save_substations

app = FastAPI(title="PostGIS Site Selector")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class BoundingBoxBody(BaseModel):
    south: float = Field(..., description="Southern latitude (min lat)")
    west: float = Field(..., description="Western longitude (min lon)")
    north: float = Field(..., description="Northern latitude (max lat)")
    east: float = Field(..., description="Eastern longitude (max lon)")


class NearestQuery(BaseModel):
    lon: float
    lat: float


@app.post("/api/substations/import")
def import_substations(body: BoundingBoxBody):
    if body.south >= body.north or body.west >= body.east:
        raise HTTPException(
            status_code=400,
            detail="Invalid bbox: need south < north and west < east.",
        )
    bbox = f"({body.south},{body.west},{body.north},{body.east})"
    conn = get_connection()
    try:
        cur = conn.cursor()
        stats = save_substations(cur, conn, bbox)
        cur.close()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=502, detail=str(e)) from e
    finally:
        conn.close()
    return {
        "ok": True,
        "bounding_box": bbox,
        **stats,
    }


@app.get("/api/nearest")
def nearest(lon: float, lat: float, limit: int = 5):
    if limit < 1 or limit > 50:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 50")
    conn = get_connection()
    try:
        cur = conn.cursor()
        items = get_nearest_infrastructures(cur, lon, lat, limit=limit)
        cur.close()
    finally:
        conn.close()
    return {"point": {"lon": lon, "lat": lat}, "nearest": items}
