import React, { useMemo } from "react";
import { AnsiUp } from "ansi_up";

// Normalize certain escaped sequences that may arrive without the ESC character.
// Example seen: "[[1;34mINFO[m] ..." -> "\u001b[1;34mINFO\u001b[m ..."
function normalizeAnsi(line = "") {
  // Replace patterns like [[1;34m with ESC[1;34m
  return line.replace(/\[\[(\d+(?:;\d+)*)m/g, (_m, codes) => `\u001b[${codes}m`);
}

export default function TerminalOutputLine({ line = "" }) {
  const normalized = useMemo(() => normalizeAnsi(line), [line]);
  const html = useMemo(() => {
    const au = new AnsiUp();
    au.use_classes = false; // inline styles
    try {
      return au.ansi_to_html(normalized || "");
    } catch (_) {
      return (normalized || "");
    }
  }, [normalized]);
  return (
    <div className="w-[80%] bg-[#0b0b0b] rounded-lg p-2 overflow-x-auto">
      <pre
        className="m-0 text-xs leading-5 text-gray-200 font-mono whitespace-pre"
        dangerouslySetInnerHTML={{ __html: html }}
      />
    </div>
  );
}
