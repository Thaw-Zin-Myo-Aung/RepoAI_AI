import RobotProfileImage from "../assets/robot.png";
import UserProfileImage from "../assets/user.png";
import PlanSummaryCard from "./PlanSummaryCard";
import PushSummaryCard from "./PushSummaryCard";
import ValidationSummaryCard from "./ValidationSummaryCard";
import TerminalConsole from "./TerminalConsole";
import FileChangeViewer from "./FileChangeViewer";

export function ChatMessage({ message, sender, kind, meta, items }) {
  const isUser = sender === "user";

  return (
    <div
      className={`flex items-end mb-4 ${
        isUser ? "justify-end" : "justify-start"
      }`}
    >
      {!isUser && (
        <div className="flex flex-col items-start max-w-[80%]">
          <span className="text-xs text-gray-400 mb-1 ml-1">AI</span>
          {/* Aggregated AI block: when items are provided, render them as a single message block */}
          {Array.isArray(items) && items.length > 0 ? (
            <div className= "max-w-[80%] space-y-2">
              {(() => {
                const nodes = [];
                let buf = [];
                const flush = (key) => {
                  if (buf.length > 0) {
                    nodes.push(
                      <div key={key} className="mt-2">
                        <TerminalConsole lines={buf} />
                      </div>
                    );
                    buf = [];
                  }
                };

                items.forEach((it, idx) => {
                  if (it.type === 'raw_line') {
                    buf.push(it.raw);
                    return;
                  }
                  // non-raw: flush and render
                  flush(`flush-${idx}`);
                  if (it.type === 'plan_summary') {
                    const m = it.meta;
                    nodes.push(
                      <div key={`plan-${idx}`} className="mt-2">
                        <PlanSummaryCard
                          summary={m?.data?.plan_summary}
                          planId={m?.data?.plan_id}
                          totalSteps={m?.data?.total_steps}
                          requiresConfirmation={m?.requires_confirmation}
                          confirmationType={m?.confirmation_type}
                        />
                      </div>
                    );
                    return;
                  }
                  if (it.type === 'validation_summary') {
                    const m = it.meta;
                    nodes.push(
                      <div key={`val-${idx}`} className="mt-2">
                        <ValidationSummaryCard
                          summary={m?.data?.validation_summary}
                          filesChanged={m?.data?.files_changed}
                          linesAdded={m?.data?.lines_added}
                          linesRemoved={m?.data?.lines_removed}
                          requiresConfirmation={m?.requires_confirmation}
                          confirmationType={m?.confirmation_type}
                        />
                      </div>
                    );
                    return;
                  }
                  if (it.type === 'push_summary') {
                    const m = it.meta;
                    nodes.push(
                      <div key={`push-${idx}`} className="mt-2">
                        <PushSummaryCard
                          summary={m?.data?.push_summary}
                          filesChanged={m?.data?.files_changed}
                          linesAdded={m?.data?.lines_added}
                          linesRemoved={m?.data?.lines_removed}
                          commitsToPush={m?.data?.commits_to_push}
                          targetBranch={m?.data?.target_branch}
                          requiresConfirmation={m?.requires_confirmation}
                          confirmationType={m?.confirmation_type}
                        />
                      </div>
                    );
                    return;
                  }
                  if (it.type === 'file_change') {
                    const fc = it.fileChange || {};
                    nodes.push(
                      <div key={`fc-${idx}`} className="mt-2">
                        <FileChangeViewer
                          filePath={fc.filePath}
                          operation={fc.operation}
                          original={fc.original}
                          modified={fc.modified}
                        />
                      </div>
                    );
                    return;
                  }
                  // default text
                  nodes.push(
                    <div key={`text-${idx}`} className="w-fit bg-[#2b2b2b] text-white px-4 py-3 rounded-2xl rounded-bl-none shadow whitespace-pre-wrap wrap-break-word">
                      {it.text}
                    </div>
                  );
                });
                // flush any trailing raw lines
                flush('tail');
                return nodes;
              })()}
            </div>
          ) : (
          !meta?.data?.raw_line && (
            <div className="w-fit bg-[#2b2b2b] text-white px-4 py-3 rounded-2xl rounded-bl-none shadow whitespace-pre-wrap wrap-break-word">
              {message}
            </div>
          ))}
          {/* Render plan summary if present */}
          {meta?.data?.plan_summary && (
            <div className="mt-2 max-w-[70%]">
              <PlanSummaryCard
                summary={meta.data.plan_summary}
                planId={meta.data.plan_id}
                totalSteps={meta.data.total_steps}
                requiresConfirmation={meta?.requires_confirmation}
                confirmationType={meta?.confirmation_type}
              />
            </div>
          )}

          {/* Render validation summary if present */}
          {meta?.data?.validation_summary && (
            <div className="mt-2 max-w-[70%]">
              <ValidationSummaryCard
                summary={meta.data.validation_summary}
                filesChanged={meta.data.files_changed}
                linesAdded={meta.data.lines_added}
                linesRemoved={meta.data.lines_removed}
                requiresConfirmation={meta?.requires_confirmation}
                confirmationType={meta?.confirmation_type}
              />
            </div>
          )}

          {/* Render file change viewer if present in meta (non-aggregated) */}
          {!items?.length && (meta?.data?.original_content != null || meta?.data?.modified_content != null) && (
            <div className="mt-2 max-w-[90%]">
              <FileChangeViewer
                filePath={meta?.data?.file_path}
                operation={meta?.data?.operation}
                original={meta?.data?.original_content ?? null}
                modified={meta?.data?.modified_content ?? null}
              />
            </div>
          )}

          {/* Render terminal output line if raw_line present */}
          {!items?.length && meta?.data?.raw_line && (
            <div className="mt-2">
              <TerminalConsole lines={[meta.data.raw_line]} />
            </div>
          )}

          {/* Render push summary if present */}
          {meta?.data?.push_summary && (
            <div className="mt-2 max-w-[70%]">
              <PushSummaryCard
                summary={meta.data.push_summary}
                filesChanged={meta.data.files_changed}
                linesAdded={meta.data.lines_added}
                linesRemoved={meta.data.lines_removed}
                commitsToPush={meta.data.commits_to_push}
                targetBranch={meta.data.target_branch}
                requiresConfirmation={meta?.requires_confirmation}
                confirmationType={meta?.confirmation_type}
              />
            </div>
          )}
        </div>
      )}

      {isUser && (
        <div className="flex flex-col items-end">
          <span className="text-xs text-gray-400 mb-1 mr-1">User</span>
          <div className="max-w-fit bg-[#ffffff] text-black px-4 py-3 rounded-2xl rounded-br-none shadow whitespace-pre-wrap wrap-break-word">
            {message}
          </div>
        </div>
      )}
    </div>
  );
}
