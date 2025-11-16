// Utility to normalize and format SSE chat events before rendering.
// The incoming evt can be: string | object with fields like { message, status, progress, stage, timestamp, ... }
// We return an object: { text, kind, meta }
// - text: string to display in the bubble
// - kind: 'progress' | 'error' | 'completed' | 'info' | 'raw'
// - meta: original event payload for future richer rendering
// Extend the classification rules as backend evolves.

export function formatChatEvent(evt) {
  if (evt == null) {
    return { text: '[empty event]', kind: 'raw', meta: evt };
  }
  // If already a string, just echo it
  if (typeof evt === 'string') {
    return { text: evt, kind: classifyText(evt), meta: evt };
  }
  // Attempt to pick a primary message field
  const message = safeString(evt.message) || safeString(evt.text) || fallbackSerialize(evt);
  const status = toLower(evt.status);
  const stage = toLower(evt.stage);
  const progress = typeof evt.progress === 'number' ? evt.progress : (typeof evt.pct === 'number' ? evt.pct : undefined);

  // Classification heuristics
  if (['error','failed','failure'].includes(status)) {
    return { text: message, kind: 'error', meta: evt };
  }
  if (['completed','complete','done','finished'].includes(status) || ['final','finalized'].includes(stage)) {
    return { text: message, kind: 'completed', meta: evt };
  }
  if (typeof progress === 'number' && progress >= 0 && progress < 100) {
    // Do not prefix the message with percentage; just classify as progress
    return { text: message, kind: 'progress', meta: evt };
  }
  if (status === 'running' || stage === 'idle') {
    return { text: message, kind: 'info', meta: evt };
  }
  return { text: message, kind: 'raw', meta: evt };
}

function classifyText(txt) {
  const t = toLower(txt);
  if (!t) return 'raw';
  if (t.includes('error') || t.includes('failed')) return 'error';
  if (t.includes('completed') || t.includes('finished')) return 'completed';
  if (t.match(/\b\d{1,3}%\b/)) return 'progress';
  return 'raw';
}

function withProgressPrefix(message, progress) {
  const pct = Math.max(0, Math.min(100, Math.round(progress)));
  return `[${pct}%] ${message}`;
}

function safeString(v) {
  if (v == null) return '';
  if (typeof v === 'string') return v;
  try { return JSON.stringify(v); } catch { return String(v); }
}

function fallbackSerialize(obj) {
  try { return JSON.stringify(obj); } catch { return String(obj); }
}

function toLower(v) {
  return typeof v === 'string' ? v.toLowerCase() : '';
}

// Optional richer formatting hook for React components.
// Given the formatted object, produce a JSX-ready piece of data.
// For now we keep it simple and just return formatted.text.
export function renderFormattedChat(formatted) {
  return formatted?.text ?? '';
}
