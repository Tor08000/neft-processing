import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { EmptyState } from "./EmptyState";
import { ShoppingCart } from "./icons";

describe("EmptyState", () => {
  it("renders title, description and actions", () => {
    render(
      <EmptyState
        title="Heading"
        description="Empty state description."
        icon={<ShoppingCart />}
        primaryAction={{ label: "Primary action" }}
        secondaryAction={{ label: "Secondary action" }}
      />,
    );

    expect(screen.getByRole("heading", { name: "Heading" })).toBeInTheDocument();
    expect(screen.getByText("Empty state description.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Primary action" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Secondary action" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Heading" }).closest(".empty-state")).not.toBeNull();
  });
});
