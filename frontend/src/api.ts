import type { ApiMeta, AuthStatus, BootstrapResponse, SearchResponse, Trait, Unit } from "./types";

const RAW_API_BASE = import.meta.env.VITE_API_BASE;
const API_BASE = RAW_API_BASE === undefined ? "" : RAW_API_BASE.replace(/\/$/, "");

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!response.ok) {
    let message = `Request failed: ${response.status}`;
    try {
      const error = await response.json();
      message = error.detail || message;
    } catch {
      // ignore json parsing
    }
    throw new Error(message);
  }

  return response.json() as Promise<T>;
}

export async function fetchMeta(setNumber = "17"): Promise<ApiMeta> {
  const data = await request<{ meta: ApiMeta }>(`/api/meta?set_number=${setNumber}`);
  return data.meta;
}

export async function fetchBootstrap(setNumber = "17"): Promise<BootstrapResponse> {
  return request<BootstrapResponse>(`/api/bootstrap?set_number=${setNumber}`);
}

export async function fetchUnits(setNumber = "17"): Promise<Unit[]> {
  const data = await request<{ units: Unit[] }>(`/api/units?set_number=${setNumber}`);
  return data.units;
}

export async function fetchTraits(setNumber = "17"): Promise<Trait[]> {
  const data = await request<{ traits: Trait[] }>(`/api/traits?set_number=${setNumber}`);
  return data.traits;
}

export async function runSearch(payload: Record<string, unknown>): Promise<SearchResponse> {
  return request<SearchResponse>("/api/search", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getAuthStatus(): Promise<AuthStatus> {
  return request<AuthStatus>("/api/auth/me");
}

export async function login(username: string, password: string): Promise<AuthStatus> {
  return request<AuthStatus>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export async function logout(): Promise<AuthStatus> {
  return request<AuthStatus>("/api/auth/logout", {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function resolveImageUrl(url?: string | null): string | undefined {
  if (!url) {
    return undefined;
  }
  return url.startsWith("http") ? url : `${API_BASE}${url}`;
}
