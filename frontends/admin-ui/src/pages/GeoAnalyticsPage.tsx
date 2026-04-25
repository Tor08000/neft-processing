import { useCallback, useEffect, useMemo, useState } from "react";
import {
  type GeoBounds,
  type GeoMetric,
  type GeoOverlayKind,
  type GeoStation,
  type GeoTile,
  fetchGeoOverlayTiles,
  fetchGeoStationsOverlay,
  fetchGeoTiles,
  tileToBounds,
} from "../api/geoAnalytics";
import { describeRuntimeError, type RuntimeErrorMeta } from "../api/runtimeError";
import { Loader } from "../components/Loader/Loader";
import { EmptyState } from "../components/common/EmptyState";
import { ErrorState } from "../components/common/ErrorState";

const METRICS: GeoMetric[] = ["tx_count", "amount_sum", "declined_count", "risk_red_count"];
const OVERLAYS: GeoOverlayKind[] = ["RISK_RED", "HEALTH_OFFLINE", "HEALTH_DEGRADED"];
const OVERLAY_COLORS: Record<GeoOverlayKind, string> = {
  RISK_RED: "#dc2626",
  HEALTH_OFFLINE: "#111827",
  HEALTH_DEGRADED: "#f97316",
};

const DEFAULT_BOUNDS: GeoBounds = {
  minLat: 55.45,
  minLon: 37.2,
  maxLat: 56.0,
  maxLon: 37.95,
};

const DATE_RANGES = [
  { label: "Last 1d", value: "1" },
  { label: "Last 7d", value: "7" },
  { label: "Last 30d", value: "30" },
];

const geoPageCopy = {
  mapError: {
    title: "Geo layer unavailable",
  },
  mapEmpty: {
    title: "No geo data for the selected range",
    description: "The current date range and layer settings did not return any geo tiles yet.",
  },
  drillDown: {
    title: "Drill-down stations",
    loading: "Loading stations",
    emptyTitle: "No stations in the selected tile",
    emptyDescription: "The selected geo tile returned no stations for the current metric and overlay.",
    firstUseTitle: "Choose a tile to inspect stations",
    firstUseDescription: "Select any visible tile on the map to open the station drill-down for that geo segment.",
    errorTitle: "Failed to load drill-down stations",
  },
  actions: {
    retry: "Retry",
    refreshLayer: "Refresh layer",
  },
} as const;

const toIsoRange = (days: number) => {
  const end = new Date();
  const start = new Date(end);
  start.setDate(end.getDate() - days);
  return { dateFrom: start.toISOString(), dateTo: end.toISOString() };
};

const getAlpha = (value: number, maxValue: number, opacity: number) => {
  if (!maxValue || maxValue <= 0) {
    return 0.2;
  }
  return Math.max(0.1, Math.min(1, (value / maxValue) * opacity));
};

const projectTileToViewport = (bounds: GeoBounds, tile: GeoTile) => {
  const tileBounds = tileToBounds(tile);
  const width = bounds.maxLon - bounds.minLon;
  const height = bounds.maxLat - bounds.minLat;
  if (width <= 0 || height <= 0) return null;

  const left = ((tileBounds.minLon - bounds.minLon) / width) * 100;
  const right = ((tileBounds.maxLon - bounds.minLon) / width) * 100;
  const top = ((bounds.maxLat - tileBounds.maxLat) / height) * 100;
  const bottom = ((bounds.maxLat - tileBounds.minLat) / height) * 100;

  if (right < 0 || left > 100 || bottom < 0 || top > 100) return null;

  return {
    left: Math.max(0, left),
    top: Math.max(0, top),
    width: Math.max(0.5, Math.min(100, right) - Math.max(0, left)),
    height: Math.max(0.5, Math.min(100, bottom) - Math.max(0, top)),
  };
};

export default function GeoAnalyticsPage() {
  const [selectedDays, setSelectedDays] = useState("7");
  const [zoom, setZoom] = useState(10);
  const [metric, setMetric] = useState<GeoMetric>("tx_count");
  const [overlayKind, setOverlayKind] = useState<GeoOverlayKind>("RISK_RED");
  const [baseEnabled, setBaseEnabled] = useState(true);
  const [overlayEnabled, setOverlayEnabled] = useState(true);
  const [opacity, setOpacity] = useState(0.6);
  const [tiles, setTiles] = useState<GeoTile[]>([]);
  const [overlayTiles, setOverlayTiles] = useState<GeoTile[]>([]);
  const [loadingTiles, setLoadingTiles] = useState(false);
  const [tilesError, setTilesError] = useState<RuntimeErrorMeta | null>(null);
  const [mapBounds, setMapBounds] = useState<GeoBounds>(DEFAULT_BOUNDS);
  const [isLayerDirty, setIsLayerDirty] = useState(true);
  const [selectedTileId, setSelectedTileId] = useState<string | null>(null);
  const [selectedTile, setSelectedTile] = useState<GeoTile | null>(null);
  const [stations, setStations] = useState<GeoStation[]>([]);
  const [stationsLoading, setStationsLoading] = useState(false);
  const [stationsError, setStationsError] = useState<RuntimeErrorMeta | null>(null);

  const dateRange = useMemo(() => toIsoRange(Number(selectedDays)), [selectedDays]);

  const reloadLayer = useCallback(async () => {
    setLoadingTiles(true);
    setTilesError(null);
    try {
      const [base, overlays] = await Promise.all([
        baseEnabled ? fetchGeoTiles({ ...dateRange, bounds: mapBounds, zoom, metric }) : Promise.resolve([]),
        overlayEnabled
          ? fetchGeoOverlayTiles({ ...dateRange, bounds: mapBounds, zoom, overlayKind })
          : Promise.resolve([]),
      ]);
      setTiles(base);
      setOverlayTiles(overlays);
      setSelectedTile(null);
      setSelectedTileId(null);
      setStations([]);
      setStationsError(null);
      setIsLayerDirty(false);
    } catch (err) {
      setTilesError(
        describeRuntimeError(
          err,
          "Geo tiles owner route returned an internal error. Retry or inspect request metadata below.",
        ),
      );
    } finally {
      setLoadingTiles(false);
    }
  }, [baseEnabled, dateRange, mapBounds, metric, overlayEnabled, overlayKind, zoom]);

  useEffect(() => {
    void reloadLayer();
  }, [reloadLayer]);

  const requestDrillDown = useCallback(
    async (tile: GeoTile) => {
      const tileBounds = tileToBounds(tile);
      setSelectedTileId(`${tile.zoom}-${tile.tile_x}-${tile.tile_y}`);
      setSelectedTile(tile);
      setStationsLoading(true);
      setStationsError(null);
      try {
        const data = await fetchGeoStationsOverlay({
          ...dateRange,
          bounds: tileBounds,
          metric,
          overlayKind: overlayEnabled ? overlayKind : undefined,
          limit: 200,
        });
        setStations(data);
      } catch (err) {
        setStationsError(
          describeRuntimeError(
            err,
            "Drill-down stations owner route returned an internal error. Retry or inspect request metadata below.",
          ),
        );
      } finally {
        setStationsLoading(false);
      }
    },
    [dateRange, metric, overlayEnabled, overlayKind],
  );

  const baseMaxValue = Math.max(...tiles.map((tile) => tile.value), 0);
  const overlayMaxValue = Math.max(...overlayTiles.map((tile) => tile.value), 0);

  const nudgeBounds = (latDelta: number, lonDelta: number) => {
    setMapBounds((prev) => ({
      minLat: prev.minLat + latDelta,
      maxLat: prev.maxLat + latDelta,
      minLon: prev.minLon + lonDelta,
      maxLon: prev.maxLon + lonDelta,
    }));
    setIsLayerDirty(true);
  };

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <h1 className="neft-h1">Geo Analytics</h1>
      <div style={{ display: "grid", gridTemplateColumns: "7fr 3fr", gap: 16 }}>
        <div style={{ position: "relative", borderRadius: 12, overflow: "hidden", minHeight: 620, background: "#e2e8f0" }}>
          <div style={{ position: "absolute", inset: 0, background: "linear-gradient(45deg, #f8fafc 25%, #e2e8f0 25%, #e2e8f0 50%, #f8fafc 50%, #f8fafc 75%, #e2e8f0 75%, #e2e8f0 100%)", backgroundSize: "24px 24px" }} />
          {baseEnabled &&
            tiles.map((tile) => {
              const id = `base-${tile.zoom}-${tile.tile_x}-${tile.tile_y}`;
              const rect = projectTileToViewport(mapBounds, tile);
              if (!rect) return null;
              return (
                <button
                  key={id}
                  onClick={() => void requestDrillDown(tile)}
                  title={`${tile.tile_x}/${tile.tile_y}/${tile.zoom}`}
                  style={{
                    position: "absolute",
                    left: `${rect.left}%`,
                    top: `${rect.top}%`,
                    width: `${rect.width}%`,
                    height: `${rect.height}%`,
                    border: selectedTileId === `${tile.zoom}-${tile.tile_x}-${tile.tile_y}` ? "2px solid #111827" : "1px solid #1d4ed8",
                    background: `rgba(37, 99, 235, ${getAlpha(tile.value, baseMaxValue, opacity)})`,
                    cursor: "pointer",
                  }}
                />
              );
            })}
          {overlayEnabled &&
            overlayTiles.map((tile) => {
              const id = `overlay-${tile.zoom}-${tile.tile_x}-${tile.tile_y}`;
              const rect = projectTileToViewport(mapBounds, tile);
              if (!rect) return null;
              return (
                <button
                  key={id}
                  onClick={() => void requestDrillDown(tile)}
                  title={`${tile.tile_x}/${tile.tile_y}/${tile.zoom}`}
                  style={{
                    position: "absolute",
                    left: `${rect.left}%`,
                    top: `${rect.top}%`,
                    width: `${rect.width}%`,
                    height: `${rect.height}%`,
                    border: selectedTileId === `${tile.zoom}-${tile.tile_x}-${tile.tile_y}` ? "2px solid #111827" : `1px solid ${OVERLAY_COLORS[overlayKind]}`,
                    background: `${OVERLAY_COLORS[overlayKind]}${Math.round(getAlpha(tile.value, overlayMaxValue, opacity) * 255)
                      .toString(16)
                      .padStart(2, "0")}`,
                    cursor: "pointer",
                  }}
                />
              );
            })}

          <div style={{ position: "absolute", bottom: 12, left: 12, background: "rgba(255,255,255,0.9)", borderRadius: 8, padding: 8, display: "flex", gap: 8 }}>
            <button onClick={() => nudgeBounds(0.05, 0)}>↑</button>
            <button onClick={() => nudgeBounds(-0.05, 0)}>↓</button>
            <button onClick={() => nudgeBounds(0, -0.05)}>←</button>
            <button onClick={() => nudgeBounds(0, 0.05)}>→</button>
          </div>

          {loadingTiles ? (
            <div
              style={{
                position: "absolute",
                inset: 12,
                background: "rgba(255,255,255,.78)",
                display: "grid",
                placeItems: "center",
                borderRadius: 8,
                padding: 16,
              }}
            >
              <Loader label="Loading geo layer" />
            </div>
          ) : null}
          {tilesError ? (
            <div style={{ position: "absolute", top: 12, left: 12, right: 12 }}>
              <ErrorState
                title={geoPageCopy.mapError.title}
                description={tilesError.description}
                actionLabel={geoPageCopy.actions.retry}
                onAction={() => {
                  void reloadLayer();
                }}
                details={tilesError.details}
                requestId={tilesError.requestId}
                correlationId={tilesError.correlationId}
              />
            </div>
          ) : null}
          {!loadingTiles && !tilesError && tiles.length === 0 && overlayTiles.length === 0 ? (
            <div style={{ position: "absolute", top: 12, left: 12, right: 12 }}>
              <EmptyState
                title={geoPageCopy.mapEmpty.title}
                description={geoPageCopy.mapEmpty.description}
                actionLabel={geoPageCopy.actions.refreshLayer}
                actionOnClick={() => {
                  void reloadLayer();
                }}
              />
            </div>
          ) : null}
        </div>

        <aside style={{ display: "grid", gap: 12, alignContent: "start" }}>
          <section className="neft-card" style={{ padding: 12 }}>
            <h3 style={{ marginBottom: 8 }}>Controls</h3>
            <label style={{ display: "grid", gap: 4, marginBottom: 8 }}>
              Date range
              <select value={selectedDays} onChange={(event) => setSelectedDays(event.target.value)}>
                {DATE_RANGES.map((range) => (
                  <option key={range.value} value={range.value}>{range.label}</option>
                ))}
              </select>
            </label>
            <label style={{ display: "grid", gap: 4, marginBottom: 8 }}>
              Zoom
              <select value={zoom} onChange={(event) => setZoom(Number(event.target.value))}>
                {[8, 10, 12].map((z) => <option key={z} value={z}>{z}</option>)}
              </select>
            </label>
            <label style={{ display: "grid", gap: 4, marginBottom: 8 }}>
              Metric
              <select value={metric} onChange={(event) => setMetric(event.target.value as GeoMetric)}>
                {METRICS.map((option) => <option key={option} value={option}>{option}</option>)}
              </select>
            </label>
            <label style={{ display: "grid", gap: 4, marginBottom: 8 }}>
              Overlay
              <select value={overlayKind} onChange={(event) => setOverlayKind(event.target.value as GeoOverlayKind)}>
                {OVERLAYS.map((option) => <option key={option} value={option}>{option}</option>)}
              </select>
            </label>
            <label style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
              <input type="checkbox" checked={baseEnabled} onChange={(event) => setBaseEnabled(event.target.checked)} /> Base heatmap
            </label>
            <label style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
              <input type="checkbox" checked={overlayEnabled} onChange={(event) => setOverlayEnabled(event.target.checked)} /> Overlay heatmap
            </label>
            <label style={{ display: "grid", gap: 4, marginBottom: 8 }}>
              Opacity: {opacity.toFixed(1)}
              <input type="range" min={0.1} max={1} step={0.1} value={opacity} onChange={(event) => setOpacity(Number(event.target.value))} />
            </label>
            <button disabled={!isLayerDirty || loadingTiles} onClick={() => void reloadLayer()}>
              {geoPageCopy.actions.refreshLayer}
            </button>
          </section>

          <section className="neft-card" style={{ padding: 12 }}>
            <h3 style={{ marginBottom: 8 }}>Legend</h3>
            <div>Base: blue (intensity by metric)</div>
            <div>RISK_RED: red</div>
            <div>HEALTH_OFFLINE: black</div>
            <div>HEALTH_DEGRADED: orange</div>
          </section>

          <section className="neft-card" style={{ padding: 12 }}>
            <h3 style={{ marginBottom: 8 }}>{geoPageCopy.drillDown.title}</h3>
            {stationsLoading ? <Loader label={geoPageCopy.drillDown.loading} /> : null}
            {stationsError ? (
              <ErrorState
                title={geoPageCopy.drillDown.errorTitle}
                description={stationsError.description}
                actionLabel={selectedTile ? geoPageCopy.actions.retry : undefined}
                onAction={
                  selectedTile
                    ? () => {
                        void requestDrillDown(selectedTile);
                      }
                    : undefined
                }
                details={stationsError.details}
                requestId={stationsError.requestId}
                correlationId={stationsError.correlationId}
              />
            ) : null}
            {!stationsLoading && !stationsError && stations.length === 0 && !selectedTileId ? (
              <EmptyState
                title={geoPageCopy.drillDown.firstUseTitle}
                description={geoPageCopy.drillDown.firstUseDescription}
              />
            ) : null}
            {!stationsLoading && !stationsError && stations.length === 0 && selectedTileId ? (
              <EmptyState
                title={geoPageCopy.drillDown.emptyTitle}
                description={geoPageCopy.drillDown.emptyDescription}
              />
            ) : null}
            <div style={{ display: "grid", gap: 8, maxHeight: 280, overflow: "auto" }}>
              {stations.slice(0, 200).map((station, index) => (
                <article key={`${station.station_id ?? station.id ?? station.name}-${index}`} style={{ border: "1px solid #e5e7eb", borderRadius: 8, padding: 8 }}>
                  <div style={{ fontWeight: 600 }}>{station.name}</div>
                  <div>{station.address ?? "—"}</div>
                  <div>value: {station.value ?? "—"}</div>
                  <div>risk_zone: {station.risk_zone ?? "—"}</div>
                  <div>health_status: {station.health_status ?? "—"}</div>
                </article>
              ))}
            </div>
          </section>
        </aside>
      </div>
    </div>
  );
}
