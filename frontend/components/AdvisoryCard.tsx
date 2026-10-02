"use client";

import React from "react";
import { AlertOctagon, AlertTriangle, Info, CheckCircle2, Shield, BookmarkCheck } from "lucide-react";
import { ChatResponse } from "../lib/types";
import { WeatherMetrics } from "./WeatherMetrics";
import { EngineeringTrace } from "./EngineeringTrace";

interface AdvisoryCardProps {
  response: ChatResponse;
}

export const AdvisoryCard: React.FC<AdvisoryCardProps> = ({ response }) => {
  const policy = response.policy;
  const severity = policy?.severity;

  // Visual styles according to severity
  const severityStyles = {
    CRITICAL: {
      badgeBg: "bg-rose-950/60 text-rose-300 border-rose-700/60",
      cardBorder: "border-rose-900/50 shadow-rose-950/20",
      icon: <AlertOctagon className="w-4 h-4 text-rose-400" />,
      label: "CRITICAL SAFETY RISK",
    },
    HIGH: {
      badgeBg: "bg-amber-950/60 text-amber-300 border-amber-700/60",
      cardBorder: "border-amber-900/50 shadow-amber-950/20",
      icon: <AlertTriangle className="w-4 h-4 text-amber-400" />,
      label: "HIGH ADVISORY",
    },
    MODERATE: {
      badgeBg: "bg-yellow-950/60 text-yellow-300 border-yellow-700/60",
      cardBorder: "border-yellow-900/50 shadow-yellow-950/20",
      icon: <Info className="w-4 h-4 text-yellow-400" />,
      label: "MODERATE CAUTION",
    },
    LOW: {
      badgeBg: "bg-emerald-950/60 text-emerald-300 border-emerald-700/60",
      cardBorder: "border-emerald-900/50 shadow-emerald-950/20",
      icon: <CheckCircle2 className="w-4 h-4 text-emerald-400" />,
      label: "FAVORABLE WINDOW",
    },
    DEFAULT: {
      badgeBg: "bg-slate-800/80 text-slate-300 border-slate-700",
      cardBorder: "border-slate-800 shadow-slate-950/40",
      icon: <Shield className="w-4 h-4 text-cyan-400" />,
      label: "STANDARD ADVISORY",
    },
  };

  const style = severity ? severityStyles[severity] : severityStyles.DEFAULT;

  return (
    <div
      className={`w-full rounded-2xl bg-slate-900/80 backdrop-blur-md border ${style.cardBorder} p-4 sm:p-5 shadow-xl transition-all`}
    >
      {/* Top Bar: Severity Badge and Location */}
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
        <div className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold border uppercase tracking-wider ${style.badgeBg}`}>
          {style.icon}
          <span>{style.label}</span>
        </div>

        {response.location && (
          <div className="text-xs text-slate-400 font-medium flex items-center gap-1">
            <span>Location:</span>
            <span className="text-slate-200 font-semibold">
              {response.location.name}
              {response.location.country ? `, ${response.location.country}` : ""}
            </span>
          </div>
        )}
      </div>

      {/* Advisory Answer Text */}
      <div className="text-slate-100 text-sm sm:text-base leading-relaxed font-normal">
        {response.answer}
      </div>

      {/* Policy Guidance & Citation Box */}
      {policy && policy.sop_id && (
        <div className="mt-4 p-3.5 rounded-xl bg-slate-950/70 border border-slate-800 text-xs space-y-2">
          <div className="flex items-center justify-between">
            <span className="font-semibold text-cyan-300 flex items-center gap-1.5">
              <BookmarkCheck className="w-4 h-4 text-cyan-400" />
              SOP Reference: {policy.sop_id} — {policy.title}
            </span>
            <span className="text-slate-400 text-[11px]">
              Priority: <span className="font-mono text-slate-200">{policy.priority}</span>
            </span>
          </div>

          {policy.guidance && policy.guidance.length > 0 && (
            <div className="text-slate-300 pl-4 border-l-2 border-cyan-500/50 space-y-1">
              {policy.guidance.map((guide, idx) => (
                <p key={idx}>{guide}</p>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Live Weather Metrics */}
      {response.weather && <WeatherMetrics weather={response.weather} />}

      {/* Collapsible Engineering Execution Trace */}
      {response.trace && response.trace.length > 0 && (
        <EngineeringTrace trace={response.trace} policy={response.policy} />
      )}
    </div>
  );
};
