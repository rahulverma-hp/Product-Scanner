import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Card } from "../components/Card";
import { login, me } from "../api";

export const LoginPage: React.FC = () => {
  const nav = useNavigate();
  const [status, setStatus] = useState<string>("");

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  useEffect(() => {
    const guest = localStorage.getItem("guest_mode") === "1";
    if (guest) {
      nav("/scan-ui");
      return;
    }
    const token = localStorage.getItem("auth_token");
    if (!token) return;
    me(token)
      .then(() => nav("/scan-ui"))
      .catch(() => localStorage.removeItem("auth_token"));
  }, [nav]);

  const handleLogin = async () => {
    const u = username.trim();
    if (!u || !password) {
      setStatus("Username and password are required.");
      return;
    }
    setStatus("Signing in...");
    try {
      const out = await login({ username: u, password });
      localStorage.setItem("auth_token", out.token);
      localStorage.removeItem("guest_mode");
      setStatus(`Signed in as ${out.profile.username}`);
      nav("/scan-ui");
    } catch (e: any) {
      setStatus(e.message || "Login failed.");
    }
  };

  const handleGuest = () => {
    localStorage.removeItem("auth_token");
    localStorage.setItem("guest_mode", "1");
    nav("/scan-ui");
  };

  return (
    <div className="app-root profile-page">
      <Card title="Sign in">
        <h3 style={{ marginTop: 0, fontSize: "1rem", fontWeight: 500 }}>
          Login
        </h3>

        <label className="label">
          Username
          <input
            className="input"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            placeholder="Your username"
          />
        </label>

        <label className="label">
          Password
          <input
            className="input"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            placeholder="Your password"
          />
        </label>

        <div className="profile-actions">
          <button className="button" onClick={handleLogin}>
            Login
          </button>
        </div>

        <div className="profile-actions">
          <button className="button secondary" onClick={handleGuest}>
            Use as guest
          </button>
        </div>

        <div className="small" style={{ marginTop: 8 }}>
          {status}
        </div>

        <div className="small" style={{ marginTop: 12 }}>
          Don’t have an account? <Link to="/signup">Create account</Link>
        </div>
      </Card>
    </div>
  );
};

