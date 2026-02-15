import { useEffect, useMemo, useRef, useState, type ChangeEvent } from "react";
import { Link, useParams } from "react-router-dom";
import {
  fetchFuelStationPrices,
  fetchStationDetail,
  importFuelStationPrices,
  saveFuelStationPrices,
  type FuelStationPriceImportSummary,
  type StationDetail,
} from "../api/partner";
import { useAuth } from "../auth/AuthContext";
import { StatusBadge } from "../components/StatusBadge";
import { canCreateDraftPrices } from "../utils/roles";
import { formatCurrency, formatDate, formatNumber } from "../utils/format";
import {
  buildStationPricesPayload,
  mapPricesResponseToRows,
  STATION_PRICE_PRODUCTS,
  type StationPriceRow,
  validateStationPrice,
} from "./stationPrices";

export function StationDetailsPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const canManagePrices = canCreateDraftPrices(user?.roles);

  const [station, setStation] = useState<StationDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [pricesRows, setPricesRows] = useState<StationPriceRow[]>([]);
  const [priceErrors, setPriceErrors] = useState<Record<string, string>>({});
  const [pricesLoading, setPricesLoading] = useState(false);
  const [pricesError, setPricesError] = useState<string | null>(null);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [isImporting, setIsImporting] = useState(false);
  const [importSummary, setImportSummary] = useState<FuelStationPriceImportSummary | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const lastUpdated = useMemo(() => {
    const sorted = [...pricesRows]
      .map((row) => row.updatedAt)
      .filter((value): value is string => Boolean(value))
      .sort((a, b) => new Date(b).getTime() - new Date(a).getTime());
    if (!sorted.length) return null;
    const latest = sorted[0];
    const latestAuthor = pricesRows.find((row) => row.updatedAt === latest)?.updatedBy;
    return { at: latest, by: latestAuthor ?? null };
  }, [pricesRows]);

  const loadStation = () => {
    if (!user || !id) return;
    setIsLoading(true);
    setError(null);
    fetchStationDetail(user.token, id)
      .then((data) => setStation(data))
      .catch((err) => {
        console.error(err);
        setError("Не удалось загрузить данные станции");
      })
      .finally(() => setIsLoading(false));
  };

  const loadPrices = () => {
    if (!user || !id) return;
    setPricesLoading(true);
    setPricesError(null);
    setSaveMessage(null);
    fetchFuelStationPrices(user.token, id)
      .then((response) => {
        setPricesRows(mapPricesResponseToRows(response));
        setPriceErrors({});
      })
      .catch((err) => {
        console.error(err);
        setPricesError("Не удалось загрузить цены");
      })
      .finally(() => setPricesLoading(false));
  };

  useEffect(() => {
    loadStation();
    loadPrices();
  }, [user, id]);

  const setRowPrice = (productCode: string, value: string) => {
    setSaveMessage(null);
    setPricesRows((prev) => prev.map((row) => (row.productCode === productCode ? { ...row, price: value } : row)));
    setPriceErrors((prev) => ({ ...prev, [productCode]: validateStationPrice(value) ?? "" }));
  };

  const handleAddDefaultRows = () => {
    setSaveMessage(null);
    const existing = new Set(pricesRows.map((row) => row.productCode));
    const defaults = STATION_PRICE_PRODUCTS.filter((code) => !existing.has(code)).map((productCode) => ({
      productCode,
      price: "",
      currency: "RUB",
      validFrom: null,
      validTo: null,
      updatedAt: null,
      updatedBy: null,
    }));
    setPricesRows((prev) => [...prev, ...defaults]);
  };

  const handleSave = async () => {
    if (!user || !id || !canManagePrices) return;

    const nextErrors = pricesRows.reduce<Record<string, string>>((acc, row) => {
      const validation = validateStationPrice(row.price);
      if (validation) {
        acc[row.productCode] = validation;
      }
      return acc;
    }, {});
    setPriceErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) {
      setPricesError("Исправьте ошибки в форме перед сохранением");
      return;
    }

    try {
      setPricesError(null);
      setSaveMessage(null);
      setIsSaving(true);
      const payload = buildStationPricesPayload(pricesRows);
      const response = await saveFuelStationPrices(user.token, id, payload);
      setPricesRows(mapPricesResponseToRows(response));
      setSaveMessage("Цены сохранены");
    } catch (err) {
      console.error(err);
      setPricesError("Не удалось сохранить цены");
    } finally {
      setIsSaving(false);
    }
  };

  const handleImportClick = () => {
    if (!canManagePrices) return;
    fileInputRef.current?.click();
  };

  const handleImportChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file || !user || !id || !canManagePrices) return;
    try {
      setIsImporting(true);
      setPricesError(null);
      setSaveMessage(null);
      const summary = await importFuelStationPrices(user.token, id, file);
      setImportSummary(summary);
      loadPrices();
    } catch (err) {
      console.error(err);
      setPricesError("Импорт CSV завершился ошибкой");
    } finally {
      setIsImporting(false);
      event.target.value = "";
    }
  };

  if (isLoading) {
    return (
      <div className="card">
        <div className="skeleton-stack" aria-busy="true">
          <div className="skeleton-line" />
          <div className="skeleton-line" />
          <div className="skeleton-line" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="card">
        <div className="error" role="alert">
          {error}
        </div>
      </div>
    );
  }

  if (!station) {
    return (
      <div className="empty-state empty-state--full">
        <h2>Станция не найдена</h2>
        <Link className="ghost" to="/stations">
          Вернуться к списку
        </Link>
      </div>
    );
  }

  return (
    <div className="stack">
      <section className="card">
        <div className="section-title">
          <div>
            <h2>{station.name}</h2>
            <div className="muted">{station.address}</div>
          </div>
          <Link className="ghost" to="/stations">
            Назад
          </Link>
        </div>
        <div className="meta-grid">
          <div>
            <div className="label">Код станции</div>
            <div>{station.code ?? "—"}</div>
          </div>
          <div>
            <div className="label">Сеть</div>
            <div>{station.network ?? "—"}</div>
          </div>
          <div>
            <div className="label">Статус</div>
            <StatusBadge status={station.status} />
          </div>
          <div>
            <div className="label">Онлайн</div>
            {station.onlineStatus ? <StatusBadge status={station.onlineStatus} /> : "—"}
          </div>
        </div>
      </section>

      <section className="card">
        <h3>Терминалы / POS</h3>
        {station.terminals && station.terminals.length ? (
          <table className="data-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Название</th>
                <th>Статус</th>
              </tr>
            </thead>
            <tbody>
              {station.terminals.map((terminal) => (
                <tr key={terminal.id}>
                  <td>{terminal.id}</td>
                  <td>{terminal.name ?? "—"}</td>
                  <td>
                    <StatusBadge status={terminal.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="muted">Терминалы отсутствуют.</p>
        )}
      </section>

      <section className="card">
        <h3>Сводка по операциям</h3>
        {station.transactionSummary ? (
          <div className="stats-grid">
            <div className="stat">
              <div className="stat__label">Период</div>
              <div className="stat__value">{station.transactionSummary.period ?? "—"}</div>
            </div>
            <div className="stat">
              <div className="stat__label">Количество операций</div>
              <div className="stat__value">{formatNumber(station.transactionSummary.totalCount ?? null)}</div>
            </div>
            <div className="stat">
              <div className="stat__label">Сумма</div>
              <div className="stat__value">{formatCurrency(station.transactionSummary.totalAmount ?? null)}</div>
            </div>
          </div>
        ) : (
          <p className="muted">Сводка пока не доступна.</p>
        )}
      </section>

      <section className="card">
        <div className="section-title">
          <h3>Топ причин отказов</h3>
          <span className="muted">Explain доступен для ключевых отказов</span>
        </div>
        {station.declineReasons && station.declineReasons.length ? (
          <table className="data-table">
            <thead>
              <tr>
                <th>Причина</th>
                <th>Кол-во</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {station.declineReasons.map((reason) => (
                <tr key={reason.code}>
                  <td>
                    <div>{reason.label}</div>
                    <div className="muted small">{reason.code}</div>
                  </td>
                  <td>{formatNumber(reason.count)}</td>
                  <td>
                    {reason.explainUrl ? (
                      <a className="link-button" href={reason.explainUrl} target="_blank" rel="noreferrer">
                        Explain
                      </a>
                    ) : (
                      <span className="muted">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="muted">Данные по отказам отсутствуют.</p>
        )}
      </section>

      <section className="card">
        <div className="section-title">
          <h3>Цены</h3>
          <div className="neft-actions">
            {canManagePrices ? (
              <>
                <button className="secondary" type="button" onClick={handleImportClick} disabled={isImporting || isSaving}>
                  {isImporting ? "Импорт..." : "Import CSV"}
                </button>
                <button className="secondary" type="button" onClick={loadPrices} disabled={pricesLoading || isSaving || isImporting}>
                  Reset
                </button>
                <button className="primary" type="button" onClick={handleSave} disabled={isSaving || pricesLoading || isImporting}>
                  {isSaving ? "Сохранение..." : "Save"}
                </button>
              </>
            ) : (
              <span className="muted">Недостаточно прав для редактирования цен</span>
            )}
          </div>
          <input ref={fileInputRef} type="file" accept=".csv,text/csv" hidden onChange={handleImportChange} />
        </div>

        <p className="muted small">
          Формат CSV: <code>product_code,price,currency,valid_from,valid_to</code> (для MVP достаточно <code>product_code,price</code>)
        </p>

        {pricesError ? (
          <div className="warning" role="alert">
            {pricesError} <button onClick={loadPrices}>Retry</button>
          </div>
        ) : null}
        {saveMessage ? <div className="muted">{saveMessage}</div> : null}

        {pricesLoading ? (
          <div className="skeleton-stack" aria-busy="true">
            <div className="skeleton-line" />
            <div className="skeleton-line" />
            <div className="skeleton-line" />
          </div>
        ) : pricesRows.length ? (
          <table className="data-table">
            <thead>
              <tr>
                <th>Продукт</th>
                <th>Цена</th>
                <th>Валюта</th>
                <th>Обновлено</th>
              </tr>
            </thead>
            <tbody>
              {pricesRows.map((row) => (
                <tr key={row.productCode}>
                  <td>
                    <select
                      value={row.productCode}
                      onChange={(event) => {
                        const next = event.target.value;
                        setPricesRows((prev) =>
                          prev.map((item) => (item.productCode === row.productCode ? { ...item, productCode: next } : item)),
                        );
                      }}
                      disabled={!canManagePrices || isSaving || isImporting}
                    >
                      {STATION_PRICE_PRODUCTS.map((product) => (
                        <option key={product} value={product}>
                          {product}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <input
                      value={row.price}
                      inputMode="decimal"
                      onChange={(event) => setRowPrice(row.productCode, event.target.value)}
                      disabled={!canManagePrices || isSaving || isImporting}
                    />
                    {priceErrors[row.productCode] ? <div className="muted small">{priceErrors[row.productCode]}</div> : null}
                  </td>
                  <td>{row.currency}</td>
                  <td>{formatDate(row.updatedAt ?? null)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="empty-state">
            <h4>Цены не заданы</h4>
            {canManagePrices ? (
              <button className="secondary" type="button" onClick={handleAddDefaultRows}>
                Add default rows
              </button>
            ) : null}
          </div>
        )}

        {lastUpdated ? (
          <p className="muted small">
            Last updated: {formatDate(lastUpdated.at)}
            {lastUpdated.by ? ` by ${lastUpdated.by}` : ""}
          </p>
        ) : null}

        {importSummary ? (
          <div className="card">
            <div className="label">Итог импорта</div>
            <div className="meta-grid">
              <div>
                <div className="label">Inserted</div>
                <div>{importSummary.inserted}</div>
              </div>
              <div>
                <div className="label">Updated</div>
                <div>{importSummary.updated}</div>
              </div>
              <div>
                <div className="label">Skipped</div>
                <div>{importSummary.skipped}</div>
              </div>
            </div>
            {importSummary.errors.length ? (
              <div>
                <div className="label">Ошибки (до 20)</div>
                <ul>
                  {importSummary.errors.slice(0, 20).map((item, index) => (
                    <li key={`${item.row}-${index}`}>
                      Строка {item.row}: {item.error}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
        ) : null}
      </section>
    </div>
  );
}
