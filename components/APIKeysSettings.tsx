"use client";

import { useState, useEffect } from "react";

interface APIKeysSettingsProps {
    onClose: () => void;
}

export function APIKeysSettings({ onClose }: APIKeysSettingsProps) {
    const [openaiKey, setOpenaiKey] = useState("");
    const [geminiKey, setGeminiKey] = useState("");
    const [showOpenai, setShowOpenai] = useState(false);
    const [showGemini, setShowGemini] = useState(false);
    const [saved, setSaved] = useState(false);

    useEffect(() => {
        // Load saved keys from localStorage
        const savedOpenai = localStorage.getItem("voiceslide_openai_key") || "";
        const savedGemini = localStorage.getItem("voiceslide_gemini_key") || "";
        setOpenaiKey(savedOpenai);
        setGeminiKey(savedGemini);
    }, []);

    const handleSave = () => {
        localStorage.setItem("voiceslide_openai_key", openaiKey);
        localStorage.setItem("voiceslide_gemini_key", geminiKey);
        setSaved(true);
        setTimeout(() => {
            setSaved(false);
            onClose();
        }, 1000);
    };

    const handleClear = () => {
        localStorage.removeItem("voiceslide_openai_key");
        localStorage.removeItem("voiceslide_gemini_key");
        setOpenaiKey("");
        setGeminiKey("");
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

                    {/* Info */}
                    <div className="bg-zinc-800/50 rounded-lg p-3 text-xs text-zinc-400">
                        <p>⚠️ APIキーはブラウザに保存され、サーバーには保存されません。</p>
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
                        className="flex-1 px-4 py-3 bg-gradient-to-r from-cyan-500 to-blue-500 hover:from-cyan-400 hover:to-blue-400 text-white rounded-xl font-medium transition-all"
                    >
                        {saved ? "✓ 保存しました！" : "保存"}
                    </button>
                </div>
            </div>
        </div>
    );
}

// Helper function to get API keys
export function getAPIKeys() {
    if (typeof window === "undefined") return { openai: "", gemini: "" };
    return {
        openai: localStorage.getItem("voiceslide_openai_key") || "",
        gemini: localStorage.getItem("voiceslide_gemini_key") || "",
    };
}

// Helper function to check if API keys are set
export function hasAPIKeys() {
    const keys = getAPIKeys();
    return keys.openai !== "" && keys.gemini !== "";
}
