"use client";

import React from "react";
import { Compass, ShieldCheck, Globe, MapPin } from "lucide-react";
import { VoiceLanguage, LANGUAGE_LABELS, CurrentLocation } from "../lib/types";

interface HeaderProps {
  language: VoiceLanguage;
  onLanguageChange: (lang: VoiceLanguage) => void;
  currentLocation: CurrentLocation | null;
  locationStatus: string;
  onRequestLocation: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  language,
  onLanguageChange,
  currentLocation,
  locationStatus,
  onRequestLocation,
}) => {
  return (
    <header className="w-full border-b border-slate-800 bg-slate-950/80 backdrop-blur-md sticky top-0 z-40">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
        {/* Brand identity */}
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-cyan-500 to-blue-600 flex items-center justify-center shadow-lg shadow-cyan-500/20 text-white font-bold">
            <Compass className="w-5 h-5 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-extrabold tracking-tight text-xl text-white">
                WEATHER<span className="text-cyan-400">WISE</span>
              </span>
              <span className="hidden sm:inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full bg-cyan-950/60 text-cyan-300 border border-cyan-800/40">
                <ShieldCheck className="w-3 h-3 text-cyan-400" /> Grounded SOP
              </span>
            </div>
            <p className="text-[11px] text-slate-400 hidden sm:block">
              Outdoor Activity Weather-Advisory Platform
            </p>
          </div>
        </div>

        {/* Right controls: Location & Language */}
        <div className="flex items-center gap-2 sm:gap-3">
          {/* Location button */}
          <button
            onClick={onRequestLocation}
            title={currentLocation ? "Location active" : "Enable current location"}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
              currentLocation
                ? "bg-emerald-950/40 text-emerald-300 border-emerald-700/50 hover:bg-emerald-900/40"
                : "bg-slate-900 text-slate-300 border-slate-700 hover:bg-slate-800"
            }`}
          >
            <MapPin className={`w-3.5 h-3.5 ${currentLocation ? "text-emerald-400" : "text-slate-400"}`} />
            <span className="hidden md:inline">
              {currentLocation ? "Location Active" : "Detect Location"}
            </span>
          </button>

          {/* Language selector */}
          <div className="relative flex items-center">
            <Globe className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 pointer-events-none" />
            <select
              value={language}
              onChange={(e) => onLanguageChange(e.target.value as VoiceLanguage)}
              aria-label="Select interaction language"
              className="pl-8 pr-3 py-1.5 rounded-lg text-xs font-medium bg-slate-900 text-slate-200 border border-slate-700 hover:border-slate-600 focus:outline-none focus:ring-1 focus:ring-cyan-500 transition-colors cursor-pointer appearance-none"
            >
              {(Object.keys(LANGUAGE_LABELS) as VoiceLanguage[]).map((code) => {
                const item = LANGUAGE_LABELS[code];
                return (
                  <option key={code} value={code} className="bg-slate-900 text-slate-200">
                    {item.flag} {item.native} ({item.name})
                  </option>
                );
              })}
            </select>
          </div>
        </div>
      </div>
    </header>
  );
};
