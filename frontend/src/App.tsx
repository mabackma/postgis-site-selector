import { useEffect, useMemo, useState } from "react";
import { MapContainer, Marker, Popup, TileLayer, useMap } from "react-leaflet";

function Recenter({ lat, lon }: { lat: number; lon: number }) {
  const map = useMap();
  useEffect(() => {
    map.setView([lat, lon], map.getZoom());
  }, [lat, lon, map]);
  return null;
}

type Infra = {
  id: string | number;
  name: string | null;
  lon: number;
  lat: number;
};

const defaultBbox = {
  south: 60.1,
  west: 24.8,
  north: 60.3,
  east: 25.2,
};

const defaultPoint = { lon: 24.94, lat: 60.17 };

export default function App() {
  const [south, setSouth] = useState(String(defaultBbox.south));
  const [west, setWest] = useState(String(defaultBbox.west));
  const [north, setNorth] = useState(String(defaultBbox.north));
  const [east, setEast] = useState(String(defaultBbox.east));

  const [lon, setLon] = useState(String(defaultPoint.lon));
  const [lat, setLat] = useState(String(defaultPoint.lat));

  const [importMsg, setImportMsg] = useState<string | null>(null);
  const [importErr, setImportErr] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);

  const [nearest, setNearest] = useState<Infra[]>([]);
  const [nearestMsg, setNearestMsg] = useState<string | null>(null);
  const [nearestErr, setNearestErr] = useState<string | null>(null);
  const [loadingNearest, setLoadingNearest] = useState(false);

  const parsedPoint = useMemo(() => {
    const lo = Number(lon);
    const la = Number(lat);
    if (!Number.isFinite(lo) || !Number.isFinite(la)) return null;
    return { lon: lo, lat: la };
  }, [lon, lat]);

  const mapCenter = parsedPoint ?? [60.17, 24.94] as [number, number];

  async function runImport() {
    setImporting(true);
    setImportMsg(null);
    setImportErr(null);
    const s = Number(south);
    const w = Number(west);
    const n = Number(north);
    const e = Number(east);
    if (![s, w, n, e].every((x) => Number.isFinite(x))) {
      setImportErr("Enter valid numbers for all bbox fields.");
      setImporting(false);
      return;
    }
    try {
      const res = await fetch("/api/substations/import", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ south: s, west: w, north: n, east: e }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setImportErr(typeof data.detail === "string" ? data.detail : res.statusText);
        return;
      }
      const ins = data.inserted_rows ?? 0;
      const total = data.elements_from_overpass ?? "—";
      const ep = data.overpass_endpoint ? ` Server: ${data.overpass_endpoint}.` : "";
      const remark = data.overpass_remark
        ? ` Overpass note: ${data.overpass_remark}`
        : "";
      setImportMsg(
        `Imported ${ins} new row(s) (${total} objects returned from Overpass: nodes, ways, and relations with power=substation; existing ids are skipped).${ep}${remark}`,
      );
    } catch (err) {
      setImportErr(err instanceof Error ? err.message : "Request failed");
    } finally {
      setImporting(false);
    }
  }

  async function runNearest() {
    if (!parsedPoint) {
      setNearestErr("Enter valid longitude and latitude.");
      return;
    }
    setLoadingNearest(true);
    setNearestMsg(null);
    setNearestErr(null);
    try {
      const q = new URLSearchParams({
        lon: String(parsedPoint.lon),
        lat: String(parsedPoint.lat),
        limit: "5",
      });
      const res = await fetch(`/api/nearest?${q}`);
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setNearestErr(typeof data.detail === "string" ? data.detail : res.statusText);
        setNearest([]);
        return;
      }
      const items: Infra[] = data.nearest ?? [];
      setNearest(items);
      setNearestMsg(`Showing ${items.length} nearest substation(s) from the database.`);
    } catch (err) {
      setNearestErr(err instanceof Error ? err.message : "Request failed");
      setNearest([]);
    } finally {
      setLoadingNearest(false);
    }
  }

  return (
    <div className="app">
      <h1>PostGIS site selector</h1>

      <section>
        <h2>1. Load substations into PostGIS</h2>
        <p style={{ margin: "0 0 0.75rem", fontSize: "0.875rem", color: "#555" }}>
          Overpass bbox format: south, west, north, east (decimal degrees). Data is fetched from
          OpenStreetMap and stored locally; duplicate OSM node ids are ignored.
        </p>
        <div className="grid">
          <label>
            South (min lat)
            <input value={south} onChange={(e) => setSouth(e.target.value)} />
          </label>
          <label>
            West (min lon)
            <input value={west} onChange={(e) => setWest(e.target.value)} />
          </label>
          <label>
            North (max lat)
            <input value={north} onChange={(e) => setNorth(e.target.value)} />
          </label>
          <label>
            East (max lon)
            <input value={east} onChange={(e) => setEast(e.target.value)} />
          </label>
          <button type="button" onClick={runImport} disabled={importing}>
            {importing ? "Importing…" : "Import substations"}
          </button>
        </div>
        {importMsg && <div className="msg ok">{importMsg}</div>}
        {importErr && <div className="msg err">{importErr}</div>}
      </section>

      <section>
        <h2>2. Nearest infrastructures to a point</h2>
        <div className="grid">
          <label>
            Longitude
            <input value={lon} onChange={(e) => setLon(e.target.value)} />
          </label>
          <label>
            Latitude
            <input value={lat} onChange={(e) => setLat(e.target.value)} />
          </label>
          <button type="button" onClick={runNearest} disabled={loadingNearest}>
            {loadingNearest ? "Loading…" : "Find 5 nearest"}
          </button>
        </div>
        {nearestMsg && <div className="msg ok">{nearestMsg}</div>}
        {nearestErr && <div className="msg err">{nearestErr}</div>}
        {nearest.length > 0 && (
          <ol className="list">
            {nearest.map((p, i) => (
              <li key={p.id}>
                #{i + 1}: {p.name ?? "(unnamed)"} — {p.lat.toFixed(5)}, {p.lon.toFixed(5)}
              </li>
            ))}
          </ol>
        )}
        <div className="map-wrap">
          <MapContainer
            center={[mapCenter.lat, mapCenter.lon]}
            zoom={12}
            style={{ height: "100%", width: "100%" }}
            scrollWheelZoom
          >
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            {parsedPoint && <Recenter lat={parsedPoint.lat} lon={parsedPoint.lon} />}
            {parsedPoint && (
              <Marker position={[parsedPoint.lat, parsedPoint.lon]}>
                <Popup>Query point</Popup>
              </Marker>
            )}
            {nearest.map((p) => (
              <Marker key={p.id} position={[p.lat, p.lon]}>
                <Popup>
                  {p.name ?? "Substation"}
                  <br />
                  id: {p.id}
                </Popup>
              </Marker>
            ))}
          </MapContainer>
        </div>
      </section>
    </div>
  );
}
