import React, { useState } from "react";
import ClearHistoryModal from "../components/ClearHistoryModel"; // ✅ import modal
import { useLogout } from "../libs/hooks/auth/mutation";
import { useUser } from "../libs/stores/useUser";
import { useProfile } from "../libs/hooks/profile/queries";

export default function Profile() {
  const [showClearConfirm, setShowClearConfirm] = useState(false);
  const logout = useLogout(); 
  // Ensure profile is hydrated (from API/cache); this will also sync the store
  useProfile();

  // Read user from store
  const user = useUser((s) => s.user);

  const displayName = user?.username || user?.name || "Anonymous";
  const role = "GitHub User";
  const avatar = user?.avatarUrl || "https://api.dicebear.com/7.x/avataaars/svg?seed=RepoAI";
  const email = user?.email || "";
  const profileUrl = user?.profileUrl || (user?.username ? `https://github.com/${user.username}` : "");
  const historyCount = 0; // Replace with real count when available

  return (
    <div className="flex h-screen bg-[#121212] text-[#FFFFFF]">
      <div className="flex-1 overflow-auto">
        <div className="max-w-3xl mx-auto py-12">
          <h1 className="text-3xl font-bold text-white">Profile</h1>

          {/* Profile Card */}
          <div className="rounded-lg p-8 my-10">
            <div className="flex flex-col items-center">
              <div className="w-[20%] h-[20%] rounded-full mb-4 overflow-hidden bg-[#FFC285] my-4">
                <img
                  src={avatar}
                  alt="Profile"
                  className="w-full h-full object-cover"
                />
              </div>

              <h2 className="text-2xl text-white font-semibold mt-8 mb-2">
                {displayName}
              </h2>
              <p className="text-[#FFA500] mb-2">{role}</p>
              {email && <p className="text-sm mb-4 text-[#CCCCCC]">{email}</p>}
              {profileUrl && (
                <a
                  href={profileUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="text-[#FFA500] underline mb-6"
                >
                  View GitHub Profile
                </a>
              )}

              <button
                onClick={() => logout.mutate()}
                className="my-2.5 bg-[#343A40] text-[#FFFFFF] w-[50%] max-w-md py-[1%] rounded-[10px] font-medium transition-colors"
              >
                Logout
              </button>
            </div>
          </div>

          {/* Clear History Section */}
          <div className="rounded-lg p-6">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-xl font-semibold mb-2">
                  Clear All History?
                </h3>
                <p className="text-sm mb-1" style={{ color: "#FFA500" }}>
                  This will permanently delete all {historyCount} refactoring sessions.
                </p>
                <p className="text-sm" style={{ color: "#FFA500" }}>
                  This action cannot be undone.
                </p>
              </div>

              <button
                onClick={() => setShowClearConfirm(true)}
                className="text-[#FFFFFF] bg-[#343A40] p-2 rounded-[10px] font-medium transition-colors whitespace-nowrap"
              >
                Clear History
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* ✅ Modal Component */}
      {showClearConfirm && (
        <ClearHistoryModal
          onCancel={() => setShowClearConfirm(false)}
          onConfirm={() => setShowClearConfirm(false)}
        />
      )}
    </div>
  );
}
