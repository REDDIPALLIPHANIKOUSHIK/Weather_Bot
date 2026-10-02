"use client";

import React from "react";
import { Sparkles } from "lucide-react";
import { VoiceLanguage } from "../lib/types";

interface SuggestionsProps {
  language: VoiceLanguage;
  onSelect: (prompt: string) => void;
}

const SUGGESTIONS_BY_LANG: Record<VoiceLanguage, string[]> = {
  "en-IN": [
    "Is it safe to cycle in Bhopal today?",
    "Is it safe to walk here today?",
    "Should I take my child to the park in Pune this afternoon?",
    "Is today a good day for a picnic in Jaipur?",
    "Can I go running this evening in Delhi?",
    "Can I take my dog for a pet walk in Mumbai today?",
  ],
  "te-IN": [
    "ఇక్కడ ఈరోజు నడవడం సురక్షితమేనా?",
    "భోపాల్‌లో ఈరోజు సైకిల్ తొక్కడం సురక్షితమేనా?",
    "పూణేలో పిల్లల పార్కుకు వెళ్లవచ్చా?",
    "జైపూర్‌లో పిక్నిక్ చేయడానికి మంచి రోజా?",
  ],
  "hi-IN": [
    "क्या आज भोपाल में साइकिल चलाना सुरक्षित है?",
    "क्या आज यहाँ टहलना सुरक्षित है?",
    "क्या आज दोपहर पुणे में बच्चों को पार्क ले जा सकते हैं?",
    "क्या आज शाम दिल्ली में रनिंग कर सकते हैं?",
  ],
  "ta-IN": [
    "போபாலில் இன்று சைக்கிள் ஓட்டுவது பாதுகாப்பானதா?",
    "இங்கு இன்று நடைபயிற்சி மேற்கொள்வது பாதுகாப்பானதா?",
    "இன்று மாலை தில்லியில் ஓடலாமா?",
  ],
  "kn-IN": [
    "ಭೋಪಾಲ್‌ನಲ್ಲಿ ಇಂದು ಸೈಕ್ಲಿಂಗ್ ಸುರಕ್ಷಿತವೇ?",
    "ಇಲ್ಲಿ ಇಂದು ನಡೆಯುವುದು ಸುರಕ್ಷಿತವೇ?",
    "ಪುಣೆಯಲ್ಲಿ ಇಂದು ಮಕ್ಕಳ ಪಾರ್ಕ್‌ಗೆ ಹೋಗಬಹುದೇ?",
  ],
  "ml-IN": [
    "ഭോപ്പാലിൽ ഇന്ന് സൈക്കിൾ ചവിട്ടുന്നത് സുരക്ഷിതമാണോ?",
    "ഇവിടെ ഇന്ന് നടക്കുന്നത് സുരക്ഷിതമാണോ?",
  ],
  "mr-IN": [
    "भोपाळमध्ये आज सायकल चालवणे सुरक्षित आहे का?",
    "येथे आज फिरणे सुरक्षित आहे का?",
    "पुण्यात आज दुपारी मुलांना बागेत नेणे योग्य आहे का?",
  ],
  "bn-IN": [
    "আজ ভোপালে সাইকেল চালানো কি নিরাপদ?",
    "আজ এখানে হাঁটা কি নিরাপদ?",
    "আজ বিকেলে পুনেতে পার্কে যাওয়া যাবে?",
  ],
};

export const Suggestions: React.FC<SuggestionsProps> = ({ language, onSelect }) => {
  const suggestions = SUGGESTIONS_BY_LANG[language] || SUGGESTIONS_BY_LANG["en-IN"];

  return (
    <div className="w-full">
      <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-400 mb-2">
        <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
        <span>Try asking:</span>
      </div>
      <div className="flex flex-wrap gap-2">
        {suggestions.map((prompt, idx) => (
          <button
            key={idx}
            onClick={() => onSelect(prompt)}
            className="px-3 py-1.5 rounded-xl bg-slate-900/70 hover:bg-slate-800 text-slate-300 hover:text-cyan-300 border border-slate-800 hover:border-slate-700 text-xs text-left transition-all cursor-pointer"
          >
            &ldquo;{prompt}&rdquo;
          </button>
        ))}
      </div>
    </div>
  );
};
