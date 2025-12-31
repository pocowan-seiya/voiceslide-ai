"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function LoginPage() {
    const [password, setPassword] = useState("");
    const [error, setError] = useState("");
    const [isLoading, setIsLoading] = useState(true);
    const [passwordRequired, setPasswordRequired] = useState(true);
    const router = useRouter();

    useEffect(() => {
        checkAuth();
    }, []);

    const checkAuth = async () => {
        try {
            const token = localStorage.getItem("voiceslide_token");
            const res = await fetch(`${API_URL}/api/auth/check`, {
                headers: token ? { Authorization: `Bearer ${token}` } : {},
            });
            const data = await res.json();

            if (data.authenticated) {
                router.push("/");
                return;
            }

            setPasswordRequired(data.password_required);
            if (!data.password_required) {
                // No password required, auto-login
                handleLogin("");
            }
        } catch (err) {
            console.error("Auth check failed:", err);
        } finally {
            setIsLoading(false);
        }
    };

    const handleLogin = async (pwd: string) => {
        setIsLoading(true);
        setError("");

        try {
            const res = await fetch(`${API_URL}/api/auth/login`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ password: pwd }),
            });

            const data = await res.json();

            if (data.success) {
                localStorage.setItem("voiceslide_token", data.token);
                router.push("/");
            } else {
                setError(data.detail || "ログインに失敗しました");
            }
        } catch (err: any) {
            setError("サーバーに接続できません");
        } finally {
            setIsLoading(false);
        }
    };

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        handleLogin(password);
    };

    if (isLoading) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-zinc-950">
                <div className="text-cyan-400 text-xl">読み込み中...</div>
            </div>
        );
    }

    return (
        <div className="min-h-screen flex items-center justify-center bg-zinc-950">
            <div className="glass rounded-2xl p-8 w-full max-w-md">
                <div className="text-center mb-8">
                    <h1 className="text-3xl font-bold gradient-text mb-2">VoiceSlide AI</h1>
                    <p className="text-zinc-400">音声から動画を自動生成</p>
                </div>

                {passwordRequired ? (
                    <form onSubmit={handleSubmit} className="space-y-6">
                        <div>
                            <label
                                htmlFor="password"
                                className="block text-sm font-medium text-zinc-400 mb-2"
                            >
                                アクセスパスワード
                            </label>
                            <input
                                type="password"
                                id="password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                className="w-full px-4 py-3 bg-zinc-900 border border-zinc-700 rounded-xl text-white focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 outline-none"
                                placeholder="パスワードを入力"
                                autoFocus
                            />
                        </div>

                        {error && (
                            <p className="text-red-400 text-sm text-center">{error}</p>
                        )}

                        <button
                            type="submit"
                            disabled={isLoading}
                            className="w-full btn-primary py-3"
                        >
                            {isLoading ? "ログイン中..." : "ログイン"}
                        </button>
                    </form>
                ) : (
                    <div className="text-center text-zinc-400">
                        認証不要のローカルモードです
                    </div>
                )}
            </div>
        </div>
    );
}
