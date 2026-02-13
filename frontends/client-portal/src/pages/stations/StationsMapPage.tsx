import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import L from "leaflet";
import type { LatLngExpression } from "leaflet";
import { MapContainer, Marker, Popup, TileLayer, useMap, useMapEvents } from "react-leaflet";
import markerIcon from "leaflet/dist/images/marker-icon.png";
import markerIconRetina from "leaflet/dist/images/marker-icon-2x.png";
import markerShadow from "leaflet/dist/images/marker-shadow.png";
import { useAuth } from "../../auth/AuthContext";
import { fetchNearestStations, type StationMapItem } from "../../api/stationsNearest";
import "./stations-map.css";

type LatLon = { lat: number; lon: number };
type StationsQueryState = {
  centerLat: number;
  centerLon: number;
  radiusKm: number;
  partnerId: number | null;
  provider: "google" | "yandex" | "apple";
};

const DEFAULT_CENTER: LatLon = { lat: 55.751244, lon: 37.618423 };
const RADIUS_OPTIONS = [1, 3, 5, 10, 20, 50];

const stationIcon = L.icon({
  iconRetinaUrl: markerIconRetina,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
});

const activeStationIcon = L.divIcon({
  className: "stations-map-active-marker",
  iconSize: [20, 20],
  iconAnchor: [10, 10],
});

function MapEvents({ onMoveEnd }: { onMoveEnd: (center: LatLon) => void }) {
  useMapEvents({
    moveend(event: { target: { getCenter: () => { lat: number; lng: number } } }) {
      const center = event.target.getCenter();
      onMoveEnd({ lat: center.lat, lon: center.lng });
    },
  });

  return null;
}

function MapRecenter({ center }: { center: LatLon }) {
  const map = useMap();
  useEffect(() => {
    const centerPosition: LatLngExpression = [center.lat, center.lon];
    map.flyTo(centerPosition, map.getZoom(), { duration: 0.35 });
  }, [center, map]);
  return null;
}

const formatDistance = (distanceKm: number | null): string => {
  if (typeof distanceKm !== "number") return "—";
  return `${distanceKm.toFixed(1)} км`;
};

const parsePartnerId = (value: string): number | null => {
  if (!value.trim()) return null;
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed <= 0) return null;
  return parsed;
};

export function StationsMapPage() {
  const { user } = useAuth();
  const [stations, setStations] = useState<StationMapItem[]>([]);
  const [selectedStationId, setSelectedStationId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pendingCenter, setPendingCenter] = useState<LatLon | null>(null);
  const [mapCenter, setMapCenter] = useState<LatLon>(DEFAULT_CENTER);
  const [partnerInput, setPartnerInput] = useState("");
  const itemRefs = useRef<Record<string, HTMLButtonElement | null>>({});

  const [queryState, setQueryState] = useState<StationsQueryState>({
    centerLat: DEFAULT_CENTER.lat,
    centerLon: DEFAULT_CENTER.lon,
    radiusKm: 5,
    partnerId: null,
    provider: "google",
  });

  const selectedStation = useMemo(
    () => stations.find((station) => station.id === selectedStationId) ?? null,
    [selectedStationId, stations],
  );

  const loadStations = useCallback(
    async (nextQueryState: StationsQueryState) => {
      if (!user?.token) return;
      setLoading(true);
      setError(null);
      try {
        const data = await fetchNearestStations(user.token, {
          lat: nextQueryState.centerLat,
          lon: nextQueryState.centerLon,
          radiusKm: nextQueryState.radiusKm,
          partnerId: nextQueryState.partnerId,
          limit: 50,
          provider: nextQueryState.provider,
        });
        setStations(data);
        setSelectedStationId((prev) => (prev && data.some((item) => item.id === prev) ? prev : data[0]?.id ?? null));
        setPendingCenter(null);
      } catch {
        setError("Ошибка загрузки станций");
      } finally {
        setLoading(false);
      }
    },
    [user?.token],
  );

  useEffect(() => {
    void loadStations(queryState);
  }, [loadStations]);

  const handleMoveEnd = useCallback((center: LatLon) => {
    setMapCenter(center);
    setPendingCenter(center);
  }, []);

  const handleSearchHere = useCallback(() => {
    if (!pendingCenter) return;
    const nextQueryState: StationsQueryState = {
      ...queryState,
      centerLat: pendingCenter.lat,
      centerLon: pendingCenter.lon,
    };
    setQueryState(nextQueryState);
    void loadStations(nextQueryState);
  }, [loadStations, pendingCenter, queryState]);

  const handleRadiusChange = useCallback(
    (value: number) => {
      const nextQueryState: StationsQueryState = {
        ...queryState,
        radiusKm: value,
        centerLat: mapCenter.lat,
        centerLon: mapCenter.lon,
      };
      setQueryState(nextQueryState);
      setPendingCenter(null);
      void loadStations(nextQueryState);
    },
    [loadStations, mapCenter, queryState],
  );


  const handleSelectStation = useCallback((station: StationMapItem) => {
    setSelectedStationId(station.id);
    setMapCenter({ lat: station.lat, lon: station.lon });
  }, []);

  useEffect(() => {
    if (!selectedStationId) return;
    itemRefs.current[selectedStationId]?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [selectedStationId]);

  const handleRetry = useCallback(() => {
    void loadStations(queryState);
  }, [loadStations, queryState]);

  const handleIncreaseRadius = useCallback(() => {
    const nextRadius = RADIUS_OPTIONS.find((option) => option > queryState.radiusKm);
    if (!nextRadius) return;
    void handleRadiusChange(nextRadius);
  }, [handleRadiusChange, queryState.radiusKm]);

  const mapCenterPosition: LatLngExpression = [mapCenter.lat, mapCenter.lon];

  return (
    <section className="stations-map-page" aria-label="stations-map-page">
      <div className="page-header">
        <h1>Карта станций</h1>
      </div>

      <div className="stations-map-controls card">
        <label htmlFor="radius_km">Радиус поиска</label>
        <select id="radius_km" value={queryState.radiusKm} onChange={(event) => handleRadiusChange(Number(event.target.value))}>
          {RADIUS_OPTIONS.map((value) => (
            <option key={value} value={value}>
              {value} км
            </option>
          ))}
        </select>

        <label htmlFor="partner_id">Партнёр</label>
        <input
          id="partner_id"
          type="number"
          inputMode="numeric"
          min={1}
          placeholder="ID партнёра"
          value={partnerInput}
          onChange={(event) => {
            const nextValue = event.target.value;
            setPartnerInput(nextValue);
            if (!nextValue.trim() || parsePartnerId(nextValue) !== null) {
              const nextQueryState: StationsQueryState = {
                ...queryState,
                partnerId: parsePartnerId(nextValue),
                centerLat: mapCenter.lat,
                centerLon: mapCenter.lon,
              };
              setQueryState(nextQueryState);
              setPendingCenter(null);
              void loadStations(nextQueryState);
            }
          }}
        />

        <button type="button" className="secondary" disabled={!pendingCenter || loading} onClick={handleSearchHere}>
          Искать здесь
        </button>
      </div>

      {error ? (
        <div className="card stations-map-alert" role="alert">
          <p>{error}</p>
          <button type="button" className="secondary" onClick={handleRetry}>
            Повторить
          </button>
        </div>
      ) : null}

      <div className="stations-map-layout">
        <div className="stations-map-canvas card">
          <MapContainer center={mapCenterPosition} zoom={12} scrollWheelZoom className="stations-map-leaflet">
            <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" attribution="&copy; OpenStreetMap contributors" />
            <MapEvents onMoveEnd={handleMoveEnd} />
            <MapRecenter center={mapCenter} />
            {stations.map((station) => {
              const stationPosition: LatLngExpression = [station.lat, station.lon];

              return (
                <Marker
                  key={station.id}
                  position={stationPosition}
                  icon={station.id === selectedStationId ? activeStationIcon : stationIcon}
                  eventHandlers={{
                    click: () => {
                      setSelectedStationId(station.id);
                      setMapCenter({ lat: station.lat, lon: station.lon });
                    },
                  }}
                >
                  <Popup>{station.name}</Popup>
                </Marker>
              );
            })}
          </MapContainer>
          {loading ? <div className="stations-map-overlay">Загрузка станций…</div> : null}
        </div>

        <aside className="stations-map-sidebar card">
          <h2>Станции рядом</h2>
          {!loading && !stations.length ? (
            <div className="stations-map-empty-wrap">
              <p className="stations-map-empty">В радиусе не найдено</p>
              <button type="button" className="secondary" onClick={handleIncreaseRadius} disabled={queryState.radiusKm === 50}>
                Увеличить радиус
              </button>
            </div>
          ) : (
            <ul className="stations-map-list">
              {stations.map((station) => (
                <li key={station.id}>
                  <button
                    type="button"
                    className={station.id === selectedStationId ? "active" : ""}
                    onClick={() => handleSelectStation(station)}
                    ref={(el) => {
                      itemRefs.current[station.id] = el;
                    }}
                  >
                    <span>{station.name}</span>
                    <small>{formatDistance(station.distanceKm)}</small>
                  </button>
                </li>
              ))}
            </ul>
          )}

          {selectedStation ? (
            <article className="stations-map-card">
              <h3>{selectedStation.name}</h3>
              <p>{selectedStation.address}</p>
              <p>Расстояние: {formatDistance(selectedStation.distanceKm)}</p>
              <div className="stations-map-card-actions">
                <button
                  type="button"
                  className="secondary"
                  disabled={!selectedStation.navUrl}
                  title={!selectedStation.navUrl ? "Нет координат станции" : undefined}
                  onClick={() => selectedStation.navUrl && window.open(selectedStation.navUrl, "_blank", "noopener,noreferrer")}
                >
                  Навигация
                </button>
                <button type="button" className="ghost" onClick={() => void navigator.clipboard.writeText(selectedStation.address)}>
                  Скопировать адрес
                </button>
                <button
                  type="button"
                  className="ghost"
                  onClick={() => void navigator.clipboard.writeText(`${selectedStation.lat},${selectedStation.lon}`)}
                >
                  Скопировать координаты
                </button>
              </div>
            </article>
          ) : null}
        </aside>
      </div>
    </section>
  );
}
