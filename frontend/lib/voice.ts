import { CurrentLocation, VoiceLanguage, VoiceStatus } from "./types";

export interface VoiceCallbacks {
  onStatusChange?: (status: VoiceStatus, mode: "gemini_live" | "fallback", message?: string) => void;
  onUserTranscript?: (text: string, isFinal: boolean) => void;
  onAssistantTranscript?: (text: string) => void;
  onAdvisoryResult?: (data: unknown, prompt: string) => void;
  getCurrentLocation?: () => CurrentLocation | null;
}

// Convert ArrayBuffer to base64
function bufferToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  for (let i = 0; i < bytes.length; i += 8192) {
    binary += String.fromCharCode(...bytes.subarray(i, i + 8192));
  }
  return btoa(binary);
}

// Convert base64 to Float32Array PCM 24000Hz for playback
function base64ToFloat32Array(base64: string): Float32Array {
  const binaryString = atob(base64);
  const bytes = new Uint8Array(binaryString.length);
  for (let i = 0; i < binaryString.length; i++) {
    bytes[i] = binaryString.charCodeAt(i);
  }
  const int16 = new Int16Array(bytes.buffer);
  const float32 = new Float32Array(int16.length);
  for (let i = 0; i < int16.length; i++) {
    float32[i] = int16[i] / 32768.0;
  }
  return float32;
}

export class WeatherwiseVoiceEngine {
  private ws: WebSocket | null = null;
  private mediaStream: MediaStream | null = null;
  private audioContext: AudioContext | null = null;
  private scriptProcessor: ScriptProcessorNode | null = null;
  private activeSources: Set<AudioBufferSourceNode> = new Set();
  private nextPlayTime = 0;
  private isStopped = true;

  // Browser Fallback state
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  private speechRecognizer: any = null;
  private fallbackActive = false;

  constructor(
    private readonly apiBase: string,
    private readonly sessionId: string,
    private language: VoiceLanguage = "en-IN",
    private readonly callbacks: VoiceCallbacks = {}
  ) {}

  public setLanguage(lang: VoiceLanguage) {
    this.language = lang;
  }

  public async start(): Promise<void> {
    if (!this.isStopped) {
      return;
    }
    this.isStopped = false;
    this.callbacks.onStatusChange?.("connecting", "gemini_live", "Initializing voice session...");

    try {
      // 1. Request session credential from backend
      const res = await fetch(`${this.apiBase}/api/voice/session`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ language: this.language }),
      });

      if (!res.ok) {
        throw new Error(`Voice session API error: ${res.statusText}`);
      }

      const session = await res.json();

      if (session.mode === "fallback" || !session.ws_url) {
        await this.startBrowserFallback();
        return;
      }

      // 2. Connect via Gemini Live WebSocket
      await this.connectGeminiLive(session.ws_url);
    } catch (err) {
      console.warn("Gemini Live connection failed, trying browser fallback:", err);
      try {
        await this.startBrowserFallback();
      } catch (fallbackErr) {
        const msg = fallbackErr instanceof Error ? fallbackErr.message : "Voice interaction unavailable";
        this.callbacks.onStatusChange?.("error", "fallback", msg);
        this.stop();
      }
    }
  }

  public stop(): void {
    this.isStopped = true;

    // Teardown WebSocket
    if (this.ws) {
      try {
        this.ws.close();
      } catch {}
      this.ws = null;
    }

    // Stop Microphone
    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach((track) => track.stop());
      this.mediaStream = null;
    }

    // Teardown ScriptProcessor
    if (this.scriptProcessor) {
      this.scriptProcessor.disconnect();
      this.scriptProcessor = null;
    }

    // Stop queued audio sources
    this.activeSources.forEach((src) => {
      try {
        src.stop();
        src.disconnect();
      } catch {}
    });
    this.activeSources.clear();
    this.nextPlayTime = 0;

    // Close AudioContext
    if (this.audioContext && this.audioContext.state !== "closed") {
      this.audioContext.close().catch(() => {});
      this.audioContext = null;
    }

    // Stop Browser Fallback
    if (this.speechRecognizer) {
      try {
        this.speechRecognizer.abort();
      } catch {}
      this.speechRecognizer = null;
    }

    if (typeof window !== "undefined" && window.speechSynthesis) {
      try {
        window.speechSynthesis.cancel();
      } catch {}
    }
    this.fallbackActive = false;

    this.callbacks.onStatusChange?.("idle", "gemini_live", "Voice stopped");
  }

  private async connectGeminiLive(wsUrl: string): Promise<void> {
    return new Promise((resolve, reject) => {
      const socket = new WebSocket(wsUrl);
      this.ws = socket;

      socket.onopen = async () => {
        try {
          await this.startAudioCapture();
          this.callbacks.onStatusChange?.("listening", "gemini_live", "Listening for your question...");
          resolve();
        } catch (captureErr) {
          reject(captureErr);
        }
      };

      socket.onerror = () => {
        reject(new Error("Gemini Live WebSocket connection failed"));
      };

      socket.onclose = () => {
        if (!this.isStopped) {
          this.stop();
        }
      };

      socket.onmessage = async (event) => {
        try {
          const raw = typeof event.data === "string" ? event.data : await event.data.text();
          const message = JSON.parse(raw);
          await this.handleGeminiMessage(message);
        } catch (err) {
          console.error("Error processing Gemini Live message:", err);
        }
      };
    });
  }

  private async startAudioCapture(): Promise<void> {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        sampleRate: 16000,
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
      },
    });
    this.mediaStream = stream;

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
    const ctx = new AudioCtx({ sampleRate: 16000 });
    this.audioContext = ctx;

    const source = ctx.createMediaStreamSource(stream);
    // Buffer size 4096 = ~256ms audio slices
    const processor = ctx.createScriptProcessor(4096, 1, 1);
    this.scriptProcessor = processor;

    processor.onaudioprocess = (e) => {
      if (this.isStopped || !this.ws || this.ws.readyState !== WebSocket.OPEN) {
        return;
      }

      const inputData = e.inputBuffer.getChannelData(0);
      // Convert Float32 to 16-bit linear PCM
      const pcm16 = new Int16Array(inputData.length);
      for (let i = 0; i < inputData.length; i++) {
        const s = Math.max(-1, Math.min(1, inputData[i]));
        pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
      }

      const base64Audio = bufferToBase64(pcm16.buffer);
      const payload = {
        realtimeInput: {
          mediaChunks: [
            {
              mimeType: "audio/pcm;rate=16000",
              data: base64Audio,
            },
          ],
        },
      };

      this.ws.send(JSON.stringify(payload));
    };

    source.connect(processor);
    processor.connect(ctx.destination);
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  private async handleGeminiMessage(msg: any): Promise<void> {
    if (this.isStopped) return;

    // Handle user interruption
    if (msg.serverContent?.interrupted) {
      this.activeSources.forEach((src) => {
        try {
          src.stop();
          src.disconnect();
        } catch {}
      });
      this.activeSources.clear();
      this.nextPlayTime = 0;
      this.callbacks.onStatusChange?.("listening", "gemini_live", "Listening...");
      return;
    }

    // Audio Output Playback
    const parts = msg.serverContent?.modelTurn?.parts || [];
    for (const part of parts) {
      if (part.inlineData && part.inlineData.mimeType?.startsWith("audio/pcm")) {
        this.callbacks.onStatusChange?.("speaking", "gemini_live", "Weatherwise speaking...");
        this.queueAudioPlayback(part.inlineData.data);
      }
      if (part.text) {
        this.callbacks.onAssistantTranscript?.(part.text);
      }
    }

    // Tool Call Execution: get_weather_advisory
    const toolCall = msg.toolCall;
    if (toolCall && Array.isArray(toolCall.functionCalls)) {
      for (const call of toolCall.functionCalls) {
        if (call.name === "get_weather_advisory") {
          const args = call.args || {};
          const queryMessage = String(args.message || "");
          const useCurr = Boolean(args.use_current_location);

          this.callbacks.onUserTranscript?.(queryMessage, true);
          this.callbacks.onStatusChange?.("connecting", "gemini_live", "Evaluating weather and SOP rules...");

          // Call backend advisory
          const currentCoordinates = useCurr ? this.callbacks.getCurrentLocation?.() : null;

          try {
            const chatRes = await fetch(`${this.apiBase}/api/chat`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                session_id: this.sessionId,
                message: queryMessage,
                current_location: currentCoordinates,
                language: this.language,
              }),
            });

            const advisoryData = await chatRes.json();
            this.callbacks.onAdvisoryResult?.(advisoryData, queryMessage);

            // Respond back to Gemini with structured tool result
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
              const toolResponseMsg = {
                toolResponse: {
                  functionResponses: [
                    {
                      id: call.id,
                      response: {
                        output: advisoryData,
                      },
                    },
                  ],
                },
              };
              this.ws.send(JSON.stringify(toolResponseMsg));
            }
          } catch (apiErr) {
            console.error("Advisory tool execution error:", apiErr);
          }
        }
      }
    }
  }

  private queueAudioPlayback(base64Data: string): void {
    try {
      const float32Pcm = base64ToFloat32Array(base64Data);
      if (!this.audioContext || this.audioContext.state === "closed") {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
        this.audioContext = new AudioCtx({ sampleRate: 24000 });
      }

      const sampleRate = 24000;
      const audioBuffer = this.audioContext.createBuffer(1, float32Pcm.length, sampleRate);
      audioBuffer.getChannelData(0).set(float32Pcm);

      const sourceNode = this.audioContext.createBufferSource();
      sourceNode.buffer = audioBuffer;
      sourceNode.connect(this.audioContext.destination);

      const currentTime = this.audioContext.currentTime;
      const startTime = Math.max(currentTime, this.nextPlayTime);
      sourceNode.start(startTime);

      this.nextPlayTime = startTime + audioBuffer.duration;
      this.activeSources.add(sourceNode);

      sourceNode.onended = () => {
        this.activeSources.delete(sourceNode);
        if (this.activeSources.size === 0 && !this.isStopped) {
          this.callbacks.onStatusChange?.("listening", "gemini_live", "Listening...");
        }
      };
    } catch (err) {
      console.error("Error playing audio chunk:", err);
    }
  }

  // BROWSER VOICE FALLBACK IMPLEMENTATION
  private async startBrowserFallback(): Promise<void> {
    this.fallbackActive = true;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (!SpeechRecognition) {
      throw new Error("Speech recognition is not supported in this browser.");
    }

    const recognition = new SpeechRecognition();
    this.speechRecognizer = recognition;
    recognition.lang = this.language;
    recognition.continuous = false;
    recognition.interimResults = true;

    this.callbacks.onStatusChange?.("listening", "fallback", `Listening in ${this.language}...`);

    let finalTranscript = "";

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    recognition.onresult = (event: any) => {
      let interim = "";
      for (let i = event.resultIndex; i < event.results.length; ++i) {
        if (event.results[i].isFinal) {
          finalTranscript += event.results[i][0].transcript;
        } else {
          interim += event.results[i][0].transcript;
        }
      }
      this.callbacks.onUserTranscript?.(finalTranscript || interim, Boolean(finalTranscript));
    };

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    recognition.onerror = (err: any) => {
      console.warn("Speech recognition error:", err);
      if (!this.isStopped) {
        this.callbacks.onStatusChange?.("error", "fallback", "Microphone error or speech not detected.");
      }
    };

    recognition.onend = async () => {
      if (this.isStopped || !finalTranscript.trim()) {
        if (!this.isStopped) {
          this.callbacks.onStatusChange?.("idle", "fallback", "Ready.");
        }
        return;
      }

      const queryText = finalTranscript.trim();
      this.callbacks.onStatusChange?.("connecting", "fallback", "Evaluating weather and SOP rules...");

      try {
        const currentCoordinates = this.callbacks.getCurrentLocation?.();
        const res = await fetch(`${this.apiBase}/api/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            session_id: this.sessionId,
            message: queryText,
            current_location: currentCoordinates,
            language: this.language,
          }),
        });

        const data = await res.json();
        this.callbacks.onAdvisoryResult?.(data, queryText);

        // Fallback Speech Synthesis Output
        if (typeof window !== "undefined" && window.speechSynthesis) {
          this.callbacks.onStatusChange?.("speaking", "fallback", "Speaking advisory...");
          const utterance = new SpeechSynthesisUtterance(data.answer);
          utterance.lang = this.language;
          utterance.onend = () => {
            if (!this.isStopped) {
              this.callbacks.onStatusChange?.("idle", "fallback", "Ready.");
            }
          };
          window.speechSynthesis.speak(utterance);
        } else {
          this.callbacks.onStatusChange?.("idle", "fallback", "Ready.");
        }
      } catch (err) {
        console.error("Fallback advisory error:", err);
        this.callbacks.onStatusChange?.("error", "fallback", "Failed to retrieve advisory.");
      }
    };

    recognition.start();
  }
}
