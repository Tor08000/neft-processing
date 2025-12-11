import React, { useEffect, useMemo, useState } from "react";
import { fetchTariffPrices, fetchTariffs, upsertTariffPrice } from "../api/billing";
import { Table, type Column } from "../components/Table/Table";
import type { TariffPlan, TariffPrice } from "../types/billing";

interface TariffPriceForm extends Partial<TariffPrice> {
  price_per_liter: string;
  currency: string;
}

export const TariffsPage: React.FC = () => {
  const [tariffs, setTariffs] = useState<TariffPlan[]>([]);
  const [selected, setSelected] = useState<TariffPlan | null>(null);
  const [prices, setPrices] = useState<TariffPrice[]>([]);
  const [form, setForm] = useState<TariffPriceForm>({ price_per_liter: "", currency: "RUB" });
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    fetchTariffs().then((res) => setTariffs(res.items));
  }, []);

  useEffect(() => {
    if (!selected) return;
    fetchTariffPrices(selected.id).then((res) => setPrices(res.items));
  }, [selected]);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!selected) return;
    const payload: Partial<TariffPrice> = {
      ...form,
      tariff_id: selected.id,
      priority: form.priority ?? 100,
    };
    const saved = await upsertTariffPrice(selected.id, payload);
    setMessage("Price saved");
    setForm({ price_per_liter: "", currency: form.currency ?? "RUB" });
    setPrices((prev) => {
      const without = prev.filter((p) => p.id !== saved.id);
      return [...without, saved].sort((a, b) => a.priority - b.priority);
    });
  };

  const priceColumns: Column<TariffPrice>[] = useMemo(
    () => [
      { key: "product", title: "Product", render: (row) => row.product_id },
      { key: "partner", title: "Partner", render: (row) => row.partner_id || "-" },
      { key: "price", title: "Price", render: (row) => row.price_per_liter },
      { key: "currency", title: "Currency", render: (row) => row.currency },
    ],
    [],
  );

  return (
    <div>
      <h1>Tariffs</h1>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <div>
          <Table
            columns={[{ key: "name", title: "Tariff", render: (row) => row.name }]}
            data={tariffs}
            onRowClick={(row) => setSelected(row)}
          />
        </div>
        <div>
          {selected ? (
            <div>
              <h2>Prices for {selected.name}</h2>
              <Table columns={priceColumns} data={prices} onRowClick={(row) => setForm({ ...row })} />

              <form onSubmit={handleSubmit} style={{ marginTop: 12, display: "grid", gap: 8 }}>
                <label>
                  Product
                  <input
                    value={form.product_id ?? ""}
                    onChange={(e) => setForm((prev) => ({ ...prev, product_id: e.target.value }))}
                    required
                  />
                </label>
                <label>
                  Partner
                  <input
                    value={form.partner_id ?? ""}
                    onChange={(e) => setForm((prev) => ({ ...prev, partner_id: e.target.value }))}
                  />
                </label>
                <label>
                  Price per liter
                  <input
                    value={form.price_per_liter}
                    onChange={(e) => setForm((prev) => ({ ...prev, price_per_liter: e.target.value }))}
                    required
                  />
                </label>
                <label>
                  Currency
                  <input
                    value={form.currency}
                    onChange={(e) => setForm((prev) => ({ ...prev, currency: e.target.value }))}
                    required
                  />
                </label>
                <label>
                  Priority
                  <input
                    type="number"
                    value={form.priority ?? 100}
                    onChange={(e) => setForm((prev) => ({ ...prev, priority: Number(e.target.value) }))}
                  />
                </label>
                <button type="submit">Save price</button>
                {message && <span style={{ color: "green" }}>{message}</span>}
              </form>
            </div>
          ) : (
            <p>Select tariff to view prices</p>
          )}
        </div>
      </div>
    </div>
  );
};

export default TariffsPage;
