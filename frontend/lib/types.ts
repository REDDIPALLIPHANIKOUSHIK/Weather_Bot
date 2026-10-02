export type VoiceStatus = "idle" | "connecting" | "listening" | "speaking" | "error";

export type VoiceLanguage =
  | "en-IN"
  | "te-IN"
  | "hi-IN"
  | "ta-IN"
  | "kn-IN"
  | "ml-IN"
  | "mr-IN"
  | "bn-IN";

export interface CurrentLocation {
  latitude: number;
  longitude: number;
  accuracy?: number | null;
  timestamp?: string | null;
  cityName?: string | null;
}

export interface Location {
  name: string;
  country: string;
  latitude: number;
  longitude: number;
}

export interface WeatherFacts {
  temperature_2m?: number | null;
  wind_speed_10m?: number | null;
  precipitation?: number | null;
  precipitation_probability?: number | null;
  uv_index?: number | null;
  weather_code?: number | null;
  observed_at: string;
  timezone: string;
  source: string;
}

export interface PolicyResult {
  outcome: "matched" | "no_match" | "insufficient_data";
  sop_id?: string | null;
  title?: string | null;
  severity?: "LOW" | "MODERATE" | "HIGH" | "CRITICAL" | null;
  priority?: number | null;
  guidance: string[];
  trace: Array<Record<string, unknown>>;
}

export interface ChatResponse {
  answer: string;
  status: string;
  location?: Location | null;
  weather?: WeatherFacts | null;
  policy?: PolicyResult | null;
  trace: string[];
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  data?: ChatResponse | null;
}

export const LANGUAGE_LABELS: Record<VoiceLanguage, { name: string; native: string; flag: string }> = {
  "en-IN": { name: "English", native: "English", flag: "🇬🇧" },
  "te-IN": { name: "Telugu", native: "తెలుగు", flag: "🇮🇳" },
  "hi-IN": { name: "Hindi", native: "हिन्दी", flag: "🇮🇳" },
  "ta-IN": { name: "Tamil", native: "தமிழ்", flag: "🇮🇳" },
  "kn-IN": { name: "Kannada", native: "ಕನ್ನಡ", flag: "🇮🇳" },
  "ml-IN": { name: "Malayalam", native: "മലയാളം", flag: "🇮🇳" },
  "mr-IN": { name: "Marathi", native: "मराठी", flag: "🇮🇳" },
  "bn-IN": { name: "Bengali", native: "বাংলা", flag: "🇮🇳" },
};
