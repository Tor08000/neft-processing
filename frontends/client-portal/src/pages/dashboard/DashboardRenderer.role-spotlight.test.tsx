import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { DashboardRenderer } from "./DashboardRenderer";

describe("DashboardRenderer spotlight and empty states", () => {
  it("does not convert unavailable KPI data into a zero value", () => {
    render(
      <MemoryRouter>
        <DashboardRenderer
          dashboard={{
            role: "OWNER",
            timezone: "Europe/Moscow",
            widgets: [{ type: "kpi", key: "total_spend_30d", data: null }],
          }}
        />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "Общие расходы" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Данные временно недоступны" })).toBeInTheDocument();
    expect(screen.queryByText(/0,00\s*₽/)).not.toBeInTheDocument();
  });

  it("renders a role-aware spotlight and honest empty alerts state for fleet managers", () => {
    render(
      <MemoryRouter>
        <DashboardRenderer
          dashboard={{
            role: "FLEET_MANAGER",
            timezone: "Europe/Moscow",
            widgets: [
              { type: "list", key: "alerts", data: [] },
              { type: "cta", key: "fleet_actions", data: null },
            ],
          }}
        />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "Проверьте парк и ограничения до того, как появятся инциденты" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Активных предупреждений нет" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Открыть уведомления" })).toHaveAttribute("href", "/fleet/notifications");
    expect(screen.getByRole("heading", { name: "Следующие шаги fleet-контура" })).toBeInTheDocument();
  });
});
