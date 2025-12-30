import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { AuthProvider } from "../auth/AuthContext";
import { SupportRequestModal } from "./SupportRequestModal";
import type { AuthSession } from "../api/types";

const session: AuthSession = {
  token: "token-1",
  email: "client@demo.test",
  roles: ["CLIENT_OWNER"],
  subjectType: "CLIENT",
  clientId: "client-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

describe("SupportRequestModal", () => {
  it("renders create modal", () => {
    render(
      <MemoryRouter>
        <AuthProvider initialSession={session}>
          <SupportRequestModal
            isOpen
            onClose={() => undefined}
            subjectType="ORDER"
            subjectId="order-1"
            defaultTitle="Проблема с заказом"
          />
        </AuthProvider>
      </MemoryRouter>,
    );

    expect(screen.getByText("Создать обращение")).toBeInTheDocument();
    expect(screen.getByLabelText("Тема")).toBeInTheDocument();
    expect(screen.getByLabelText("Описание")).toBeInTheDocument();
  });
});
