// src/libs/utils/storage.js
// Small helpers to safely interact with localStorage and JSON values.

const isBrowser = typeof window !== 'undefined' && typeof window.localStorage !== 'undefined';

export function getJSON(key, fallback = null) {
  if (!isBrowser) return fallback;
  try {
    const raw = window.localStorage.getItem(key);
    if (raw == null) return fallback;
    return JSON.parse(raw);
  } catch (_) {
    return fallback;
  }
}

export function setJSON(key, value) {
  if (!isBrowser) return;
  try {
    if (value === undefined) return;
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch (_) {
    // no-op
  }
}

export function remove(key) {
  if (!isBrowser) return;
  try {
    window.localStorage.removeItem(key);
  } catch (_) {
    // no-op
  }
}

export const storage = { getJSON, setJSON, remove };
