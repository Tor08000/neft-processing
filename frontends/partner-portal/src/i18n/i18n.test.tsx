import { render, screen } from "@testing-library/react";
import { I18nextProvider, useTranslation } from "react-i18next";
import { describe, expect, it } from "vitest";
import i18n from "./index";

const Sample = () => {
  const { t } = useTranslation();
  return <div>{t("emptyStates.orders.title")}</div>;
};

describe("i18n", () => {
  it("renders russian translations", async () => {
    await i18n.changeLanguage("ru");
    render(
      <I18nextProvider i18n={i18n}>
        <Sample />
      </I18nextProvider>,
    );

    expect(await screen.findByText("Заказов пока нет")).toBeInTheDocument();
  });

  it("renders english translations", async () => {
    await i18n.changeLanguage("en");
    render(
      <I18nextProvider i18n={i18n}>
        <Sample />
      </I18nextProvider>,
    );

    expect(await screen.findByText("No orders yet")).toBeInTheDocument();
  });
});
