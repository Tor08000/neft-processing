import React from "react";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import App from "./App";

describe("App shell", () => {
  it("renders login page inside providers", async () => {
    render(
      <MemoryRouter initialEntries={["/login"]}>
        <App />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/Админка NEFT/i)).toBeInTheDocument();
  });
});
