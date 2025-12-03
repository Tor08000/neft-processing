import { FormEvent, useState } from "react";

interface LoginPageProps {
  onLogin: (email: string, password: string) => void;
}

export function LoginPage({ onLogin }: LoginPageProps) {
  const [email, setEmail] = useState("demo@client.neft");
  const [password, setPassword] = useState("demo");

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    onLogin(email, password);
  };

  return (
    <div className="login-wrapper">
      <form className="card login-card" onSubmit={handleSubmit}>
        <h1>Вход в клиентский кабинет</h1>
        <p>Используйте email и пароль клиента, чтобы продолжить.</p>
        <label>
          Email
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </label>

        <label>
          Пароль
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </label>

        <button type="submit" className="primary">
          Войти
        </button>
      </form>
    </div>
  );
}
