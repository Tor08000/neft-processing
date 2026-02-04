import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { I18nProvider, useI18n } from "./index";

const Sample = () => {
  const { t } = useI18n();
  return <div>{t("emptyStates.orders.title")}</div>;
};

describe("i18n", () => {
  it("renders russian translations", async () => {
    render(
      <I18nProvider locale="ru">
        <Sample />
      </I18nProvider>,
    );

    expect(await screen.findByText("Заказов пока нет")).toBeInTheDocument();
  });

  it("renders english translations", async () => {
    render(
      <I18nProvider locale="en">
        <Sample />
      </I18nProvider>,
    );

    expect(await screen.findByText("No orders yet")).toBeInTheDocument();
  });
});
