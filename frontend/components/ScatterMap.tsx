"use client";

/**
 * ScatterMap — a client-only Leaflet map showing the GPS positions of uploaded
 * site photos.  We load react-leaflet/leaflet inside a useEffect so this stays
 * strictly client-rendered (Leaflet touches `window` at import time).
 */
import { useEffect, useMemo, useState } from "react";
import type { SpatialManifest, SpatialContext } from "@/lib/types";

// react-leaflet and leaflet don't load on the server.  Use a relaxed
// component-type so TS doesn't complain.
type RLModule = typeof import("react-leaflet");

interface ScatterMapProps {
  spatialContext?: SpatialManifest | null;
  className?: string;
  height?: number;
}

interface ResolvedComponents {
  MapContainer: RLModule["MapContainer"];
  TileLayer: RLModule["TileLayer"];
  Marker: RLModule["Marker"];
  Popup: RLModule["Popup"];
}

/** Centre + zoom for a set of photo GPS coords (defaults to PH if none). */
function autoBounds(entries: [string, SpatialContext][]) {
  if (entries.length === 0) return { centre: [12.8797, 121.774] as [number, number], zoom: 6 };
  if (entries.length === 1) {
    const [, c] = entries[0];
    return { centre: [c.latitude ?? 0, c.longitude ?? 0] as [number, number], zoom: 15 };
  }
  const lats = entries.map(([, c]) => c.latitude ?? 0);
  const lngs = entries.map(([, c]) => c.longitude ?? 0);
  const minLat = Math.min(...lats);
  const maxLat = Math.max(...lats);
  const minLng = Math.min(...lngs);
  const maxLng = Math.max(...lngs);
  const span = Math.max(maxLat - minLat, maxLng - minLng);
  const zoom = span > 5 ? 8 : span > 1 ? 11 : span > 0.1 ? 14 : 16;
  return { centre: [(minLat + maxLat) / 2, (minLng + maxLng) / 2] as [number, number], zoom };
}

export default function ScatterMap({ spatialContext, className = "", height = 280 }: ScatterMapProps) {
  const [rl, setRl] = useState<ResolvedComponents | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const [reactLeaflet, leaflet] = await Promise.all([
        import("react-leaflet"),
        import("leaflet"),
      ]);
      // Patch the default icon to use a CDN so it works in Next.js builds.
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      delete (leaflet.Icon.Default.prototype as any)._getIconUrl;
      leaflet.Icon.Default.mergeOptions({
        iconRetinaUrl:
          "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png",
        iconUrl:
          "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png",
        shadowUrl:
          "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png",
      });
      if (cancelled) return;
      setRl({
        MapContainer: reactLeaflet.MapContainer,
        TileLayer: reactLeaflet.TileLayer,
        Marker: reactLeaflet.Marker,
        Popup: reactLeaflet.Popup,
      });
      setReady(true);
    })().catch(() => {
      // Leave ready=false; render a placeholder.
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const entries = useMemo<[string, SpatialContext][]>(() => {
    if (!spatialContext?.files) return [];
    return Object.entries(spatialContext.files).filter(
      (kv): kv is [string, SpatialContext] =>
        kv[1] !== null &&
        typeof kv[1].latitude === "number" &&
        typeof kv[1].longitude === "number",
    );
  }, [spatialContext]);

  const { centre, zoom } = useMemo(() => autoBounds(entries), [entries]);

  if (!ready || !rl) {
    return (
      <div
        className={`flex items-center justify-center rounded-md bg-slate-800 text-slate-400 text-xs ${className}`}
        style={{ minHeight: height }}
      >
        Loading map…
      </div>
    );
  }

  if (entries.length === 0) {
    return (
      <div
        className={`flex items-center justify-center rounded-md bg-slate-800 text-slate-400 text-xs ${className}`}
        style={{ minHeight: height }}
      >
        No GPS data available for the uploaded photos.
      </div>
    );
  }

  const { MapContainer, TileLayer, Marker, Popup } = rl;
  return (
    <div className={className} style={{ minHeight: height }}>
      <MapContainer
        center={centre}
        zoom={zoom}
        scrollWheelZoom
        style={{ height, width: "100%", borderRadius: "0.375rem" }}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {entries.map(([filename, ctx]) => {
          const lat = ctx.latitude as number;
          const lng = ctx.longitude as number;
          const loc = ctx.site_location;
          return (
            <Marker key={filename} position={[lat, lng]}>
              <Popup>
                <div className="text-xs">
                  <p className="font-semibold">{filename}</p>
                  {loc?.region && <p>{loc.region}</p>}
                  {loc?.municipality && (
                    <p>
                      {loc.municipality}
                      {loc.barangay ? `, ${loc.barangay}` : ""}
                    </p>
                  )}
                  <p className="text-slate-500">
                    {lat.toFixed(6)}, {lng.toFixed(6)}
                    {ctx.accuracy_m != null ? ` · ±${ctx.accuracy_m}m` : ""}
                  </p>
                </div>
              </Popup>
            </Marker>
          );
        })}
      </MapContainer>
    </div>
  );
}