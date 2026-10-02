"use client";

import React from "react";
import { Thermometer, Wind, CloudRain, Sun, Clock, Database } from "lucide-react";
import { WeatherFacts } from "../lib/types";

interface WeatherMetricsProps {
  weather: WeatherFacts;
}

export const WeatherMetrics: React.FC<WeatherMetricsProps> = ({ weather }) => {
  return (
    <div className="mt-3 pt-3 border-t border-slate-800/80">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
        {/* Temperature */}
        <div className="p-2.5 rounded-lg bg-slate-900/60 border border-slate-800/70 flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-orange-500/10 text-orange-400 flex items-center justify-center shrink-0">
            <Thermometer className="w-4 h-4" />
          </div>
          <div>
            <div className="text-[11px] text-slate-400">Temperature</div>
            <div className="text-sm font-bold text-slate-100">
              {weather.temperature_2m !== undefined && weather.temperature_2m !== null
                ? `${weather.temperature_2m}°C`
                : "N/A"}
            </div>
          </div>
        </div>

        {/* Wind Speed */}
        <div className="p-2.5 rounded-lg bg-slate-900/60 border border-slate-800/70 flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-cyan-500/10 text-cyan-400 flex items-center justify-center shrink-0">
            <Wind className="w-4 h-4" />
          </div>
          <div>
            <div className="text-[11px] text-slate-400">Wind Speed</div>
            <div className="text-sm font-bold text-slate-100">
              {weather.wind_speed_10m !== undefined && weather.wind_speed_10m !== null
                ? `${weather.wind_speed_10m} km/h`
                : "N/A"}
            </div>
          </div>
        </div>

        {/* Rain Probability / Precip */}
        <div className="p-2.5 rounded-lg bg-slate-900/60 border border-slate-800/70 flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-blue-500/10 text-blue-400 flex items-center justify-center shrink-0">
            <CloudRain className="w-4 h-4" />
          </div>
          <div>
            <div className="text-[11px] text-slate-400">Precipitation</div>
            <div className="text-sm font-bold text-slate-100">
              {weather.precipitation_probability !== undefined && weather.precipitation_probability !== null
                ? `${weather.precipitation_probability}% prob`
                : weather.precipitation !== undefined && weather.precipitation !== null
                ? `${weather.precipitation} mm`
                : "0 mm"}
            </div>
          </div>
        </div>

        {/* UV Index */}
        <div className="p-2.5 rounded-lg bg-slate-900/60 border border-slate-800/70 flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-amber-500/10 text-amber-400 flex items-center justify-center shrink-0">
            <Sun className="w-4 h-4" />
          </div>
          <div>
            <div className="text-[11px] text-slate-400">UV Index</div>
            <div className="text-sm font-bold text-slate-100">
              {weather.uv_index !== undefined && weather.uv_index !== null ? weather.uv_index : "N/A"}
            </div>
          </div>
        </div>
      </div>

      {/* Observation timestamp and Source */}
      <div className="mt-2.5 flex flex-wrap items-center justify-between text-[11px] text-slate-500 gap-2">
        <span className="flex items-center gap-1">
          <Clock className="w-3 h-3 text-slate-500" />
          Observed: {weather.observed_at} ({weather.timezone})
        </span>
        <span className="flex items-center gap-1 font-medium text-slate-400">
          <Database className="w-3 h-3 text-cyan-500" />
          {weather.source}
        </span>
      </div>
    </div>
  );
};
