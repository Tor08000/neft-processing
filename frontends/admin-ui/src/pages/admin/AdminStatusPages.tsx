import React from "react";
import { Link } from "react-router-dom";
import { EmptyState } from "@shared/brand/components";

interface AdminStatusProps {
  requestId?: string;
}

const RequestId: React.FC<AdminStatusProps> = ({ requestId }) => {
  if (!requestId) return null;
  return <div className="admin-request-id">Request ID: {requestId}</div>;
};

export const AdminLoadingPage: React.FC = () => (
  <EmptyState title="Загрузка" description="Проверяем доступ к админ-порталу..." />
);

export const AdminUnauthorizedPage: React.FC<AdminStatusProps> = ({ requestId }) => (
  <EmptyState
    title="401 — Не авторизован"
    description={
      <>
        Требуется повторный вход.
        <RequestId requestId={requestId} />
      </>
    }
    action={
      <Link className="ghost neft-btn-secondary" to="/login">
        Войти
      </Link>
    }
  />
);

export const AdminForbiddenPage: React.FC<AdminStatusProps> = ({ requestId }) => (
  <EmptyState
    title="403 — Доступ запрещён"
    description={
      <>
        У вас нет прав доступа к этому разделу.
        <RequestId requestId={requestId} />
      </>
    }
    action={
      <Link className="ghost neft-btn-secondary" to="/">
        Вернуться на главную
      </Link>
    }
  />
);

export const AdminNotFoundPage: React.FC = () => (
  <EmptyState
    title="404 — Страница не найдена"
    description="Проверьте адрес и попробуйте снова."
    action={
      <Link className="ghost neft-btn-secondary" to="/">
        На главную
      </Link>
    }
  />
);

export const AdminCrashPage: React.FC = () => (
  <EmptyState
    title="TECH_ERROR"
    description="Произошла непредвиденная ошибка. Попробуйте обновить страницу."
    action={
      <Link className="ghost neft-btn-secondary" to="/">
        На главную
      </Link>
    }
  />
);

export const AdminTechErrorPage: React.FC<AdminStatusProps & { message?: string }> = ({ requestId, message }) => (
  <EmptyState
    title="TECH_ERROR"
    description={
      <>
        {message ?? "Не удалось загрузить данные админ-портала. Попробуйте позже."}
        <RequestId requestId={requestId} />
      </>
    }
    action={
      <Link className="ghost neft-btn-secondary" to="/login">
        Перейти к входу
      </Link>
    }
  />
);

export const AdminServiceUnavailablePage: React.FC<AdminStatusProps> = ({ requestId }) => (
  <EmptyState
    title="SERVICE_UNAVAILABLE"
    description={
      <>
        Сервис временно недоступен. Попробуйте позже.
        <RequestId requestId={requestId} />
      </>
    }
    action={
      <Link className="ghost neft-btn-secondary" to="/">
        На главную
      </Link>
    }
  />
);
