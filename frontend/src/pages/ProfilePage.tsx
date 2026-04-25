// src/pages/ProfilePage.tsx
import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Card } from "../components/Card";
import { login, me, register } from "../api";

export const ProfilePage: React.FC = () => {
  const nav = useNavigate();
  const [status, setStatus] = useState<string>("");

  const [username, setUsername] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [age, setAge] = useState<number | "">("");
  const [gender, setGender] = useState("");
  const [height, setHeight] = useState<number | "">("");
  const [weight, setWeight] = useState<number | "">("");

  useEffect(() => {
    const token = localStorage.getItem("auth_token");
    if (!token) return;
    me(token)
      .then((data) => {
        setStatus(`Signed in as ${data.profile.username}`);
        nav("/scan-ui");
      })
      .catch(() => {
        localStorage.removeItem("auth_token");
      });
  }, []);

  const handleRegister = async () => {
    const u = username.trim();
    if (!u) {
      setStatus("Username is required.");
      return;
    }
    if (!password || password.length < 6) {
      setStatus("Password is required (min 6 chars).");
      return;
    }
    if (!age || !gender || !height || !weight) {
      setStatus("Age, gender, height and weight are required.");
      return;
    }
    setStatus("Creating account...");
    try {
      const out = await register({
        username: u,
        display_name: displayName.trim() || undefined,
        password,
        age: Number(age),
        gender,
        height_cm: Number(height),
        weight_kg: Number(weight),
      });
      localStorage.setItem("auth_token", out.token);
      setStatus(`Signed in as ${out.profile.username}`);
      nav("/scan-ui");
    } catch (e: any) {
      setStatus(e.message || "Failed to save profile.");
    }
  };

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
      setStatus(`Signed in as ${out.profile.username}`);
      nav("/scan-ui");
    } catch (e: any) {
      setStatus(e.message || "Login failed.");
    }
  };

  return (
    <div className="app-root profile-page">
      <Card title="Sign in">
        <h3 style={{ marginTop: 0, fontSize: "1rem", fontWeight: 500 }}>
          Login or create account
        </h3>
        <label className="label">
          Username <span className="small">(unique)</span>
          <input
            className="input"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            placeholder="Unique username"
          />
        </label>
        <label className="label">
          Display name <span className="small">(optional)</span>
          <input
            className="input"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            placeholder="Common name"
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
            placeholder="Min 6 characters"
          />
        </label>
        <label className="label">
          Age
          <input
            className="input"
            type="number"
            value={age}
            onChange={(e) => setAge(e.target.value ? Number(e.target.value) : "")}
          />
        </label>
        <label className="label">
          Gender
          <select
            className="select"
            value={gender}
            onChange={(e) => setGender(e.target.value)}
          >
            <option value="">Select</option>
            <option value="male">Male</option>
            <option value="female">Female</option>
          </select>
        </label>
        <label className="label">
          Height (cm)
          <input
            className="input"
            type="number"
            value={height}
            onChange={(e) =>
              setHeight(e.target.value ? Number(e.target.value) : "")
            }
          />
        </label>
        <label className="label">
          Weight (kg)
          <input
            className="input"
            type="number"
            value={weight}
            onChange={(e) =>
              setWeight(e.target.value ? Number(e.target.value) : "")
            }
          />
        </label>
        <div className="profile-actions">
          <button className="button" onClick={handleLogin}>
            Login
          </button>
        </div>
        <div className="profile-actions">
          <button className="button secondary" onClick={handleRegister}>
            Create account
          </button>
        </div>

        <div className="small" style={{ marginTop: 8 }}>{status}</div>
      </Card>
    </div>
  );
};