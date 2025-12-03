import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { login as loginRequest } from "../api/auth";
import { useAuth } from "../auth/AuthContext";

export const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { setToken } = useAuth();
  const [email, setEmail] = useState("admin@example.com");
  const [password, setPassword] = useState("admin");
  const loginMutation = useMutation({
    mutationFn: () => loginRequest(email, password),
    onSuccess: (token) => {
      setToken(token);
      queryClient.invalidateQueries({ queryKey: ["me"] });
      queryClient.invalidateQueries({ queryKey: ["operations"] });
      navigate("/operations");
    },
  });
  const error = loginMutation.error as Error | null;

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    loginMutation.mutate();
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <h1>NEFT Admin</h1>
        <p className="muted">Войдите, чтобы посмотреть журнал операций</p>
        <form onSubmit={handleSubmit} className="login-form">
          <label>
            Email
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </label>
          <label>
            Пароль
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
            />
          </label>
          {error && <div className="error-text">{error.message}</div>}
          <button type="submit" disabled={loginMutation.isPending}>
            {loginMutation.isPending ? "Входим..." : "Войти"}
          </button>
        </form>
      </div>
    </div>
  );
};

export default LoginPage;
