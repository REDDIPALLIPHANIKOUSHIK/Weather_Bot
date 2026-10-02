"use client";

import React, { useEffect, useState } from "react";
import { MapPin, Thermometer, Wind, CloudRain, Sun, Compass } from "lucide-react";
import { CurrentLocation, VoiceLanguage, WeatherFacts } from "../lib/types";

interface CurrentLocationWidgetProps {
  currentLocation: CurrentLocation | null;
  language?: VoiceLanguage;
  onActivitySelect: (query: string) => void;
}

export const CurrentLocationWidget: React.FC<CurrentLocationWidgetProps> = ({
  currentLocation,
  language = "en-IN",
  onActivitySelect,
}) => {
  const [weather, setWeather] = useState<WeatherFacts | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!currentLocation) {
      setWeather(null);
      return;
    }

    let isMounted = true;
    setLoading(true);

    // Fetch live weather facts directly from Open-Meteo for the current GPS coordinates
    const fetchLiveCoordsWeather = async () => {
      try {
        const url = `https://api.open-meteo.com/v1/forecast?latitude=${currentLocation.latitude}&longitude=${currentLocation.longitude}&current=temperature_2m,wind_speed_10m,precipitation,weather_code&hourly=temperature_2m,precipitation_probability,uv_index&forecast_days=1&timezone=auto`;
        const res = await fetch(url);
        if (res.ok && isMounted) {
          const data = await res.json();
          const curr = data.current || {};
          const hourly = data.hourly || {};
          const precipProb = (hourly.precipitation_probability || [])[0] ?? 0;
          const uv = (hourly.uv_index || [])[0] ?? 0;

          setWeather({
            temperature_2m: curr.temperature_2m,
            wind_speed_10m: curr.wind_speed_10m,
            precipitation: curr.precipitation,
            precipitation_probability: precipProb,
            uv_index: uv,
            weather_code: curr.weather_code,
            observed_at: curr.time || new Date().toISOString(),
            timezone: data.timezone || "Local",
            source: "Open-Meteo",
          });
        }
      } catch (err) {
        console.warn("Could not prefetch coordinate weather:", err);
      } finally {
        if (isMounted) setLoading(false);
      }
    };

    fetchLiveCoordsWeather();
    return () => {
      isMounted = false;
    };
  }, [currentLocation]);

  if (!currentLocation) return null;

  return (
    <div className="w-full rounded-2xl bg-gradient-to-r from-slate-900/90 via-cyan-950/20 to-slate-900/90 border border-cyan-800/40 p-4 shadow-xl backdrop-blur-md">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        {/* Location Info */}
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-xl bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 flex items-center justify-center shrink-0">
            <MapPin className="w-5 h-5 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold text-slate-100">
                {currentLocation.cityName || "Current Location"}
              </span>
              <span className="text-[10px] px-2 py-0.2 rounded-full bg-emerald-950/80 text-emerald-400 border border-emerald-800/60 font-semibold">
                Live GPS
              </span>
            </div>
            <p className="text-[11px] text-slate-400">
              {currentLocation.latitude.toFixed(4)}°N, {currentLocation.longitude.toFixed(4)}°E
              {currentLocation.accuracy ? ` • ±${Math.round(currentLocation.accuracy)}m` : ""}
            </p>
          </div>
        </div>

        {/* Live Weather Snapshot */}
        {weather && (
          <div className="flex items-center gap-3 bg-slate-950/60 border border-slate-800 px-3 py-1.5 rounded-xl text-xs">
            <div className="flex items-center gap-1 text-slate-100 font-bold">
              <Thermometer className="w-3.5 h-3.5 text-orange-400" />
              <span>{weather.temperature_2m}°C</span>
            </div>
            <div className="flex items-center gap-1 text-slate-300 font-medium">
              <Wind className="w-3.5 h-3.5 text-cyan-400" />
              <span>{weather.wind_speed_10m} km/h</span>
            </div>
            <div className="flex items-center gap-1 text-slate-300 font-medium">
              <CloudRain className="w-3.5 h-3.5 text-blue-400" />
              <span>{weather.precipitation_probability}%</span>
            </div>
            {weather.uv_index !== null && weather.uv_index !== undefined && (
              <div className="flex items-center gap-1 text-slate-300 font-medium">
                <Sun className="w-3.5 h-3.5 text-amber-400" />
                <span>UV {weather.uv_index}</span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Quick Location Safety Actions */}
      <div className="mt-3 pt-3 border-t border-slate-800/60 flex flex-wrap items-center gap-2 text-xs">
        <span className="text-[11px] text-cyan-300 font-medium flex items-center gap-1">
          <Compass className="w-3 h-3 text-cyan-400" />
          {language === "te-IN"
            ? "ఇక్కడి భద్రతను తనిఖీ చేయండి:"
            : language === "hi-IN"
            ? "यहाँ सुरक्षा की जांच करें:"
            : language === "ta-IN"
            ? "இங்கே பாதுகாப்பை சரிபார்க்கவும்:"
            : language === "kn-IN"
            ? "ಇಲ್ಲಿ ಸುರಕ್ಷತೆಯನ್ನು ಪರಿಶೀಲಿಸಿ:"
            : "Check safety here:"}
        </span>

        {language === "te-IN" ? (
          <>
            <button
              onClick={() => onActivitySelect("ఇక్కడ ఈరోజు నడవడానికి వీలుగా ఉందా?")}
              className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-[11px] font-medium border border-slate-700 transition-colors cursor-pointer"
            >
              నడక / వాకింగ్
            </button>
            <button
              onClick={() => onActivitySelect("ఇక్కడ ఈరోజు సైకిల్ తొక్కడం సురక్షితమేనా?")}
              className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-[11px] font-medium border border-slate-700 transition-colors cursor-pointer"
            >
              సైక్లింగ్
            </button>
            <button
              onClick={() => onActivitySelect("ఈ సమయంలో ఇక్కడ పిల్లలను పార్కుకు తీసుకెళ్లవచ్చా?")}
              className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-[11px] font-medium border border-slate-700 transition-colors cursor-pointer"
            >
              పిల్లల పార్క్
            </button>
            <button
              onClick={() => onActivitySelect("ఈ సాయంత్రం ఇక్కడ రన్నింగ్ చేయవచ్చా?")}
              className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-[11px] font-medium border border-slate-700 transition-colors cursor-pointer"
            >
              రన్నింగ్
            </button>
            <button
              onClick={() => onActivitySelect("ఈరోజు ఇక్కడ పిక్నిక్ చేసుకోవడానికి మంచి రోజా?")}
              className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-[11px] font-medium border border-slate-700 transition-colors cursor-pointer"
            >
              పిక్నిక్
            </button>
          </>
        ) : language === "hi-IN" ? (
          <>
            <button
              onClick={() => onActivitySelect("क्या आज यहाँ टहलना सुरक्षित है?")}
              className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-[11px] font-medium border border-slate-700 transition-colors cursor-pointer"
            >
              टहलना
            </button>
            <button
              onClick={() => onActivitySelect("क्या आज यहाँ साइकिल चलाना सुरक्षित है?")}
              className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-[11px] font-medium border border-slate-700 transition-colors cursor-pointer"
            >
              साइकिलिंग
            </button>
            <button
              onClick={() => onActivitySelect("क्या मैं अभी यहाँ बच्चे को पार्क ले जा सकता हूँ?")}
              className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-[11px] font-medium border border-slate-700 transition-colors cursor-pointer"
            >
              बच्चों का पार्क
            </button>
            <button
              onClick={() => onActivitySelect("क्या मैं आज शाम यहाँ दौड़ने जा सकता हूँ?")}
              className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-[11px] font-medium border border-slate-700 transition-colors cursor-pointer"
            >
              दौड़ना
            </button>
            <button
              onClick={() => onActivitySelect("क्या आज यहाँ पिकनिक के लिए अच्छा दिन है?")}
              className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-[11px] font-medium border border-slate-700 transition-colors cursor-pointer"
            >
              पिकनिक
            </button>
          </>
        ) : (
          <>
            <button
              onClick={() => onActivitySelect("Can I take my child to the park in my location now?")}
              className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-[11px] font-medium border border-slate-700 transition-colors cursor-pointer"
            >
              Children&apos;s Park Visit
            </button>
            <button
              onClick={() => onActivitySelect("Is it safe to cycle here today?")}
              className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-[11px] font-medium border border-slate-700 transition-colors cursor-pointer"
            >
              Cycling
            </button>
            <button
              onClick={() => onActivitySelect("Is it safe to go for a walk here now?")}
              className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-[11px] font-medium border border-slate-700 transition-colors cursor-pointer"
            >
              Walking
            </button>
            <button
              onClick={() => onActivitySelect("Can I go running here this evening?")}
              className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-[11px] font-medium border border-slate-700 transition-colors cursor-pointer"
            >
              Running
            </button>
            <button
              onClick={() => onActivitySelect("Is it a good time for a picnic here today?")}
              className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-[11px] font-medium border border-slate-700 transition-colors cursor-pointer"
            >
              Picnic
            </button>
          </>
        )}
      </div>
    </div>
  );
};
