import { useCallback, useEffect, useMemo, useState } from "react";
import L from "leaflet";
import { MapContainer, Marker, TileLayer, useMap, useMapEvents } from "react-leaflet";
import markerIcon from "leaflet/dist/images/marker-icon.png";
import markerIconRetina from "leaflet/dist/images/marker-icon-2x.png";
import markerShadow from "leaflet/dist/images/marker-shadow.png";
import { useAuth } from "../../auth/AuthContext";
import { fetchNearestStations, type StationMapItem } from "../../api/logisticsStations";
import "./stations-map.css";

type LatLon = { lat: number; lon: number };

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
    map.flyTo([center.lat, center.lon], map.getZoom(), { duration: 0.35 });
  }, [center, map]);
  return null;
}

const formatDistance = (distanceKm: number | null): string => {
  if (typeof distanceKm !== "number") return "—";
  return `${distanceKm.toFixed(1)} км`;
};

export function StationsMapPage() {
  const { user } = useAuth();
  const [stations, setStations] = useState<StationMapItem[]>([]);
  const [selectedStationId, setSelectedStationId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [radiusKm, setRadiusKm] = useState(5);
  const [queryCenter, setQueryCenter] = useState<LatLon>(DEFAULT_CENTER);
  const [mapCenter, setMapCenter] = useState<LatLon>(DEFAULT_CENTER);
  const [pendingCenter, setPendingCenter] = useState<LatLon | null>(null);

  const selectedStation = useMemo(
    () => stations.find((station) => station.id === selectedStationId) ?? null,
    [selectedStationId, stations],
  );

  const loadStations = useCallback(
    async (center: LatLon, nextRadiusKm = radiusKm) => {
      if (!user?.token) return;
      setLoading(true);
      setError(null);
      try {
        const data = await fetchNearestStations(user.token, {
          lat: center.lat,
          lon: center.lon,
          radiusKm: nextRadiusKm,
          limit: 50,
          provider: "google",
        });
        setStations(data);
        setSelectedStationId((prev) => (prev && data.some((item) => item.id === prev) ? prev : data[0]?.id ?? null));
        setQueryCenter(center);
        setPendingCenter(null);
      } catch {
        setError("Ошибка загрузки станций");
      } finally {
        setLoading(false);
      }
    },
    [radiusKm, user?.token],
  );

  useEffect(() => {
    void loadStations(DEFAULT_CENTER, radiusKm);
  }, [loadStations, radiusKm]);

  const handleMoveEnd = useCallback((center: LatLon) => {
    setMapCenter(center);
    setPendingCenter(center);
  }, []);

  const handleSearchHere = useCallback(() => {
    if (!pendingCenter) return;
    void loadStations(pendingCenter, radiusKm);
  }, [loadStations, pendingCenter, radiusKm]);

  const handleRadiusChange = useCallback(
    (value: number) => {
      setRadiusKm(value);
      void loadStations(mapCenter, value);
    },
    [loadStations, mapCenter],
  );

  const handleSelectStation = useCallback((station: StationMapItem) => {
    setSelectedStationId(station.id);
    setMapCenter({ lat: station.lat, lon: station.lon });
  }, []);

  return (
    <section className="stations-map-page" aria-label="stations-map-page">
      <div className="page-header">
        <h1>Карта станций</h1>
      </div>

      <div className="stations-map-controls card">
        <label htmlFor="radius_km">Радиус поиска</label>
        <select id="radius_km" value={radiusKm} onChange={(event) => handleRadiusChange(Number(event.target.value))}>
          {RADIUS_OPTIONS.map((value) => (
            <option key={value} value={value}>
              {value} км
            </option>
          ))}
        </select>
        <button type="button" className="secondary" disabled={!pendingCenter || loading} onClick={handleSearchHere}>
          Искать здесь
        </button>
      </div>

      {error ? (
        <div className="card stations-map-alert" role="alert">
          <p>{error}</p>
          <button type="button" className="secondary" onClick={() => void loadStations(pendingCenter ?? queryCenter, radiusKm)}>
            Повторить
          </button>
        </div>
      ) : null}

      <div className="stations-map-layout">
        <div className="stations-map-canvas card">
          <MapContainer center={[mapCenter.lat, mapCenter.lon]} zoom={12} scrollWheelZoom className="stations-map-leaflet">
            <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
            <MapEvents onMoveEnd={handleMoveEnd} />
            <MapRecenter center={mapCenter} />
            {stations.map((station) => (
              <Marker
                key={station.id}
                position={[station.lat, station.lon]}
                icon={stationIcon}
                eventHandlers={{ click: () => setSelectedStationId(station.id) }}
              />
            ))}
          </MapContainer>
          {loading ? <div className="stations-map-overlay">Загружаем станции…</div> : null}
        </div>

        <aside className="stations-map-sidebar card">
          <h2>Станции рядом</h2>
          {!loading && !stations.length ? (
            <p className="stations-map-empty">Станций в радиусе не найдено. Попробуйте увеличить радиус.</p>
          ) : (
            <ul className="stations-map-list">
              {stations.map((station) => (
                <li key={station.id}>
                  <button
                    type="button"
                    className={station.id === selectedStationId ? "active" : ""}
                    onClick={() => handleSelectStation(station)}
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
                  onClick={() => selectedStation.navUrl && window.open(selectedStation.navUrl, "_blank", "noopener,noreferrer")}
                >
                  Проложить маршрут
                </button>
                <button type="button" className="ghost" onClick={() => void navigator.clipboard.writeText(selectedStation.address)}>
                  Скопировать адрес
                </button>
              </div>
            </article>
          ) : null}
        </aside>
      </div>
    </section>
  );
}
