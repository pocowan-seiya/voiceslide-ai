"use client";

import { useState, useEffect } from "react";
import { createClient } from "@/lib/supabase/client";
import type { UserSettings } from "@/lib/supabase/types";

// Model IDs MUST match what Google / OpenRouter actually serve.
//
// History note:
// - 以前のコードでは OpenRouter 側の slug を `google/gemini-3-flash` と
//   書いていたが、OpenRouter の正しい slug は末尾に `-preview` を付けた
//   `google/gemini-3-flash-preview` が正しい。これが原因で Polish/Outline
//   が 400 "not a valid model ID" で落ちていた。
// - 直接 Gemini API の方は `gemini-3-flash-preview` で正しいので変更なし。
// - 2.5-flash は OPENROUTER_SAFE_FALLBACK_MODEL として backend で採用され
//   ているので、ドロップダウンにも残しておく（全部壊れた時の保険）。
const GEMINI_MODELS = [
    { id: "gemini-3-flash-preview", label: "Gemini 3 Flash Preview (推奨)" },
    { id: "gemini-3.1-flash-lite-preview", label: "Gemini 3.1 Flash Lite Preview" },
    { id: "gemini-2.5-flash", label: "Gemini 2.5 Flash" },
    { id: "gemini-2.5-pro", label: "Gemini 2.5 Pro" },
    { id: "gemini-2.0-flash", label: "Gemini 2.0 Flash (旧)" },
];

const OPENROUTER_TEXT_MODELS = [
    { id: "google/gemini-3-flash-preview", label: "Gemini 3 Flash Preview (推奨)" },
    { id: "google/gemini-3.1-pro-preview", label: "Gemini 3.1 Pro Preview (Google)" },
    { id: "google/gemini-3.1-flash-lite", label: "Gemini 3.1 Flash Lite (Google)" },
    { id: "google/gemini-2.5-pro-preview", label: "Gemini 2.5 Pro (Google)" },
    { id: "google/gemini-2.5-flash", label: "Gemini 2.5 Flash (安全な fallback)" },
    { id: "anthropic/claude-opus-4-7", label: "Claude Opus 4.7 (Anthropic)" },
    { id: "anthropic/claude-sonnet-4-6", label: "Claude Sonnet 4.6 (Anthropic)" },
    { id: "openai/gpt-4.1", label: "GPT-4.1 (OpenAI)" },
    { id: "openai/gpt-4.1-mini", label: "GPT-4.1 Mini (OpenAI)" },
    { id: "deepseek/deepseek-r1", label: "DeepSeek R1" },
];

const OPENROUTER_DESIGN_MODELS = [
    { id: "google/gemini-3-flash-preview", label: "Gemini 3 Flash Preview (推奨)" },
    { id: "google/gemini-3.1-pro-preview", label: "Gemini 3.1 Pro Preview (Google)" },
    { id: "google/gemini-3.1-flash-lite", label: "Gemini 3.1 Flash Lite (Google)" },
    { id: "google/gemini-2.5-pro-preview", label: "Gemini 2.5 Pro (Google)" },
    { id: "google/gemini-2.5-flash", label: "Gemini 2.5 Flash (安全な fallback)" },
    { id: "anthropic/claude-sonnet-4-6", label: "Claude Sonnet 4.6 (Anthropic)" },
    { id: "anthropic/claude-opus-4-7", label: "Claude Opus 4.7 (Anthropic)" },
    { id: "openai/gpt-4.1", label: "GPT-4.1 (OpenAI)" },
    { id: "openai/gpt-4.1-mini", label: "GPT-4.1 Mini (OpenAI)" },
    { id: "deepseek/deepseek-r1", label: "DeepSeek R1" },
];

interface APIKeysSettingsProps {
    onClose: () => void;
}

export function APIKeysSettings({ onClose }: APIKeysSettingsProps) {
    const [openaiKey, setOpenaiKey] = useState("");
    const [geminiKey, setGeminiKey] = useState("");
    const [geminiModel, setGeminiModel] = useState("gemini-3-flash-preview");
    const [openrouterKey, setOpenrouterKey] = useState("");
    const [openrouterModel, setOpenrouterModel] = useState("google/gemini-3-flash-preview");
    const [openrouterDesignModel, setOpenrouterDesignModel] = useState("google/gemini-3-flash-preview");
    const [showOpenai, setShowOpenai] = useState(false);
    const [showGemini, setShowGemini] = useState(false);
    const [showOpenrouter, setShowOpenrouter] = useState(false);
    const [saved, setSaved] = useState(false);
    const [saving, setSaving] = useState(false);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        loadKeys();
    }, []);

    const loadKeys = async () => {
        const supabase = createClient();
        const { data: { user } } = await supabase.auth.getUser();

        if (user) {
            // ログイン済み: Supabaseから読み込み
            const { data } = await supabase
                .from("user_settings")
                .select("*")
                .eq("user_id", user.id)
                .single();

            if (data && (data.openai_key || data.gemini_key || data.openrouter_key)) {
                // Supabaseにキーがある → それを使う
                setOpenaiKey(data.openai_key || "");
                setGeminiKey(data.gemini_key || "");
                setGeminiModel(data.gemini_model || "gemini-3-flash-preview");
                setOpenrouterKey(data.openrouter_key || "");
                setOpenrouterModel(data.openrouter_model || "google/gemini-3-flash-preview");
                setOpenrouterDesignModel(data.openrouter_design_model || "google/gemini-3-flash-preview");
                // localStorageにもバックアップ
                syncToLocalStorage(data.openai_key, data.gemini_key, data.gemini_model, data.openrouter_key || "", data.openrouter_model || "google/gemini-3-flash-preview", data.openrouter_design_model || "google/gemini-3-flash-preview");
            } else {
                // Supabaseにキーが無い → localStorageから移行
                const localOpenai = localStorage.getItem("voiceslide_openai_key") || "";
                const localGemini = localStorage.getItem("voiceslide_gemini_key") || "";
                const localModel = localStorage.getItem("voiceslide_gemini_model") || "gemini-3-flash-preview";
                const localOpenrouter = localStorage.getItem("voiceslide_openrouter_key") || "";
                const localOpenrouterModel = localStorage.getItem("voiceslide_openrouter_model") || "google/gemini-3-flash-preview";
                const localOpenrouterDesignModel = localStorage.getItem("voiceslide_openrouter_design_model") || "google/gemini-3-flash-preview";
                setOpenaiKey(localOpenai);
                setGeminiKey(localGemini);
                setGeminiModel(localModel);
                setOpenrouterKey(localOpenrouter);
                setOpenrouterModel(localOpenrouterModel);
                setOpenrouterDesignModel(localOpenrouterDesignModel);

                if (localOpenai || localGemini || localOpenrouter) {
                    // localStorageにキーがある → Supabaseへ自動移行
                    await supabase.from("user_settings").upsert({
                        user_id: user.id,
                        openai_key: localOpenai,
                        gemini_key: localGemini,
                        gemini_model: localModel,
                        openrouter_key: localOpenrouter,
                        openrouter_model: localOpenrouterModel,
                        openrouter_design_model: localOpenrouterDesignModel,
                    }, { onConflict: "user_id" });
                }
            }
        } else {
            // 未ログイン: localStorageから読み込み（フォールバック）
            setOpenaiKey(localStorage.getItem("voiceslide_openai_key") || "");
            setGeminiKey(localStorage.getItem("voiceslide_gemini_key") || "");
            setGeminiModel(localStorage.getItem("voiceslide_gemini_model") || "gemini-3-flash-preview");
            setOpenrouterKey(localStorage.getItem("voiceslide_openrouter_key") || "");
            setOpenrouterModel(localStorage.getItem("voiceslide_openrouter_model") || "google/gemini-3-flash-preview");
            setOpenrouterDesignModel(localStorage.getItem("voiceslide_openrouter_design_model") || "google/gemini-3-flash-preview");
        }
        setIsLoading(false);
    };

    const syncToLocalStorage = (openai: string, gemini: string, model: string, openrouter: string, openrouterModel: string, openrouterDesignModel: string) => {
        localStorage.setItem("voiceslide_openai_key", openai);
        localStorage.setItem("voiceslide_gemini_key", gemini);
        localStorage.setItem("voiceslide_gemini_model", model || "gemini-3-flash-preview");
        localStorage.setItem("voiceslide_openrouter_key", openrouter);
        localStorage.setItem("voiceslide_openrouter_model", openrouterModel || "google/gemini-3-flash-preview");
        localStorage.setItem("voiceslide_openrouter_design_model", openrouterDesignModel || "google/gemini-3-flash-preview");
    };

    const handleSave = async () => {
        setSaving(true);

        // localStorageにも保存（互換性維持）
        syncToLocalStorage(openaiKey, geminiKey, geminiModel, openrouterKey, openrouterModel, openrouterDesignModel);

        // Supabaseにも保存
        const supabase = createClient();
        const { data: { user } } = await supabase.auth.getUser();
        if (user) {
            await supabase.from("user_settings").upsert({
                user_id: user.id,
                openai_key: openaiKey,
                gemini_key: geminiKey,
                gemini_model: geminiModel,
                openrouter_key: openrouterKey,
                openrouter_model: openrouterModel,
                openrouter_design_model: openrouterDesignModel,
            }, { onConflict: "user_id" });
        }

        setSaving(false);
        setSaved(true);
        setTimeout(() => {
            setSaved(false);
            onClose();
        }, 1000);
    };

    const handleClear = async () => {
        localStorage.removeItem("voiceslide_openai_key");
        localStorage.removeItem("voiceslide_gemini_key");
        localStorage.removeItem("voiceslide_gemini_model");
        localStorage.removeItem("voiceslide_openrouter_key");
        localStorage.removeItem("voiceslide_openrouter_model");
        localStorage.removeItem("voiceslide_openrouter_design_model");
        setOpenaiKey("");
        setGeminiKey("");
        setGeminiModel("gemini-3-flash-preview");
        setOpenrouterKey("");
        setOpenrouterModel("google/gemini-3-flash-preview");
        setOpenrouterDesignModel("google/gemini-3-flash-preview");

        // Supabaseからもクリア
        const supabase = createClient();
        const { data: { user } } = await supabase.auth.getUser();
        if (user) {
            await supabase.from("user_settings").upsert({
                user_id: user.id,
                openai_key: "",
                gemini_key: "",
                gemini_model: "gemini-3-flash-preview",
                openrouter_key: "",
                openrouter_model: "google/gemini-3-flash-preview",
                openrouter_design_model: "google/gemini-3-flash-preview",
            }, { onConflict: "user_id" });
        }
    };

    const hasOpenrouterKey = openrouterKey.trim().length > 0;

    return (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
            <div className="glass rounded-2xl p-6 w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto">
                <div className="flex justify-between items-center mb-6">
                    <h2 className="text-xl font-bold text-white">🔑 APIキー設定</h2>
                    <button
                        onClick={onClose}
                        className="text-zinc-400 hover:text-white text-2xl"
                    >
                        ×
                    </button>
                </div>

                {isLoading ? (
                    <div className="flex items-center justify-center py-8">
                        <svg className="animate-spin h-6 w-6 text-purple-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                        </svg>
                    </div>
                ) : (
                    <>
                        <div className="space-y-4">
                            {/* OpenRouter API Key (Priority) */}
                            <div className="border border-purple-500/30 rounded-xl p-4 bg-purple-500/5">
                                <div className="flex items-center gap-2 mb-3">
                                    <span className="text-sm font-bold text-purple-400">OpenRouter API Key（推奨）</span>
                                    <span className="text-[10px] bg-purple-500/20 text-purple-300 px-2 py-0.5 rounded-full">
                                        多モデル対応
                                    </span>
                                </div>
                                <div className="relative">
                                    <input
                                        type={showOpenrouter ? "text" : "password"}
                                        value={openrouterKey}
                                        onChange={(e) => setOpenrouterKey(e.target.value)}
                                        className="w-full px-4 py-3 bg-zinc-900 border border-zinc-700 rounded-xl text-white focus:border-purple-500 focus:ring-1 focus:ring-purple-500 outline-none pr-12"
                                        placeholder="sk-or-v1-..."
                                        autoComplete="new-password"
                                        autoCorrect="off"
                                        autoCapitalize="off"
                                        spellCheck={false}
                                        data-lpignore="true"
                                        data-1p-ignore="true"
                                        data-form-type="other"
                                        name="openrouter-key-field-no-autofill"
                                    />
                                    <button
                                        type="button"
                                        onClick={() => setShowOpenrouter(!showOpenrouter)}
                                        className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-400 hover:text-white"
                                    >
                                        {showOpenrouter ? "🙈" : "👁️"}
                                    </button>
                                </div>
                                <p className="text-xs text-zinc-500 mt-1">
                                    <a
                                        href="https://openrouter.ai/keys"
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="text-purple-400 hover:underline"
                                    >
                                        OpenRouter
                                    </a>
                                    で取得。Claude, GPT, Gemini等を1つのキーで利用可能
                                </p>

                                {/* OpenRouter Model Selection */}
                                {hasOpenrouterKey && (
                                    <div className="mt-3 space-y-3">
                                        <div>
                                            <label className="block text-sm font-medium text-zinc-400 mb-2">
                                                テキスト生成モデル
                                                <span className="text-[10px] text-zinc-500 ml-2">アウトライン・文字起こし整形</span>
                                            </label>
                                            <select
                                                value={openrouterModel}
                                                onChange={(e) => setOpenrouterModel(e.target.value)}
                                                className="w-full px-4 py-3 bg-zinc-900 border border-zinc-700 rounded-xl text-white focus:border-purple-500 focus:ring-1 focus:ring-purple-500 outline-none appearance-none cursor-pointer"
                                            >
                                                {OPENROUTER_TEXT_MODELS.map((m) => (
                                                    <option key={m.id} value={m.id}>
                                                        {m.label}
                                                    </option>
                                                ))}
                                            </select>
                                        </div>
                                        <div>
                                            <label className="block text-sm font-medium text-zinc-400 mb-2">
                                                デザイン生成モデル
                                                <span className="text-[10px] text-zinc-500 ml-2">スライドHTML生成</span>
                                            </label>
                                            <select
                                                value={openrouterDesignModel}
                                                onChange={(e) => setOpenrouterDesignModel(e.target.value)}
                                                className="w-full px-4 py-3 bg-zinc-900 border border-zinc-700 rounded-xl text-white focus:border-purple-500 focus:ring-1 focus:ring-purple-500 outline-none appearance-none cursor-pointer"
                                            >
                                                {OPENROUTER_DESIGN_MODELS.map((m) => (
                                                    <option key={m.id} value={m.id}>
                                                        {m.label}
                                                    </option>
                                                ))}
                                            </select>
                                        </div>
                                        <p className="text-xs text-zinc-500">
                                            画像生成（イラスト）は引き続きGemini APIを使用します。
                                        </p>
                                    </div>
                                )}
                            </div>

                            {/* Separator */}
                            <div className="flex items-center gap-3 text-zinc-500 text-xs">
                                <div className="flex-1 h-px bg-zinc-700" />
                                {hasOpenrouterKey ? "以下は任意（文字起こし・画像生成用）" : "直接APIキー"}
                                <div className="flex-1 h-px bg-zinc-700" />
                            </div>

                            {/* OpenAI API Key */}
                            <div>
                                <label className="block text-sm font-medium text-zinc-400 mb-2">
                                    OpenAI API Key（文字起こし用）
                                </label>
                                <div className="relative">
                                    <input
                                        type={showOpenai ? "text" : "password"}
                                        value={openaiKey}
                                        onChange={(e) => setOpenaiKey(e.target.value)}
                                        className="w-full px-4 py-3 bg-zinc-900 border border-zinc-700 rounded-xl text-white focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 outline-none pr-12"
                                        placeholder="sk-proj-..."
                                        autoComplete="new-password"
                                        autoCorrect="off"
                                        autoCapitalize="off"
                                        spellCheck={false}
                                        data-lpignore="true"
                                        data-1p-ignore="true"
                                        data-form-type="other"
                                        name="openai-key-field-no-autofill"
                                    />
                                    <button
                                        type="button"
                                        onClick={() => setShowOpenai(!showOpenai)}
                                        className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-400 hover:text-white"
                                    >
                                        {showOpenai ? "🙈" : "👁️"}
                                    </button>
                                </div>
                                <p className="text-xs text-zinc-500 mt-1">
                                    <a
                                        href="https://platform.openai.com/api-keys"
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="text-cyan-500 hover:underline"
                                    >
                                        OpenAI Dashboard
                                    </a>
                                    で取得できます
                                </p>
                            </div>

                            {/* Gemini API Key */}
                            <div>
                                <label className="block text-sm font-medium text-zinc-400 mb-2">
                                    Gemini API Key（{hasOpenrouterKey ? "画像生成用" : "アウトライン・スライド生成用"}）
                                </label>
                                <div className="relative">
                                    <input
                                        type={showGemini ? "text" : "password"}
                                        value={geminiKey}
                                        onChange={(e) => setGeminiKey(e.target.value)}
                                        className="w-full px-4 py-3 bg-zinc-900 border border-zinc-700 rounded-xl text-white focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 outline-none pr-12"
                                        placeholder="AIzaSy..."
                                        autoComplete="new-password"
                                        autoCorrect="off"
                                        autoCapitalize="off"
                                        spellCheck={false}
                                        data-lpignore="true"
                                        data-1p-ignore="true"
                                        data-form-type="other"
                                        name="gemini-key-field-no-autofill"
                                    />
                                    <button
                                        type="button"
                                        onClick={() => setShowGemini(!showGemini)}
                                        className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-400 hover:text-white"
                                    >
                                        {showGemini ? "🙈" : "👁️"}
                                    </button>
                                </div>
                                <p className="text-xs text-zinc-500 mt-1">
                                    <a
                                        href="https://aistudio.google.com/app/apikey"
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="text-cyan-500 hover:underline"
                                    >
                                        Google AI Studio
                                    </a>
                                    で取得できます
                                </p>
                            </div>

                            {/* Gemini Model Selection (only when not using OpenRouter) */}
                            {!hasOpenrouterKey && (
                                <div>
                                    <label className="block text-sm font-medium text-zinc-400 mb-2">
                                        Gemini モデル
                                    </label>
                                    <select
                                        value={geminiModel}
                                        onChange={(e) => setGeminiModel(e.target.value)}
                                        className="w-full px-4 py-3 bg-zinc-900 border border-zinc-700 rounded-xl text-white focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 outline-none appearance-none cursor-pointer"
                                    >
                                        {GEMINI_MODELS.map((m) => (
                                            <option key={m.id} value={m.id}>
                                                {m.label}
                                            </option>
                                        ))}
                                    </select>
                                    <p className="text-xs text-zinc-500 mt-1">
                                        軽量モデルはAPI消費が少なく高速ですが、品質が下がる場合があります
                                    </p>
                                </div>
                            )}

                            {/* Info */}
                            <div className="bg-zinc-800/50 rounded-lg p-3 text-xs text-zinc-400">
                                <p>🔒 APIキーはアカウントに安全に保存されます。</p>
                                {hasOpenrouterKey ? (
                                    <p className="mt-1">💡 OpenRouterキーが設定されているため、テキスト生成にOpenRouterを優先使用します。文字起こし（OpenAI）と画像生成（Gemini）は直接APIキーが必要です。</p>
                                ) : (
                                    <p className="mt-1">💡 両方のキーが必要です。OpenAI（Whisper）とGemini（アウトライン生成）を使用します。</p>
                                )}
                            </div>
                        </div>

                        {/* Buttons */}
                        <div className="flex gap-3 mt-6">
                            <button
                                onClick={handleClear}
                                className="flex-1 px-4 py-3 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-xl transition-colors"
                            >
                                クリア
                            </button>
                            <button
                                onClick={handleSave}
                                disabled={saving}
                                className="flex-1 px-4 py-3 bg-gradient-to-r from-cyan-500 to-blue-500 hover:from-cyan-400 hover:to-blue-400 text-white rounded-xl font-medium transition-all disabled:opacity-50"
                            >
                                {saved ? "✓ 保存しました！" : saving ? "保存中..." : "保存"}
                            </button>
                        </div>
                    </>
                )}
            </div>
        </div>
    );
}

// Helper function to get API keys (localStorage fallback for API calls)
export function getAPIKeys() {
    if (typeof window === "undefined") return { openai: "", gemini: "", geminiModel: "", openrouter: "", openrouterModel: "", openrouterDesignModel: "" };
    return {
        openai: localStorage.getItem("voiceslide_openai_key") || "",
        gemini: localStorage.getItem("voiceslide_gemini_key") || "",
        geminiModel: localStorage.getItem("voiceslide_gemini_model") || "",
        openrouter: localStorage.getItem("voiceslide_openrouter_key") || "",
        openrouterModel: localStorage.getItem("voiceslide_openrouter_model") || "",
        openrouterDesignModel: localStorage.getItem("voiceslide_openrouter_design_model") || "",
    };
}

// Helper function to check if API keys are set
export function hasAPIKeys() {
    const keys = getAPIKeys();
    // OpenRouter key alone is sufficient for text generation (still needs OpenAI for transcription)
    const hasTextGen = keys.openrouter !== "" || keys.gemini !== "";
    return keys.openai !== "" && hasTextGen;
}
