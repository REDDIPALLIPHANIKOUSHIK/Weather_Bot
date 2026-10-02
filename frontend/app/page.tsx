"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { Send, Sparkles, MessageSquare, Loader2, Bot, AlertCircle } from "lucide-react";
import { Header } from "../components/Header";
import { LocationBar } from "../components/LocationBar";
import { VoiceController } from "../components/VoiceController";
import { AdvisoryCard } from "../components/AdvisoryCard";
import { Suggestions } from "../components/Suggestions";
import { CurrentLocationWidget } from "../components/CurrentLocationWidget";
import {
  ChatMessage,
  ChatResponse,
  CurrentLocation,
  VoiceLanguage,
  VoiceStatus,
} from "../lib/types";
import { WeatherwiseVoiceEngine } from "../lib/voice";
import { reverseGeocodeCoordinates, detectCurrentLocation } from "../lib/reverse-geo";

export default function Home() {
  // Session ID for contextual follow-ups
  const [sessionId] = useState(() => `session_${Math.random().toString(36).substring(2, 11)}`);

  // Language state
  const [language, setLanguage] = useState<VoiceLanguage>("en-IN");

  // Location state
  const [currentLocation, setCurrentLocation] = useState<CurrentLocation | null>(null);
  const [locationStatus, setLocationStatus] = useState<
    "idle" | "detecting" | "granted" | "denied" | "unavailable"
  >("idle");
  const [locationError, setLocationError] = useState<string>("");

  // Chat conversation state
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Voice engine state
  const [voiceStatus, setVoiceStatus] = useState<VoiceStatus>("idle");
  const [voiceMode, setVoiceMode] = useState<"gemini_live" | "fallback">("gemini_live");
  const [voiceStatusMsg, setVoiceStatusMsg] = useState("");
  const [userVoiceTranscript, setUserVoiceTranscript] = useState("");
  const [assistantVoiceTranscript, setAssistantVoiceTranscript] = useState("");

  const voiceEngineRef = useRef<WeatherwiseVoiceEngine | null>(null);
  const chatScrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll chat to bottom
  useEffect(() => {
    chatScrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  // Automatically detect location on load (network/IP + browser GPS)
  useEffect(() => {
    let isMounted = true;

    async function autoInitLocation() {
      // 1. First fetch network/IP location immediately so site shows weather right away
      try {
        const fastLoc = await detectCurrentLocation();
        if (isMounted && fastLoc) {
          setCurrentLocation(fastLoc);
          setLocationStatus("granted");
        }
      } catch (err) {
        console.warn("Initial network location error:", err);
      }

      // 2. Concurrently request high-precision GPS if supported
      if (typeof navigator !== "undefined" && navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
          async (pos) => {
            if (!isMounted) return;
            const lat = pos.coords.latitude;
            const lon = pos.coords.longitude;
            const gpsLoc: CurrentLocation = {
              latitude: lat,
              longitude: lon,
              accuracy: pos.coords.accuracy,
              timestamp: new Date(pos.timestamp).toISOString(),
              cityName: null,
              city_name: null,
            };
            setCurrentLocation(gpsLoc);
            setLocationStatus("granted");

            try {
              const name = await reverseGeocodeCoordinates(lat, lon);
              if (isMounted) {
                setCurrentLocation((prev) =>
                  prev ? { ...prev, cityName: name, city_name: name } : prev
                );
              }
            } catch (err) {
              console.warn("Reverse geocode failed:", err);
            }
          },
          (err) => {
            console.info("Browser GPS response:", err.message);
          },
          { enableHighAccuracy: true, timeout: 8000, maximumAge: 60000 }
        );
      }
    }

    autoInitLocation();
    return () => {
      isMounted = false;
    };
  }, []);

  // Request browser geolocation on user click
  const handleRequestLocation = useCallback(() => {
    if (!navigator.geolocation) {
      setLocationStatus("unavailable");
      setLocationError("Geolocation is not supported by your browser.");
      return;
    }

    setLocationStatus("detecting");
    setLocationError("");

    navigator.geolocation.getCurrentPosition(
      async (position) => {
        const lat = position.coords.latitude;
        const lon = position.coords.longitude;
        const initialCoords: CurrentLocation = {
          latitude: lat,
          longitude: lon,
          accuracy: position.coords.accuracy,
          timestamp: new Date(position.timestamp).toISOString(),
          cityName: null,
          city_name: null,
        };
        setCurrentLocation(initialCoords);
        setLocationStatus("granted");

        // Reverse geocode coordinates to get friendly city/place name
        try {
          const resolvedName = await reverseGeocodeCoordinates(lat, lon);
          setCurrentLocation((prev) =>
            prev ? { ...prev, cityName: resolvedName, city_name: resolvedName } : prev
          );
        } catch (e) {
          console.warn("Could not reverse-geocode:", e);
        }
      },
      (error) => {
        if (error.code === error.PERMISSION_DENIED) {
          setLocationStatus("denied");
          setLocationError("Location permission denied. Please allow access in browser or specify a city.");
        } else if (error.code === error.TIMEOUT) {
          setLocationStatus("unavailable");
          setLocationError("Location request timed out. Please try again.");
        } else {
          setLocationStatus("unavailable");
          setLocationError("Location information is unavailable.");
        }
      },
      {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 60000,
      }
    );
  }, []);

  const handleClearLocation = useCallback(() => {
    setCurrentLocation(null);
    setLocationStatus("idle");
    setLocationError("");
  }, []);

  // Send typed query to Weatherwise backend
  const handleSendMessage = async (textToSend?: string) => {
    const query = (textToSend || inputValue).trim();
    if (!query || isLoading) return;

    setInputValue("");
    setErrorMessage(null);

    const userMessage: ChatMessage = {
      id: `user_${Date.now()}`,
      role: "user",
      content: query,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          message: query,
          current_location: currentLocation,
          language: language,
        }),
      });

      if (!res.ok) {
        throw new Error("Unable to reach the weather advisory service. Please try again.");
      }

      const data: ChatResponse = await res.json();

      const assistantMessage: ChatMessage = {
        id: `asst_${Date.now()}`,
        role: "assistant",
        content: data.answer,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        data: data,
      };

      setMessages((prev) => [...prev, assistantMessage]);

      // If user query required location and it was missing, trigger prompt
      if (data.status === "needs_location" && locationStatus === "idle") {
        handleRequestLocation();
      }
    } catch (err) {
      setErrorMessage(
        err instanceof Error ? err.message : "An unexpected error occurred. Please try again."
      );
    } finally {
      setIsLoading(false);
    }
  };

  // Initialize and manage Voice Engine
  const startVoice = useCallback(async () => {
    if (voiceEngineRef.current) {
      voiceEngineRef.current.stop();
    }

    const engine = new WeatherwiseVoiceEngine("", sessionId, language, {
      onStatusChange: (status, mode, msg) => {
        setVoiceStatus(status);
        setVoiceMode(mode);
        if (msg) setVoiceStatusMsg(msg);
      },
      onUserTranscript: (text) => {
        setUserVoiceTranscript(text);
      },
      onAssistantTranscript: (text) => {
        setAssistantVoiceTranscript(text);
      },
      onAdvisoryResult: (data, prompt) => {
        const asstData = data as ChatResponse;
        setMessages((prev) => [
          ...prev,
          {
            id: `voice_user_${Date.now()}`,
            role: "user",
            content: prompt,
            timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
          },
          {
            id: `voice_asst_${Date.now()}`,
            role: "assistant",
            content: asstData.answer,
            timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
            data: asstData,
          },
        ]);
      },
      getCurrentLocation: () => currentLocation,
    });

    voiceEngineRef.current = engine;
    await engine.start();
  }, [sessionId, language, currentLocation]);

  const stopVoice = useCallback(() => {
    if (voiceEngineRef.current) {
      voiceEngineRef.current.stop();
      voiceEngineRef.current = null;
    }
    setVoiceStatus("idle");
    setVoiceStatusMsg("");
  }, []);

  const handleLanguageChange = (newLang: VoiceLanguage) => {
    setLanguage(newLang);
    if (voiceEngineRef.current) {
      voiceEngineRef.current.setLanguage(newLang);
    }
  };

  // Teardown voice on unmount
  useEffect(() => {
    return () => {
      if (voiceEngineRef.current) {
        voiceEngineRef.current.stop();
      }
    };
  }, []);

  return (
    <div className="flex flex-col min-h-screen bg-slate-950 text-slate-100">
      {/* Header */}
      <Header
        language={language}
        onLanguageChange={handleLanguageChange}
        currentLocation={currentLocation}
        locationStatus={locationStatus}
        onRequestLocation={handleRequestLocation}
      />

      {/* Main Content Area */}
      <main className="flex-1 max-w-4xl w-full mx-auto px-4 sm:px-6 py-6 flex flex-col gap-6">
        {/* Location Bar */}
        <LocationBar
          currentLocation={currentLocation}
          status={locationStatus}
          errorMessage={locationError}
          onRequestLocation={handleRequestLocation}
          onClearLocation={handleClearLocation}
        />

        {/* Live Weather Widget for Detected Current Location */}
        <CurrentLocationWidget
          currentLocation={currentLocation}
          language={language}
          onActivitySelect={(q) => handleSendMessage(q)}
        />

        {/* Real-time Voice Controller */}
        <VoiceController
          status={voiceStatus}
          mode={voiceMode}
          language={language}
          statusMessage={voiceStatusMsg}
          userTranscript={userVoiceTranscript}
          assistantTranscript={assistantVoiceTranscript}
          onStart={startVoice}
          onStop={stopVoice}
          onLanguageChange={handleLanguageChange}
        />

        {/* Conversation Stream */}
        <div className="flex-1 flex flex-col gap-5 min-h-[300px]">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 px-4 text-center rounded-2xl border border-slate-900 bg-slate-900/30">
              <div className="w-12 h-12 rounded-2xl bg-cyan-500/10 text-cyan-400 flex items-center justify-center mb-3 shadow-inner">
                <Bot className="w-6 h-6" />
              </div>
              <h2 className="text-lg font-bold text-slate-100">Welcome to Weatherwise</h2>
              <p className="text-xs text-slate-400 max-w-md mt-1 leading-relaxed">
                Ask about cycling, running, hiking, walking, picnics, commuting, or park visits.
                All safety recommendations are grounded in live Open-Meteo forecasts and written SOP policies.
              </p>
              <div className="mt-6 w-full max-w-lg">
                <Suggestions language={language} onSelect={(p) => handleSendMessage(p)} />
              </div>
            </div>
          ) : (
            <div className="space-y-6">
              {messages.map((msg) => (
                <div key={msg.id} className="space-y-2">
                  {msg.role === "user" ? (
                    <div className="flex justify-end">
                      <div className="max-w-[85%] sm:max-w-[75%] rounded-2xl rounded-tr-sm bg-cyan-600/90 text-white px-4 py-2.5 text-sm shadow-md">
                        <p>{msg.content}</p>
                        <span className="text-[10px] text-cyan-200 mt-1 block text-right">
                          {msg.timestamp}
                        </span>
                      </div>
                    </div>
                  ) : (
                    <div className="flex flex-col items-start gap-1">
                      {msg.data ? (
                        <AdvisoryCard response={msg.data} />
                      ) : (
                        <div className="max-w-[85%] sm:max-w-[75%] rounded-2xl rounded-tl-sm bg-slate-900 border border-slate-800 text-slate-100 px-4 py-2.5 text-sm">
                          <p>{msg.content}</p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}

              {/* Loading State */}
              {isLoading && (
                <div className="flex items-center gap-3 p-4 rounded-2xl bg-slate-900/60 border border-slate-800 text-xs text-slate-300">
                  <Loader2 className="w-4 h-4 animate-spin text-cyan-400" />
                  <span>Fetching live Open-Meteo forecast and evaluating written SOP policies...</span>
                </div>
              )}

              {/* Error banner */}
              {errorMessage && (
                <div className="flex items-center gap-2.5 p-3.5 rounded-xl bg-rose-950/50 border border-rose-800/80 text-rose-300 text-xs">
                  <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
                  <span>{errorMessage}</span>
                </div>
              )}

              <div ref={chatScrollRef} />
            </div>
          )}
        </div>

        {/* Input Form Area */}
        <div className="sticky bottom-4 z-30 pt-2 bg-gradient-to-t from-slate-950 via-slate-950/90 to-transparent">
          {messages.length > 0 && (
            <div className="mb-2">
              <Suggestions language={language} onSelect={(p) => handleSendMessage(p)} />
            </div>
          )}

          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSendMessage();
            }}
            className="flex items-center gap-2 p-2 rounded-2xl bg-slate-900/90 border border-slate-800 focus-within:border-cyan-500/80 shadow-2xl backdrop-blur-md transition-colors"
          >
            <div className="pl-3 text-slate-500">
              <MessageSquare className="w-4 h-4" />
            </div>

            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder={
                language === "te-IN"
                  ? 'వాతావరణ ప్రశ్న అడగండి (ఉదా: "భోపాల్‌లో సైకిల్ తొక్కడం సురక్షితమేనా?" లేదా "ఇక్కడ నడవవచ్చా?")...'
                  : language === "hi-IN"
                  ? 'मौसम संबंधी प्रश्न पूछें (उदा: "क्या आज भोपाल में साइकिल चलाना सुरक्षित है?" या "क्या मैं यहाँ टहल सकता हूँ?")...'
                  : language === "ta-IN"
                  ? 'வானிலை கேள்வியைக் கேளுங்கள் (எ.கா. "இன்று போபாலில் சைக்கிள் ஓட்டலாமா?")...'
                  : language === "kn-IN"
                  ? 'ಹವಾಮಾನ ಪ್ರಶ್ನೆಯನ್ನು ಕೇಳಿ (ಉದಾ: "ಭೋಪಾಲ್‌ನಲ್ಲಿ ಇಂದು ಸೈಕ್ಲಿಂಗ್ ಸುರಕ್ಷಿತವೇ?")...'
                  : 'Ask a weather question (e.g., "Is it safe to cycle in Bhopal today?" or "Can I walk here?")...'
              }
              aria-label="Outdoor weather advisory question"
              disabled={isLoading}
              className="flex-1 bg-transparent px-2 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none disabled:opacity-50"
            />

            <button
              type="submit"
              disabled={isLoading || !inputValue.trim()}
              aria-label="Send query"
              className="p-2.5 rounded-xl bg-cyan-500 hover:bg-cyan-400 disabled:opacity-40 disabled:hover:bg-cyan-500 text-slate-950 font-bold transition-all shadow-md cursor-pointer shrink-0"
            >
              {isLoading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
            </button>
          </form>
        </div>
      </main>

      {/* Footer */}
      <footer className="w-full border-t border-slate-900 py-4 text-center text-[11px] text-slate-500">
        <div className="max-w-6xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-2">
          <span>Weatherwise © {new Date().getFullYear()} — Grounded Outdoor Safety Advisory</span>
          <span className="flex items-center gap-1.5">
            <Sparkles className="w-3 h-3 text-cyan-400" />
            Deterministic SOP Policy Engine &bull; Live Open-Meteo &bull; Multilingual Gemini Live
          </span>
        </div>
      </footer>
    </div>
  );
}
