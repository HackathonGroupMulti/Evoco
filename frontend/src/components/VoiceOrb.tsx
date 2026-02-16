import { useCallback, useRef, useState } from "react";

// Local type declarations for the Web Speech API
interface SpeechRecognitionResult {
  readonly isFinal: boolean;
  readonly length: number;
  [index: number]: { transcript: string; confidence: number };
}

interface SpeechRecognitionResultList {
  readonly length: number;
  [index: number]: SpeechRecognitionResult;
}

interface SpeechRecognitionEventLocal {
  readonly results: SpeechRecognitionResultList;
}

interface SpeechRecognitionInstance {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((event: SpeechRecognitionEventLocal) => void) | null;
  onerror: (() => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
}

interface VoiceOrbProps {
  onTranscript: (text: string) => void;
  onComplete: (text: string) => void;
}

export function VoiceOrb({ onTranscript, onComplete }: VoiceOrbProps) {
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null);

  const toggleListening = useCallback(() => {
    if (isListening) {
      recognitionRef.current?.stop();
      setIsListening(false);
      if (transcript.trim()) {
        onComplete(transcript.trim());
      }
      return;
    }

    // Check for browser support
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) return;

    const recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "en-US";

    recognition.onresult = (event: SpeechRecognitionEventLocal) => {
      let final = "";
      let interim = "";
      for (let i = 0; i < event.results.length; i++) {
        if (event.results[i].isFinal) {
          final += event.results[i][0].transcript;
        } else {
          interim += event.results[i][0].transcript;
        }
      }
      const text = final || interim;
      setTranscript(text);
      onTranscript(text);
    };

    recognition.onerror = () => {
      setIsListening(false);
    };

    recognition.onend = () => {
      setIsListening(false);
    };

    recognitionRef.current = recognition;
    recognition.start();
    setIsListening(true);
    setTranscript("");
  }, [isListening, transcript, onTranscript, onComplete]);

  // Check browser support
  const hasSupport = typeof window !== "undefined" &&
    (window.SpeechRecognition || window.webkitSpeechRecognition);

  if (!hasSupport) return null;

  return (
    <div className="flex flex-col items-center gap-3">
      <button
        onClick={toggleListening}
        className={`relative flex h-14 w-14 items-center justify-center rounded-full transition-all duration-300 ${
          isListening
            ? "bg-gradient-to-br from-neon-cyan to-neon-purple voice-orb listening"
            : "bg-gradient-to-br from-neon-cyan/20 to-neon-purple/20 border border-neon-cyan/30 hover:border-neon-cyan/60 hover:shadow-[0_0_20px_rgba(34,211,238,0.2)]"
        }`}
      >
        {/* Expanding rings when listening */}
        {isListening && (
          <>
            <div className="absolute inset-0 rounded-full border-2 border-neon-cyan/40" style={{ animation: "ring-expand 1.5s ease-out infinite" }} />
            <div className="absolute inset-0 rounded-full border-2 border-neon-cyan/20" style={{ animation: "ring-expand 1.5s ease-out infinite 0.5s" }} />
          </>
        )}
        <svg
          viewBox="0 0 24 24"
          fill="none"
          className={`h-6 w-6 ${isListening ? "text-white" : "text-neon-cyan/60"}`}
        >
          <path
            d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"
            fill="currentColor"
          />
          <path
            d="M19 10v2a7 7 0 0 1-14 0v-2"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
          />
          <line x1="12" y1="19" x2="12" y2="23" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        </svg>
      </button>
      <span className="text-[11px] text-muted-foreground/40">
        {isListening ? "Listening... tap to send" : "or speak your request"}
      </span>
      {isListening && transcript && (
        <p className="text-xs text-neon-cyan/70 max-w-xs text-center italic animate-pulse">
          "{transcript}"
        </p>
      )}
    </div>
  );
}

// Type declarations for Speech Recognition API
declare global {
  interface Window {
    SpeechRecognition: new () => SpeechRecognitionInstance;
    webkitSpeechRecognition: new () => SpeechRecognitionInstance;
  }
}
