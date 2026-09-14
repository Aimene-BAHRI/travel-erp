const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly body: unknown,
  ) {
    super(`API request failed with status ${status}`);
  }
}

function getCookie(name: string) {
  return document.cookie
    .split("; ")
    .find((item) => item.startsWith(`${name}=`))
    ?.split("=")[1];
}

export async function ensureCsrfToken() {
  const response = await fetch(`${API_URL}/auth/csrf/`, { credentials: "include" });
  if (!response.ok) throw new ApiError(response.status, await response.json());
  const data = (await response.json()) as { csrfToken: string };
  return data.csrfToken;
}

let refreshRequest: Promise<boolean> | null = null;

function refreshSession() {
  if (refreshRequest) return refreshRequest;
  refreshRequest = (async () => {
    const csrfToken =
      decodeURIComponent(getCookie("csrftoken") ?? "") ||
      (await ensureCsrfToken());
    const response = await fetch(`${API_URL}/auth/refresh/`, {
      method: "POST",
      credentials: "include",
      headers: { "X-CSRFToken": csrfToken },
    });
    return response.ok;
  })().finally(() => {
    refreshRequest = null;
  });
  return refreshRequest;
}

export async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = init.method?.toUpperCase() ?? "GET";
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    const csrfToken = decodeURIComponent(getCookie("csrftoken") ?? "") || (await ensureCsrfToken());
    headers.set("X-CSRFToken", csrfToken);
  }
  let response = await fetch(`${API_URL}${path}`, { ...init, headers, credentials: "include" });
  if (
    response.status === 401 &&
    path !== "/auth/login/" &&
    path !== "/auth/refresh/" &&
    (await refreshSession())
  ) {
    response = await fetch(`${API_URL}${path}`, {
      ...init,
      headers,
      credentials: "include",
    });
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(response.status, body);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export async function downloadFile(path: string, filename: string) {
  let response = await fetch(`${API_URL}${path}`, { credentials: "include" });
  if (response.status === 401 && await refreshSession()) {
    response = await fetch(`${API_URL}${path}`, { credentials: "include" });
  }
  if (!response.ok) throw new ApiError(response.status, await response.json().catch(() => null));
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
