"use client";

import { useState, useCallback, DragEvent } from "react";
import { Header } from "@/components/Header";

// 本番環境：Next.js API Routes経由でバックエンドにプロキシ
// ローカル：直接バックエンドに接続
const API_URL = process.env.NEXT_PUBLIC_API_URL || "";

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
    removedSilences: number;
    removedFillers: number;
    totalRemovedSeconds: number;
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

  const [editText, setEditText] = useState("");
  const [isDragging, setIsDragging] = useState(false);
  const [isEditingTranscript, setIsEditingTranscript] = useState(false);
  const [editedTranscript, setEditedTranscript] = useState("");

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
      updateState({ error: err.message, isProcessing: false });
    }
  };

  // Step 2: Transcribe
  const handleTranscribe = async () => {
    updateState({ isProcessing: true });

    try {
      const res = await fetch(`${API_URL}/api/transcribe/${state.jobId}`, {
        method: "POST",
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Transcription failed");

      updateState({
        transcript: data.transcript,
        isProcessing: false,
      });
      setEditText(data.transcript);
    } catch (err: any) {
      updateState({ error: err.message, isProcessing: false });
    }
  };

  // Step 3: Polish Transcript
  const handlePolishTranscript = async () => {
    updateState({ isProcessing: true });

    try {
      const res = await fetch(`${API_URL}/api/polish-transcript/${state.jobId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ transcript: editText }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Polish failed");

      updateState({
        polishedTranscript: data.polished_transcript,
        step: 3,
        isProcessing: false,
      });
      setEditText(data.polished_transcript);
    } catch (err: any) {
      updateState({ error: err.message, isProcessing: false });
    }
  };

  // Step 4: Generate Outline
  const handleGenerateOutline = async () => {
    updateState({ isProcessing: true });

    try {
      const res = await fetch(`${API_URL}/api/generate-outline/${state.jobId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ transcript: editText }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Outline generation failed");

      updateState({
        outline: data.outline,
        step: 4,
        isProcessing: false,
      });
    } catch (err: any) {
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

  // Step 5 (Full AI): Generate Slides automatically
  const handleGenerateSlides = async () => {
    updateState({ isProcessing: true });

    try {
      const res = await fetch(`${API_URL}/api/generate-slides/${state.jobId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Slide generation failed");

      updateState({
        slideCount: data.slide_count,
        slidePreviews: data.slide_previews.map((p: string) => `${API_URL}${p}`),
        step: 6 as Step, // フルAIモードのステップ6は動画生成
        isProcessing: false,
      });
    } catch (err: any) {
      updateState({ error: err.message, isProcessing: false });
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

  // Step 10: Generate Video
  const handleGenerateVideo = async () => {
    updateState({ isProcessing: true });

    try {
      const res = await fetch(`${API_URL}/api/generate-video/${state.jobId}`, {
        method: "POST",
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Video generation failed");

      updateState({
        videoUrl: `${API_URL}${data.video_url}`,
        step: 10,
        isProcessing: false,
      });
    } catch (err: any) {
      updateState({ error: err.message, isProcessing: false });
    }
  };

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

  return (
    <div className="min-h-screen flex flex-col">
      <Header />

      <main className="flex-1 container mx-auto px-4 py-8 max-w-5xl">
        {/* Progress */}
        <div className="mb-8 overflow-x-auto">
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
              <button
                onClick={handleTranscribe}
                disabled={state.isProcessing}
                className="btn-primary"
              >
                {state.isProcessing ? "処理中...（無音・フィラー除去含む）" : "📝 文字起こし開始"}
              </button>
              <p className="text-xs text-zinc-500 mt-3">
                ✨ 自動で無音区間と「えっと」などのフィラーを除去します
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
                <button
                  onClick={() => {
                    setIsEditingTranscript(!isEditingTranscript);
                    setEditedTranscript(editText);
                  }}
                  className={`text-sm px-3 py-1 rounded-lg transition-all ${isEditingTranscript
                    ? 'bg-cyan-500 text-white'
                    : 'bg-zinc-700 text-zinc-300 hover:bg-zinc-600'
                    }`}
                >
                  {isEditingTranscript ? '✏️ 編集中' : '📝 手動で編集'}
                </button>
              </div>

              {/* Cleanup Info */}
              {state.cleanupInfo && (
                <div className="mb-4 p-3 rounded-lg bg-green-500/10 border border-green-500/30 text-sm">
                  <span className="text-green-400">✨ クリーンアップ完了:</span>
                  <span className="text-zinc-300 ml-2">
                    無音{state.cleanupInfo.removedSilences}箇所、
                    フィラー{state.cleanupInfo.removedFillers}箇所を除去
                    （計{state.cleanupInfo.totalRemovedSeconds.toFixed(1)}秒短縮）
                  </span>
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
                    <button onClick={handleGenerateOutline} disabled={state.isProcessing} className="btn-primary">
                      {state.isProcessing ? "処理中..." : "📋 アウトライン生成"}
                    </button>
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
                        {slide.number}
                      </span>
                      <span className="font-semibold text-lg">{slide.title}</span>
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

                  {/* スライドプレビュー */}
                  {state.slidePreviews.length > 0 && (
                    <div className="grid grid-cols-3 gap-4 mb-6">
                      {state.slidePreviews.map((preview, i) => (
                        <div key={i} className="rounded-lg overflow-hidden border border-zinc-700">
                          <img src={preview} alt={`Slide ${i + 1}`} className="w-full h-auto" />
                        </div>
                      ))}
                    </div>
                  )}

                  <button
                    onClick={handleGenerateVideo}
                    disabled={state.isProcessing}
                    className="btn-primary w-full"
                  >
                    {state.isProcessing ? "動画生成中..." : "🎬 動画を生成"}
                  </button>
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
              <button
                onClick={handleGenerateSlides}
                disabled={state.isProcessing}
                className="btn-primary"
              >
                {state.isProcessing ? "スライド生成中..." : "✨ AIでスライドを生成"}
              </button>
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

              {/* タイムライン表示 */}
              <div className="mb-6 p-4 bg-zinc-900 rounded-lg">
                <div className="flex h-8 rounded-lg overflow-hidden mb-2">
                  {state.timingMap.map((item, i) => {
                    const totalDuration = state.timingMap[state.timingMap.length - 1]?.end_time || 1;
                    const width = ((item.end_time - item.start_time) / totalDuration) * 100;
                    const colors = ['bg-cyan-600', 'bg-purple-600', 'bg-orange-600', 'bg-green-600', 'bg-pink-600', 'bg-yellow-600'];
                    return (
                      <div
                        key={i}
                        className={`${colors[i % colors.length]} flex items-center justify-center text-xs font-bold border-r border-zinc-800`}
                        style={{ width: `${width}%`, minWidth: '20px' }}
                        title={`スライド${item.slide_number}: ${item.start_time?.toFixed(1)}s - ${item.end_time?.toFixed(1)}s`}
                      >
                        {item.slide_number}
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
            <div className="text-center">
              <span className="text-6xl">🎉</span>
              <h2 className="text-3xl font-bold mt-4 mb-6 gradient-text">完成しました！</h2>
              <video src={state.videoUrl} controls className="w-full rounded-xl mb-6" />
              <div className="flex justify-center gap-4">
                <a href={`${API_URL}/api/download/${state.jobId}`} className="btn-primary" download>
                  📥 ダウンロード
                </a>
                <button onClick={handleReset} className="btn-secondary">
                  🔄 新規作成
                </button>
              </div>
            </div>
          )}

          {/* Processing Indicator */}
          {state.isProcessing && (
            <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
              <div className="bg-zinc-900 rounded-2xl p-8 text-center">
                <div className="text-5xl mb-4 animate-bounce">⚙️</div>
                <p className="text-xl">処理中...</p>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
