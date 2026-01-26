import React from "react";
import { Link } from "react-router-dom";
import { EmptyState } from "@shared/brand/components";

interface AdminStatusProps {
  requestId?: string;
  errorId?: string;
}

const RequestMeta: React.FC<AdminStatusProps> = ({ requestId, errorId }) => {
  if (!requestId && !errorId) return null;
  return (
    <div className="admin-request-id">
      {errorId ? <div>Error ID: {errorId}</div> : null}
      {requestId ? <div>Request ID: {requestId}</div> : null}
    </div>
  );
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
        <RequestMeta requestId={requestId} />
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
        <RequestMeta requestId={requestId} />
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

export const AdminTechErrorPage: React.FC<AdminStatusProps & { message?: string }> = ({
  requestId,
  errorId,
  message,
}) => (
  <EmptyState
    title="TECH_ERROR"
    description={
      <>
        {message ?? "Не удалось загрузить данные админ-портала. Попробуйте позже."}
        <RequestMeta requestId={requestId} errorId={errorId} />
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
        <RequestMeta requestId={requestId} />
      </>
    }
    action={
      <Link className="ghost neft-btn-secondary" to="/">
        На главную
      </Link>
    }
  />
);
