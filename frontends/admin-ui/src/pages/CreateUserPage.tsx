import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { createUser } from "../api/adminUsers";
import { ValidationError } from "../api/http";
import { useAuth } from "../auth/AuthContext";
import AdminWriteActionModal from "../components/admin/AdminWriteActionModal";
import { createUserPageCopy } from "./operatorKeyPageCopy";
import { ADMIN_ROLE_CATALOG, DEFAULT_ADMIN_ROLE_CODE } from "../types/users";

export const CreateUserPage: React.FC = () => {
  const { accessToken } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [roles, setRoles] = useState<string[]>([DEFAULT_ADMIN_ROLE_CODE]);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [pendingCreate, setPendingCreate] = useState<{
    email: string;
    password: string;
    full_name?: string;
    roles: string[];
  } | null>(null);

  const toggleRole = (role: string) => {
    setRoles((current) => (current.includes(role) ? current.filter((item) => item !== role) : [...current, role]));
  };

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    if (password !== confirmPassword) {
      setError(createUserPageCopy.errors.passwordMismatch);
      return;
    }
    if (roles.length === 0) {
      setError(createUserPageCopy.errors.rolesRequired);
      return;
    }
    if (!accessToken) return;
    setPendingCreate({
      email,
      password,
      full_name: fullName || undefined,
      roles,
    });
  };

  const confirmCreate = async ({ reason, correlationId }: { reason: string; correlationId: string }) => {
    if (!accessToken || !pendingCreate) return;
    setSubmitting(true);
    try {
      await createUser(accessToken, {
        ...pendingCreate,
        reason,
        correlation_id: correlationId,
      });
      setPendingCreate(null);
      navigate("/admins");
    } catch (err) {
      if (err instanceof ValidationError) {
        setError(createUserPageCopy.errors.invalidData);
        return;
      }
      setError(createUserPageCopy.errors.createFailed);
      console.error(createUserPageCopy.errors.createLog, err);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="card">
      <h2>{createUserPageCopy.header.title}</h2>
      <p className="muted">{createUserPageCopy.header.description}</p>
      {error ? <div className="error-text">{error}</div> : null}
      <form className="form-grid" onSubmit={handleSubmit}>
        <label className="label">{createUserPageCopy.labels.email}</label>
        <input
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
          placeholder={createUserPageCopy.placeholders.email}
        />

        <label className="label">{createUserPageCopy.labels.fullName}</label>
        <input
          type="text"
          value={fullName}
          onChange={(event) => setFullName(event.target.value)}
          placeholder={createUserPageCopy.placeholders.fullName}
        />

        <label className="label">{createUserPageCopy.labels.password}</label>
        <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} required />

        <label className="label">{createUserPageCopy.labels.confirmPassword}</label>
        <input
          type="password"
          value={confirmPassword}
          onChange={(event) => setConfirmPassword(event.target.value)}
          required
        />

        <label className="label">{createUserPageCopy.labels.roles}</label>
        <div className="stack">
          {ADMIN_ROLE_CATALOG.map((role) => (
            <label key={role.code} className="checkbox" style={{ display: "grid", gap: 4 }}>
              <span>
                <input type="checkbox" checked={roles.includes(role.code)} onChange={() => toggleRole(role.code)} />{" "}
                {role.label}
              </span>
              <span className="muted small">{role.description}</span>
            </label>
          ))}
        </div>

        <div style={{ display: "flex", gap: 12 }}>
          <button type="submit" disabled={submitting}>
            {submitting ? createUserPageCopy.actions.submitting : createUserPageCopy.actions.submit}
          </button>
          <button type="button" className="ghost" onClick={() => navigate(-1)}>
            {createUserPageCopy.actions.cancel}
          </button>
        </div>
      </form>
      <AdminWriteActionModal
        isOpen={pendingCreate !== null}
        title={createUserPageCopy.modal.title}
        onCancel={() => setPendingCreate(null)}
        onConfirm={confirmCreate}
      />
    </div>
  );
};

export default CreateUserPage;
