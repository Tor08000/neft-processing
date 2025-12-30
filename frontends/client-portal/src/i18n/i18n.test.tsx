import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { I18nProvider, useI18n } from "./index";

const Sample = () => {
  const { t } = useI18n();
  return <div>{t("emptyStates.marketplaceOrders.title")}</div>;
};

describe("i18n", () => {
  it("renders russian translations", () => {
    render(
      <I18nProvider locale="ru">
        <Sample />
      </I18nProvider>,
    );

    expect(screen.getByText("Заказов пока нет")).toBeInTheDocument();
  });

  it("renders english translations", () => {
    render(
      <I18nProvider locale="en">
        <Sample />
      </I18nProvider>,
    );

    expect(screen.getByText("No orders yet")).toBeInTheDocument();
  });
});
