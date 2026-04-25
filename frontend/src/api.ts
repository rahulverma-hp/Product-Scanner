// src/api.ts
export interface Profile {
  id: number;
  username: string;
  display_name?: string | null;
  age: number;
  gender: string;
  height_cm: number;
  weight_kg: number;
}

// In dev, Vite proxies these paths to the Flask backend (see vite.config.ts),
// so we use relative URLs here. In production (GitHub Pages), call the hosted API.
const BASE_URL = import.meta.env.PROD
  ? "https://product-scanner-3gh1.onrender.com"
  : "";

export async function register(body: {
  username: string;
  display_name?: string;
  password: string;
  age: number;
  gender: string;
  height_cm: number;
  weight_kg: number;
}): Promise<{ token: string; profile: Profile }> {
  const res = await fetch(`${BASE_URL}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      ...body,
      username: body.username.trim(),
      display_name: body.display_name?.trim() || undefined,
    }),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data?.error || `Register failed (${res.status})`);
  }
  return data;
}

export async function login(body: {
  username: string;
  password: string;
}): Promise<{ token: string; profile: Profile }> {
  const res = await fetch(`${BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...body, username: body.username.trim() }),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data?.error || `Login failed (${res.status})`);
  }
  return data;
}

export async function me(token: string): Promise<{ profile: Profile }> {
  const res = await fetch(`${BASE_URL}/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data?.error || `Not authenticated (${res.status})`);
  }
  return data;
}

export async function scanProduct(barcode: string, token?: string | null) {
  const res = await fetch(`${BASE_URL}/scan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      barcode,
      ...(token ? { auth_token: token } : {}),
    }),
  });
  return res.json();
}