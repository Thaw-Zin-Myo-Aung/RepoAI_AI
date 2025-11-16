import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// Simple card to display a markdown-like plan summary and metadata
// Props: { summary: string, planId?: string, totalSteps?: number, requiresConfirmation?: boolean, confirmationType?: string }
export default function PlanSummaryCard({ summary, planId, totalSteps, requiresConfirmation, confirmationType }) {
  return (
    <div className="w-full bg-[#1a1a1a] border border-[#333] rounded-xl p-4 text-sm text-gray-200">
      <div className="flex items-center justify-between mb-2">
        <div className="font-semibold text-white">Plan Summary</div>
        <div className="text-xs text-gray-400 space-x-2">
          {planId && <span>id: {planId}</span>}
          {typeof totalSteps === 'number' && <span>steps: {totalSteps}</span>}
          {requiresConfirmation && (
            <span className="text-amber-400">needs {confirmationType || 'confirmation'}</span>
          )}
        </div>
      </div>
      {summary ? (
        <ReactMarkdown
          // Keep styling simple to avoid Tailwind Typography dependency
          className="wrap-break-word text-gray-100 text-sm leading-6 space-y-2"
          remarkPlugins={[remarkGfm]}
          components={{
            h1: ({node, ...props}) => <h1 className="text-lg font-semibold text-white mt-2" {...props} />,
            h2: ({node, ...props}) => <h2 className="text-base font-semibold text-white mt-2" {...props} />,
            h3: ({node, ...props}) => <h3 className="text-sm font-semibold text-white mt-2" {...props} />,
            p: ({node, ...props}) => <p className="text-gray-200" {...props} />,
            li: ({node, ...props}) => <li className="ml-4 list-disc" {...props} />,
            code: ({inline, className, children, ...props}) => (
              <code className={`bg-[#111] border border-[#333] rounded px-1.5 py-0.5 ${inline ? '' : 'block p-3'}`} {...props}>
                {children}
              </code>
            )
          }}
        >
          {summary}
        </ReactMarkdown>
      ) : (
        <div className="text-gray-400 italic">No summary available.</div>
      )}
    </div>
  );
}
