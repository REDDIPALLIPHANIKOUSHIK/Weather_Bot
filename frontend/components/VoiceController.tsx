"use client";

import React from "react";
import { Mic, MicOff, Radio, Volume2, Globe, Sparkles } from "lucide-react";
import { VoiceStatus, VoiceLanguage, LANGUAGE_LABELS } from "../lib/types";

interface VoiceControllerProps {
  status: VoiceStatus;
  mode: "gemini_live" | "fallback";
  language: VoiceLanguage;
  statusMessage?: string;
  userTranscript?: string;
  assistantTranscript?: string;
  onStart: () => void;
  onStop: () => void;
  onLanguageChange: (lang: VoiceLanguage) => void;
}

export const VoiceController: React.FC<VoiceControllerProps> = ({
  status,
  mode,
  language,
  statusMessage,
  userTranscript,
  assistantTranscript,
  onStart,
  onStop,
  onLanguageChange,
}) => {
  const isVoiceActive = status !== "idle" && status !== "error";

  return (
    <div className="w-full rounded-2xl bg-gradient-to-b from-slate-900/90 to-slate-950/90 border border-slate-800 p-4 sm:p-5 shadow-2xl backdrop-blur-md">
      {/* Top Header: Voice Status & Mode */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <div className="flex items-center gap-2">
          <div
            className={`w-2.5 h-2.5 rounded-full ${
              status === "listening"
                ? "bg-cyan-400 animate-ping"
                : status === "speaking"
                ? "bg-emerald-400 animate-bounce"
                : status === "connecting"
                ? "bg-amber-400 animate-pulse"
                : status === "error"
                ? "bg-rose-500"
                : "bg-slate-600"
            }`}
          />
          <span className="text-xs font-semibold text-slate-200 uppercase tracking-wide">
            Voice Status: {status}
          </span>
          <span className="text-[11px] px-2 py-0.5 rounded-full font-medium bg-slate-800 text-slate-400 border border-slate-700/60">
            {mode === "gemini_live" ? "Gemini Live Voice" : "Browser Web Speech Fallback"}
          </span>
        </div>

        {/* Language selector in voice box */}
        <div className="flex items-center gap-1.5 text-xs text-slate-400">
          <Globe className="w-3.5 h-3.5 text-slate-400" />
          <select
            value={language}
            onChange={(e) => onLanguageChange(e.target.value as VoiceLanguage)}
            disabled={isVoiceActive}
            aria-label="Voice conversation language"
            className="bg-slate-950 text-slate-200 border border-slate-800 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-cyan-500 disabled:opacity-50 cursor-pointer"
          >
            {(Object.keys(LANGUAGE_LABELS) as VoiceLanguage[]).map((code) => {
              const item = LANGUAGE_LABELS[code];
              return (
                <option key={code} value={code}>
                  {item.flag} {item.native} ({item.name})
                </option>
              );
            })}
          </select>
        </div>
      </div>

      {/* Main Interactive Controls & Visualizer */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4 p-4 rounded-xl bg-slate-950/60 border border-slate-900">
        <div className="flex items-center gap-4">
          {/* Start / Stop Button with Pulse */}
          <button
            onClick={isVoiceActive ? onStop : onStart}
            aria-label={isVoiceActive ? "Stop voice interaction" : "Start voice interaction"}
            className={`relative flex items-center justify-center w-14 h-14 rounded-2xl font-bold transition-all shadow-lg cursor-pointer ${
              isVoiceActive
                ? "bg-rose-600 hover:bg-rose-500 text-white shadow-rose-900/30 scale-105"
                : "bg-cyan-500 hover:bg-cyan-400 text-slate-950 shadow-cyan-500/20"
            }`}
          >
            {isVoiceActive ? <MicOff className="w-6 h-6" /> : <Mic className="w-6 h-6" />}
            {status === "listening" && (
              <span className="absolute -inset-1 rounded-2xl border-2 border-cyan-400 animate-ping opacity-60 pointer-events-none" />
            )}
          </button>

          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-sm text-slate-100">
                {isVoiceActive ? "Voice Conversation Active" : "Start Real-Time Voice"}
              </span>
              {status === "speaking" && (
                <span className="inline-flex items-center gap-1 text-[11px] text-emerald-400 font-medium">
                  <Volume2 className="w-3.5 h-3.5 animate-pulse" /> Speaking
                </span>
              )}
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              {statusMessage ||
                (isVoiceActive
                  ? "Speak naturally. Weatherwise will query live Open-Meteo & written SOPs."
                  : "Click Start Voice to talk in real-time. Speaks and understands all 8 languages.")}
            </p>
          </div>
        </div>

        {/* Stop Voice button for clear accessibility */}
        {isVoiceActive && (
          <button
            onClick={onStop}
            className="w-full sm:w-auto px-4 py-2 rounded-xl bg-rose-950/80 hover:bg-rose-900 text-rose-200 border border-rose-800 text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors cursor-pointer"
          >
            <MicOff className="w-3.5 h-3.5" /> Stop Voice
          </button>
        )}
      </div>

      {/* Live Voice Transcripts */}
      {(userTranscript || assistantTranscript) && (
        <div className="mt-3 p-3.5 rounded-xl bg-slate-950/80 border border-slate-800/80 text-xs space-y-2">
          {userTranscript && (
            <div className="flex items-start gap-2 text-slate-300">
              <Radio className="w-3.5 h-3.5 text-cyan-400 mt-0.5 shrink-0" />
              <div>
                <span className="font-semibold text-cyan-300">You: </span>
                <span>{userTranscript}</span>
              </div>
            </div>
          )}
          {assistantTranscript && (
            <div className="flex items-start gap-2 text-slate-300 pt-2 border-t border-slate-900">
              <Sparkles className="w-3.5 h-3.5 text-emerald-400 mt-0.5 shrink-0" />
              <div>
                <span className="font-semibold text-emerald-300">Weatherwise Voice: </span>
                <span>{assistantTranscript}</span>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
