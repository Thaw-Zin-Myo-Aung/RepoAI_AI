import React, { useState, useEffect } from "react";
import { Coffee } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useSession } from "../libs/stores/useSession";
//import { repoData } from "../config/repoData"; // ✅ import centralized variables

export default function Loading() {
  const [progress, setProgress] = useState(0);
  const navigate = useNavigate();
  const currentConversation = useSession((s) => s.currentConversation);
  // src/config/repoData.js
const repoData = {
  repoName: "Awesome-Repo",
  branch: "main",
  analysisTime: 100, // milliseconds per progress step (adjust as needed)
  nextRoute: "/chat-box", // route to navigate after analysis
  messages: {
    loading: "Analyzing...",
    complete: "Analysis complete",
    waiting: "Please wait while we analyze your repository. This may take a few minutes."
  }
};


  useEffect(() => {
    const interval = setInterval(() => {
      setProgress((prev) => {
        if (prev >= 100) {
          clearInterval(interval);
          setTimeout(() => {
            const convId = currentConversation?.id;
            const target = convId
              ? `${repoData.nextRoute}/${encodeURIComponent(convId)}`
              : repoData.nextRoute;
            navigate(target);
          }, 500);
          return 100;
        }
        return prev + 1;
      });
    }, repoData.analysisTime); // ✅ configurable speed

    return () => clearInterval(interval);
  }, [navigate, currentConversation]);

  return (
    <div className="min-h-screen bg-[#121212] flex items-center justify-center px-[5%] text-[#FFFFFF] animate-fade-in">
      <div className="text-center max-w-3xl w-full">
        {/* Coffee Icon */}
        <div className="mb-8 flex justify-center">
          <div className="w-48 h-48 bg-neutral-900 rounded-2xl flex items-center justify-center animate-pulse">
            <Coffee className="w-24 h-24 text-white" strokeWidth={1.5} />
          </div>
        </div>

        {/* Title */}
        <h1 className="text-4xl font-bold mb-4">
          Analyzing your repository: <br /> 
          <h2>{repoData.repoName}</h2> 
          <h3>({repoData.branch})</h3>
        </h1>

        {/* Status Message */}
  <div className="flex justify-end m-0">
          <p className="text-gray-400 text-base mt-2">
            {progress < 100 ? repoData.messages.loading : repoData.messages.complete}
          </p>
        </div>

        {/* Progress Section */}
        <div className="max-w-2xl mx-auto mb-4 flex items-center gap-4">
          <div className="flex-1 bg-[#222222] rounded-full h-[12px] overflow-hidden my-[5px]">
            <div
              className="h-full rounded-full transition-all duration-200 ease-linear bg-[#FFFFFF] shadow-[0_0_10px_#FFFFFF]"
              style={{ width: `${progress}%` }}
            ></div>
          </div>

          <div className="ml-2.5 text-white text-sm font-semibold w-12 text-right">
            {progress}%
          </div>
        </div>

        {/* Additional text */}
        <p className="text-lg text-[#FFFFFF] mb-8">
          {repoData.messages.waiting}
        </p>
      </div>
    </div>
  );
}
