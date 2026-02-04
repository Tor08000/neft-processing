type Vehicle = {
  plate: string;
  model: string;
  status: "active" | "service";
  mileage?: number;
  fuelUsage?: number;
};

const formatNumber = (value: number) => new Intl.NumberFormat("ru-RU").format(value);

export function VehicleCard({ vehicle }: { vehicle: Vehicle }) {
  const statusLabel = vehicle.status === "active" ? "Активен" : "В сервисе";
  const statusClass = vehicle.status === "active" ? "neftc-status-chip--success" : "neftc-status-chip--warning";

  return (
    <article className="neftc-card neftc-vehicle-card">
      <div className="neftc-vehicle-card__header">
        <div>
          <div className="neftc-vehicle-card__plate">{vehicle.plate}</div>
          <div className="neftc-text-muted">{vehicle.model}</div>
        </div>
        <span className={`neftc-status-chip ${statusClass}`}>{statusLabel}</span>
      </div>
      <div className="neftc-vehicle-card__stats">
        {vehicle.mileage !== undefined ? (
          <div>
            <div className="neftc-vehicle-card__value">{formatNumber(vehicle.mileage)} км</div>
            <div className="neftc-vehicle-card__label">Пробег</div>
          </div>
        ) : null}
        {vehicle.fuelUsage !== undefined ? (
          <div>
            <div className="neftc-vehicle-card__value">{vehicle.fuelUsage.toFixed(1)} л/100</div>
            <div className="neftc-vehicle-card__label">Средний расход</div>
          </div>
        ) : null}
      </div>
    </article>
  );
}
