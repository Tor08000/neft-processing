import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ExportsPage } from "./ExportsPage";

const useAuthMock = vi.fn();
const listExportJobsMock = vi.fn();

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => useAuthMock(),
}));

vi.mock("../api/exports", () => ({
  listExportJobs: (...args: unknown[]) => listExportJobsMock(...args),
  buildExportJobDownloadUrl: (jobId: string) => `/api/core/client/exports/jobs/${jobId}/download`,
}));

describe("ExportsPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    useAuthMock.mockReturnValue({
      user: {
        token: "test.header.payload",
        email: "client@neft.test",
        roles: ["CLIENT_OWNER"],
        timezone: "Europe/Moscow",
      },
    });
  });

  it("renders shared table toolbar and footer for export jobs", async () => {
    listExportJobsMock
      .mockResolvedValueOnce({
        items: [
          {
            id: "job-1",
            org_id: "org-1",
            created_by_user_id: "user-1",
            report_type: "documents",
            format: "CSV",
            status: "DONE",
            filters: {},
            file_name: "documents.csv",
            processed_rows: 12,
            row_count: 12,
            created_at: "2026-04-12T10:00:00Z",
          },
        ],
        next_cursor: "cursor-2",
      })
      .mockResolvedValueOnce({
        items: [],
        next_cursor: null,
      });

    render(<ExportsPage />);

    expect(await screen.findByText("documents")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Сбросить" })).toBeInTheDocument();
    expect(screen.getByText("Загружено задач: 1")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Скачать" })).toHaveAttribute(
      "href",
      "/api/core/client/exports/jobs/job-1/download",
    );

    fireEvent.click(screen.getByRole("button", { name: "Показать ещё" }));

    await waitFor(() => expect(listExportJobsMock).toHaveBeenCalledTimes(2));
    expect(listExportJobsMock).toHaveBeenLastCalledWith(
      {
        status: undefined,
        report_type: undefined,
        cursor: "cursor-2",
        limit: 20,
        only_my: true,
      },
      expect.any(Object),
    );
  });
});
