export default function RefactorPreviewModal({
  originalCode,
  refactoredCode,
  onAccept,
  onCancel,
}) {
  return (
    <div className="fixed inset-0 bg-black bg-opacity-70 flex items-center justify-center z-50">
      <div className="bg-[#121212] rounded-xl w-full max-w-5xl border border-[#2b2b2b] shadow-lg">
        {/* Header */}
        <div className="border-b border-[#2b2b2b] p-5">
          <h2 className="text-2xl font-semibold text-white">
            Refactor Preview
          </h2>
        </div>

        {/* Code Section */}
        <div className="grid grid-cols-2 gap-6 p-6">
          {/* Original Code */}
          <div>
            <h3 className="text-sm text-gray-400 mb-2">Original Code</h3>
            <div className="bg-black border border-[#2b2b2b] rounded-lg h-80 overflow-y-auto no-scrollbar p-4">
              <pre className="text-gray-300 text-sm whitespace-pre-wrap">
                {originalCode}
              </pre>
            </div>
          </div>

          {/* Refactored Code */}
          <div>
            <h3 className="text-sm text-gray-400 mb-2">Refactored Code</h3>
            <div className="bg-black border border-[#2b2b2b] rounded-lg h-80 overflow-y-auto no-scrollbar p-4">
              <pre className="text-gray-300 text-sm whitespace-pre-wrap">
                {refactoredCode}
              </pre>
            </div>
          </div>
        </div>

        {/* Buttons */}
        <div className="border-t border-[#2b2b2b] p-6 flex justify-end gap-4">
          <button
            onClick={onCancel}
            className="px-6 py-2 bg-[#2b2b2b] hover:bg-[#3b3b3b] text-white rounded-lg transition-all"
          >
            Cancel
          </button>
          <button
            onClick={onAccept}
            className="px-6 py-2 bg-[#FFA500] hover:bg-[#ffb94d] text-black font-semibold rounded-lg transition-all"
          >
            Accept and Save
          </button>
        </div>
      </div>
    </div>
  );
}
