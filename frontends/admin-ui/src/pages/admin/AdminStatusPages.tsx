import React from "react";
import { Link } from "react-router-dom";
import { EmptyState } from "@shared/brand/components";
import { adminStatusCopy } from "./runtimeStatusCopy";

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
  <EmptyState title={adminStatusCopy.loading.title} description={adminStatusCopy.loading.description} />
);

export const AdminUnauthorizedPage: React.FC<AdminStatusProps> = ({ requestId, errorId }) => (
  <EmptyState
    title={adminStatusCopy.unauthorized.title}
    description={
      <>
        {adminStatusCopy.unauthorized.description}
        <RequestMeta requestId={requestId} errorId={errorId} />
      </>
    }
    action={
      <Link className="ghost neft-btn-secondary" to="/login">
        {adminStatusCopy.unauthorized.action}
      </Link>
    }
  />
);

export const AdminForbiddenPage: React.FC<AdminStatusProps> = ({ requestId, errorId }) => (
  <EmptyState
    title="FORBIDDEN_ROLE"
    description={
      <>
        {adminStatusCopy.forbidden.description}
        <RequestMeta requestId={requestId} errorId={errorId} />
      </>
    }
    action={
      <Link className="ghost neft-btn-secondary" to="/">
        {adminStatusCopy.forbidden.action}
      </Link>
    }
  />
);

export const AdminNotFoundPage: React.FC = () => (
  <EmptyState
    title={adminStatusCopy.notFound.title}
    description={adminStatusCopy.notFound.description}
    action={
      <Link className="ghost neft-btn-secondary" to="/">
        {adminStatusCopy.notFound.action}
      </Link>
    }
  />
);

export const AdminMisconfigPage: React.FC<AdminStatusProps> = ({ requestId, errorId }) => (
  <EmptyState
    title="MISCONFIG"
    description={
      <>
        {adminStatusCopy.misconfig.description}
        <RequestMeta requestId={requestId} errorId={errorId} />
      </>
    }
    action={
      <Link className="ghost neft-btn-secondary" to="/login">
        {adminStatusCopy.misconfig.action}
      </Link>
    }
  />
);

export const AdminCrashPage: React.FC = () => (
  <EmptyState
    title={adminStatusCopy.crash.title}
    description={adminStatusCopy.crash.description}
    action={
      <div className="actions">
        <Link className="ghost neft-btn-secondary" to="/">
          {adminStatusCopy.crash.homeAction}
        </Link>
        <button className="ghost neft-btn-secondary" type="button" onClick={() => window.location.reload()}>
          {adminStatusCopy.crash.refreshAction}
        </button>
      </div>
    }
  />
);

export const AdminTechErrorPage: React.FC<AdminStatusProps & { message?: string }> = ({
  requestId,
  errorId,
  message,
}) => (
  <EmptyState
    title={adminStatusCopy.techError.title}
    description={
      <>
        {message ?? adminStatusCopy.techError.fallbackMessage}
        <RequestMeta requestId={requestId} errorId={errorId} />
      </>
    }
    action={
      <div className="actions">
        <Link className="ghost neft-btn-secondary" to="/">
          {adminStatusCopy.techError.homeAction}
        </Link>
        <button className="ghost neft-btn-secondary" type="button" onClick={() => window.location.reload()}>
          {adminStatusCopy.techError.refreshAction}
        </button>
      </div>
    }
  />
);

export const AdminServiceUnavailablePage: React.FC<AdminStatusProps> = ({ requestId }) => (
  <EmptyState
    title="SERVICE_UNAVAILABLE"
    description={
      <>
        {adminStatusCopy.serviceUnavailable.description}
        <RequestMeta requestId={requestId} />
      </>
    }
    action={
      <Link className="ghost neft-btn-secondary" to="/">
        {adminStatusCopy.serviceUnavailable.action}
      </Link>
    }
  />
);
