// Central registry of API endpoints (relative paths after /route)
// Keep only string constants & small helpers here. Do not perform fetch.
// Example usage: api.get(ENDPOINTS.USER) or api.post(ENDPOINTS.REPOS, body)

export const ENDPOINTS = Object.freeze({
  USER: "api/user/profile", // current authenticated user session/profile
  REPOS: "repos",
  AUTH: {
    TOKEN: "api/auth/token",
    STATUS: "api/auth/status",
    LOGIN: "api/auth/login", // if you need an internal call (not used for OAuth redirect)
    LOGOUT: "api/auth/logout",
  },
  REPOSITORIES: {
    LIST: "api/repos",
    SYNC: "api/github/sync_repos",
  },
  BRANCHES: {
    LIST: (repoId) => `api/repos/${repoId}/branches`,
    SYNC_BRANCHES: (owner, repo) => `api/github/${owner}/${repo}/branches/sync`,
  },
  REPOAI:{
    HEALTH_CHECK: "api/health",
    START_REFACTOR: "api/refactor",
    REFACTOR_SSE: (session_id) => `api/refactor/${session_id}/sse`,
    REFACTOR_CONFIRM_PLAN: (session_id) => `api/refactor/${session_id}/confirm-plan`,
    REFACTOR_VALIDATION: (session_id) => `api/refactor/${session_id}/confirm-validation`,
    REFACTOR_PUSH: (session_id) => `api/refactor/${session_id}/confirm-push`,
  },
  CONVERSATION: {
    UPDATE: (id) => `api/conversations/${id}`,
    DELETE: (id) => `api/conversations/${id}`,
    CREATE: "api/conversations",
    LIST: () => `api/conversations`,
    DETAIL: (id) => `api/conversations/${id}/chats`,
  },
  CHAT: {
    CREATE: (conv_id) => `api/conversations/${conv_id}/chats`,
    UPDATE: (conv_id, chat_id) => `api/conversations/${conv_id}/chats/${chat_id}`,
    DELETE: (conv_id) => `api/conversations/${conv_id}/chats`,
  },
});

// Pattern for feature grouping example (extend when needed)
// export const CHAT = {
//   ROOT: 'chat',
//   SESSIONS: 'chat/sessions',
//   SESSION: (id) => `chat/sessions/${id}`,
// };
