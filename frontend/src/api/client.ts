function resolveApiBase(): string {
  const configured = import.meta.env.VITE_API_BASE_URL
  if (typeof configured === 'string' && configured.trim() !== '') {
    return configured.replace(/\/$/, '')
  }
  // Dev local: Vite proxy en :5173 → API :8000. Producción: mismo origen (exe/nginx).
  return import.meta.env.DEV ? 'http://localhost:8000' : ''
}

const API_BASE = resolveApiBase()

export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export async function apiFetch<T>(
  path: string,
  options?: RequestInit & { signal?: AbortSignal },
): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      Accept: 'application/json',
      ...options?.headers,
    },
  })

  if (!response.ok) {
    throw new ApiError(`API no disponible (${response.status})`, response.status)
  }

  return response.json() as Promise<T>
}

export function apiGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  return apiFetch<T>(path, { signal })
}

export function apiPost<T>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  return apiFetch<T>(path, {
    method: 'POST',
    signal,
    headers: { 'Content-Type': 'application/json' },
    body: body != null ? JSON.stringify(body) : undefined,
  })
}

export function apiPatch<T>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  return apiFetch<T>(path, {
    method: 'PATCH',
    signal,
    headers: { 'Content-Type': 'application/json' },
    body: body != null ? JSON.stringify(body) : undefined,
  })
}

export function apiDelete<T>(path: string, signal?: AbortSignal): Promise<T> {
  return apiFetch<T>(path, { method: 'DELETE', signal })
}
