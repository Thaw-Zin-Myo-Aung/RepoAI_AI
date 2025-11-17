import React, { useEffect, useMemo, useRef } from "react";
import { AnsiUp } from "ansi_up";

function normalizeAnsi(line = "") {
  return line.replace(/\[\[(\d+(?:;\d+)*)m/g, (_m, codes) => `\u001b[${codes}m`)
             .replace(/\[(m)/g, (_m, tail) => `\u001b[${tail}`);
}

export default function TerminalConsole({
  lines = [],
  // Constrain width so it doesn't stretch excessively on large screens
  widthClass = "w-full max-w-screen-lg mx-auto",
  // Provide a consistent vertical footprint; responsive tweak for larger screens
  heightClass = "h-[340px] md:h-[420px]",
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
      className={`${widthClass} ${heightClass} shrink-0 bg-[#0b0b0b] border border-[#222] rounded-lg p-3 overflow-x-auto overflow-y-auto shadow-inner`}
    >
      <pre
        className="m-0 text-xs leading-5 text-gray-200 font-mono whitespace-pre"
        dangerouslySetInnerHTML={{ __html: html }}
      />
    </div>
  );
}
