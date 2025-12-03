import React from "react";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";

describe("App shell", () => {
  it("renders login page inside providers", async () => {
    const client = new QueryClient();
    render(
      <QueryClientProvider client={client}>
        <App />
      </QueryClientProvider>,
    );

    expect(await screen.findByText(/NEFT Admin/i)).toBeInTheDocument();
  });
});
