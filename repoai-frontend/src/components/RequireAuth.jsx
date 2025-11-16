import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useProfile } from '../libs/hooks/profile/queries';
// ENDPOINTS no longer needed directly here; using centralized auth queries

// Protects routes by verifying the current session from /route/user.
// If unauthenticated (401 handled globally) or user missing, redirects to /login.
export default function RequireAuth({ children }) {
  const location = useLocation();
  // Query current user/session profile and sync to store
  const { data, isLoading, isError, error } = useProfile();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen text-white bg-[#121212]">
        <p>Checking authentication…</p>
      </div>
    );
  }

  // Unauthenticated conditions: 401 error or missing user identity
  if ((isError && error?.status === 401) || !data || !data.username) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return children;
}
