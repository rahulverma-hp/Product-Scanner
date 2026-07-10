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

export async function deleteProfile(token: string): Promise<{ ok: boolean }> {
  const res = await fetch(`${BASE_URL}/me`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data?.error || `Delete failed (${res.status})`);
  }
  return data;
}

export async function scanPackagePhoto(
  image: File,
  barcode?: string,
  token?: string | null
) {
  const form = new FormData();
  form.append("image", image);
  if (barcode?.trim()) {
    form.append("barcode", barcode.trim());
  }
  const headers: Record<string, string> = {};
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  const res = await fetch(`${BASE_URL}/scan/package-photo`, {
    method: "POST",
    headers,
    body: form,
  });
  let data: any = null;
  try {
    data = await res.json();
  } catch {
    throw new Error(`Server error (${res.status}). Is the backend running on port 5000?`);
  }
  if (!res.ok) {
    throw new Error(data?.error || `Package photo scan failed (${res.status})`);
  }
  return data;
}

export async function scanProduct(barcode: string, token?: string | null) {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  const res = await fetch(`${BASE_URL}/scan`, {
    method: "POST",
    headers,
    body: JSON.stringify({ barcode }),
  });
  let data: any = null;
  try {
    data = await res.json();
  } catch {
    throw new Error(`Server error (${res.status}). Is the backend running on port 5000?`);
  }
  if (!res.ok) {
    throw new Error(data?.error || `Scan failed (${res.status})`);
  }
  return data;
}