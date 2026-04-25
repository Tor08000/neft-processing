import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { EmptyState } from "./EmptyState";
import { Package } from "./icons";

describe("EmptyState", () => {
  it("renders title, description, icon, and actions", () => {
    render(
      <EmptyState
        title="Р—Р°РіРѕР»РѕРІРѕРє"
        description="РћРїРёСЃР°РЅРёРµ empty-state."
        icon={<Package />}
        primaryAction={{ label: "РћСЃРЅРѕРІРЅРѕРµ РґРµР№СЃС‚РІРёРµ" }}
        secondaryAction={{ label: "Р’С‚РѕСЂРёС‡РЅРѕРµ РґРµР№СЃС‚РІРёРµ" }}
      />,
    );

    expect(screen.getByRole("heading", { name: "Р—Р°РіРѕР»РѕРІРѕРє" })).toBeInTheDocument();
    expect(screen.getByText("РћРїРёСЃР°РЅРёРµ empty-state.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "РћСЃРЅРѕРІРЅРѕРµ РґРµР№СЃС‚РІРёРµ" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Р’С‚РѕСЂРёС‡РЅРѕРµ РґРµР№СЃС‚РІРёРµ" })).toBeInTheDocument();
    expect(document.querySelector(".empty-state svg")).not.toBeNull();
  });
});
