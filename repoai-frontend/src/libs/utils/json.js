// src/libs/utils/json.js
// Safe JSON stringify utility that handles circular references gracefully.
// Usage: safeJSONStringify(value, space?)

export function safeJSONStringify(value, space = 0) {
  const seen = new WeakSet();
  try {
    return JSON.stringify(value, (key, val) => {
      if (typeof val === 'object' && val !== null) {
        if (seen.has(val)) return '[Circular]';
        seen.add(val);
      }
      // Drop functions and symbols explicitly
      if (typeof val === 'function' || typeof val === 'symbol') return undefined;
      return val;
    }, space);
  } catch (e) {
    try {
      // Last resort string coercion
      return String(value);
    } catch (_) {
      return '';
    }
  }
}
