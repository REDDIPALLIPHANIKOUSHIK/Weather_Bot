"use client";

import React from "react";
import { MapPin, Navigation, AlertCircle, CheckCircle2, RotateCw } from "lucide-react";
import { CurrentLocation } from "../lib/types";

interface LocationBarProps {
  currentLocation: CurrentLocation | null;
  status: "idle" | "detecting" | "granted" | "denied" | "unavailable";
  errorMessage?: string;
  onRequestLocation: () => void;
  onClearLocation: () => void;
}

export const LocationBar: React.FC<LocationBarProps> = ({
  currentLocation,
  status,
  errorMessage,
  onRequestLocation,
  onClearLocation,
}) => {
  return (
    <div className="w-full bg-slate-900/50 border border-slate-800 rounded-xl p-3 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-xs">
      <div className="flex items-center gap-2.5">
        <div
          className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 ${
            status === "granted"
              ? "bg-emerald-950/60 text-emerald-400 border border-emerald-800/50"
              : status === "detecting"
              ? "bg-cyan-950/60 text-cyan-400 border border-cyan-800/50"
              : status === "denied" || status === "unavailable"
              ? "bg-rose-950/60 text-rose-400 border border-rose-800/50"
              : "bg-slate-800 text-slate-400"
          }`}
        >
          {status === "detecting" ? (
            <RotateCw className="w-3.5 h-3.5 animate-spin" />
          ) : status === "granted" ? (
            <CheckCircle2 className="w-3.5 h-3.5" />
          ) : status === "denied" || status === "unavailable" ? (
            <AlertCircle className="w-3.5 h-3.5" />
          ) : (
            <MapPin className="w-3.5 h-3.5" />
          )}
        </div>

        <div>
          <span className="font-semibold text-slate-200">
            {status === "detecting"
              ? "Detecting your location..."
              : status === "granted"
              ? "Using your current live location"
              : status === "denied"
              ? "Location permission denied"
              : status === "unavailable"
              ? "Location unavailable"
              : "Live browser location is ready to connect"}
          </span>
          <p className="text-slate-400 text-[11px] mt-0.5">
            {status === "granted" && currentLocation?.accuracy
              ? `GPS accuracy: ±${Math.round(currentLocation.accuracy)}m • Active for questions about "here"`
              : status === "denied"
              ? "You can type an explicit city name in your question, or retry permission in your browser."
              : status === "unavailable"
              ? errorMessage || "Unable to acquire GPS fix. Please specify a city manually."
              : "Enabling location lets you ask about 'here' or 'where I am' with real GPS coordinates."}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2 self-end sm:self-center shrink-0">
        {status === "granted" ? (
          <button
            onClick={onClearLocation}
            className="px-2.5 py-1 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded border border-slate-700/60 transition-colors"
          >
            Clear GPS
          </button>
        ) : (
          <button
            onClick={onRequestLocation}
            disabled={status === "detecting"}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-white font-medium shadow-sm transition-colors cursor-pointer"
          >
            <Navigation className="w-3 h-3" />
            {status === "denied" || status === "unavailable" ? "Retry GPS" : "Use My Location"}
          </button>
        )}
      </div>
    </div>
  );
};
