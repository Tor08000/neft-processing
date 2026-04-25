import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { createSupportTicket, navigateMock } = vi.hoisted(() => ({
  createSupportTicket: vi.fn(),
  navigateMock: vi.fn(),
}));

vi.mock("../api/supportTickets", () => ({
  createSupportTicket,
}));

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({
    user: {
      token: "test.header.payload",
      email: "client@example.test",
      roles: ["CLIENT_OWNER"],
      subjectType: "CLIENT",
      clientId: "client-1",
      expiresAt: Date.now() + 60_000,
    },
  }),
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    useNavigate: () => navigateMock,
  };
});

import { SupportTicketNewPage } from "./SupportTicketNewPage";

describe("SupportTicketNewPage", () => {
  beforeEach(() => {
    createSupportTicket.mockResolvedValue({ id: "ticket-1" });
    navigateMock.mockReset();
  });

  it("prefills the form from the support topic contour and submits an owner-backed ticket", async () => {
    const user = userEvent.setup();

    render(
      <MemoryRouter initialEntries={["/client/support/new?topic=document_signature"]}>
        <Routes>
          <Route path="/client/support/new" element={<SupportTicketNewPage />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByDisplayValue("Проблема с подписанием документа")).toBeInTheDocument();
    expect(
      screen.getByDisplayValue("Опишите документ, шаг подписания и что именно не удалось выполнить."),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Создать обращение" }));

    expect(createSupportTicket).toHaveBeenCalledWith(
      {
        subject: "Проблема с подписанием документа",
        message: "Опишите документ, шаг подписания и что именно не удалось выполнить.",
        priority: "NORMAL",
      },
      expect.objectContaining({ token: "test.header.payload" }),
    );
    expect(navigateMock).toHaveBeenCalledWith("/client/support/ticket-1");
  });
});
