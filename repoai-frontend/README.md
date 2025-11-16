# Repo-AI-Frontend

## Environment variables

Create a .env.local file in the project root with at least:

- VITE_API_BASE_URL: Base URL of your backend API (no trailing slash). Example:
	- VITE_API_BASE_URL=http://localhost:8081
- Optional: VITE_LOGIN_URL: Full URL to initiate OAuth login (used by Login page). Example:
	- VITE_LOGIN_URL=http://localhost:8081/api/auth/login
- Optional: VITE_AUTH_REDIRECT_URL: Client-side login page to redirect on 401 responses. Example:
	- VITE_AUTH_REDIRECT_URL=http://localhost:3000/login

Notes:
- All API requests are automatically sent to `${VITE_API_BASE_URL}/route/<endpoint>`.
- 401 Unauthorized responses trigger a redirect to VITE_AUTH_REDIRECT_URL (fallback to http://localhost:3000/login).
- The Login page redirects the browser to VITE_LOGIN_URL (fallback to http://localhost:8081/api/auth/login).

## API layer and hooks

- Central API utilities live in `src/libs/api/api.js`.
- Endpoints are centralized in `src/libs/api/endpoints.js`.
- Use React Query hooks from `api.js`:
	- `useGetQuery(endpoint, params?, options?)` for GET requests
	- `usePost|usePut|usePatch|useDelete(endpoint, options?)` for write operations

Example:

```
import { useGetQuery } from './libs/api/api';
import { ENDPOINTS } from './libs/api/endpoints';

const { data, isLoading, error } = useGetQuery(ENDPOINTS.USER);
```