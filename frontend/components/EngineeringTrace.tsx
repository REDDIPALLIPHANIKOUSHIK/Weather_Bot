"use client";

import React, { useState } from "react";
import { Terminal, ChevronDown, ChevronUp, Cpu, Check, AlertTriangle, X } from "lucide-react";
import { PolicyResult } from "../lib/types";

interface EngineeringTraceProps {
  trace: string[];
  policy?: PolicyResult | null;
}

export const EngineeringTrace: React.FC<EngineeringTraceProps> = ({ trace, policy }) => {
  const [isOpen, setIsOpen] = useState(false);

  if (!trace || trace.length === 0) return null;

  return (
    <div className="mt-3 border border-slate-800/80 rounded-xl overflow-hidden bg-slate-950/60">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-3 py-2 flex items-center justify-between text-xs font-mono text-slate-400 hover:text-slate-200 hover:bg-slate-900/50 transition-colors"
      >
        <span className="flex items-center gap-2">
          <Terminal className="w-3.5 h-3.5 text-cyan-400" />
          <span>Execution Trace ({trace.length} pipeline steps)</span>
        </span>
        {isOpen ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5 text-slate-500" />}
      </button>

      {isOpen && (
        <div className="p-3 bg-slate-950 border-t border-slate-900 text-xs font-mono space-y-2">
          {/* Timeline steps */}
          <div className="space-y-1 pl-2 border-l border-slate-800">
            {trace.map((step, idx) => (
              <div key={idx} className="flex items-start gap-2 text-slate-300">
                <span className="text-cyan-500 text-[10px] select-none mt-0.5">[{idx + 1}]</span>
                <span className="text-[11px] leading-relaxed">{step}</span>
              </div>
            ))}
          </div>

          {/* Policy Decision Trace if present */}
          {policy?.trace && policy.trace.length > 0 && (
            <div className="mt-3 pt-2.5 border-t border-slate-900">
              <div className="flex items-center gap-1.5 text-cyan-400 text-[11px] font-semibold mb-1.5">
                <Cpu className="w-3 h-3" />
                <span>Deterministic SOP Candidate Evaluations:</span>
              </div>
              <div className="space-y-1.5">
                {policy.trace.map((item, i) => {
                  const isMatch = Boolean(item.matched);
                  return (
                    <div
                      key={i}
                      className={`p-2 rounded border text-[11px] ${
                        isMatch
                          ? "bg-emerald-950/30 border-emerald-800/40 text-emerald-200"
                          : "bg-slate-900/40 border-slate-800/60 text-slate-400"
                      }`}
                    >
                      <div className="flex items-center justify-between font-semibold">
                        <span className="flex items-center gap-1">
                          {isMatch ? (
                            <Check className="w-3 h-3 text-emerald-400" />
                          ) : (
                            <X className="w-3 h-3 text-slate-500" />
                          )}
                          {item.sop_id ? String(item.sop_id) : "Rule"}: {item.title ? String(item.title) : "Evaluation"}
                        </span>
                        {item.severity ? (
                          <span className="text-[10px] uppercase font-bold px-1.5 py-0.5 rounded bg-slate-800/80">
                            {String(item.severity)} (Priority {String(item.priority)})
                          </span>
                        ) : null}
                      </div>
                      {item.detail ? (
                        <div className="mt-1 text-[10px] font-mono text-slate-400 pl-4">
                          Condition: {String(item.detail)}
                        </div>
                      ) : null}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
