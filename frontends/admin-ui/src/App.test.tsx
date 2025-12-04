import React from "react";
import { render, screen } from "@testing-library/react";
import App from "./App";

describe("App shell", () => {
  it("renders login page inside providers", async () => {
    render(<App />);

    expect(await screen.findByText(/NEFT Admin/i)).toBeInTheDocument();
  });
});
