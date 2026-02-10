"use client";

import { useState, useCallback, DragEvent, useEffect, useMemo, useRef } from "react";
import { Header } from "@/components/Header";
import { APIKeysSettings, getAPIKeys, hasAPIKeys } from "@/components/APIKeysSettings";
import { SupportChat } from "@/components/SupportChat";

// 本番環境：Frontend (Next.js) + Backend (FastAPI) を別々にデプロイ
// NEXT_PUBLIC_API_URL 環境変数でバックエンドURLを指定
const rawApiUrl = process.env.NEXT_PUBLIC_API_URL || "";
const API_URL = rawApiUrl.endsWith('/') ? rawApiUrl.slice(0, -1) : rawApiUrl;

// Debug log
if (typeof window !== "undefined") {
  console.log("[Config] API_URL:", API_URL);
}

// Helper to get API headers with keys
function getAPIHeaders(): HeadersInit {
  const keys = getAPIKeys();
  const headers: HeadersInit = {};
  if (keys.openai) headers["x-openai-key"] = keys.openai;
  if (keys.gemini) headers["x-gemini-key"] = keys.gemini;
  return headers;
}

// Helper for fetch with automatic retry on network errors
async function fetchWithRetry(
  url: string,
  options?: RequestInit,
  maxRetries: number = 3,
  delayMs: number = 1000
): Promise<Response> {
  let lastError: Error | null = null;
  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      const res = await fetch(url, options);
      return res;
    } catch (err: any) {
      lastError = err;
      console.log(`[Fetch] Attempt ${attempt + 1} failed: ${err.message}, retrying...`);
      if (attempt < maxRetries - 1) {
        await new Promise(resolve => setTimeout(resolve, delayMs));
      }
    }
  }
  throw lastError || new Error("Fetch failed after retries");
}

type Step = 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10;
type WorkflowMode = "hybrid" | "full-ai" | null;

interface JobState {
  jobId: string | null;
  step: Step;
  workflowMode: WorkflowMode;
  transcript: string;
  polishedTranscript: string;
  outline: any;
  polishedOutline: any;
  slideCount: number;
  slidePreviews: string[];
  timingMap: any[];
  videoUrl: string | null;
  isProcessing: boolean;
  error: string | null;
  cleanupInfo: {
    removed_silences: number;
    removed_fillers: number;
    total_removed_seconds: number;
  } | null;
}

const HYBRID_STEPS = [
  { id: 1, label: "音声", icon: "🎙️" },
  { id: 2, label: "文字起こし", icon: "📝" },
  { id: 3, label: "ブラッシュアップ", icon: "✨" },
  { id: 4, label: "アウトライン", icon: "📋" },
  { id: 5, label: "アウトライン改善", icon: "🔄" },
  { id: 6, label: "出力", icon: "📤" },
  { id: 7, label: "スライド作成", icon: "👤" },
  { id: 8, label: "スライド読込", icon: "📥" },
  { id: 9, label: "AIマッピング", icon: "🤖" },
  { id: 10, label: "動画生成", icon: "🎬" },
];

const FULL_AI_STEPS = [
  { id: 1, label: "音声", icon: "🎙️" },
  { id: 2, label: "文字起こし", icon: "📝" },
  { id: 3, label: "ブラッシュアップ", icon: "✨" },
  { id: 4, label: "アウトライン", icon: "📋" },
  { id: 5, label: "スライド生成", icon: "🎨" },
  { id: 6, label: "動画生成", icon: "🎬" },
];

export default function Home() {
  const [state, setState] = useState<JobState>({
    jobId: null,
    step: 1,
    workflowMode: null,
    transcript: "",
    polishedTranscript: "",
    outline: null,
    polishedOutline: null,
    slideCount: 0,
    slidePreviews: [],
    timingMap: [],
    videoUrl: null,
    isProcessing: false,
    error: null,
    cleanupInfo: null,
  });

  const [editedTranscript, setEditedTranscript] = useState<string>("");
  const [editText, setEditText] = useState<string>("");
  const [scriptText, setScriptText] = useState<string>("");
  const [showScriptInput, setShowScriptInput] = useState<boolean>(false);
  const [isEditingTranscript, setIsEditingTranscript] = useState<boolean>(false);
  const [isDragging, setIsDragging] = useState(false); // This was originally here, keeping it.
  const [showSettings, setShowSettings] = useState(false);
  const [hasKeys, setHasKeys] = useState(false);

  // Timeline drag state
  const [draggingBoundary, setDraggingBoundary] = useState<number | null>(null);
  const timelineRef = useRef<HTMLDivElement>(null);

  // Support chat error context
  const errorContext = useMemo(() => {
    if (!state.error) return undefined;
    const stepLabels: { [key: number]: string } = {
      1: "audio_upload", 2: "transcribe", 3: "polish_transcript",
      4: "generate_outline", 5: "generate_slides", 6: "generate_video",
      7: "user_slides", 8: "upload_slides", 9: "ai_mapping", 10: "generate_video"
    };
    return {
      step: stepLabels[state.step] || `step_${state.step}`,
      errorMessage: state.error,
      workflowMode: state.workflowMode || "unknown",
      timestamp: new Date().toISOString()
    };
  }, [state.error, state.step, state.workflowMode]);

  // Slide feedback editing
  const [selectedSlide, setSelectedSlide] = useState<number | null>(null);
  const [slideFeedback, setSlideFeedback] = useState("");
  const [slideImage, setSlideImage] = useState<{ file: File | null; preview: string | null }>({ file: null, preview: null });
  const [isRegenerating, setIsRegenerating] = useState(false);

  // Slide zoom modal
  const [zoomedSlide, setZoomedSlide] = useState<number | null>(null);

  // Color theme selection
  const [selectedColorTheme, setSelectedColorTheme] = useState<string>(""); // empty = AI chooses

  // Font style selection
  const [selectedFontStyle, setSelectedFontStyle] = useState<string>(""); // empty = AI chooses

  // User images for slides
  const [userImages, setUserImages] = useState<{ file: File; preview: string }[]>([]);
  // Progress tracking
  const [progress, setProgress] = useState<{ percent: number, message: string }>({ percent: 0, message: "" });

  // Batch slide generation tracking
  const [batchState, setBatchState] = useState<{
    isComplete: boolean;
    nextStart: number | null;
    slidesCompleted: number;
    totalSlides: number;
  }>({ isComplete: true, nextStart: null, slidesCompleted: 0, totalSlides: 0 });

  // Queue status tracking for multi-user scenarios
  const [queueStatus, setQueueStatus] = useState<{
    position: number;
    status: string;
    estimatedWait: number;
    activeCount: number;
    waitingCount: number;
  }>({ position: 0, status: "unknown", estimatedWait: 0, activeCount: 0, waitingCount: 0 });

  // ===== User Preference Settings =====
  // Audio cleanup settings
  const [audioSettings, setAudioSettings] = useState<{
    cleanupEnabled: boolean;
    cleanupMode: "strict" | "natural";
    silenceThreshold: number; // seconds (0.3 - 1.0)
  }>({ cleanupEnabled: true, cleanupMode: "natural", silenceThreshold: 0.5 });

  // Slide count settings
  const [slideSettings, setSlideSettings] = useState<{
    mode: "auto" | "fewer" | "more" | "custom";
    customCount: number;
  }>({ mode: "auto", customCount: 10 });

  // Design preference (free-form text)
  const [designPreference, setDesignPreference] = useState<string>("");

  // Text density setting: simple (title+headline) or standard (title+headline+points)
  const [textDensity, setTextDensity] = useState<"simple" | "standard">("standard");

  // Illustration settings: add AI-generated illustrations to slides
  const [addIllustrations, setAddIllustrations] = useState<boolean>(false);
  const [illustrationPercentage, setIllustrationPercentage] = useState<number>(50);

  // Reference image for illustration (style guide)
  const [referenceImage, setReferenceImage] = useState<{ file: File; preview: string } | null>(null);

  // Illustration request text (e.g., "use this character", "make it watercolor style")
  const [illustrationRequest, setIllustrationRequest] = useState<string>("");

  // OP/ED video for YouTube
  const [introVideo, setIntroVideo] = useState<File | null>(null);
  const [outroVideo, setOutroVideo] = useState<File | null>(null);
  const [concatVideoUrl, setConcatVideoUrl] = useState<string | null>(null);
  const [isConcatenating, setIsConcatenating] = useState(false);

  // BGM mixing feature
  const [bgmEnabled, setBgmEnabled] = useState(false);
  const [bgmFile, setBgmFile] = useState<File | null>(null);
  const [bgmMixed, setBgmMixed] = useState(false);
  const [bgmMixing, setBgmMixing] = useState(false);
  const [bgmFeedback, setBgmFeedback] = useState("");
  const [bgmVolume, setBgmVolume] = useState(-27);
  // BGM playback settings
  const [bgmPlayMode, setBgmPlayMode] = useState<'loop' | 'single' | 'minute'>('loop');
  const [bgmFadeIn, setBgmFadeIn] = useState(true);
  const [bgmFadeOut, setBgmFadeOut] = useState(true);

  // Slide undo history
  const [slideCanUndo, setSlideCanUndo] = useState<{ [key: number]: boolean }>({});
  const [isUndoing, setIsUndoing] = useState(false);
  // Check for API keys on mount
  useEffect(() => {
    setHasKeys(hasAPIKeys());
  }, [showSettings]);

  // Wake Lock to prevent sleep during processing
  useEffect(() => {
    let wakeLock: WakeLockSentinel | null = null;

    const requestWakeLock = async () => {
      if ('wakeLock' in navigator && state.isProcessing) {
        try {
          wakeLock = await navigator.wakeLock.request('screen');
          console.log('[WakeLock] Acquired - screen will stay on');
        } catch (err) {
          console.log('[WakeLock] Failed to acquire:', err);
        }
      }
    };

    if (state.isProcessing) {
      requestWakeLock();
    }

    return () => {
      if (wakeLock) {
        wakeLock.release();
        console.log('[WakeLock] Released');
      }
    };
  }, [state.isProcessing]);

  const STEPS = state.workflowMode === "full-ai" ? FULL_AI_STEPS : HYBRID_STEPS;

  // Drag & Drop handlers
  const handleDragEnter = useCallback((e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDragOver = useCallback((e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const updateState = (updates: Partial<JobState>) => {
    setState((prev) => ({ ...prev, ...updates }));
  };

  // Helper: Set error with timestamp for easier log correlation
  const setError = (message: string, isProcessing = false) => {
    const now = new Date();
    const timestamp = now.toLocaleString('ja-JP', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false
    });
    updateState({ error: `[${timestamp}] ${message}`, isProcessing });
  };

  // Step 1: Upload Audio
  const handleUploadAudio = async (file: File) => {
    updateState({ isProcessing: true, error: null });

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch(`${API_URL}/api/upload-audio`, {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Upload failed");

      updateState({ jobId: data.job_id, step: 2, isProcessing: false });
    } catch (err: any) {
      setError(err.message);
    }
  };

  // Step 2: Transcribe (async with polling)
  const handleTranscribe = async () => {
    // Check if API keys are set
    if (!hasAPIKeys()) {
      setShowSettings(true);
      updateState({ error: "APIキーを設定してください" });
      return;
    }

    updateState({ isProcessing: true, error: null });
    setProgress({ percent: 5, message: "処理を開始中..." });

    try {
      // If BGM is enabled, upload and mix
      if (bgmEnabled && bgmFile) {
        // Re-upload BGM to ensure it's in the job (in case of server restart)
        setProgress({ percent: 8, message: "BGMをアップロード中..." });
        const formData = new FormData();
        formData.append('file', bgmFile);
        const uploadRes = await fetch(
          `${API_URL}/api/audio/${state.jobId}/upload-bgm`,
          { method: 'POST', body: formData }
        );
        if (!uploadRes.ok) {
          console.error('BGM upload failed');
        }

        // Then mix
        setProgress({ percent: 15, message: "BGMをミキシング中..." });
        const mixParams = new URLSearchParams({
          bgm_volume: bgmVolume.toString(),
          play_mode: bgmPlayMode,
          fade_in: bgmFadeIn.toString(),
          fade_out: bgmFadeOut.toString(),
        });
        const mixRes = await fetch(
          `${API_URL}/api/audio/${state.jobId}/mix-bgm?${mixParams}`,
          { method: 'POST' }
        );
        if (!mixRes.ok) {
          const errorData = await mixRes.json().catch(() => ({}));
          console.error('BGM mix failed:', errorData);
        } else {
          setBgmMixed(true);
        }
      }

      // Start transcription (returns immediately)
      setProgress({ percent: 20, message: "文字起こしを開始中..." });
      const params = new URLSearchParams({
        cleanup_audio: audioSettings.cleanupEnabled.toString(),
        cleanup_mode: audioSettings.cleanupMode,
        silence_threshold: audioSettings.silenceThreshold.toString(),
      });

      const startRes = await fetchWithRetry(`${API_URL}/api/transcribe/${state.jobId}?${params}`, {
        method: "POST",
        headers: getAPIHeaders(),
      });
      const startData = await startRes.json();
      if (!startRes.ok) throw new Error(startData.detail || startData.error || "Start failed");

      // Poll for status
      let completed = false;
      while (!completed) {
        await new Promise(resolve => setTimeout(resolve, 2000)); // Wait 2 seconds

        const statusRes = await fetchWithRetry(`${API_URL}/api/transcribe-status/${state.jobId}`, {
          headers: getAPIHeaders(),
        });
        const statusData = await statusRes.json();

        if (statusData.status === "completed") {
          completed = true;
          setProgress({ percent: 100, message: "完了！" });
          updateState({
            transcript: statusData.transcript,
            cleanupInfo: statusData.cleanup || null,
            isProcessing: false,
          });
          setEditText(statusData.transcript);
        } else if (statusData.status === "error") {
          throw new Error(statusData.error || "Transcription failed");
        } else {
          // Still processing - update progress message
          setProgress({ percent: 50, message: statusData.progress || "処理中..." });
        }
      }
    } catch (err: any) {
      setProgress({ percent: 0, message: "" });
      updateState({ error: err.message, isProcessing: false });
    }
  };

  // Step 3: Polish Transcript
  const handlePolishTranscript = async () => {
    if (!hasAPIKeys()) {
      setShowSettings(true);
      updateState({ error: "APIキーを設定してください" });
      return;
    }

    updateState({ isProcessing: true, error: null });

    try {
      const res = await fetch(`${API_URL}/api/polish-transcript/${state.jobId}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...getAPIHeaders()
        },
        body: JSON.stringify({
          transcript: editText,
          original_script: scriptText
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || data.error || "Polish failed");

      updateState({
        polishedTranscript: data.polished_transcript,
        step: 3,
        isProcessing: false,
      });
      setEditText(data.polished_transcript);
      // ブラッシュアップ後は自動で編集モードON（手動修正しやすく）
      setIsEditingTranscript(true);
    } catch (err: any) {
      updateState({ error: err.message, isProcessing: false });
    }
  };

  // Step 4: Generate Outline
  const handleGenerateOutline = async () => {
    if (!hasAPIKeys()) {
      setShowSettings(true);
      updateState({ error: "APIキーを設定してください" });
      return;
    }

    updateState({ isProcessing: true, error: null });
    setProgress({ percent: 10, message: "アウトライン生成を開始中..." });

    try {
      // Start outline generation (returns immediately)
      const startRes = await fetchWithRetry(`${API_URL}/api/generate-outline/${state.jobId}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...getAPIHeaders()
        },
        body: JSON.stringify({
          transcript: editText,
          slide_count_mode: slideSettings.mode,
          custom_slide_count: slideSettings.customCount,
        }),
      });
      const startData = await startRes.json();
      if (!startRes.ok) throw new Error(startData.detail || startData.error || "Start failed");

      // Poll for status
      let completed = false;
      while (!completed) {
        await new Promise(resolve => setTimeout(resolve, 2000));

        const statusRes = await fetchWithRetry(`${API_URL}/api/outline-status/${state.jobId}`, {
          headers: getAPIHeaders(),
        });
        const statusData = await statusRes.json();

        if (statusData.status === "completed") {
          completed = true;
          setProgress({ percent: 100, message: "完了！" });
          updateState({
            outline: statusData.outline,
            step: 4,
            isProcessing: false,
          });
        } else if (statusData.status === "error") {
          throw new Error(statusData.error || "Outline generation failed");
        } else {
          setProgress({ percent: 50, message: statusData.progress || "処理中..." });
        }
      }
    } catch (err: any) {
      setProgress({ percent: 0, message: "" });
      updateState({ error: err.message, isProcessing: false });
    }
  };

  // Step 5: Polish Outline
  const handlePolishOutline = async () => {
    updateState({ isProcessing: true });

    try {
      const res = await fetch(`${API_URL}/api/polish-outline/${state.jobId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ outline: state.outline }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Outline polish failed");

      updateState({
        polishedOutline: data.polished_outline,
        step: 5,
        isProcessing: false,
      });
    } catch (err: any) {
      updateState({ error: err.message, isProcessing: false });
    }
  };

  // Step 6: Export Outline (move to next step based on mode)
  const handleExportComplete = () => {
    if (state.workflowMode === "full-ai") {
      // フルAIモードではスライド生成へ
      updateState({ step: 5 as Step }); // スライド生成ステップ
    } else {
      // ハイブリッドモードではユーザーがスライド作成
      updateState({ step: 7 as Step });
    }
  };

  // Step 5 (Full AI): Generate Slides in batches (5 at a time) to avoid timeout
  // Auto-continues to next batch until all slides are complete
  const handleGenerateSlides = async (startSlide: number = 1) => {
    if (!hasAPIKeys()) {
      setShowSettings(true);
      updateState({ error: "APIキーを設定してください" });
      return;
    }

    updateState({ isProcessing: true });
    setProgress({ percent: 0, message: startSlide === 1 ? "デザイン戦略を生成中..." : `スライド ${startSlide} から生成中...` });

    try {
      // Upload user images first (if any and first batch)
      if (startSlide === 1 && userImages.length > 0) {
        setProgress({ percent: 0, message: "画像をアップロード中..." });

        const formData = new FormData();
        userImages.forEach((img) => {
          formData.append("files", img.file);
        });

        const uploadRes = await fetch(`${API_URL}/api/upload-slide-images/${state.jobId}`, {
          method: "POST",
          body: formData,
        });

        if (!uploadRes.ok) {
          console.warn("[Images] Upload failed, continuing without images");
        } else {
          const uploadData = await uploadRes.json();
          console.log(`[Images] Uploaded ${uploadData.image_count} images`);
        }
      }

      // Upload reference image for illustrations (if any and first batch)
      if (startSlide === 1 && addIllustrations) {
        setProgress({ percent: 0, message: "イラスト設定をアップロード中..." });

        const formData = new FormData();
        if (referenceImage) {
          formData.append("file", referenceImage.file);
        }
        if (illustrationRequest.trim()) {
          formData.append("illustration_request", illustrationRequest.trim());
        }

        // Only upload if there's something to send
        if (referenceImage || illustrationRequest.trim()) {
          const uploadRes = await fetch(`${API_URL}/api/upload-reference-image/${state.jobId}`, {
            method: "POST",
            body: formData,
          });

          if (!uploadRes.ok) {
            console.warn("[Illustration Settings] Upload failed, continuing without reference");
          } else {
            console.log("[Illustration Settings] Uploaded successfully");
          }
        }
      }

      const headers: HeadersInit = {
        "Content-Type": "application/json",
        ...getAPIHeaders()
      };
      if (selectedColorTheme) {
        (headers as Record<string, string>)["x-color-theme"] = selectedColorTheme;
      }
      if (selectedFontStyle) {
        (headers as Record<string, string>)["x-font-style"] = selectedFontStyle;
      }

      // Use batch endpoint (returns immediately, runs in background)
      const res = await fetch(`${API_URL}/api/generate-slides-batch/${state.jobId}`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          start_slide: startSlide,
          batch_size: 5,
          design_preference: designPreference || "",
          text_density: textDensity,
          add_illustrations: addIllustrations,
          illustration_percentage: illustrationPercentage,
        })
      });

      const initData = await res.json();
      if (!res.ok) throw new Error(initData.detail || "Failed to start slide generation");

      console.log(`[Async] Started batch generation, polling for status...`);

      // Single polling interval for batch status (5 seconds to avoid timeout)
      const pollInterval = setInterval(async () => {
        try {
          // Also poll queue status for waiting indicator
          try {
            const queueRes = await fetch(`${API_URL}/api/queue-status/${state.jobId}`, {
              headers: getAPIHeaders()
            });
            if (queueRes.ok) {
              const queueData = await queueRes.json();
              setQueueStatus({
                position: queueData.position,
                status: queueData.status,
                estimatedWait: queueData.estimated_wait_minutes,
                activeCount: queueData.active_count,
                waitingCount: queueData.waiting_count
              });
            }
          } catch (e) {
            // Queue status is optional, don't fail on error
          }

          const statusRes = await fetchWithRetry(`${API_URL}/api/batch-status/${state.jobId}`, {
            headers: getAPIHeaders()
          });

          if (!statusRes.ok) {
            console.log(`[Poll] Status check failed: ${statusRes.status}`);
            return; // Skip this poll, try again next interval
          }

          const statusData = await statusRes.json();

          // Update progress
          if (statusData.total > 0) {
            setProgress({
              percent: (statusData.current / statusData.total) * 100,
              message: statusData.message
            });
          }

          // Check if complete or error
          if (statusData.status === "complete") {
            clearInterval(pollInterval);

            // Update batch state
            setBatchState({
              isComplete: statusData.is_complete,
              nextStart: statusData.next_start,
              slidesCompleted: statusData.batch_end,
              totalSlides: statusData.total_slides
            });

            setProgress({
              percent: (statusData.batch_end / statusData.total_slides) * 100,
              message: `スライド ${statusData.batch_start}-${statusData.batch_end} 完了`
            });

            updateState({
              slideCount: statusData.batch_end,
              slidePreviews: statusData.slide_previews.map((p: string) => `${API_URL}${p}`),
              step: statusData.is_complete ? 6 as Step : 5 as Step,
              isProcessing: !statusData.is_complete,
            });
            setSelectedSlide(null);
            setSlideFeedback("");

            // Auto-continue to next batch if not complete
            if (!statusData.is_complete && statusData.next_start) {
              console.log(`[AutoBatch] Continuing to batch starting at slide ${statusData.next_start}`);
              setTimeout(() => {
                handleGenerateSlides(statusData.next_start);
              }, 2000);
            }
          } else if (statusData.status === "error") {
            clearInterval(pollInterval);
            updateState({ error: statusData.message || "Slide generation failed", isProcessing: false });
          }
          // If still "processing", continue polling
        } catch (pollErr: any) {
          // Don't stop polling on fetch errors - just log and retry
          console.log(`[Poll] Error: ${pollErr.message}, will retry...`);
        }
      }, 5000); // Poll every 5 seconds (reduced from 2s to prevent timeout)

    } catch (err: any) {
      updateState({ error: err.message, isProcessing: false });
    }
  };

  // Slide Feedback: Regenerate a slide based on user feedback
  const handleSlideFeedback = async (type: string = "general") => {
    if (!selectedSlide) return;

    // For general/copy/layout updates, need text feedback. For image regen, feedback is optional but recommended.
    // If regenerating image, we allow empty feedback if user just wants "new variant"
    const isImageRegen = type === "image" || type === "regenerate_image";
    if (!isImageRegen && !slideFeedback.trim() && !slideImage.file) return;

    setIsRegenerating(true);

    try {
      // Convert image to base64 if present
      let imageBase64: string | null = null;
      if (slideImage.file) {
        const buffer = await slideImage.file.arrayBuffer();
        const bytes = new Uint8Array(buffer);
        let binary = '';
        bytes.forEach(byte => binary += String.fromCharCode(byte));
        imageBase64 = btoa(binary);
      }

      const res = await fetch(`${API_URL}/api/slides/${state.jobId}/feedback`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...getAPIHeaders()
        },
        body: JSON.stringify({
          slide_number: selectedSlide,
          feedback: slideFeedback || (isImageRegen ? "Create a variation" : "Fix this"),
          feedback_type: slideImage.file ? "add_image" : type,
          image_base64: imageBase64,
          image_filename: slideImage.file?.name || null,
        })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Feedback failed");

      // Update the slide preview with cache buster
      const newPreviews = [...state.slidePreviews];
      newPreviews[selectedSlide - 1] = `${API_URL}${data.preview_url}`;
      updateState({ slidePreviews: newPreviews });

      // Update undo state
      if (data.can_undo !== undefined) {
        setSlideCanUndo(prev => ({ ...prev, [selectedSlide]: data.can_undo }));
      }

      setSlideFeedback("");
      setSlideImage({ file: null, preview: null });

      // Step 10 (完成画面): スライド変更後、動画を自動再生成
      if (state.step === 10) {
        setSelectedSlide(null);
        setIsRegenerating(false);
        // 少し待ってから自動で動画再生成を開始
        setTimeout(() => {
          handleGenerateVideo();
        }, 500);
        return;
      }
    } catch (err: any) {
      updateState({ error: err.message });
    } finally {
      setIsRegenerating(false);
    }
  };

  // Image Regeneration: Regenerate only the AI illustration for a slide
  const handleImageRegenerate = async () => {
    if (!selectedSlide || !slideFeedback.trim()) return;

    setIsRegenerating(true);

    try {
      const res = await fetch(`${API_URL}/api/slides/${state.jobId}/regenerate-image`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...getAPIHeaders()
        },
        body: JSON.stringify({
          slide_number: selectedSlide,
          feedback: slideFeedback
        })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Image regeneration failed");

      // Update the slide preview with cache buster
      const newPreviews = [...state.slidePreviews];
      newPreviews[selectedSlide - 1] = `${API_URL}${data.preview_url}`;
      updateState({ slidePreviews: newPreviews });

      setSlideFeedback("");
    } catch (err: any) {
      updateState({ error: err.message });
    } finally {
      setIsRegenerating(false);
    }
  };

  // Slide Undo: Restore previous version
  const handleSlideUndo = async () => {
    if (!selectedSlide || !slideCanUndo[selectedSlide]) return;

    setIsUndoing(true);

    try {
      const res = await fetch(`${API_URL}/api/slides/${state.jobId}/undo/${selectedSlide}`, {
        method: "POST",
        headers: getAPIHeaders()
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Undo failed");

      // Update the slide preview
      const newPreviews = [...state.slidePreviews];
      newPreviews[selectedSlide - 1] = `${API_URL}${data.preview_url}`;
      updateState({ slidePreviews: newPreviews });

      // Update undo state
      setSlideCanUndo(prev => ({ ...prev, [selectedSlide]: data.can_undo }));

    } catch (err: any) {
      updateState({ error: err.message });
    } finally {
      setIsUndoing(false);
    }
  };

  // Step 8: Upload Slides (single file or multiple images)
  const handleUploadSlides = async (files: FileList | File[]) => {
    updateState({ isProcessing: true });

    const fileArray = Array.from(files);
    const formData = new FormData();

    // Check if it's a PDF or multiple images
    if (fileArray.length === 1 && fileArray[0].name.endsWith(".pdf")) {
      formData.append("file", fileArray[0]);
      formData.append("file_type", "pdf");
    } else {
      // Multiple images - append all
      fileArray.forEach((file, i) => {
        formData.append("files", file);
      });
      formData.append("file_type", "images");
    }

    try {
      const res = await fetch(`${API_URL}/api/upload-slides/${state.jobId}`, {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Slide upload failed");

      updateState({
        slideCount: data.slide_count,
        slidePreviews: data.slide_previews,
        step: 8,
        isProcessing: false,
      });
    } catch (err: any) {
      updateState({ error: err.message, isProcessing: false });
    }
  };

  // Step 9: AI Mapping
  const handleMapSlides = async () => {
    updateState({ isProcessing: true });

    try {
      const res = await fetch(`${API_URL}/api/map-slides/${state.jobId}`, {
        method: "POST",
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Mapping failed");

      updateState({
        timingMap: data.timing_map,
        step: 9,
        isProcessing: false,
      });
    } catch (err: any) {
      updateState({ error: err.message, isProcessing: false });
    }
  };

  // Step 10: Generate Video (with edited timing if available)
  const handleGenerateVideo = async () => {
    updateState({ isProcessing: true });

    try {
      // Send edited timing map if available
      const body = state.timingMap.length > 0
        ? JSON.stringify({ timing_map: state.timingMap })
        : undefined;

      const res = await fetch(`${API_URL}/api/generate-video/${state.jobId}`, {
        method: "POST",
        headers: body ? { "Content-Type": "application/json" } : undefined,
        body,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Video generation failed");

      updateState({
        videoUrl: `${API_URL}${data.video_url}?t=${Date.now()}`,
        step: 10,
        isProcessing: false,
        // timing_mapをバックエンドから取得（タイムライン編集用）
        ...(data.timing_map ? { timingMap: data.timing_map } : {}),
      });
    } catch (err: any) {
      updateState({ error: err.message, isProcessing: false });
    }
  };

  // Delete a slide from the timing map
  const handleDeleteSlide = (slideIndex: number) => {
    if (state.timingMap.length <= 1) {
      // Cannot delete if only one slide remains
      return;
    }

    const newTimingMap = [...state.timingMap];
    const deletedSlide = newTimingMap[slideIndex];
    const deletedDuration = (deletedSlide.end_time || 0) - (deletedSlide.start_time || 0);

    // Remove the slide
    newTimingMap.splice(slideIndex, 1);

    // Extend the previous slide's duration (or next if first slide deleted)
    if (slideIndex > 0) {
      // Extend previous slide
      newTimingMap[slideIndex - 1].end_time = (newTimingMap[slideIndex - 1].end_time || 0) + deletedDuration;
    } else if (newTimingMap.length > 0) {
      // First slide deleted - adjust start times of remaining slides
      newTimingMap[0].start_time = 0;
    }

    // Recalculate continuous timing and renumber slides
    for (let i = 0; i < newTimingMap.length; i++) {
      newTimingMap[i].slide_number = i + 1;
      if (i > 0) {
        newTimingMap[i].start_time = newTimingMap[i - 1].end_time;
      }
    }

    // Also remove from slidePreviews if applicable
    const newPreviews = [...state.slidePreviews];
    if (slideIndex < newPreviews.length) {
      newPreviews.splice(slideIndex, 1);
    }

    updateState({
      timingMap: newTimingMap,
      slidePreviews: newPreviews
    });
  };

  // Timeline drag handlers for adjusting slide boundaries
  const handleBoundaryDragStart = (boundaryIndex: number) => {
    setDraggingBoundary(boundaryIndex);
  };

  const handleBoundaryDrag = useCallback((e: MouseEvent) => {
    if (draggingBoundary === null || !timelineRef.current) return;

    const rect = timelineRef.current.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const percentage = Math.max(0, Math.min(1, mouseX / rect.width));

    const totalDuration = state.timingMap[state.timingMap.length - 1]?.end_time || 1;
    const newTime = percentage * totalDuration;

    // Get the slides on each side of this boundary
    const leftSlide = state.timingMap[draggingBoundary];
    const rightSlide = state.timingMap[draggingBoundary + 1];

    if (!leftSlide || !rightSlide) return;

    // Minimum 3 seconds per slide
    const minDuration = 3;
    const minLeftEnd = leftSlide.start_time + minDuration;
    const maxLeftEnd = rightSlide.end_time - minDuration;

    const clampedTime = Math.max(minLeftEnd, Math.min(maxLeftEnd, newTime));

    // Update timing map
    const newTimingMap = [...state.timingMap];
    newTimingMap[draggingBoundary].end_time = clampedTime;
    newTimingMap[draggingBoundary + 1].start_time = clampedTime;

    updateState({ timingMap: newTimingMap });
  }, [draggingBoundary, state.timingMap]);

  const handleBoundaryDragEnd = useCallback(() => {
    setDraggingBoundary(null);
  }, []);

  // Add/remove mouse listeners when dragging
  useEffect(() => {
    if (draggingBoundary !== null) {
      document.addEventListener('mousemove', handleBoundaryDrag);
      document.addEventListener('mouseup', handleBoundaryDragEnd);
      return () => {
        document.removeEventListener('mousemove', handleBoundaryDrag);
        document.removeEventListener('mouseup', handleBoundaryDragEnd);
      };
    }
  }, [draggingBoundary, handleBoundaryDrag, handleBoundaryDragEnd]);

  const handleReset = () => {
    setState({
      jobId: null,
      step: 1,
      workflowMode: null,
      transcript: "",
      polishedTranscript: "",
      outline: null,
      polishedOutline: null,
      slideCount: 0,
      slidePreviews: [],
      timingMap: [],
      videoUrl: null,
      isProcessing: false,
      error: null,
      cleanupInfo: null,
    });
    setEditText("");
    setIsEditingTranscript(false);
    setEditedTranscript("");
  };

  // 前のステップに戻る（状態を適切にリセット）
  const goToPreviousStep = () => {
    if (state.step > 1 && !state.isProcessing) {
      const targetStep = (state.step - 1) as Step;

      // 戻る先のステップに応じて、それ以降のデータをクリア
      // ポイント: targetStepに必要なデータは保持し、それ以降のステップで生成されたデータのみクリア
      const resetData: Partial<typeof state> = {
        step: targetStep,
        error: null,
      };

      // Step 1に戻る: モード選択に戻る
      if (targetStep === 1) {
        resetData.workflowMode = null;
      }

      // Step 2以前に戻る: Step 3以降のデータをクリア（文字起こしは残す）
      // → Step 2は音声アップロード済み状態なのでtranscript, polishedTranscriptは保持

      // Step 3以前に戻る: Step 4以降のデータをクリア
      if (targetStep < 4) {
        resetData.outline = null;
        resetData.polishedOutline = null;
      }

      // Step 5以前に戻る（フルAIモード）: Step 6以降のデータをクリア
      if (targetStep < 6) {
        // スライド情報はStep 6で生成されるのでクリア
        // ただしハイブリッドモードでStep 7-8でアップロードする場合は別
        if (state.workflowMode === "full-ai") {
          resetData.slideCount = 0;
          resetData.slidePreviews = [];
        }
      }

      // Step 8以前に戻る（ハイブリッドモード）: スライド情報をクリア
      if (targetStep < 8 && state.workflowMode === "hybrid") {
        resetData.slideCount = 0;
        resetData.slidePreviews = [];
      }

      // Step 9以前に戻る: タイミングマップをクリア
      if (targetStep < 9) {
        resetData.timingMap = [];
      }

      // Step 10以前に戻る: 動画をクリア
      if (targetStep < 10) {
        resetData.videoUrl = null;
      }

      updateState(resetData);
    }
  };

  // 動画をダウンロードフォルダに保存する関数
  const handleDownloadVideo = async (url: string, filename: string) => {
    try {
      const response = await fetch(url);
      if (!response.ok) throw new Error('Download failed');
      const blob = await response.blob();
      const blobUrl = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = blobUrl;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(blobUrl);
    } catch (error) {
      console.error('Download error:', error);
      // フォールバック: 新しいタブで開く
      window.open(url, '_blank');
    }
  };

  const formatOutlineForCopy = () => {
    const outline = state.polishedOutline || state.outline;
    if (!outline) return "";

    let text = `# ${outline.presentation_title || outline.title || "プレゼンテーション"}\n\n`;

    const totalDuration = outline.total_duration;
    if (totalDuration) {
      const min = Math.floor(totalDuration / 60);
      const sec = Math.floor(totalDuration % 60);
      text += `**音声の長さ**: ${min}分${sec}秒\n\n`;
    }

    text += `---\n\n`;

    (outline.slides || []).forEach((slide: any) => {
      // タイムスタンプ
      const start = slide.timestamp_start || 0;
      const end = slide.timestamp_end || 0;
      const startStr = `${String(Math.floor(start / 60)).padStart(2, '0')}:${String(Math.floor(start % 60)).padStart(2, '0')}`;
      const endStr = `${String(Math.floor(end / 60)).padStart(2, '0')}:${String(Math.floor(end % 60)).padStart(2, '0')}`;
      const duration = end - start;

      // slide_copyから情報を取得（新形式）
      const slideCopy = slide.slide_copy || {};
      const headline = slideCopy.headline || slide.title || `スライド ${slide.number}`;
      const subheadline = slideCopy.subheadline || "";
      const bulletPoints = slideCopy.bullet_points || [];
      const keyMessage = slideCopy.key_message || "";

      text += `## スライド ${slide.number}\n`;
      text += `**⏱️ ${startStr} - ${endStr}** (${duration.toFixed(0)}秒間)\n\n`;

      // 見出し
      text += `### 📌 見出し\n`;
      text += `**${headline}**\n`;
      if (subheadline) {
        text += `*${subheadline}*\n`;
      }
      text += `\n`;

      // キーメッセージ
      if (keyMessage) {
        text += `### 💡 キーメッセージ\n`;
        text += `> ${keyMessage}\n\n`;
      }

      // 箇条書き
      if (bulletPoints.length > 0) {
        text += `### 📝 ポイント\n`;
        bulletPoints.forEach((point: string) => {
          text += `- ${point}\n`;
        });
        text += `\n`;
      }

      // キーワード
      const keywords = slide.keywords || [];
      if (keywords.length > 0) {
        text += `**🔑 キーワード**: ${keywords.join(', ')}\n\n`;
      }

      // ビジュアル提案
      const visualSuggestion = slide.visual_suggestion || {};
      if (visualSuggestion.type || visualSuggestion.description) {
        text += `### 🎨 ビジュアル提案\n`;
        if (visualSuggestion.type) {
          text += `- タイプ: ${visualSuggestion.type}\n`;
        }
        if (visualSuggestion.description) {
          text += `- 内容: ${visualSuggestion.description}\n`;
        }
        text += `\n`;
      }

      // 話し手の言葉
      if (slide.speakers_words) {
        text += `💬 **この時間帯の発言**:\n`;
        text += `「${slide.speakers_words}」\n\n`;
      }

      text += `---\n\n`;
    });
    return text;
  };

  // OP/ED video concatenation
  const handleConcatVideo = async () => {
    if (!introVideo && !outroVideo) {
      alert("オープニングまたはエンディング動画を選択してください");
      return;
    }

    setIsConcatenating(true);
    setConcatVideoUrl(null);

    try {
      const formData = new FormData();
      if (introVideo) {
        formData.append("intro_video", introVideo);
      }
      if (outroVideo) {
        formData.append("outro_video", outroVideo);
      }

      const res = await fetch(`${API_URL}/api/concat-video/${state.jobId}`, {
        method: "POST",
        headers: getAPIHeaders(),
        body: formData
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "動画結合エラー");

      setConcatVideoUrl(`${API_URL}${data.video_url}`);
      alert("OP/ED動画を結合しました！");
    } catch (err: any) {
      alert(`エラー: ${err.message}`);
    } finally {
      setIsConcatenating(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col">
      <Header />

      {/* API Keys Settings Modal */}
      {showSettings && <APIKeysSettings onClose={() => setShowSettings(false)} />}

      {/* Slide Zoom Modal */}
      {zoomedSlide !== null && state.slidePreviews.length > 0 && (
        <div
          className="fixed inset-0 bg-black/90 z-50 flex items-center justify-center p-4"
          onClick={() => setZoomedSlide(null)}
        >
          {/* Close button */}
          <button
            className="absolute top-4 right-4 text-white/80 hover:text-white text-3xl"
            onClick={() => setZoomedSlide(null)}
          >
            ✕
          </button>

          {/* Slide counter */}
          <div className="absolute top-4 left-1/2 -translate-x-1/2 text-white/80 text-lg">
            スライド {zoomedSlide + 1} / {state.slidePreviews.length}
          </div>

          {/* Previous button */}
          {zoomedSlide > 0 && (
            <button
              className="absolute left-4 top-1/2 -translate-y-1/2 text-white/60 hover:text-white text-5xl transition-colors"
              onClick={(e) => { e.stopPropagation(); setZoomedSlide(zoomedSlide - 1); }}
            >
              ‹
            </button>
          )}

          {/* Slide image */}
          <img
            src={state.slidePreviews[zoomedSlide]}
            alt={`Slide ${zoomedSlide + 1}`}
            className="max-w-full max-h-[85vh] rounded-lg shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          />

          {/* Next button */}
          {zoomedSlide < state.slidePreviews.length - 1 && (
            <button
              className="absolute right-4 top-1/2 -translate-y-1/2 text-white/60 hover:text-white text-5xl transition-colors"
              onClick={(e) => { e.stopPropagation(); setZoomedSlide(zoomedSlide + 1); }}
            >
              ›
            </button>
          )}

          {/* Thumbnail strip */}
          <div className="absolute bottom-4 left-1/2 -translate-x-1/2 flex gap-2 max-w-full overflow-x-auto px-4">
            {state.slidePreviews.map((preview, i) => (
              <img
                key={i}
                src={preview}
                alt={`Thumbnail ${i + 1}`}
                onClick={(e) => { e.stopPropagation(); setZoomedSlide(i); }}
                className={`h-16 rounded cursor-pointer transition-all ${i === zoomedSlide ? 'ring-2 ring-cyan-500 opacity-100' : 'opacity-50 hover:opacity-80'
                  }`}
              />
            ))}
          </div>
        </div>
      )}

      <main className="flex-1 container mx-auto px-4 py-8 max-w-5xl">
        {/* Settings Button */}
        <div className="flex justify-end mb-4">
          <button
            onClick={() => setShowSettings(true)}
            className={`px-4 py-2 rounded-lg text-sm flex items-center gap-2 transition-all ${hasKeys
              ? "bg-zinc-800 hover:bg-zinc-700 text-zinc-300"
              : "bg-yellow-600/20 hover:bg-yellow-600/30 text-yellow-400 border border-yellow-600/50"
              }`}
          >
            🔑 {hasKeys ? "APIキー設定" : "APIキーを設定してください"}
          </button>
        </div>

        {/* Progress with Back Button */}
        <div className="mb-8">
          {/* Back Button - Temporarily disabled for stable release
          {state.step > 1 && (
            <div className="mb-3">
              <button
                onClick={goToPreviousStep}
                disabled={state.isProcessing}
                className="flex items-center gap-2 text-zinc-400 hover:text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <span className="text-lg">←</span>
                <span className="text-sm">前のステップに戻る</span>
              </button>
            </div>
          )}
          */}

          {/* Progress Steps */}
          <div className="overflow-x-auto">
            <div className="flex items-center min-w-max">
              {STEPS.map((step, i) => (
                <div key={step.id} className="flex items-center">
                  <div
                    className={`flex flex-col items-center ${state.step >= step.id ? "opacity-100" : "opacity-40"
                      }`}
                  >
                    <div
                      className={`w-10 h-10 rounded-full flex items-center justify-center text-lg mb-1 ${state.step > step.id
                        ? "bg-green-500"
                        : state.step === step.id
                          ? "bg-cyan-500 animate-pulse"
                          : "bg-zinc-700"
                        }`}
                    >
                      {state.step > step.id ? "✓" : step.icon}
                    </div>
                    <span className="text-xs text-zinc-400 whitespace-nowrap">{step.label}</span>
                  </div>
                  {i < STEPS.length - 1 && (
                    <div
                      className={`w-8 h-0.5 mx-1 ${state.step > step.id ? "bg-green-500" : "bg-zinc-700"
                        }`}
                    />
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Error */}
        {state.error && (
          <div className="glass rounded-xl p-4 mb-6 border-l-4 border-red-500">
            <p className="text-red-400">❌ {state.error}</p>
            <button onClick={handleReset} className="btn-secondary mt-2 text-sm">
              やり直す
            </button>
          </div>
        )}

        {/* Content */}
        <div className="glass rounded-2xl p-8">
          {/* Step 1: Mode Selection + Upload Audio */}
          {state.step === 1 && (
            <div>
              {/* Mode Selection */}
              {!state.workflowMode && (
                <div className="mb-8">
                  <h2 className="text-2xl font-bold mb-6 gradient-text">ワークフローを選択</h2>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {/* Hybrid Mode */}
                    <button
                      onClick={() => updateState({ workflowMode: "hybrid" })}
                      className="p-6 rounded-xl border-2 border-zinc-700 hover:border-cyan-500 transition-all text-left group"
                    >
                      <div className="text-4xl mb-4">📥 + 🤖</div>
                      <h3 className="text-xl font-bold mb-2 group-hover:text-cyan-400">ハイブリッドモード</h3>
                      <p className="text-sm text-zinc-400 mb-4">
                        自分でスライドを作成し、AIが音声と同期
                      </p>
                      <div className="text-xs text-zinc-500">
                        <div>✅ 自分のデザインを使いたい</div>
                        <div>✅ 既存のスライドがある</div>
                        <div>✅ 細かいコントロールが欲しい</div>
                      </div>
                    </button>

                    {/* Full AI Mode */}
                    <button
                      onClick={() => updateState({ workflowMode: "full-ai" })}
                      className="p-6 rounded-xl border-2 border-zinc-700 hover:border-purple-500 transition-all text-left group"
                    >
                      <div className="text-4xl mb-4">🎨 ✨</div>
                      <h3 className="text-xl font-bold mb-2 group-hover:text-purple-400">フルAIモード</h3>
                      <p className="text-sm text-zinc-400 mb-4">
                        AIがスライドも自動生成して動画を完成
                      </p>
                      <div className="text-xs text-zinc-500">
                        <div>✅ 手軽に動画を作りたい</div>
                        <div>✅ 時間がない</div>
                        <div>✅ AIにお任せしたい</div>
                      </div>
                    </button>
                  </div>
                </div>
              )}

              {/* Audio Upload (after mode selection) */}
              {state.workflowMode && (
                <>
                  <div className="flex items-center justify-between mb-6">
                    <h2 className="text-2xl font-bold gradient-text">音声ファイルをアップロード</h2>
                    <button
                      onClick={() => updateState({ workflowMode: null })}
                      className="text-sm text-zinc-500 hover:text-zinc-300"
                    >
                      ← モード変更
                    </button>
                  </div>
                  <div className="mb-4 p-3 rounded-lg bg-zinc-800/50 flex items-center gap-3">
                    <span className="text-2xl">{state.workflowMode === "hybrid" ? "📥" : "🎨"}</span>
                    <span className="text-sm text-zinc-400">
                      {state.workflowMode === "hybrid"
                        ? "ハイブリッドモード：スライドを後でアップロード"
                        : "フルAIモード：スライドもAIが自動生成"}
                    </span>
                  </div>
                  <label
                    className={`upload-zone flex flex-col items-center justify-center w-full h-48 rounded-xl cursor-pointer transition-all ${isDragging ? 'border-cyan-500 bg-cyan-500/10 scale-[1.02]' : ''}`}
                    onDragEnter={handleDragEnter}
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    onDrop={(e) => {
                      e.preventDefault();
                      setIsDragging(false);
                      const files = e.dataTransfer.files;
                      if (files?.[0]) {
                        const ext = files[0].name.split('.').pop()?.toLowerCase();
                        if (['mp3', 'wav', 'm4a'].includes(ext || '')) {
                          handleUploadAudio(files[0]);
                        } else {
                          updateState({ error: '対応形式: MP3, WAV, M4A' });
                        }
                      }
                    }}
                  >
                    <span className="text-5xl mb-4">{isDragging ? '📎' : '🎙️'}</span>
                    <p className="text-lg">{isDragging ? 'ここにドロップ！' : '音声ファイルをドラッグ&ドロップ'}</p>
                    <p className="text-sm text-zinc-500">MP3, WAV, M4A対応</p>
                    <input
                      type="file"
                      accept=".mp3,.wav,.m4a"
                      className="hidden"
                      onChange={(e) => e.target.files?.[0] && handleUploadAudio(e.target.files[0])}
                      disabled={state.isProcessing}
                    />
                  </label>
                </>
              )}
            </div>
          )}
          {/* Step 2: Transcribe */}
          {state.step === 2 && !state.transcript && (
            <div className="text-center">
              <h2 className="text-2xl font-bold mb-6 gradient-text">文字起こし</h2>

              {/* Audio Cleanup Settings */}
              <div className="bg-zinc-800/50 rounded-xl p-4 mb-6 max-w-md mx-auto text-left">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-sm font-medium">🔇 無音・フィラー除去</span>
                  <button
                    onClick={() => setAudioSettings(prev => ({ ...prev, cleanupEnabled: !prev.cleanupEnabled }))}
                    className={`w-12 h-6 rounded-full transition-all relative ${audioSettings.cleanupEnabled ? 'bg-cyan-500' : 'bg-zinc-600'
                      }`}
                  >
                    <span className={`absolute w-5 h-5 bg-white rounded-full top-0.5 transition-all ${audioSettings.cleanupEnabled ? 'left-6' : 'left-0.5'
                      }`} />
                  </button>
                </div>

                {audioSettings.cleanupEnabled && (
                  <div className="mt-4 grid grid-cols-2 gap-3">
                    <button
                      onClick={() => setAudioSettings(prev => ({ ...prev, cleanupMode: "natural", silenceThreshold: 0.8 }))}
                      className={`p-3 rounded-lg border text-left transition-all relative overflow-hidden ${audioSettings.cleanupMode === "natural"
                        ? "border-emerald-500 bg-emerald-500/10 text-emerald-100"
                        : "border-zinc-700 bg-zinc-800 text-zinc-400 hover:border-zinc-600"
                        }`}
                    >
                      <div className="text-sm font-bold mb-1">😌 ナチュラル</div>
                      <div className="text-[10px] opacity-70 leading-tight">自然な間を残してカット</div>
                      {audioSettings.cleanupMode === "natural" && (
                        <div className="absolute top-2 right-2 w-2 h-2 rounded-full bg-emerald-500 shadow-[0_0_10px_#10b981]" />
                      )}
                    </button>

                    <button
                      onClick={() => setAudioSettings(prev => ({ ...prev, cleanupMode: "strict", silenceThreshold: 0.5 }))}
                      className={`p-3 rounded-lg border text-left transition-all relative overflow-hidden ${audioSettings.cleanupMode === "strict"
                        ? "border-cyan-500 bg-cyan-500/10 text-cyan-100"
                        : "border-zinc-700 bg-zinc-800 text-zinc-400 hover:border-zinc-600"
                        }`}
                    >
                      <div className="text-sm font-bold mb-1">⚡️ クッキリ</div>
                      <div className="text-[10px] opacity-70 leading-tight">間を詰めてテンポアップ</div>
                      {audioSettings.cleanupMode === "strict" && (
                        <div className="absolute top-2 right-2 w-2 h-2 rounded-full bg-cyan-500 shadow-[0_0_10px_#06b6d4]" />
                      )}
                    </button>
                  </div>
                )}

                {/* Sensitivity Slider */}
                {audioSettings.cleanupEnabled && (
                  <div className="mt-4 bg-zinc-900/50 rounded-lg p-3">
                    <div className="flex justify-between text-xs text-zinc-400 mb-2">
                      <span>敏感さ調整</span>
                      <span className="text-zinc-500">{audioSettings.silenceThreshold.toFixed(1)}秒以上を無音と判定</span>
                    </div>
                    <input
                      type="range"
                      min="0.3"
                      max="1.0"
                      step="0.1"
                      value={audioSettings.silenceThreshold}
                      onChange={(e) => setAudioSettings(prev => ({ ...prev, silenceThreshold: parseFloat(e.target.value) }))}
                      className="w-full h-2 bg-zinc-700 rounded-lg appearance-none cursor-pointer accent-cyan-500"
                    />
                    <div className="flex justify-between text-[10px] text-zinc-600 mt-1">
                      <span>敏感（短い無音もカット）</span>
                      <span>鈍感（長い無音のみカット）</span>
                    </div>
                  </div>
                )}
              </div>

              {/* BGM Section - Simplified (toggle + upload only) */}
              {state.jobId && (
                <div className="bg-zinc-800/50 rounded-xl p-4 mb-6 max-w-md mx-auto">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <span className="text-lg">🎵</span>
                      <span className="text-sm font-medium">BGM追加（オプション）</span>
                    </div>
                    <button
                      onClick={() => {
                        setBgmEnabled(!bgmEnabled);
                        if (bgmEnabled) {
                          setBgmFile(null);
                          setBgmMixed(false);
                        }
                      }}
                      className={`w-12 h-6 rounded-full transition-all relative ${bgmEnabled ? 'bg-purple-500' : 'bg-zinc-600'}`}
                    >
                      <span className={`absolute w-5 h-5 bg-white rounded-full top-0.5 transition-all ${bgmEnabled ? 'left-6' : 'left-0.5'}`} />
                    </button>
                  </div>

                  {bgmEnabled && (
                    <div>
                      {/* BGM Upload */}
                      {!bgmFile ? (
                        <label className="block w-full py-3 px-4 border-2 border-dashed border-zinc-600 rounded-lg cursor-pointer hover:border-purple-500 transition-colors text-center">
                          <span className="text-sm text-zinc-400">🎶 BGM音源をアップロード (MP3/WAV)</span>
                          <input
                            type="file"
                            accept="audio/*"
                            className="hidden"
                            onChange={async (e) => {
                              const file = e.target.files?.[0];
                              if (file) {
                                setBgmFile(file);
                                // Upload to backend
                                const formData = new FormData();
                                formData.append('file', file);
                                try {
                                  await fetch(
                                    `${API_URL}/api/audio/${state.jobId}/upload-bgm`,
                                    { method: 'POST', body: formData }
                                  );
                                } catch (err) {
                                  console.error('BGM upload error:', err);
                                }
                              }
                            }}
                          />
                        </label>
                      ) : (
                        <div className="space-y-3">
                          <div className="flex items-center justify-between p-2 bg-zinc-700 rounded-lg">
                            <div className="flex items-center gap-2">
                              <span className="text-green-400">✓</span>
                              <span className="text-sm truncate">{bgmFile.name}</span>
                            </div>
                            <button
                              onClick={() => setBgmFile(null)}
                              className="text-zinc-400 hover:text-white text-sm"
                            >変更</button>
                          </div>

                          {/* BGM Playback Mode */}
                          <div className="bg-zinc-900/50 rounded-lg p-3">
                            <div className="text-xs text-zinc-400 mb-2">🎵 再生モード</div>
                            <div className="grid grid-cols-3 gap-2">
                              <button
                                onClick={() => setBgmPlayMode('loop')}
                                className={`py-2 px-2 rounded-lg text-xs transition-all ${bgmPlayMode === 'loop' ? 'bg-purple-500 text-white' : 'bg-zinc-700 text-zinc-300 hover:bg-zinc-600'}`}
                              >
                                🔁 ループ
                              </button>
                              <button
                                onClick={() => setBgmPlayMode('single')}
                                className={`py-2 px-2 rounded-lg text-xs transition-all ${bgmPlayMode === 'single' ? 'bg-purple-500 text-white' : 'bg-zinc-700 text-zinc-300 hover:bg-zinc-600'}`}
                              >
                                ▶️ 1曲
                              </button>
                              <button
                                onClick={() => setBgmPlayMode('minute')}
                                className={`py-2 px-2 rounded-lg text-xs transition-all ${bgmPlayMode === 'minute' ? 'bg-purple-500 text-white' : 'bg-zinc-700 text-zinc-300 hover:bg-zinc-600'}`}
                              >
                                ⏱️ 1分
                              </button>
                            </div>
                            <p className="text-[10px] text-zinc-500 mt-2">
                              {bgmPlayMode === 'loop' && 'BGMをループで再生し続けます'}
                              {bgmPlayMode === 'single' && '1曲分再生後にフェードアウト'}
                              {bgmPlayMode === 'minute' && '1分経過時点でフェードアウト'}
                            </p>
                          </div>

                          {/* Fade Settings */}
                          <div className="flex gap-4">
                            <label className="flex items-center gap-2 cursor-pointer">
                              <input
                                type="checkbox"
                                checked={bgmFadeIn}
                                onChange={(e) => setBgmFadeIn(e.target.checked)}
                                className="w-4 h-4 rounded accent-purple-500"
                              />
                              <span className="text-xs text-zinc-300">フェードイン</span>
                            </label>
                            <label className="flex items-center gap-2 cursor-pointer">
                              <input
                                type="checkbox"
                                checked={bgmFadeOut}
                                onChange={(e) => setBgmFadeOut(e.target.checked)}
                                className="w-4 h-4 rounded accent-purple-500"
                              />
                              <span className="text-xs text-zinc-300">フェードアウト</span>
                            </label>
                          </div>
                        </div>
                      )}
                      <p className="text-xs text-zinc-500 mt-2">
                        文字起こし時にBGMをミックスします
                      </p>
                    </div>
                  )}
                </div>
              )}

              <button
                onClick={handleTranscribe}
                disabled={state.isProcessing}
                className="btn-primary"
              >
                {state.isProcessing ? "処理中..." : "📝 文字起こし開始"}
              </button>
              <p className="text-xs text-zinc-500 mt-3">
                {audioSettings.cleanupEnabled
                  ? "✨ 無音区間と「えっと」などのフィラーを自動除去します"
                  : "⚠️ クリーンアップなしで文字起こしします"}
              </p>
            </div>
          )}

          {/* Step 2-3: Transcript Display & Edit */}
          {(state.step === 2 || state.step === 3) && state.transcript && (
            <div>
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-2xl font-bold gradient-text">
                  {state.step === 2 ? "文字起こし結果" : "ブラッシュアップ完了"}
                </h2>
                <div className="flex gap-2">
                  <button
                    onClick={() => setShowScriptInput(!showScriptInput)}
                    className={`text-xs px-3 py-1 rounded-lg transition-all ${showScriptInput
                      ? 'bg-purple-500 text-white'
                      : 'bg-zinc-700 text-zinc-300 hover:bg-zinc-600'
                      }`}
                  >
                    {showScriptInput ? '📖 台本を隠す' : '📄 台本を入力'}
                  </button>
                  <button
                    onClick={() => {
                      setIsEditingTranscript(!isEditingTranscript);
                      if (!isEditingTranscript) setEditedTranscript(editText);
                    }}
                    className={`text-xs px-3 py-1 rounded-lg transition-all ${isEditingTranscript
                      ? 'bg-cyan-500 text-white'
                      : 'bg-zinc-700 text-zinc-300 hover:bg-zinc-600'
                      }`}
                  >
                    {isEditingTranscript ? '✏️ 編集中' : '📝 手動で編集'}
                  </button>
                </div>
              </div>

              {/* Script Input Section (Optional) */}
              {showScriptInput && (
                <div className="mb-4 p-4 bg-purple-500/5 border border-purple-500/20 rounded-xl">
                  <div className="flex justify-between items-center mb-2">
                    <label className="text-sm font-medium text-purple-300">参考台本 (任意)</label>
                    <span className="text-[10px] text-zinc-500">ブラッシュアップ時に用語やスタイルを参考にします</span>
                  </div>
                  <textarea
                    value={scriptText}
                    onChange={(e) => setScriptText(e.target.value)}
                    className="w-full h-32 bg-zinc-900/50 border border-purple-500/30 rounded-lg p-3 text-sm text-white resize-none focus:border-purple-500 focus:ring-1 focus:ring-purple-500/30 transition-all"
                    placeholder="元々の台本や、守ってほしい用語・言い回しを入力してください..."
                  />
                </div>
              )}

              {/* Cleanup Info */}
              {state.cleanupInfo && (
                <div className="mb-4 p-3 rounded-lg bg-green-500/10 border border-green-500/30 text-sm">
                  <span className="text-green-400">✨ クリーンアップ完了:</span>
                  <span className="text-zinc-300 ml-2">
                    無音{state.cleanupInfo.removed_silences || 0}箇所、
                    フィラー{state.cleanupInfo.removed_fillers || 0}箇所を除去
                    （計{(state.cleanupInfo.total_removed_seconds || 0).toFixed(1)}秒短縮）
                  </span>
                </div>
              )}

              {/* Audio Preview & BGM Adjustment */}
              {state.jobId && state.step === 2 && (
                <div className="mb-4 bg-zinc-800/50 rounded-xl p-4">
                  <div className="flex items-center gap-2 mb-3">
                    <span className="text-lg">{bgmMixed ? '🎵' : '🎤'}</span>
                    <span className="text-sm font-medium">
                      {bgmMixed ? 'BGM入り音声' : 'カット済み音声'}
                    </span>
                  </div>

                  {/* Audio Player */}
                  <audio
                    key={bgmMixed ? `mixed-${Date.now()}` : 'trimmed'}
                    controls
                    className="w-full mb-3"
                    src={bgmMixed
                      ? `${API_URL}/api/audio/${state.jobId}/mixed?t=${Date.now()}`
                      : `${API_URL}/api/audio/${state.jobId}/trimmed`
                    }
                  >
                    お使いのブラウザは音声再生に対応していません
                  </audio>

                  {/* BGM Adjustment Controls (only if BGM mixed) */}
                  {bgmMixed && (
                    <div className="space-y-3 mb-3 p-3 bg-zinc-900/50 rounded-lg">
                      <div className="flex justify-between text-xs text-zinc-400">
                        <span>🎛️ BGM音量調整</span>
                        <span className="text-zinc-500">{bgmVolume}dB</span>
                      </div>
                      <input
                        type="range"
                        min="-30"
                        max="-5"
                        step="1"
                        value={bgmVolume}
                        onChange={(e) => setBgmVolume(parseInt(e.target.value))}
                        className="w-full h-2 bg-zinc-700 rounded-lg appearance-none cursor-pointer accent-purple-500"
                      />
                      <div className="flex gap-2">
                        <input
                          type="text"
                          value={bgmFeedback}
                          onChange={(e) => setBgmFeedback(e.target.value)}
                          placeholder="例: BGMをもう少し小さく"
                          className="flex-1 px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm"
                        />
                        <button
                          onClick={async () => {
                            setBgmMixing(true);
                            try {
                              const params = bgmFeedback
                                ? `feedback=${encodeURIComponent(bgmFeedback)}`
                                : `bgm_volume=${bgmVolume}`;
                              await fetch(
                                `${API_URL}/api/audio/${state.jobId}/adjust-bgm?${params}`,
                                { method: 'POST' }
                              );
                              setBgmFeedback('');
                              // Force audio reload
                              setBgmMixed(false);
                              setTimeout(() => setBgmMixed(true), 100);
                            } catch (err) {
                              console.error('BGM adjust error:', err);
                            } finally {
                              setBgmMixing(false);
                            }
                          }}
                          disabled={bgmMixing}
                          className="px-4 py-2 bg-purple-600 hover:bg-purple-500 disabled:bg-zinc-600 text-white rounded-lg text-sm"
                        >
                          {bgmMixing ? '調整中...' : '調整'}
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Download Button */}
                  <button
                    onClick={async (e) => {
                      const btn = e.currentTarget;
                      btn.textContent = '⏳ ダウンロード中...';
                      btn.disabled = true;
                      try {
                        const endpoint = bgmMixed ? 'mixed' : 'trimmed';
                        const res = await fetch(
                          `${API_URL}/api/audio/${state.jobId}/${endpoint}`
                        );
                        if (!res.ok) throw new Error('Download failed');
                        const blob = await res.blob();
                        const url = window.URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url;
                        a.download = `audio_${state.jobId}${bgmMixed ? '_mixed' : ''}.mp3`;
                        document.body.appendChild(a);
                        a.click();
                        document.body.removeChild(a);
                        window.URL.revokeObjectURL(url);
                        btn.innerHTML = '✅ ダウンロード完了！';
                        setTimeout(() => {
                          btn.innerHTML = `<span>⬇️</span><span>${bgmMixed ? 'BGM入り音声をダウンロード' : 'カット済み音声をダウンロード'}</span>`;
                          btn.disabled = false;
                        }, 2000);
                      } catch (err) {
                        console.error('Download error:', err);
                        alert('ダウンロードに失敗しました');
                        btn.innerHTML = `<span>⬇️</span><span>${bgmMixed ? 'BGM入り音声をダウンロード' : 'カット済み音声をダウンロード'}</span>`;
                        btn.disabled = false;
                      }
                    }}
                    className="w-full py-3 px-4 bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 active:scale-[0.98] disabled:opacity-50 text-white font-medium rounded-xl text-sm transition-all flex items-center justify-center gap-2 shadow-lg shadow-cyan-500/20 cursor-pointer"
                  >
                    <span>⬇️</span>
                    <span>{bgmMixed ? 'BGM入り音声をダウンロード' : 'カット済み音声をダウンロード'}</span>
                  </button>
                </div>
              )}

              {isEditingTranscript && (
                <div className="mb-3 p-3 rounded-lg bg-yellow-500/10 border border-yellow-500/30 text-sm">
                  <span className="text-yellow-400">💡 ヒント:</span>
                  <span className="text-zinc-300 ml-2">
                    誤字修正や不要な部分の削除ができます。編集後に次のステップへ進んでください。
                  </span>
                </div>
              )}

              <textarea
                value={editText}
                onChange={(e) => setEditText(e.target.value)}
                className={`w-full h-64 bg-zinc-900 border rounded-xl p-4 text-white resize-none transition-all ${isEditingTranscript
                  ? 'border-cyan-500 ring-2 ring-cyan-500/30'
                  : 'border-zinc-700'
                  }`}
                readOnly={!isEditingTranscript}
                placeholder="文字起こし結果がここに表示されます"
              />
              <div className="flex justify-between items-center mt-4">
                <span className="text-xs text-zinc-500">
                  {editText.length}文字
                </span>
                <div className="flex gap-4">
                  {state.step === 2 && (
                    <button onClick={handlePolishTranscript} disabled={state.isProcessing} className="btn-primary">
                      {state.isProcessing ? "処理中..." : "✨ ブラッシュアップ"}
                    </button>
                  )}
                  {state.step === 3 && (
                    <div className="flex items-center gap-4">
                      {/* Slide count selector */}
                      <select
                        value={slideSettings.mode}
                        onChange={(e) => setSlideSettings(prev => ({ ...prev, mode: e.target.value as any }))}
                        className="bg-zinc-800 text-white px-3 py-2 rounded-lg border border-zinc-600 text-sm"
                      >
                        <option value="auto">📊 自動</option>
                        <option value="fewer">📉 少なめ（5-7枚）</option>
                        <option value="more">📈 多め（15枚以上）</option>
                        <option value="custom">🎯 指定</option>
                      </select>
                      {slideSettings.mode === "custom" && (
                        <input
                          type="number"
                          min="3"
                          max="30"
                          value={slideSettings.customCount}
                          onChange={(e) => setSlideSettings(prev => ({ ...prev, customCount: parseInt(e.target.value) || 10 }))}
                          className="w-16 bg-zinc-800 text-white px-2 py-2 rounded-lg border border-zinc-600 text-sm"
                        />
                      )}
                      <button onClick={handleGenerateOutline} disabled={state.isProcessing} className="btn-primary">
                        {state.isProcessing ? "処理中..." : "📋 アウトライン生成"}
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Step 4-5: Outline */}
          {(state.step === 4 || state.step === 5) && state.outline && (
            <div>
              <h2 className="text-2xl font-bold mb-4 gradient-text">
                {state.step === 4 ? "音声同期アウトライン" : "改善されたアウトライン"}
              </h2>

              {/* 音声一致度スコア */}
              {(state.polishedOutline || state.outline).audio_match_score && (
                <div className="mb-4 flex items-center gap-2">
                  <span className="text-sm text-zinc-400">音声一致度:</span>
                  <span className="px-3 py-1 bg-cyan-500/20 text-cyan-400 rounded-full text-sm font-bold">
                    {(state.polishedOutline || state.outline).audio_match_score}%
                  </span>
                </div>
              )}

              <div className="bg-zinc-900 rounded-xl p-4 max-h-96 overflow-y-auto">
                <h3 className="text-xl font-bold mb-4">
                  {(state.polishedOutline || state.outline).presentation_title || (state.polishedOutline || state.outline).title}
                </h3>
                {((state.polishedOutline || state.outline).slides || []).map((slide: any, i: number) => (
                  <div key={i} className="mb-4 p-4 bg-zinc-800 rounded-lg border-l-4 border-cyan-500">
                    {/* ヘッダー：番号とタイトル */}
                    <div className="flex items-center gap-3 mb-3">
                      <span className="w-8 h-8 bg-cyan-500 rounded-full flex items-center justify-center text-sm font-bold">
                        {slide.number || i + 1}
                      </span>
                      <span className="font-semibold text-lg">
                        {slide.slide_copy?.headline || slide.title || `スライド ${i + 1}`}
                      </span>
                      {slide.energy_level && (
                        <span className="text-lg">
                          {slide.energy_level === 'high' ? '🔥' : slide.energy_level === 'medium' ? '⚡' : '🌊'}
                        </span>
                      )}
                    </div>

                    {/* タイムスタンプ */}
                    {slide.timestamp_start !== undefined && (
                      <div className="text-xs text-cyan-400 mb-2">
                        ⏱️ {String(Math.floor(slide.timestamp_start / 60)).padStart(2, '0')}:
                        {String(Math.floor(slide.timestamp_start % 60)).padStart(2, '0')} -
                        {String(Math.floor(slide.timestamp_end / 60)).padStart(2, '0')}:
                        {String(Math.floor(slide.timestamp_end % 60)).padStart(2, '0')}
                      </div>
                    )}

                    {/* 話し手の言葉 */}
                    {slide.speakers_words && (
                      <div className="text-sm text-zinc-300 italic mb-2 pl-3 border-l-2 border-zinc-600">
                        「{slide.speakers_words}」
                      </div>
                    )}

                    {/* 視覚的役割 */}
                    {slide.visual_role && (
                      <div className="text-sm text-zinc-400 mb-2">
                        <span className="text-zinc-500">視覚的役割:</span> {slide.visual_role}
                      </div>
                    )}

                    {/* キーワード */}
                    {slide.keywords && slide.keywords.length > 0 && (
                      <div className="flex gap-2 flex-wrap mt-2">
                        {slide.keywords.map((kw: string, ki: number) => (
                          <span key={ki} className="px-2 py-1 bg-zinc-700 rounded text-xs">
                            {kw}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
              <div className="flex justify-end gap-4 mt-4">
                {state.step === 4 && (
                  <button onClick={handlePolishOutline} disabled={state.isProcessing} className="btn-primary">
                    {state.isProcessing ? "処理中..." : "🔄 ブラッシュアップ"}
                  </button>
                )}
                {state.step === 5 && state.workflowMode === "hybrid" && (
                  <button onClick={() => updateState({ step: 6 as Step })} className="btn-primary">
                    📤 アウトラインを出力
                  </button>
                )}
              </div>
            </div>
          )}

          {/* Step 6: Export (Hybrid) or Slide Generation (Full AI) */}
          {state.step === 6 && (
            <div>
              {state.workflowMode === "full-ai" ? (
                // フルAIモード: 動画生成へ（スライドは生成済み）
                <div>
                  <h2 className="text-2xl font-bold mb-4 gradient-text">🎨 スライド生成完了</h2>
                  <p className="text-zinc-400 mb-4">
                    AIが{state.slideCount}枚のスライドを自動生成しました。
                  </p>

                  {/* スライドプレビュー（クリックで選択、ダブルクリックで拡大） */}
                  {state.slidePreviews.length > 0 && (
                    <>
                      <p className="text-sm text-zinc-500 mb-2">
                        クリックで選択、ダブルクリックまたは🔍で拡大表示
                      </p>
                      <div className="space-y-4 mb-6">
                        {/* スライドを3つずつの行に分割 */}
                        {Array.from({ length: Math.ceil(state.slidePreviews.length / 3) }, (_, rowIndex) => {
                          const startIdx = rowIndex * 3;
                          const rowSlides = state.slidePreviews.slice(startIdx, startIdx + 3);
                          const rowContainsSelected = selectedSlide && selectedSlide >= startIdx + 1 && selectedSlide <= startIdx + 3;

                          return (
                            <div key={rowIndex}>
                              {/* スライド行 */}
                              <div className="grid grid-cols-3 gap-4">
                                {rowSlides.map((preview, i) => {
                                  const slideNum = startIdx + i + 1;
                                  return (
                                    <div
                                      key={slideNum}
                                      onClick={() => setSelectedSlide(slideNum)}
                                      onDoubleClick={() => setZoomedSlide(startIdx + i)}
                                      className={`rounded-lg overflow-hidden border-2 cursor-pointer transition-all relative group ${selectedSlide === slideNum
                                        ? 'border-amber-500 ring-2 ring-amber-500/50 scale-105'
                                        : 'border-zinc-700 hover:border-zinc-500'
                                        }`}
                                    >
                                      <img
                                        src={preview}
                                        alt={`Slide ${slideNum}`}
                                        className="w-full h-auto"
                                        onError={(e) => {
                                          console.error(`[Image Error] Failed to load: ${preview}`);
                                          e.currentTarget.style.border = "2px solid red";
                                          // e.currentTarget.src = "fallback_image_url"; // Optional
                                        }}
                                      />
                                      <div className="bg-zinc-800 text-center text-xs py-1">
                                        スライド {slideNum}
                                      </div>
                                      <button
                                        onClick={(e) => { e.stopPropagation(); setZoomedSlide(startIdx + i); }}
                                        className="absolute top-2 right-2 bg-black/60 hover:bg-black/80 text-white text-sm px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition-opacity"
                                      >
                                        🔍
                                      </button>
                                    </div>
                                  );
                                })}
                              </div>

                              {/* この行に選択中のスライドがある場合、フィードバック入力を表示 */}
                              {rowContainsSelected && selectedSlide && (
                                <div className="mt-4 bg-zinc-800/50 rounded-xl p-4 border border-amber-500/50 animate-fadeIn">
                                  <h4 className="font-semibold mb-2 text-amber-400">
                                    📝 スライド {selectedSlide} を編集
                                  </h4>
                                  <textarea
                                    value={slideFeedback}
                                    onChange={(e) => setSlideFeedback(e.target.value)}
                                    placeholder="例：タイトルを「価値の創造」に変更。背景をもっと暗く。ポイントを3つに減らして..."
                                    className="w-full h-20 bg-zinc-900 border border-zinc-700 rounded-lg p-3 text-white resize-none mb-2"
                                    autoFocus
                                  />

                                  {/* フィードバック定型文ボタン */}
                                  <div className="flex flex-wrap gap-1 mb-3">
                                    <button
                                      onClick={() => setSlideFeedback(prev => prev + (prev ? '\n' : '') + 'レイアウトを再構築してください')}
                                      className="text-[10px] bg-zinc-700/50 hover:bg-zinc-600/50 text-zinc-300 px-2 py-1 rounded-md transition-colors"
                                    >
                                      📐 レイアウト再構築
                                    </button>
                                    <button
                                      onClick={() => setSlideFeedback(prev => prev + (prev ? '\n' : '') + 'タイトルを「〇〇」に変更してください')}
                                      className="text-[10px] bg-zinc-700/50 hover:bg-zinc-600/50 text-zinc-300 px-2 py-1 rounded-md transition-colors"
                                    >
                                      ✏️ タイトル変更
                                    </button>
                                    <button
                                      onClick={() => setSlideFeedback(prev => prev + (prev ? '\n' : '') + '添付の画像を右カラムに挿入してください')}
                                      className="text-[10px] bg-zinc-700/50 hover:bg-zinc-600/50 text-zinc-300 px-2 py-1 rounded-md transition-colors"
                                    >
                                      🖼️ 画像挿入
                                    </button>
                                  </div>

                                  {/* 画像アップロード（コンパクト版） */}
                                  <div className="flex items-center gap-3 mb-3">
                                    <label className="cursor-pointer flex items-center gap-2 text-sm text-zinc-400 hover:text-zinc-300">
                                      {slideImage.preview ? (
                                        <>
                                          <img src={slideImage.preview} alt="Preview" className="w-10 h-8 object-cover rounded" />
                                          <span className="text-cyan-400">{slideImage.file?.name}</span>
                                          <button
                                            onClick={(e) => { e.preventDefault(); setSlideImage({ file: null, preview: null }); }}
                                            className="text-red-400 hover:text-red-300"
                                          >
                                            ✕
                                          </button>
                                        </>
                                      ) : (
                                        <span>📎 画像を追加</span>
                                      )}
                                      <input
                                        type="file"
                                        accept="image/*"
                                        className="hidden"
                                        onChange={(e) => {
                                          const file = e.target.files?.[0];
                                          if (file) {
                                            const preview = URL.createObjectURL(file);
                                            setSlideImage({ file, preview });
                                          }
                                        }}
                                      />
                                    </label>
                                  </div>

                                  {/* 更新ボタン（1ボタンに統合） */}
                                  <div className="flex gap-2 mb-3">
                                    <button
                                      onClick={() => handleSlideFeedback('general')}
                                      disabled={isRegenerating || (!slideFeedback.trim() && !slideImage.file)}
                                      className="flex-1 group relative overflow-hidden bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-400 hover:to-orange-500 text-white font-medium py-3 px-4 rounded-xl transition-all disabled:opacity-40 disabled:cursor-not-allowed shadow-lg"
                                    >
                                      <div className="flex items-center justify-center gap-2">
                                        {isRegenerating ? (
                                          <>
                                            <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                            <span>更新中...</span>
                                          </>
                                        ) : (
                                          <>
                                            <span className="text-lg">✨</span>
                                            <span>スライドを更新</span>
                                          </>
                                        )}
                                      </div>
                                    </button>

                                    {/* イラスト再生成（イラストモード時のみ） */}
                                    {addIllustrations && (
                                      <button
                                        onClick={() => handleSlideFeedback('image')}
                                        disabled={isRegenerating}
                                        className="group relative overflow-hidden bg-gradient-to-br from-pink-600/40 to-pink-700/50 hover:from-pink-500/50 hover:to-pink-600/60 border border-pink-500/30 text-white text-xs py-3 px-3 rounded-xl transition-all disabled:opacity-40 disabled:cursor-not-allowed"
                                        title="イラストのみ再生成"
                                      >
                                        <span className="text-lg">🎨</span>
                                      </button>
                                    )}
                                  </div>

                                  <div className="flex gap-2 mt-2">
                                    <button
                                      onClick={handleSlideUndo}
                                      disabled={isUndoing || isRegenerating || !slideCanUndo[selectedSlide]}
                                      className={`flex-1 text-sm py-2 rounded-lg transition-all ${slideCanUndo[selectedSlide]
                                        ? 'bg-amber-600/20 border border-amber-500/30 text-amber-400 hover:bg-amber-600/30'
                                        : 'bg-zinc-800/50 border border-zinc-700 text-zinc-500 cursor-not-allowed'
                                        }`}
                                    >
                                      {isUndoing ? "戻し中..." : slideCanUndo[selectedSlide] ? "↩️ 前に戻す" : "↩️ 履歴なし"}
                                    </button>
                                    <button
                                      onClick={() => {
                                        setSelectedSlide(null);
                                        setSlideFeedback("");
                                        setSlideImage({ file: null, preview: null });
                                      }}
                                      className="px-4 text-sm py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-zinc-400 hover:bg-zinc-700"
                                    >
                                      ✕ 閉じる
                                    </button>
                                  </div>
                                </div>
                              )
                              }
                            </div>
                          );
                        })}
                      </div>
                    </>
                  )}





                  <div className="flex gap-4 flex-wrap">
                    <button
                      onClick={handleGenerateVideo}
                      disabled={state.isProcessing}
                      className="btn-primary flex-1"
                    >
                      {state.isProcessing ? "動画生成中..." : "🎬 動画を生成"}
                    </button>
                    <button
                      onClick={() => updateState({ step: 5 as Step })}
                      disabled={state.isProcessing}
                      className="btn-secondary"
                    >
                      🔄 スライド再生成
                    </button>
                    <button
                      onClick={() => {
                        const downloadUrl = `${API_URL}/api/download-slides/${state.jobId}`;
                        window.open(downloadUrl, '_blank');
                      }}
                      className="btn-secondary"
                      title="スライド画像をZIPでダウンロード"
                    >
                      📥 画像一括DL
                    </button>
                  </div>
                </div>
              ) : (
                // ハイブリッドモード: アウトライン出力
                <div>
                  <h2 className="text-2xl font-bold mb-4 gradient-text">アウトライン出力</h2>
                  <p className="text-zinc-400 mb-4">
                    このアウトラインをコピーして、お好きなツール（Canva、PowerPoint等）でスライドを作成してください。
                  </p>
                  <textarea
                    readOnly
                    value={formatOutlineForCopy()}
                    className="w-full h-64 bg-zinc-900 border border-zinc-700 rounded-xl p-4 text-white resize-none"
                  />
                  <div className="flex justify-between mt-4">
                    <button
                      onClick={() => navigator.clipboard.writeText(formatOutlineForCopy())}
                      className="btn-secondary"
                    >
                      📋 コピー
                    </button>
                    <button onClick={handleExportComplete} className="btn-primary">
                      ✅ スライド作成完了 → 次へ
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Step 5 (Full AI): Generate Slides */}
          {state.step === 5 && state.workflowMode === "full-ai" && (
            <div className="text-center">
              <h2 className="text-2xl font-bold mb-6 gradient-text">🎨 AIスライド生成</h2>
              <p className="text-zinc-400 mb-6">
                アウトラインを元に、AIがスライドを自動デザインします。
              </p>

              {/* Slide Settings */}

              <div className="border-t border-zinc-700 pt-6">
                {/* ===== SLIDE OPTIONS ===== */}
                <>
                  {/* Color Theme Selector */}
                  <div className="mb-6">
                    <label className="block text-sm font-medium text-zinc-400 mb-2">
                      🎨 カラーテーマ
                    </label>
                    <select
                      value={selectedColorTheme}
                      onChange={(e) => setSelectedColorTheme(e.target.value)}
                      className="w-full max-w-md mx-auto bg-zinc-800 border border-zinc-700 rounded-lg px-4 py-3 text-white"
                    >
                      <option value="">AIにおまかせ（コンテンツに最適な配色）</option>
                      <option value="cosmic">🌌 Cosmic Dark - 宇宙的な深みと神秘感</option>
                      <option value="warm">🌅 Warm Sunset - 温かみのあるオレンジ・ゴールド</option>
                      <option value="elegant">💜 Elegant Purple - エレガントな紫・ピンク</option>
                      <option value="nature">🌿 Nature Green - 自然とリラックス</option>
                      <option value="ocean">🌊 Ocean Blue - 海のような開放感</option>
                      <option value="mono">⚫ Monochrome - シンプルでクリーン</option>
                    </select>
                  </div>

                  {/* Font Style Selector */}
                  <div className="mb-6">
                    <label className="block text-sm font-medium text-zinc-400 mb-2">
                      ✒️ フォントスタイル
                    </label>
                    <select
                      value={selectedFontStyle}
                      onChange={(e) => setSelectedFontStyle(e.target.value)}
                      className="w-full max-w-md mx-auto bg-zinc-800 border border-zinc-700 rounded-lg px-4 py-3 text-white"
                    >
                      <option value="">AIにおまかせ（コンテンツに最適なフォント）</option>
                      <option value="gothic">🔲 ゴシック体 - モダンでクリーン</option>
                      <option value="mincho">📜 明朝体 - 上品でエレガント</option>
                      <option value="pop">🎈 ポップ体 - カジュアルで親しみやすい</option>
                      <option value="handwritten">✍️ 手書き風 - 温かみと個性</option>
                    </select>
                  </div>

                  {/* User Image Upload for Slides */}
                  <div className="mb-6">
                    <label className="block text-sm font-medium text-zinc-400 mb-2">
                      🖼️ スライドに使う画像（任意・複数可）
                    </label>
                    <div className="w-full max-w-md mx-auto">
                      <label className="block cursor-pointer">
                        <div className="border-2 border-dashed border-zinc-600 hover:border-zinc-500 rounded-lg p-4 text-center transition-all">
                          <span className="text-sm text-zinc-500">📎 クリックして画像を選択（複数OK）</span>
                          <input
                            type="file"
                            accept="image/*"
                            multiple
                            className="hidden"
                            onChange={(e) => {
                              const files = Array.from(e.target.files || []);
                              const newImages = files.map(file => ({
                                file,
                                preview: URL.createObjectURL(file)
                              }));
                              setUserImages(prev => [...prev, ...newImages]);
                            }}
                          />
                        </div>
                      </label>
                      {userImages.length > 0 && (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {userImages.map((img, idx) => (
                            <div key={idx} className="relative group">
                              <img
                                src={img.preview}
                                alt={`Upload ${idx + 1}`}
                                className="w-16 h-16 object-cover rounded border border-zinc-600"
                              />
                              <button
                                onClick={() => setUserImages(prev => prev.filter((_, i) => i !== idx))}
                                className="absolute -top-2 -right-2 bg-red-500 text-white text-xs w-5 h-5 rounded-full opacity-0 group-hover:opacity-100 transition-opacity"
                              >
                                ✕
                              </button>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Design Preference Input */}
                  <div className="mb-6">
                    <label className="block text-sm font-medium text-zinc-400 mb-2">
                      📝 デザイン要望（任意）
                    </label>
                    <textarea
                      value={designPreference}
                      onChange={(e) => setDesignPreference(e.target.value)}
                      placeholder="例: 背景は白で、シンプルでミニマルなデザイン"
                      className="w-full max-w-md mx-auto bg-zinc-800 border border-zinc-700 rounded-lg px-4 py-3 text-white resize-none"
                      rows={2}
                    />
                  </div>

                  {/* Text Density Selector */}
                  <div className="mb-6">
                    <label className="block text-sm font-medium text-zinc-400 mb-2">
                      📋 テキスト量
                    </label>
                    <div className="flex justify-center gap-4">
                      <button
                        type="button"
                        onClick={() => setTextDensity("simple")}
                        className={`px-4 py-2 rounded-lg border transition-all ${textDensity === "simple"
                          ? "border-cyan-500 bg-cyan-500/20 text-cyan-400"
                          : "border-zinc-600 text-zinc-400 hover:border-zinc-500"
                          }`}
                      >
                        📌 シンプル
                        <span className="block text-xs mt-1 opacity-70">タイトル + 見出し</span>
                      </button>
                      <button
                        type="button"
                        onClick={() => setTextDensity("standard")}
                        className={`px-4 py-2 rounded-lg border transition-all ${textDensity === "standard"
                          ? "border-cyan-500 bg-cyan-500/20 text-cyan-400"
                          : "border-zinc-600 text-zinc-400 hover:border-zinc-500"
                          }`}
                      >
                        📝 標準
                        <span className="block text-xs mt-1 opacity-70">タイトル + 見出し + ポイント</span>
                      </button>
                    </div>
                  </div>

                  {/* ===== ILLUSTRATION TOGGLE & OPTIONS ===== */}
                  <div className="mb-6 border-t border-zinc-700 pt-6">
                    <div className="flex items-center justify-between max-w-md mx-auto mb-4">
                      <div>
                        <label className="block text-sm font-medium text-white">
                          🎨 イラストを追加
                          <span className="ml-2 px-2 py-0.5 text-xs bg-yellow-500/20 text-yellow-400 rounded-full border border-yellow-500/30">
                            開発中
                          </span>
                        </label>
                        <p className="text-xs text-zinc-500">AIがスライドにイラストを生成します</p>
                      </div>
                      <button
                        type="button"
                        onClick={() => setAddIllustrations(!addIllustrations)}
                        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${addIllustrations ? "bg-purple-600" : "bg-zinc-600"
                          }`}
                      >
                        <span
                          className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${addIllustrations ? "translate-x-6" : "translate-x-1"
                            }`}
                        />
                      </button>
                    </div>

                    {/* Illustration Options (shown when toggle is ON) */}
                    {addIllustrations && (
                      <div className="bg-zinc-800/50 rounded-xl p-4 max-w-md mx-auto border border-purple-500/30">
                        {/* Illustration Percentage Slider */}
                        <div className="mb-4">
                          <label className="block text-sm font-medium text-zinc-300 mb-2">
                            📊 イラストの割合: <span className="text-purple-400">{illustrationPercentage}%</span>
                          </label>
                          <input
                            type="range"
                            min="10"
                            max="100"
                            step="10"
                            value={illustrationPercentage}
                            onChange={(e) => setIllustrationPercentage(Number(e.target.value))}
                            className="w-full h-2 bg-zinc-700 rounded-lg appearance-none cursor-pointer accent-purple-500"
                          />
                          <div className="flex justify-between text-xs text-zinc-500 mt-1">
                            <span>10%</span>
                            <span>50%</span>
                            <span>100%</span>
                          </div>
                          <p className="text-xs text-zinc-500 mt-2">
                            AIが「ここにイラストがあるとわかりやすい」と判断したスライドに追加します
                          </p>
                        </div>

                        {/* Reference Image Upload */}
                        <div className="mb-4">
                          <label className="block text-sm font-medium text-zinc-300 mb-2">
                            🖼️ リファレンス画像（任意）
                          </label>
                          <label className="block cursor-pointer">
                            <div className="border-2 border-dashed border-purple-600 hover:border-purple-500 rounded-lg p-3 text-center transition-all">
                              <span className="text-sm text-zinc-400">📎 スタイルの参考画像をアップロード</span>
                              <input
                                type="file"
                                accept="image/*"
                                className="hidden"
                                onChange={(e) => {
                                  const file = e.target.files?.[0];
                                  if (file) {
                                    setReferenceImage({
                                      file,
                                      preview: URL.createObjectURL(file)
                                    });
                                  }
                                }}
                              />
                            </div>
                          </label>
                          {referenceImage && (
                            <div className="mt-2 flex justify-center">
                              <div className="relative group">
                                <img
                                  src={referenceImage.preview}
                                  alt="Reference"
                                  className="w-24 h-24 object-cover rounded-lg border-2 border-purple-500"
                                />
                                <button
                                  onClick={() => setReferenceImage(null)}
                                  className="absolute -top-2 -right-2 bg-red-500 text-white text-xs w-5 h-5 rounded-full opacity-0 group-hover:opacity-100 transition-opacity"
                                >
                                  ✕
                                </button>
                              </div>
                            </div>
                          )}
                        </div>

                        {/* Illustration Request Text */}
                        <div>
                          <label className="block text-sm font-medium text-zinc-300 mb-2">
                            💬 イラストへのリクエスト（任意）
                          </label>
                          <textarea
                            value={illustrationRequest}
                            onChange={(e) => setIllustrationRequest(e.target.value)}
                            placeholder="例: このキャラクターを使って、水彩画風に..."
                            className="w-full bg-zinc-700 border border-zinc-600 rounded-lg px-3 py-2 text-white placeholder-zinc-500 resize-none text-sm"
                            rows={2}
                          />
                        </div>
                      </div>
                    )}
                  </div>
                </>
              </div>

              <button
                onClick={() => handleGenerateSlides(1)}
                disabled={state.isProcessing}
                className="btn-primary"
              >
                {state.isProcessing ? "スライド生成中..." : "✨ AIでスライドを生成（5枚ずつ）"}
              </button>

              {/* Batch progress indicator and continue button */}
              {!batchState.isComplete && batchState.nextStart && (
                <div className="mt-6 p-4 bg-zinc-800/50 rounded-xl border border-zinc-700">
                  <div className="text-lg font-semibold text-amber-400 mb-3">
                    📊 進捗: {batchState.slidesCompleted}/{batchState.totalSlides}枚 生成完了
                  </div>

                  {/* Slide preview grid for current batch */}
                  {state.slidePreviews.length > 0 && (
                    <div className="mb-4">
                      <h4 className="text-sm text-gray-400 mb-2">生成済みスライド（クリックで選択してフィードバック）</h4>
                      <div className="grid grid-cols-5 gap-2">
                        {state.slidePreviews.map((preview, i) => (
                          <div
                            key={i}
                            onClick={() => setSelectedSlide(i + 1)}
                            className={`rounded-lg overflow-hidden border-2 cursor-pointer transition-all ${selectedSlide === i + 1
                              ? 'border-amber-500 ring-2 ring-amber-500/50 scale-105'
                              : 'border-zinc-700 hover:border-zinc-500'
                              }`}
                          >
                            <img src={preview} alt={`Slide ${i + 1}`} className="w-full h-auto" />
                            <div className="bg-zinc-800 text-center text-xs py-1">
                              {i + 1}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Feedback input for selected slide */}
                  {selectedSlide && (
                    <div className="bg-zinc-900/50 rounded-lg p-3 mb-4 border border-zinc-600">
                      <h4 className="font-semibold mb-2 text-amber-400">
                        📝 スライド {selectedSlide} を修正
                      </h4>
                      <textarea
                        value={slideFeedback}
                        onChange={(e) => setSlideFeedback(e.target.value)}
                        placeholder="例：タイトルを変更、背景をもっと明るく、ポイントを追加..."
                        className="w-full h-20 bg-zinc-800 border border-zinc-700 rounded-lg p-2 text-white resize-none mb-2 text-sm"
                      />
                      {/* フィードバック定型文ボタン */}
                      <div className="flex flex-wrap gap-1 mb-2">
                        <button
                          onClick={() => setSlideFeedback(prev => prev + (prev ? '\n' : '') + 'レイアウトを再構築してください')}
                          className="text-[10px] bg-zinc-700/50 hover:bg-zinc-600/50 text-zinc-300 px-2 py-1 rounded-md transition-colors"
                        >
                          📐 レイアウト再構築
                        </button>
                        <button
                          onClick={() => setSlideFeedback(prev => prev + (prev ? '\n' : '') + 'タイトルを「〇〇」に変更してください')}
                          className="text-[10px] bg-zinc-700/50 hover:bg-zinc-600/50 text-zinc-300 px-2 py-1 rounded-md transition-colors"
                        >
                          ✏️ タイトル変更
                        </button>
                        <button
                          onClick={() => setSlideFeedback(prev => prev + (prev ? '\n' : '') + '添付の画像を右カラムに挿入してください')}
                          className="text-[10px] bg-zinc-700/50 hover:bg-zinc-600/50 text-zinc-300 px-2 py-1 rounded-md transition-colors"
                        >
                          🖼️ 画像挿入
                        </button>
                      </div>
                      {/* 更新ボタン（1ボタンに統合） */}
                      <div className="flex gap-2 mb-2">
                        <button
                          onClick={() => handleSlideFeedback('general')}
                          disabled={isRegenerating || !slideFeedback.trim()}
                          className="flex-1 bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-400 hover:to-orange-500 text-white font-medium py-2 rounded-lg transition-colors flex items-center justify-center gap-1"
                        >
                          {isRegenerating ? '更新中...' : '✨ スライドを更新'}
                        </button>
                        {addIllustrations && (
                          <button
                            onClick={() => handleSlideFeedback('image')}
                            disabled={isRegenerating}
                            className="bg-pink-600/80 hover:bg-pink-600 text-white text-xs py-2 px-3 rounded-lg transition-colors"
                            title="イラストのみ再生成"
                          >
                            🎨
                          </button>
                        )}
                      </div>
                      <div className="flex justify-end">
                        <button
                          onClick={() => {
                            setSelectedSlide(null);
                            setSlideFeedback("");
                          }}
                          className="text-zinc-500 hover:text-zinc-300 text-xs py-1 px-2 flex items-center gap-1 transition-colors"
                        >
                          ✕ キャンセル
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Continue to next batch button */}
                  <button
                    onClick={() => handleGenerateSlides(batchState.nextStart!)}
                    disabled={state.isProcessing}
                    className="btn-primary w-full"
                  >
                    {state.isProcessing
                      ? "生成中..."
                      : `➡️ 次のバッチへ（${batchState.nextStart}-${Math.min(batchState.nextStart + 4, batchState.totalSlides)}枚目を生成）`}
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Step 7: User Creates Slides (instruction) */}
          {state.step === 7 && (
            <div>
              <h2 className="text-2xl font-bold mb-4 gradient-text">スライドをアップロード</h2>
              <p className="text-zinc-400 mb-6">
                作成したスライドをPDFまたは画像ファイルでアップロードしてください。
              </p>
              <label
                className={`upload-zone flex flex-col items-center justify-center w-full h-48 rounded-xl cursor-pointer transition-all ${isDragging ? 'border-cyan-500 bg-cyan-500/10 scale-[1.02]' : ''}`}
                onDragEnter={handleDragEnter}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={(e) => {
                  e.preventDefault();
                  setIsDragging(false);
                  const files = e.dataTransfer.files;
                  if (files?.length) {
                    handleUploadSlides(files);
                  }
                }}
              >
                <span className="text-5xl mb-4">{isDragging ? '📎' : '📥'}</span>
                <p className="text-lg">{isDragging ? 'ここにドロップ！' : 'PDF または 画像ファイル'}</p>
                <p className="text-sm text-zinc-500">✨ 複数画像をまとめてドラッグ可能</p>
                <input
                  type="file"
                  accept=".pdf,.png,.jpg,.jpeg"
                  multiple
                  className="hidden"
                  onChange={(e) => e.target.files?.length && handleUploadSlides(e.target.files)}
                  disabled={state.isProcessing}
                />
              </label>
            </div>
          )}

          {/* Step 8: Slides Uploaded */}
          {state.step === 8 && state.slideCount > 0 && (
            <div>
              <h2 className="text-2xl font-bold mb-4 gradient-text">スライド読み込み完了</h2>
              <p className="mb-4">{state.slideCount}枚のスライドを検出しました</p>
              <div className="grid grid-cols-4 gap-2 mb-6">
                {state.slidePreviews.slice(0, 8).map((url, i) => (
                  <img
                    key={i}
                    src={`${API_URL}${url}`}
                    alt={`Slide ${i + 1}`}
                    className="w-full aspect-video object-cover rounded-lg"
                  />
                ))}
              </div>
              <button onClick={handleMapSlides} disabled={state.isProcessing} className="btn-primary w-full">
                {state.isProcessing ? "処理中..." : "🤖 AIでタイミングを自動マッピング"}
              </button>
            </div>
          )}

          {/* Step 9: Timing Map */}
          {state.step === 9 && state.timingMap.length > 0 && (
            <div>
              <h2 className="text-2xl font-bold mb-4 gradient-text">🤖 AIマッピング結果</h2>

              {/* 合計時間の表示 */}
              <div className="mb-4 p-3 bg-zinc-900 rounded-lg flex items-center justify-between">
                <span className="text-sm text-zinc-400">音声の長さ:</span>
                <span className="text-cyan-400 font-bold">
                  {state.timingMap.length > 0 && state.timingMap[state.timingMap.length - 1].end_time
                    ? `${Math.floor(state.timingMap[state.timingMap.length - 1].end_time / 60)}:${String(Math.floor(state.timingMap[state.timingMap.length - 1].end_time % 60)).padStart(2, '0')}`
                    : '--:--'}
                </span>
              </div>

              {/* タイムライン表示 - ドラッグで調整可能 */}
              <div className="mb-6 p-4 bg-zinc-900 rounded-lg">
                <div className="text-xs text-zinc-400 mb-2 flex items-center gap-2">
                  <span>⬅️➡️ 境界線をドラッグして調整</span>
                </div>
                <div
                  ref={timelineRef}
                  className="flex h-10 rounded-lg overflow-visible mb-2 relative"
                  style={{ cursor: draggingBoundary !== null ? 'ew-resize' : 'default' }}
                >
                  {state.timingMap.map((item, i) => {
                    const totalDuration = state.timingMap[state.timingMap.length - 1]?.end_time || 1;
                    const width = ((item.end_time - item.start_time) / totalDuration) * 100;
                    const colors = ['bg-cyan-600', 'bg-purple-600', 'bg-orange-600', 'bg-green-600', 'bg-pink-600', 'bg-yellow-600'];
                    const isLastSlide = i === state.timingMap.length - 1;

                    return (
                      <div
                        key={i}
                        className={`${colors[i % colors.length]} flex items-center justify-center text-xs font-bold relative group`}
                        style={{ width: `${width}%`, minWidth: '30px' }}
                        title={`スライド${item.slide_number}: ${item.start_time?.toFixed(1)}s - ${item.end_time?.toFixed(1)}s`}
                      >
                        {item.slide_number}

                        {/* Drag handle on right edge (not on last slide) */}
                        {!isLastSlide && (
                          <div
                            className="absolute right-0 top-0 bottom-0 w-3 cursor-ew-resize z-10 flex items-center justify-center opacity-0 group-hover:opacity-100 hover:opacity-100 transition-opacity"
                            style={{ transform: 'translateX(50%)' }}
                            onMouseDown={(e) => {
                              e.preventDefault();
                              handleBoundaryDragStart(i);
                            }}
                          >
                            <div className="w-1 h-6 bg-white rounded shadow-lg" />
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
                <div className="flex justify-between text-xs text-zinc-500">
                  <span>0:00</span>
                  <span>
                    {state.timingMap.length > 0 && state.timingMap[state.timingMap.length - 1].end_time
                      ? `${Math.floor(state.timingMap[state.timingMap.length - 1].end_time / 60)}:${String(Math.floor(state.timingMap[state.timingMap.length - 1].end_time % 60)).padStart(2, '0')}`
                      : '--:--'}
                  </span>
                </div>
              </div>

              {/* 詳細リスト */}
              <div className="space-y-2 mb-6 max-h-64 overflow-y-auto">
                {state.timingMap.map((item, i) => {
                  const duration = (item.end_time || 0) - (item.start_time || 0);
                  return (
                    <div key={i} className="flex items-center gap-4 p-3 bg-zinc-900 rounded-lg border-l-4 border-cyan-500">
                      <span className="w-10 h-10 bg-cyan-500 rounded-full flex items-center justify-center font-bold text-lg">
                        {item.slide_number}
                      </span>
                      <div className="flex-1">
                        <div className="flex items-center gap-3">
                          <span className="text-cyan-400 font-mono">
                            {Math.floor((item.start_time || 0) / 60)}:{String(Math.floor((item.start_time || 0) % 60)).padStart(2, '0')}
                          </span>
                          <span className="text-zinc-600">→</span>
                          <span className="text-cyan-400 font-mono">
                            {Math.floor((item.end_time || 0) / 60)}:{String(Math.floor((item.end_time || 0) % 60)).padStart(2, '0')}
                          </span>
                          <span className="text-zinc-500 text-sm">
                            ({duration.toFixed(1)}秒)
                          </span>
                        </div>
                        {(item.match_reason || item.reason) && (
                          <div className="text-xs text-zinc-400 mt-1">
                            💡 {item.match_reason || item.reason}
                          </div>
                        )}
                      </div>
                      {/* Delete button - only show if more than 1 slide */}
                      {state.timingMap.length > 1 && (
                        <button
                          onClick={() => handleDeleteSlide(i)}
                          className="p-2 text-zinc-500 hover:text-red-400 hover:bg-red-900/20 rounded-lg transition-colors"
                          title="このスライドを削除"
                        >
                          🗑️
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>
              <button onClick={handleGenerateVideo} disabled={state.isProcessing} className="btn-primary w-full">
                {state.isProcessing ? "処理中..." : "🎬 動画を生成"}
              </button>
            </div>
          )}

          {/* Step 10: Complete */}
          {state.step === 10 && state.videoUrl && (
            <div>
              <div className="text-center">
                <span className="text-6xl">🎉</span>
                <h2 className="text-3xl font-bold mt-4 mb-6 gradient-text">完成しました！</h2>
              </div>

              <video src={state.videoUrl} controls className="w-full rounded-xl mb-6" />

              <div className="flex flex-wrap justify-center gap-3 mb-8">
                <button
                  onClick={() => handleDownloadVideo(`${API_URL}/api/download/${state.jobId}`, `voiceslide_${state.jobId}.mp4`)}
                  className="btn-primary"
                >
                  📥 動画をダウンロード
                </button>
                <button
                  onClick={() => {
                    const downloadUrl = `${API_URL}/api/download-slides/${state.jobId}`;
                    window.open(downloadUrl, '_blank');
                  }}
                  className="btn-secondary"
                  title="スライド画像をZIPでダウンロード"
                >
                  🖼️ スライド画像一括DL
                </button>
                <button onClick={handleReset} className="btn-secondary">
                  🔄 新規作成
                </button>
              </div>

              {/* Video Feedback Section */}
              <div className="border-t border-zinc-700 pt-6">
                <h3 className="text-xl font-semibold mb-4">💡 修正したい場合</h3>
                <p className="text-zinc-400 mb-4">
                  スライドをクリックして修正し、動画を再生成できます。
                </p>

                {/* Slide Previews for Feedback */}
                {state.slidePreviews.length > 0 && (
                  <>
                    <p className="text-sm text-zinc-500 mb-2">
                      クリックで選択、ダブルクリックまたは🔍で拡大表示
                    </p>
                    <div className="grid grid-cols-4 gap-3 mb-6">
                      {state.slidePreviews.map((preview, i) => (
                        <div
                          key={i}
                          onClick={() => setSelectedSlide(i + 1)}
                          onDoubleClick={() => setZoomedSlide(i)}
                          className={`rounded-lg overflow-hidden border-2 cursor-pointer transition-all relative group ${selectedSlide === i + 1
                            ? 'border-amber-500 ring-2 ring-amber-500/50 scale-105'
                            : 'border-zinc-700 hover:border-zinc-500'
                            }`}
                        >
                          <img src={preview} alt={`Slide ${i + 1}`} className="w-full h-auto" />
                          <div className="bg-zinc-800 text-center text-xs py-1">
                            {i + 1}
                          </div>
                          {/* Zoom button */}
                          <button
                            onClick={(e) => { e.stopPropagation(); setZoomedSlide(i); }}
                            className="absolute top-1 right-1 bg-black/60 hover:bg-black/80 text-white text-xs px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition-opacity"
                          >
                            🔍
                          </button>
                        </div>
                      ))}
                    </div>
                  </>
                )}

                {/* Feedback Input */}
                {selectedSlide && (
                  <div className="bg-zinc-800/50 rounded-xl p-4 mb-4 border border-zinc-700">
                    <h4 className="font-semibold mb-2 text-amber-400">
                      📝 スライド {selectedSlide} を編集
                    </h4>
                    <textarea
                      value={slideFeedback}
                      onChange={(e) => setSlideFeedback(e.target.value)}
                      placeholder="修正したい内容を入力..."
                      className="w-full h-20 bg-zinc-900 border border-zinc-700 rounded-lg p-3 text-white resize-none mb-2"
                    />

                    {/* フィードバック定型文ボタン */}
                    <div className="flex flex-wrap gap-1 mb-3">
                      <button
                        onClick={() => setSlideFeedback(prev => prev + (prev ? '\n' : '') + 'レイアウトを再構築してください')}
                        className="text-[10px] bg-zinc-700/50 hover:bg-zinc-600/50 text-zinc-300 px-2 py-1 rounded-md transition-colors"
                      >
                        📐 レイアウト再構築
                      </button>
                      <button
                        onClick={() => setSlideFeedback(prev => prev + (prev ? '\n' : '') + '「〇〇」のコピーを「〇〇」に変更してください')}
                        className="text-[10px] bg-zinc-700/50 hover:bg-zinc-600/50 text-zinc-300 px-2 py-1 rounded-md transition-colors"
                      >
                        ✏️ コピー変更
                      </button>
                      <button
                        onClick={() => setSlideFeedback(prev => prev + (prev ? '\n' : '') + '添付の画像を右側に挿入してください')}
                        className="text-[10px] bg-zinc-700/50 hover:bg-zinc-600/50 text-zinc-300 px-2 py-1 rounded-md transition-colors"
                      >
                        🖼️ 画像挿入
                      </button>
                    </div>

                    {/* 更新ボタン（1ボタンに統合） */}
                    <div className="flex gap-2 mb-3">
                      <button
                        onClick={() => handleSlideFeedback('general')}
                        disabled={isRegenerating || !slideFeedback.trim()}
                        className="flex-1 group relative overflow-hidden bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-400 hover:to-orange-500 text-white font-medium py-3 px-4 rounded-xl transition-all disabled:opacity-40 disabled:cursor-not-allowed shadow-lg"
                      >
                        <div className="flex items-center justify-center gap-2">
                          {isRegenerating ? (
                            <>
                              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                              <span>更新中...</span>
                            </>
                          ) : (
                            <>
                              <span className="text-lg">✨</span>
                              <span>スライドを更新</span>
                            </>
                          )}
                        </div>
                      </button>

                      {/* イラスト再生成（イラストモード時のみ） */}
                      {addIllustrations && (
                        <button
                          onClick={() => handleSlideFeedback('image')}
                          disabled={isRegenerating}
                          className="group relative overflow-hidden bg-gradient-to-br from-pink-600/40 to-pink-700/50 hover:from-pink-500/50 hover:to-pink-600/60 border border-pink-500/30 text-white text-xs py-3 px-3 rounded-xl transition-all disabled:opacity-40 disabled:cursor-not-allowed"
                          title="イラストのみ再生成"
                        >
                          <span className="text-lg">🎨</span>
                        </button>
                      )}
                    </div>

                    <div className="flex justify-end">
                      <button
                        onClick={() => {
                          setSelectedSlide(null);
                          setSlideFeedback("");
                        }}
                        className="btn-secondary"
                      >
                        ✕
                      </button>
                    </div>
                  </div>
                )}

                {/* タイムライン編集セクション */}
                {state.timingMap.length > 0 && (
                  <div className="bg-zinc-800/50 rounded-xl p-4 mb-4 border border-zinc-700">
                    <h4 className="font-semibold mb-3 text-white flex items-center gap-2">
                      ⏱️ タイムライン編集
                    </h4>
                    <p className="text-xs text-zinc-400 mb-3">
                      境界線をドラッグして各スライドの表示時間を調整できます。🗑️で不要なスライドを削除できます。
                    </p>
                    {/* Timeline bar */}
                    <div
                      ref={timelineRef}
                      className="flex h-10 rounded-lg overflow-visible mb-2 relative"
                      style={{ cursor: draggingBoundary !== null ? 'ew-resize' : 'default' }}
                    >
                      {state.timingMap.map((item, i) => {
                        const totalDuration = state.timingMap[state.timingMap.length - 1]?.end_time || 1;
                        const width = ((item.end_time - item.start_time) / totalDuration) * 100;
                        const colors = ['bg-cyan-600', 'bg-purple-600', 'bg-orange-600', 'bg-green-600', 'bg-pink-600', 'bg-yellow-600'];
                        const isLastSlide = i === state.timingMap.length - 1;

                        return (
                          <div
                            key={i}
                            className={`${colors[i % colors.length]} flex items-center justify-center text-xs font-bold relative group`}
                            style={{ width: `${width}%`, minWidth: '30px' }}
                            title={`スライド${item.slide_number}: ${item.start_time?.toFixed(1)}s - ${item.end_time?.toFixed(1)}s`}
                          >
                            {item.slide_number}
                            {!isLastSlide && (
                              <div
                                className="absolute right-0 top-0 bottom-0 w-3 cursor-ew-resize z-10 flex items-center justify-center opacity-0 group-hover:opacity-100 hover:opacity-100 transition-opacity"
                                style={{ transform: 'translateX(50%)' }}
                                onMouseDown={(e) => {
                                  e.preventDefault();
                                  handleBoundaryDragStart(i);
                                }}
                              >
                                <div className="w-1 h-6 bg-white rounded shadow-lg" />
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                    <div className="flex justify-between text-xs text-zinc-500 mb-3">
                      <span>0:00</span>
                      <span>
                        {state.timingMap[state.timingMap.length - 1]?.end_time
                          ? `${Math.floor(state.timingMap[state.timingMap.length - 1].end_time / 60)}:${String(Math.floor(state.timingMap[state.timingMap.length - 1].end_time % 60)).padStart(2, '0')}`
                          : '--:--'}
                      </span>
                    </div>
                    {/* Slide timing list */}
                    <div className="space-y-1 max-h-48 overflow-y-auto">
                      {state.timingMap.map((item, i) => {
                        const duration = (item.end_time || 0) - (item.start_time || 0);
                        return (
                          <div key={i} className="flex items-center gap-3 p-2 bg-zinc-900 rounded-lg">
                            <span className="w-7 h-7 bg-cyan-500 rounded-full flex items-center justify-center font-bold text-sm shrink-0">
                              {item.slide_number}
                            </span>
                            <div className="flex-1 flex items-center gap-2 text-sm">
                              <span className="text-cyan-400 font-mono">
                                {Math.floor((item.start_time || 0) / 60)}:{String(Math.floor((item.start_time || 0) % 60)).padStart(2, '0')}
                              </span>
                              <span className="text-zinc-600">→</span>
                              <span className="text-cyan-400 font-mono">
                                {Math.floor((item.end_time || 0) / 60)}:{String(Math.floor((item.end_time || 0) % 60)).padStart(2, '0')}
                              </span>
                              <span className="text-zinc-500 text-xs">({duration.toFixed(1)}秒)</span>
                            </div>
                            {state.timingMap.length > 1 && (
                              <button
                                onClick={() => handleDeleteSlide(i)}
                                className="p-1 text-zinc-500 hover:text-red-400 hover:bg-red-900/20 rounded transition-colors"
                                title="このスライドを削除"
                              >
                                🗑️
                              </button>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Regenerate Video Button */}
                <button
                  onClick={() => {
                    setSelectedSlide(null);
                    handleGenerateVideo();
                  }}
                  disabled={state.isProcessing}
                  className="btn-secondary w-full"
                >
                  {state.isProcessing ? "⏳ 動画を再生成中..." : "🎬 動画を再生成"}
                </button>

                {/* OP/ED Video Section */}
                <div className="border-t border-zinc-700 pt-4 mt-4">
                  <h4 className="font-semibold mb-3 text-lg">📽️ YouTube用 OP/ED追加</h4>
                  <p className="text-zinc-500 text-sm mb-3">
                    オープニング・エンディング動画をアップロードして結合できます
                  </p>

                  <div className="grid grid-cols-2 gap-3 mb-4">
                    {/* Intro Video */}
                    <div>
                      <label className="block text-sm text-zinc-400 mb-1">🎬 オープニング</label>
                      <input
                        type="file"
                        accept="video/*"
                        onChange={(e) => setIntroVideo(e.target.files?.[0] || null)}
                        className="w-full text-xs file:mr-2 file:py-1 file:px-2 file:rounded file:border-0 file:bg-zinc-700 file:text-white"
                      />
                      {introVideo && (
                        <p className="text-xs text-cyan-400 mt-1 truncate">{introVideo.name}</p>
                      )}
                    </div>

                    {/* Outro Video */}
                    <div>
                      <label className="block text-sm text-zinc-400 mb-1">🎬 エンディング</label>
                      <input
                        type="file"
                        accept="video/*"
                        onChange={(e) => setOutroVideo(e.target.files?.[0] || null)}
                        className="w-full text-xs file:mr-2 file:py-1 file:px-2 file:rounded file:border-0 file:bg-zinc-700 file:text-white"
                      />
                      {outroVideo && (
                        <p className="text-xs text-cyan-400 mt-1 truncate">{outroVideo.name}</p>
                      )}
                    </div>
                  </div>

                  <button
                    onClick={handleConcatVideo}
                    disabled={isConcatenating || (!introVideo && !outroVideo)}
                    className="w-full bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-500 hover:to-pink-500 disabled:opacity-50 text-white py-2 px-4 rounded-lg transition-all"
                  >
                    {isConcatenating ? "⏳ 結合中..." : "🎞️ OP/EDを結合"}
                  </button>

                  {/* Concatenated Video Preview */}
                  {concatVideoUrl && (
                    <div className="mt-4 p-3 bg-zinc-800/50 rounded-lg">
                      <p className="text-sm text-green-400 mb-2">✅ 結合完了！</p>
                      <video
                        src={concatVideoUrl}
                        controls
                        className="w-full rounded-lg"
                      />
                      <button
                        onClick={() => handleDownloadVideo(concatVideoUrl, "voiceslide_youtube.mp4")}
                        className="block w-full mt-2 text-center bg-green-600 hover:bg-green-500 text-white py-2 rounded-lg"
                      >
                        📥 YouTube用動画をダウンロード
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Processing Indicator with Enhanced Progress */}
          {state.isProcessing && (
            <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
              <div className="bg-zinc-900 rounded-2xl p-8 text-center min-w-[350px]">
                <div className="text-5xl mb-4 animate-bounce">⚙️</div>

                {/* Progress bar */}
                {progress.percent > 0 && (
                  <div className="mb-4">
                    <div className="bg-zinc-700 rounded-full h-4 overflow-hidden">
                      <div
                        className="bg-gradient-to-r from-amber-500 to-orange-500 h-full transition-all duration-500"
                        style={{ width: `${progress.percent}%` }}
                      />
                    </div>

                    {/* Detailed Progress Info */}
                    <div className="flex justify-between items-center mt-3">
                      <p className="text-3xl font-bold text-amber-400">{Math.round(progress.percent)}%</p>
                      {batchState.totalSlides > 0 && (
                        <p className="text-sm text-zinc-400">
                          {batchState.slidesCompleted || Math.round(progress.percent / 100 * batchState.totalSlides)} / {batchState.totalSlides} 枚
                        </p>
                      )}
                    </div>

                    {/* ETA */}
                    {batchState.totalSlides > 0 && progress.percent > 5 && (
                      <p className="text-xs text-zinc-500 mt-2">
                        残り約 {Math.round((100 - progress.percent) / progress.percent * (batchState.totalSlides * 8) / 60)} 分
                      </p>
                    )}
                  </div>
                )}

                {/* Queue Waiting Indicator */}
                {queueStatus.status === "waiting" && queueStatus.position > 0 && (
                  <div className="mb-4 p-3 bg-blue-900/30 rounded-lg border border-blue-500/30">
                    <p className="text-blue-400 text-lg font-medium">
                      ⏳ 現在 {queueStatus.position} 番目です
                    </p>
                    {queueStatus.estimatedWait > 0 && (
                      <p className="text-blue-300 text-sm mt-1">
                        推定待機時間: 約 {queueStatus.estimatedWait} 分
                      </p>
                    )}
                    <p className="text-zinc-500 text-xs mt-2">
                      {queueStatus.activeCount} 件処理中 / {queueStatus.waitingCount} 件待機中
                    </p>
                  </div>
                )}

                <p className="text-lg text-zinc-300">{progress.message || "処理中..."}</p>

                {/* Keep-awake notice */}
                <p className="text-xs text-zinc-600 mt-4">
                  💡 生成中はこのタブを開いたままにしてください
                </p>
              </div>
            </div>
          )}
        </div>
      </main>

      {/* AI Support Chat Widget */}
      <SupportChat
        errorContext={errorContext}
        apiUrl={API_URL}
        geminiKey={getAPIKeys().gemini}
      />
    </div>
  );
}
