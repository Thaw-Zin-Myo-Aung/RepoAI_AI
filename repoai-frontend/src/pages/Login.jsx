import React, { useEffect } from 'react';

// Configurable backend OAuth login URL (fallback keeps current behavior)

import { useAuthStatus } from '../libs/hooks/auth/queries';
const LOGIN_URL = import.meta.env.VITE_LOGIN_URL || 'http://localhost:8081/api/auth/login';

import { Coffee } from 'lucide-react';
export default function RepoAILogin() {
  const { data, isLoading } = useAuthStatus();

  // If already authenticated, redirect away from login
  useEffect(() => {
    if (!isLoading && (data?.authenticated === true || data?.username)) {
      window.location.replace('/home');
    }
  }, [isLoading, data]);
  return (
    <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: '#000000' }}>
      <div className="text-center">
        {/* Coffee Cup Icon */}
        <div className="flex justify-center mb-8">
           <Coffee className="w-24 h-24 text-white" strokeWidth={1.5} />
        </div>

        {/* Title */}
        <h1 className="text-4xl font-bold mb-8" style={{ color: '#FFFFFF' }}>
          Log in to RepoAI
        </h1>

        {/* Description */}
        <p className="mb-1 text-[#FFFFFF]">
          We use GitHub OAuth for secure and simple authentication.
        </p>
  <p className="mb-16 mt-0 text-[#FFFFFF]">
          Your personal information is never stored on our servers.
        </p>

         {/* Login Button */}
         <button  onClick={() => { window.location.href = LOGIN_URL; }}
  className="px-3 py-1 rounded-[10px] bg-[#FFA500] flex items-center gap-1 mx-auto my-[25px] transition-all duration-200 hover:opacity-90"
>
          <svg 
            width="24" 
            height="24" 
            viewBox="0 0 24 24" 
            fill="currentColor"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/>
          </svg>
          <div className="mx-3 text-2xl font-semibold">
  Login with GitHub
</div>

        </button>
      </div>
    </div>
  );
}