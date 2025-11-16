// src/libs/hooks/auth/mutation.js
// React Query mutation hooks for authentication write actions (logout, etc.)

import { useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { usePost } from '../../api/api';
import { ENDPOINTS } from '../../api/endpoints';
import { useUser } from '../../stores/useUser';

/**
 * useLogout
 * Sends POST to logout endpoint and clears cached auth/user queries.
 * Optionally accepts react-query mutation options; preserves caller's onSuccess.
 */
export function useLogout(options = {}) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const clearUser = useUser((s) => s.clearUser);

  return usePost(ENDPOINTS.AUTH.LOGOUT, {
    ...options,
    onSuccess: (result, variables, context) => {
      // Remove or invalidate relevant auth-related queries
      queryClient.removeQueries({ queryKey: [ENDPOINTS.USER] });
      queryClient.removeQueries({ queryKey: [ENDPOINTS.AUTH.STATUS] });

      // Clear any persisted user information (Zustand + localStorage)
      try {
        clearUser();
      } catch (_) {
        // no-op
      }

      // Optional: navigate or perform extra side-effects here (caller can do in their onSuccess)
      if (typeof options.onSuccess === 'function') {
        options.onSuccess(result, variables, context);
      }
      // Prefer client-side navigation if Router is available; fallback to hard redirect
      try {
        navigate('/login', { replace: true });
      } catch (_) {
        window.location.replace('/login');
      }
    },
  });
}
