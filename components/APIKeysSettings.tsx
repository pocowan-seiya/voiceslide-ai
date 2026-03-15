"use client";

import { useState, useEffect } from "react";

const GEMINI_MODELS = [
    { id: "gemini-3-flash-preview", label: "Gemini 3 Flash Preview (デフォルト)" },
    { id: "gemini-3.1-flash-lite-preview", label: "Gemini 3.1 Flash Lite ⚡ 最新・超軽量" },
    { id: "gemini-2.5-flash-lite", label: "Gemini 2.5 Flash Lite (軽量・安定版)" },
    { id: "gemini-2.5-flash", label: "Gemini 2.5 Flash" },
    { id: "gemini-2.0-flash", label: "Gemini 2.0 Flash" },
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

    useEffect(() => {
        // Load saved keys from localStorage
        const savedOpenai = localStorage.getItem("voiceslide_openai_key") || "";
        const savedGemini = localStorage.getItem("voiceslide_gemini_key") || "";
        const savedModel = localStorage.getItem("voiceslide_gemini_model") || "gemini-3-flash-preview";
        setOpenaiKey(savedOpenai);
        setGeminiKey(savedGemini);
        setGeminiModel(savedModel);
    }, []);

    const handleSave = () => {
        localStorage.setItem("voiceslide_openai_key", openaiKey);
        localStorage.setItem("voiceslide_gemini_key", geminiKey);
        localStorage.setItem("voiceslide_gemini_model", geminiModel);
        setSaved(true);
        setTimeout(() => {
            setSaved(false);
            onClose();
        }, 1000);
    };

    const handleClear = () => {
        localStorage.removeItem("voiceslide_openai_key");
        localStorage.removeItem("voiceslide_gemini_key");
        localStorage.removeItem("voiceslide_gemini_model");
        setOpenaiKey("");
        setGeminiKey("");
        setGeminiModel("gemini-3-flash-preview");
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
