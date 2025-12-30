import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { EmptyState } from "./EmptyState";
import { ShoppingCart } from "./icons";

describe("EmptyState", () => {
  it("matches snapshot", () => {
    const { container } = render(
      <EmptyState
        title="Заголовок"
        description="Описание empty-state."
        icon={<ShoppingCart />}
        primaryAction={{ label: "Основное действие" }}
        secondaryAction={{ label: "Вторичное действие" }}
      />,
    );

    expect(container).toMatchSnapshot();
  });
});
