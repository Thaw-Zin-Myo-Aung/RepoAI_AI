import React from "react";
import { useNavigate } from "react-router-dom";

export default function ClearHistoryModal({ onCancel, onConfirm }) {
  const navigate = useNavigate();

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="rounded-lg p-6 max-w-md w-full bg-[#212121]">
        <h3 className="text-xl font-semibold mb-4">Confirm Clear History</h3>
        <p className="text-gray-300 mb-6">
          Are you sure you want to delete all refactoring sessions? This action
          cannot be undone.
        </p>

        <div className="flex gap-3 justify-end">
          {/* ❌ Cancel Button */}
          <button
            onClick={onCancel}
            className="px-[15px] py-[3px] rounded-lg bg-gray-600 text-white hover:bg-gray-500 transition"
          >
            Cancel
          </button>

          {/* ✅ Confirm Button */}
          <button
            onClick={() => {
              onConfirm();
              navigate("/chat-history", { state: { clear: true } });
            }}
            className="px-[15px] py-[3px] rounded-lg bg-[#FFA500] text-[#000000] hover:bg-[#ffb733] transition"
          >
            Clear History
          </button>
        </div>
      </div>
    </div>
  );
}
