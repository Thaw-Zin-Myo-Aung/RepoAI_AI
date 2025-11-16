import React, { useEffect, useMemo, useRef } from "react";
import { AnsiUp } from "ansi_up";

function normalizeAnsi(line = "") {
  return line.replace(/\[\[(\d+(?:;\d+)*)m/g, (_m, codes) => `\u001b[${codes}m`)
             .replace(/\[(m)/g, (_m, tail) => `\u001b[${tail}`);
}

export default function TerminalConsole({
  lines = [],
  widthClass = "w-full max-w-full",
  heightClass = "h-64",
}) {
  const html = useMemo(() => {
    const au = new AnsiUp();
    au.use_classes = false;
    try {
      const text = (lines || []).map((l) => normalizeAnsi(l ?? "")).join("");
      return au.ansi_to_html(text);
    } catch (_) {
      return (lines || []).join("");
    }
  }, [lines]);

  const containerRef = useRef(null);

  // Auto-scroll to bottom whenever content updates
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [html]);

  return (
    <div
      ref={containerRef}
      className={`${widthClass} ${heightClass} bg-[#0b0b0b] border border-[#222] rounded-lg p-3 overflow-x-auto overflow-y-auto`}
    >
      <pre
        className="m-0 text-xs leading-5 text-gray-200 font-mono whitespace-pre"
        dangerouslySetInnerHTML={{ __html: html }}
      />
    </div>
  );
}
