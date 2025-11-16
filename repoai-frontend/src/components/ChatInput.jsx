import { useState } from "react";

export default function ChatInput({ chatMessages, setChatMessages, onSend, placeholder = "Enter your prompt", disabled = false, loading = false }) {
  const [inputText, setInputText] = useState("");

  const handleSend = () => {
    if (disabled || !inputText.trim()) return;

    if (onSend) {
      onSend(inputText); // call ChatBox handler
    }

    setInputText("");
  };

  return (
    <div className="w-full bg-[#0d0d0d] border-t border-[#1f1f1f] px-6 py-4 flex items-center gap-3">
      <input
        type="text"
        placeholder={placeholder}
        value={inputText}
        onChange={(e) => setInputText(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && handleSend()}
        disabled={disabled}
        aria-busy={loading}
        className={`flex-1 bg-[#1a1a1a] text-gray-200 placeholder-gray-500 px-4 py-3 rounded-xl focus:outline-none ${disabled ? 'opacity-60 cursor-not-allowed' : ''}`}
      />
      <button
        onClick={handleSend}
        disabled={disabled}
        className={`flex items-center gap-2 bg-[#f5a623] hover:bg-[#e89920] text-black font-medium px-6 py-3 rounded-xl transition-all ${disabled ? 'opacity-60 cursor-not-allowed hover:bg-[#f5a623]' : ''}`}
      >
        {loading && (
          <span className="inline-block h-4 w-4 border-2 border-black/40 border-t-black rounded-full animate-spin" />
        )}
        {loading ? 'Generating' : 'Send'}
      </button>
    </div>
  );
}
