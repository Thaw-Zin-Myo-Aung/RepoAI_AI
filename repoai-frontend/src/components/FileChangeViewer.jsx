import React, { useMemo } from "react";
import { diffLines } from "diff";

// Simple side-by-side file change viewer using 'diff' (jsdiff) and Tailwind styles.
// Props:
// - filePath: string
// - operation: 'created' | 'modified' | 'deleted' | string
// - original: string | null
// - modified: string | null
// - className: string (optional)
export default function FileChangeViewer({
  filePath,
  operation,
  original,
  modified,
  className = "",
}) {
  const left = original ?? "";
  const right = modified ?? "";

  const leftLines = useMemo(() => left.split("\n"), [left]);
  const rightLines = useMemo(() => right.split("\n"), [right]);

  const chunks = useMemo(() => {
    // Compute a unified diff between left and right
    return diffLines(left, right, { newlineIsToken: true });
  }, [left, right]);

  // Build line-by-line aligned arrays for side-by-side display
  const aligned = useMemo(() => {
    const rows = [];
    let lNum = 1;
    let rNum = 1;

    chunks.forEach((part) => {
      const lines = part.value.split("\n");
      // Drop the trailing empty element from split if part.value ends with \n
      const effectiveLines =
        lines.length > 0 && lines[lines.length - 1] === ""
          ? lines.slice(0, -1)
          : lines;

      if (part.added) {
        // only on right
        effectiveLines.forEach((text) => {
          rows.push({
            lNum: "",
            lText: "",
            lType: "context",
            rNum: rNum++,
            rText: text,
            rType: "added",
          });
        });
      } else if (part.removed) {
        // only on left
        effectiveLines.forEach((text) => {
          rows.push({
            lNum: lNum++,
            lText: text,
            lType: "removed",
            rNum: "",
            rText: "",
            rType: "context",
          });
        });
      } else {
        // unchanged on both
        effectiveLines.forEach((text) => {
          rows.push({
            lNum: lNum++,
            lText: text,
            lType: "context",
            rNum: rNum++,
            rText: text,
            rType: "context",
          });
        });
      }
    });
    return rows;
  }, [chunks]);

  const opBadge = (op) => {
    const base = "px-2 py-0.5 rounded text-xs font-semibold";
    switch ((op || "").toLowerCase()) {
      case "created":
        return <span className={`${base} bg-green-600/20 text-green-300`}>CREATED</span>;
      case "deleted":
        return <span className={`${base} bg-red-600/20 text-red-300`}>DELETED</span>;
      case "modified":
      default:
        return <span className={`${base} bg-blue-600/20 text-blue-300`}>MODIFIED</span>;
    }
  };

  const showOriginal = (operation || '').toLowerCase() !== 'created' && original != null;

  return (
    <div className={`w-full bg-[#111] border border-[#2a2a2a] rounded-lg overflow-hidden ${className}`}>
      <div className="flex items-center justify-between px-3 py-2 border-b border-[#2a2a2a] bg-[#161616]">
        <div className="text-sm text-gray-300 truncate">{filePath || "(file)"}</div>
        <div>{opBadge(operation)}</div>
      </div>
      <div className={`grid ${showOriginal ? 'grid-cols-2' : 'grid-cols-1'} text-sm`}>
        {showOriginal && (
          <div className="border-r border-[#2a2a2a]">
            <Header title="Original" />
            <div className="font-mono text-xs leading-5">
              {aligned.map((row, i) => (
                <CodeRow key={`l-${i}`} num={row.lNum} text={row.lText} type={row.lType} />
              ))}
            </div>
          </div>
        )}
        <div>
          <Header title={showOriginal ? "Modified" : "New File"} />
          <div className="font-mono text-xs leading-5">
            {aligned.map((row, i) => (
              <CodeRow key={`r-${i}`} num={row.rNum} text={row.rText} type={row.rType} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function Header({ title }) {
  return (
    <div className="sticky top-0 z-10 bg-[#151515] border-b border-[#2a2a2a] px-3 py-1.5 text-gray-400 text-xs">
      {title}
    </div>
  );
}

function CodeRow({ num, text, type }) {
  // Intensify color accents for added/removed lines
  const bg =
    type === "added"
      ? "bg-green-800/50 border-l-2 border-green-400"
      : type === "removed"
      ? "bg-red-800/40 border-l-2 border-red-400"
      : "bg-[#111]";
  const numCls = "w-12 shrink-0 text-right pr-3 text-gray-500 select-none";
  return (
  <div className={`flex px-3 py-0.5 ${bg}`}>
      <div className={numCls}>{num}</div>
  <pre className="whitespace-pre-wrap wrap-break-word text-gray-200">
        {text === "" ? "\u00A0" : text}
      </pre>
    </div>
  );
}
