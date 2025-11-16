// src/libs/api/api.js
// Centralized API utilities + reusable React hook for performing requests.
// Features:
// - BASE_URL from Vite env (VITE_API_BASE_URL)
// - Normalized route concatenation: BASE_URL + '/route/' + endpoint
// - GET with query params object support
// - POST/PUT/PATCH with JSON body (auto stringified) & optional body-less requests
// - DELETE requests
// - Abortable requests & auto cancellation on component unmount
// - Unified error object with status/code/message
// - Hook returns { data, error, loading, execute, reset }
// - Safe to call execute with overrides each time

import { useMemo } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';

// Read and normalize base URL (strip trailing slash). Fallback to localhost.
export const BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000').replace(/\/$/, '');

// Ensure route base segment is always exactly '/route'
const ROUTE_BASE = '/route';

function buildUrl(endpoint, params) {
	// Normalize leading slash on endpoint
	const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
	const base = `${BASE_URL}${cleanEndpoint}`; // e.g. http://..../route/users
	if (!params || Object.keys(params).length === 0) return base;
	const usp = new URLSearchParams();
	Object.entries(params).forEach(([k, v]) => {
		if (v === undefined || v === null) return;
		if (Array.isArray(v)) {
			v.forEach(item => usp.append(k, item));
		} else {
			usp.append(k, String(v));
		}
	});
	const qs = usp.toString();
	return qs ? `${base}?${qs}` : base;
}

const AUTH_REDIRECT_URL = (import.meta.env.VITE_AUTH_REDIRECT_URL || 'http://localhost:3000/login');

async function coreRequest({ method = 'GET', endpoint, params, body, headers, signal }) {
	if (!endpoint) throw new Error('endpoint is required');
	const url = buildUrl(endpoint, method === 'GET' ? params : undefined);
	const init = { method, headers: { 'Content-Type': 'application/json', ...(headers || {}) }, signal, credentials: 'include' };
	if (body !== undefined && body !== null && method !== 'GET' && method !== 'HEAD') {
		init.body = typeof body === 'string' ? body : JSON.stringify(body);
	}

	let res;
	try {
		res = await fetch(url, init);
	} catch (networkErr) {
		// Network / CORS / Abort error
		if (networkErr.name === 'AbortError') throw networkErr; // propagate abort
		throw {
			type: 'NETWORK',
			message: networkErr.message,
			original: networkErr,
		};
	}

	const contentType = res.headers.get('content-type') || '';
	let parsed;
	if (contentType.includes('application/json')) {
		try { parsed = await res.json(); } catch { parsed = null; }
	} else {
		parsed = await res.text().catch(() => null);
	}

		if (!res.ok) {
				// Global 401 handler: force login redirect
				if (res.status === 401) {
					try {
						const loginUrl = AUTH_REDIRECT_URL;
						if (typeof window !== 'undefined' && window.location) {
							// Avoid redirect loop if already on login page
							if (!window.location.href.startsWith(loginUrl)) {
								window.location.href = loginUrl;
							}
						}
					} catch (_) {
						// no-op
					}
				}
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

// Convenience wrappers
export const api = {
	get: (endpoint, params, options = {}) => coreRequest({ method: 'GET', endpoint, params, ...options }),
	post: (endpoint, body, options = {}) => coreRequest({ method: 'POST', endpoint, body, ...options }),
	put: (endpoint, body, options = {}) => coreRequest({ method: 'PUT', endpoint, body, ...options }),
	patch: (endpoint, body, options = {}) => coreRequest({ method: 'PATCH', endpoint, body, ...options }),
	delete: (endpoint, options = {}) => coreRequest({ method: 'DELETE', endpoint, ...options }),
	request: coreRequest,
};

// (Legacy manual useApi hook removed; React Query hooks below are the preferred interface.)

// ---------------------------------------------------------------------------
// React Query integration (preferred)
// ---------------------------------------------------------------------------

/** Build a stable query key. */
export function qk(base, params) {
	if (Array.isArray(base)) return params ? [...base, params] : base;
	return params ? [base, params] : [base];
}

/** useGetQuery – perform a GET request with optional query params. */
export function useGetQuery(endpoint, params, options = {}) {
	const key = useMemo(() => options.key || qk(endpoint, params), [options.key, endpoint, params]);
	return useQuery({
		queryKey: key,
		queryFn: () => api.get(endpoint, params),
		select: (res) => res.data,
		...options,
	});
}

/** Generic mutation hook for POST/PUT/PATCH/DELETE. */
export function useApiMutation(method, endpoint, options = {}) {
	return useMutation({
		mutationFn: (variables) => {
			switch (method) {
				case 'POST':
					return api.post(endpoint, variables);
				case 'PUT':
					return api.put(endpoint, variables);
				case 'PATCH':
					return api.patch(endpoint, variables);
				case 'DELETE':
					return api.delete(endpoint);
				default:
					throw new Error(`Unsupported method for mutation: ${method}`);
			}
		},
		...options,
	});
}

export const usePost = (endpoint, options) => useApiMutation('POST', endpoint, options);
export const usePut = (endpoint, options) => useApiMutation('PUT', endpoint, options);
export const usePatch = (endpoint, options) => useApiMutation('PATCH', endpoint, options);
export const useDelete = (endpoint, options) => useApiMutation('DELETE', endpoint, options);

// Example React Query usage:
// const usersQuery = useGetQuery('users', { page: 1 });
// const createUser = usePost('users');
// createUser.mutate({ name: 'Alice' });

