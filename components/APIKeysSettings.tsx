"use client";

import { useState, useEffect } from "react";
import { createClient } from "@/lib/supabase/client";
import type { UserSettings } from "@/lib/supabase/types";

const GEMINI_MODELS = [
    { id: "gemini-3-flash-preview", label: "Gemini 3 Flash Preview" },
    { id: "gemini-3.1-flash-lite-preview", label: "Gemini 3.1 Flash Lite Preview" },
];

interface APIKeysSettingsProps {
    onClose: () => void;
}

export function APIKeysSettings({ onClose }: APIKeysSettingsProps) {
    const [openaiKey, setOpenaiKey] = useState("");
    const [geminiKey, setGeminiKey] = useState("");
    const [geminiModel, setGeminiModel] = useState("gemini-3-flash-preview");
    const [showOpenai, setShowOpenai] = useState(false);
    const [showGemini, setShowGemini] = useState(false);
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

            if (data && (data.openai_key || data.gemini_key)) {
                // Supabaseにキーがある → それを使う
                setOpenaiKey(data.openai_key);
                setGeminiKey(data.gemini_key);
                setGeminiModel(data.gemini_model || "gemini-3-flash-preview");
                // localStorageにもバックアップ
                syncToLocalStorage(data.openai_key, data.gemini_key, data.gemini_model);
            } else {
                // Supabaseにキーが無い → localStorageから移行
                const localOpenai = localStorage.getItem("voiceslide_openai_key") || "";
                const localGemini = localStorage.getItem("voiceslide_gemini_key") || "";
                const localModel = localStorage.getItem("voiceslide_gemini_model") || "gemini-3-flash-preview";
                setOpenaiKey(localOpenai);
                setGeminiKey(localGemini);
                setGeminiModel(localModel);

                if (localOpenai || localGemini) {
                    // localStorageにキーがある → Supabaseへ自動移行
                    await supabase.from("user_settings").upsert({
                        user_id: user.id,
                        openai_key: localOpenai,
                        gemini_key: localGemini,
                        gemini_model: localModel,
                    }, { onConflict: "user_id" });
                }
            }
        } else {
            // 未ログイン: localStorageから読み込み（フォールバック）
            setOpenaiKey(localStorage.getItem("voiceslide_openai_key") || "");
            setGeminiKey(localStorage.getItem("voiceslide_gemini_key") || "");
            setGeminiModel(localStorage.getItem("voiceslide_gemini_model") || "gemini-3-flash-preview");
        }
        setIsLoading(false);
    };

    const syncToLocalStorage = (openai: string, gemini: string, model: string) => {
        localStorage.setItem("voiceslide_openai_key", openai);
        localStorage.setItem("voiceslide_gemini_key", gemini);
        localStorage.setItem("voiceslide_gemini_model", model || "gemini-3-flash-preview");
    };

    const handleSave = async () => {
        setSaving(true);

        // localStorageにも保存（互換性維持）
        syncToLocalStorage(openaiKey, geminiKey, geminiModel);

        // Supabaseにも保存
        const supabase = createClient();
        const { data: { user } } = await supabase.auth.getUser();
        if (user) {
            await supabase.from("user_settings").upsert({
                user_id: user.id,
                openai_key: openaiKey,
                gemini_key: geminiKey,
                gemini_model: geminiModel,
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
        setOpenaiKey("");
        setGeminiKey("");
        setGeminiModel("gemini-3-flash-preview");

        // Supabaseからもクリア
        const supabase = createClient();
        const { data: { user } } = await supabase.auth.getUser();
        if (user) {
            await supabase.from("user_settings").upsert({
                user_id: user.id,
                openai_key: "",
                gemini_key: "",
                gemini_model: "gemini-3-flash-preview",
            }, { onConflict: "user_id" });
        }
    };

    return (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
            <div className="glass rounded-2xl p-6 w-full max-w-lg mx-4">
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
                                    Gemini API Key（アウトライン・スライド生成用）
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

                            {/* Gemini Model Selection */}
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

                            {/* Info */}
                            <div className="bg-zinc-800/50 rounded-lg p-3 text-xs text-zinc-400">
                                <p>🔒 APIキーはアカウントに安全に保存されます。</p>
                                <p className="mt-1">💡 両方のキーが必要です。OpenAI（Whisper）とGemini（アウトライン生成）を使用します。</p>
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
    if (typeof window === "undefined") return { openai: "", gemini: "", geminiModel: "" };
    return {
        openai: localStorage.getItem("voiceslide_openai_key") || "",
        gemini: localStorage.getItem("voiceslide_gemini_key") || "",
        geminiModel: localStorage.getItem("voiceslide_gemini_model") || "",
    };
}

// Helper function to check if API keys are set
export function hasAPIKeys() {
    const keys = getAPIKeys();
    return keys.openai !== "" && keys.gemini !== "";
}
