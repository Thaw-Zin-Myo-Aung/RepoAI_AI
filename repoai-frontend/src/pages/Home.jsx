import { Plus } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useUser } from '../libs/stores/useUser';
import { useProfile } from '../libs/hooks/profile/queries';

export default function Home() {
  const navigate = useNavigate();

  // Hydrate user profile into store (from API/cache)
  const { isLoading } = useProfile();
  const user = useUser((s) => s.user);

  if (isLoading && !user) {
    return (
      <div className="flex items-center justify-center h-screen text-white bg-[#121212]">
        <p>Loading user data...</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen bg-[#121212] text-white">
      {/* Header */}
      <div className="px-8 py-6 border-b border-neutral-800 mx-[5%]">
        <h1 className="text-3xl font-bold mb-2 text-[#FFFFFF] m-0">
          {user?.username ? `Welcome, @${user.username}` : 'Welcome to Repo AI'}
        </h1>
        <p className="text-[#FFA500] my-5">
          {user?.username
            ? 'Connected to GitHub • Your repositories are ready to analyze'
            : 'Not connected to GitHub'}
        </p>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col items-center justify-center text-center">
        <div className="max-w-3xl">
          <div className="mb-[75px]">
            <h2 className="text-[35px] font-bold leading-tight text-[#FFFFFF] m-5">
              Welcome to Repo AI
            </h2>
            <p className="text-[35px] text-[#FFFFFF] mb-20">
              Your AI-Powered Code Refactoring Assistant
            </p>
          </div>

          <button
            onClick={() => navigate('/init-chat', { state: { repos: [] } })}
            className="gap-2 bg-[#FFA500] hover:bg-yellow-600 text-black font-bold p-3 rounded-[10px] inline-flex items-center transition-colors text-lg mb-[30px]"
          >
            <Plus className="w-6 h-6" />
            <div className="font-bold text-[20px]">Create a new chat</div>
          </button>

          <p className="text-[#FFA500]">
            Pick a repository and branch to analyze your code
          </p>
        </div>

        {/* Optional Repository Preview */}
        {/* <div className="mt-10 text-left">
          <h3 className="text-lg font-semibold mb-2">Repositories:</h3>
          <ul className="space-y-1 text-gray-300">
            {(user?.repositories || []).map((repo) => (
              <li key={repo.id}>
                <span className="font-medium">{repo.name}</span> — branch: {repo.branch}
              </li>
            ))}
          </ul>
        </div> */}
      </div>
    </div>
  );
}
