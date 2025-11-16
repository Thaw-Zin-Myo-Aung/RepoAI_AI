// src/libs/api/repoai.js
// Lightweight API client for the RepoAI service (separate backend)
// Usage: import { repoai, useRepoGetQuery, useRepoPost } from './repoai'

import { useMemo } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';

// Base URL for RepoAI service (exposed via Vite env)
export const REPOAI_BASE_URL = (import.meta.env.VITE_REPOAI_URL || 'https://repoai-service-1057557503959.us-central1.run.app').replace(/\/$/, '');

function buildRepoAiUrl(endpoint, params) {
  // Allow endpoint with or without leading slash
  const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  const base = `${REPOAI_BASE_URL}${cleanEndpoint}`;
  if (!params || Object.keys(params).length === 0) return base;
  const usp = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v === undefined || v === null) return;
    if (Array.isArray(v)) v.forEach(item => usp.append(k, item));
    else usp.append(k, String(v));
  });
  const qs = usp.toString();
  return qs ? `${base}?${qs}` : base;
}

async function coreRepoAiRequest({ method = 'GET', endpoint, params, body, headers, signal }) {
  if (!endpoint) throw new Error('endpoint is required');
  const url = buildRepoAiUrl(endpoint, method === 'GET' ? params : undefined);
  const init = { method, headers: { 'Content-Type': 'application/json', ...(headers || {}) }, signal, credentials: 'include' };
  if (body !== undefined && body !== null && method !== 'GET' && method !== 'HEAD') {
    init.body = typeof body === 'string' ? body : JSON.stringify(body);
  }

  let res;
  try {
    res = await fetch(url, init);
  } catch (networkErr) {
    if (networkErr.name === 'AbortError') throw networkErr;
    throw { type: 'NETWORK', message: networkErr.message, original: networkErr };
  }

  const contentType = res.headers.get('content-type') || '';
  let parsed;
  if (contentType.includes('application/json')) {
    try { parsed = await res.json(); } catch { parsed = null; }
  } else {
    parsed = await res.text().catch(() => null);
  }

  if (!res.ok) {
    throw {
      type: 'HTTP',
      status: res.status,
      statusText: res.statusText,
      message: (parsed && parsed.message) || `Request failed (${res.status})`,
      body: parsed,
      url,
      method,
    };
  }

  return { data: parsed, status: res.status, headers: res.headers, url };
}

export const repoai = {
  get: (endpoint, params, options = {}) => coreRepoAiRequest({ method: 'GET', endpoint, params, ...options }),
  post: (endpoint, body, options = {}) => coreRepoAiRequest({ method: 'POST', endpoint, body, ...options }),
  put: (endpoint, body, options = {}) => coreRepoAiRequest({ method: 'PUT', endpoint, body, ...options }),
  patch: (endpoint, body, options = {}) => coreRepoAiRequest({ method: 'PATCH', endpoint, body, ...options }),
  delete: (endpoint, options = {}) => coreRepoAiRequest({ method: 'DELETE', endpoint, ...options }),
  request: coreRepoAiRequest,
};

// React Query helpers (parallel to src/libs/api/api.js but for RepoAI)
export function qkRepo(base, params) {
  if (Array.isArray(base)) return params ? [...base, params] : base;
  return params ? [base, params] : [base];
}

const DEFAULT_OPTIONS = { staleTime: 20_000, refetchOnWindowFocus: false };

export function useRepoGetQuery(endpoint, params, options = {}) {
  const key = useMemo(() => options.key || qkRepo(endpoint, params), [options.key, endpoint, params]);
  return useQuery({ queryKey: key, queryFn: () => repoai.get(endpoint, params), select: (res) => res.data, ...DEFAULT_OPTIONS, ...options });
}

export function useRepoApiMutation(method, endpoint, options = {}) {
  return useMutation({ mutationFn: (variables) => {
    switch (method) {
      case 'POST': return repoai.post(endpoint, variables);
      case 'PUT': return repoai.put(endpoint, variables);
      case 'PATCH': return repoai.patch(endpoint, variables);
      case 'DELETE': return repoai.delete(endpoint, variables);
      default: throw new Error(`Unsupported method for repoai mutation: ${method}`);
    }
  }, ...options });
}

export const useRepoPost = (endpoint, options) => useRepoApiMutation('POST', endpoint, options);
export const useRepoPut = (endpoint, options) => useRepoApiMutation('PUT', endpoint, options);
export const useRepoPatch = (endpoint, options) => useRepoApiMutation('PATCH', endpoint, options);
export const useRepoDelete = (endpoint, options) => useRepoApiMutation('DELETE', endpoint, options);

export default { repoai, useRepoGetQuery, useRepoPost, useRepoPut, useRepoPatch, useRepoDelete };
