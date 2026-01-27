"use client";

import { useState, useRef, useEffect } from "react";

interface Message {
    role: "user" | "assistant";
    content: string;
    timestamp: Date;
}

interface ErrorContext {
    step: string;
    errorMessage: string;
    workflowMode: string;
    timestamp: string;
}

interface SupportChatProps {
    errorContext?: ErrorContext;
    apiUrl: string;
    geminiKey?: string;
}

type TabType = "chat" | "feedback";
type FeedbackCategory = "error" | "request" | "feedback";

export function SupportChat({ errorContext, apiUrl, geminiKey }: SupportChatProps) {
    const [isOpen, setIsOpen] = useState(false);
    const [activeTab, setActiveTab] = useState<TabType>("chat");
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const [hasNewError, setHasNewError] = useState(false);
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLInputElement>(null);

    // Feedback form state
    const [feedbackCategory, setFeedbackCategory] = useState<FeedbackCategory>("feedback");
    const [feedbackMessage, setFeedbackMessage] = useState("");
    const [feedbackSent, setFeedbackSent] = useState(false);
    const [isSendingFeedback, setIsSendingFeedback] = useState(false);
    const [chatFeedbackSent, setChatFeedbackSent] = useState(false);

    // エラーコンテキストが変わったら通知
    useEffect(() => {
        if (errorContext?.errorMessage) {
            setHasNewError(true);
        }
    }, [errorContext?.errorMessage]);

    // メッセージが追加されたら自動スクロール
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages]);

    // チャットを開いたときにフォーカス
    useEffect(() => {
        if (isOpen) {
            inputRef.current?.focus();
            setHasNewError(false);
        }
    }, [isOpen]);

    const sendMessage = async (content: string, includeContext: boolean = false) => {
        if (!content.trim() && !includeContext) return;

        const userMessage = includeContext && errorContext
            ? `エラーが発生しました。\n\nエラー内容: ${errorContext.errorMessage}\nステップ: ${errorContext.step}\nモード: ${errorContext.workflowMode}\n\n${content || "このエラーの原因と解決方法を教えてください。"}`
            : content;

        const newUserMessage: Message = {
            role: "user",
            content: userMessage,
            timestamp: new Date(),
        };

        setMessages((prev) => [...prev, newUserMessage]);
        setInput("");
        setIsLoading(true);

        try {
            const response = await fetch(`${apiUrl}/support/chat`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    ...(geminiKey && { "X-Gemini-Key": geminiKey }),
                },
                body: JSON.stringify({
                    message: userMessage,
                    context: includeContext ? errorContext : undefined,
                    history: messages.map((m) => ({ role: m.role, content: m.content })),
                }),
            });

            if (!response.ok) {
                throw new Error("チャットサーバーに接続できませんでした");
            }

            const data = await response.json();

            const assistantMessage: Message = {
                role: "assistant",
                content: data.reply,
                timestamp: new Date(),
            };

            setMessages((prev) => [...prev, assistantMessage]);
        } catch {
            const errorMessage: Message = {
                role: "assistant",
                content: "申し訳ございません。一時的にサポートに接続できませんでした。しばらくしてからお試しください。",
                timestamp: new Date(),
            };
            setMessages((prev) => [...prev, errorMessage]);
        } finally {
            setIsLoading(false);
        }
    };

    const sendFeedback = async () => {
        if (!feedbackMessage.trim()) return;

        setIsSendingFeedback(true);

        try {
            const response = await fetch(`${apiUrl}/support/feedback`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    category: feedbackCategory,
                    message: feedbackMessage,
                    context: errorContext,
                }),
            });

            if (response.ok) {
                setFeedbackSent(true);
                setFeedbackMessage("");
                setTimeout(() => setFeedbackSent(false), 3000);
            }
        } catch {
            console.error("Feedback send failed");
        } finally {
            setIsSendingFeedback(false);
        }
    };

    const sendChatAsFeedback = async () => {
        if (messages.length === 0) return;

        setIsSendingFeedback(true);

        // Format conversation for email
        const conversationText = messages
            .map((m) => `[${m.role === "user" ? "ユーザー" : "AI"}] ${m.content}`)
            .join("\n\n");

        try {
            const response = await fetch(`${apiUrl}/support/feedback`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    category: "feedback",
                    message: `【チャット会話からのフィードバック】\n\n${conversationText}`,
                    context: errorContext,
                }),
            });

            if (response.ok) {
                setChatFeedbackSent(true);
                setTimeout(() => setChatFeedbackSent(false), 3000);
            }
        } catch {
            console.error("Chat feedback send failed");
        } finally {
            setIsSendingFeedback(false);
        }
    };

    const handleKeyPress = (e: React.KeyboardEvent) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            sendMessage(input);
        }
    };

    const handleOpenWithError = () => {
        setIsOpen(true);
        setHasNewError(false);
        // エラーコンテキストがあれば自動送信
        if (errorContext?.errorMessage) {
            setTimeout(() => sendMessage("", true), 300);
        }
    };

    const categoryLabels: Record<FeedbackCategory, { icon: string; label: string }> = {
        error: { icon: "🚨", label: "エラー報告" },
        request: { icon: "💡", label: "機能リクエスト" },
        feedback: { icon: "📝", label: "感想・フィードバック" },
    };

    return (
        <>
            {/* フローティングボタン */}
            <button
                onClick={() => (errorContext?.errorMessage ? handleOpenWithError() : setIsOpen(!isOpen))}
                className={`
          fixed bottom-6 right-6 z-50
          w-14 h-14 rounded-full
          flex items-center justify-center
          transition-all duration-300
          ${hasNewError
                        ? "bg-gradient-to-r from-red-500 to-orange-500 animate-pulse"
                        : "bg-gradient-to-r from-indigo-500 to-purple-600"
                    }
          hover:scale-110 hover:shadow-lg hover:shadow-indigo-500/30
          ${isOpen ? "rotate-45" : ""}
        `}
                title={hasNewError ? "エラーについてサポートに相談" : "サポートチャット"}
            >
                {isOpen ? (
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                ) : (
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                    </svg>
                )}
                {hasNewError && !isOpen && (
                    <span className="absolute -top-1 -right-1 w-4 h-4 bg-red-500 rounded-full animate-ping" />
                )}
            </button>

            {/* チャットウィンドウ */}
            {isOpen && (
                <div
                    className="
            fixed bottom-24 right-6 z-50
            w-96 h-[500px] max-h-[70vh]
            rounded-2xl overflow-hidden
            flex flex-col
            animate-slide-up
            shadow-2xl shadow-black/50
          "
                    style={{
                        background: "rgba(24, 24, 27, 0.95)",
                        backdropFilter: "blur(20px)",
                        border: "1px solid rgba(255, 255, 255, 0.1)",
                    }}
                >
                    {/* ヘッダー + タブ */}
                    <div
                        className="px-5 py-4"
                        style={{
                            background: "linear-gradient(135deg, rgba(99, 102, 241, 0.2) 0%, rgba(139, 92, 246, 0.2) 100%)",
                            borderBottom: "1px solid rgba(255, 255, 255, 0.1)",
                        }}
                    >
                        <div className="flex items-center gap-3 mb-3">
                            <div className="w-10 h-10 rounded-full bg-gradient-to-r from-indigo-500 to-purple-600 flex items-center justify-center">
                                <span className="text-xl">🤖</span>
                            </div>
                            <div>
                                <h3 className="font-semibold text-white">VoiSlide サポート</h3>
                                <p className="text-xs text-gray-400">AIがお手伝いします</p>
                            </div>
                        </div>

                        {/* タブ切り替え */}
                        <div className="flex gap-2">
                            <button
                                onClick={() => setActiveTab("chat")}
                                className={`flex-1 py-2 px-3 rounded-lg text-sm font-medium transition-colors ${activeTab === "chat"
                                    ? "bg-indigo-500/30 text-indigo-300"
                                    : "text-gray-400 hover:text-gray-300"
                                    }`}
                            >
                                💬 チャット
                            </button>
                            <button
                                onClick={() => setActiveTab("feedback")}
                                className={`flex-1 py-2 px-3 rounded-lg text-sm font-medium transition-colors ${activeTab === "feedback"
                                    ? "bg-indigo-500/30 text-indigo-300"
                                    : "text-gray-400 hover:text-gray-300"
                                    }`}
                            >
                                📩 フィードバック
                            </button>
                        </div>
                    </div>

                    {/* チャットタブ */}
                    {activeTab === "chat" && (
                        <>
                            <div className="flex-1 overflow-y-auto p-4 space-y-4">
                                {messages.length === 0 && (
                                    <div className="text-center text-gray-500 py-8">
                                        <p className="text-4xl mb-3">👋</p>
                                        <p className="text-sm">こんにちは！</p>
                                        <p className="text-sm">エラーや操作について、お気軽にご質問ください。</p>
                                    </div>
                                )}

                                {messages.map((msg, idx) => (
                                    <div
                                        key={idx}
                                        className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                                    >
                                        <div
                                            className={`
                    max-w-[80%] px-4 py-3 rounded-2xl
                    ${msg.role === "user"
                                                    ? "bg-gradient-to-r from-indigo-500 to-purple-600 text-white rounded-br-md"
                                                    : "bg-zinc-800 text-gray-100 rounded-bl-md"
                                                }
                  `}
                                        >
                                            <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                                            <p className="text-xs opacity-50 mt-1">
                                                {msg.timestamp.toLocaleTimeString("ja-JP", { hour: "2-digit", minute: "2-digit" })}
                                            </p>
                                        </div>
                                    </div>
                                ))}

                                {isLoading && (
                                    <div className="flex justify-start">
                                        <div className="bg-zinc-800 px-4 py-3 rounded-2xl rounded-bl-md">
                                            <div className="flex gap-1">
                                                <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                                                <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                                                <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                                            </div>
                                        </div>
                                    </div>
                                )}

                                <div ref={messagesEndRef} />
                            </div>

                            <div className="p-4" style={{ borderTop: "1px solid rgba(255, 255, 255, 0.1)" }}>
                                <div className="flex gap-2">
                                    <input
                                        ref={inputRef}
                                        type="text"
                                        value={input}
                                        onChange={(e) => setInput(e.target.value)}
                                        onKeyPress={handleKeyPress}
                                        placeholder="メッセージを入力..."
                                        disabled={isLoading}
                                        className="flex-1 px-4 py-3 rounded-xl bg-zinc-800 text-white placeholder-gray-500 border border-zinc-700 focus:outline-none focus:border-indigo-500 transition-colors disabled:opacity-50"
                                    />
                                    <button
                                        onClick={() => sendMessage(input)}
                                        disabled={isLoading || !input.trim()}
                                        className="px-4 py-3 rounded-xl bg-gradient-to-r from-indigo-500 to-purple-600 text-white font-medium hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed"
                                    >
                                        <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                                        </svg>
                                    </button>
                                </div>

                                {/* フィードバックを送信ボタン */}
                                {messages.length > 0 && (
                                    <div className="mt-2">
                                        {chatFeedbackSent ? (
                                            <p className="text-center text-sm text-green-400">✅ フィードバックを送信しました！</p>
                                        ) : (
                                            <button
                                                onClick={sendChatAsFeedback}
                                                disabled={isSendingFeedback}
                                                className="w-full py-2 px-3 rounded-lg text-sm text-gray-400 hover:text-indigo-300 hover:bg-indigo-500/10 transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
                                            >
                                                <span>📩</span>
                                                <span>{isSendingFeedback ? "送信中..." : "この会話をフィードバックとして送信"}</span>
                                            </button>
                                        )}
                                    </div>
                                )}
                            </div>
                        </>
                    )}

                    {/* フィードバックタブ */}
                    {activeTab === "feedback" && (
                        <div className="flex-1 overflow-y-auto p-4">
                            {feedbackSent ? (
                                <div className="text-center py-12">
                                    <p className="text-5xl mb-4">✅</p>
                                    <p className="text-lg text-white font-medium">送信しました！</p>
                                    <p className="text-sm text-gray-400 mt-2">貴重なご意見をありがとうございます。</p>
                                </div>
                            ) : (
                                <>
                                    <p className="text-sm text-gray-400 mb-4">
                                        ご意見・ご要望をお聞かせください。開発チームに直接届きます。
                                    </p>

                                    {/* カテゴリ選択 */}
                                    <div className="space-y-2 mb-4">
                                        {(Object.keys(categoryLabels) as FeedbackCategory[]).map((cat) => (
                                            <button
                                                key={cat}
                                                onClick={() => setFeedbackCategory(cat)}
                                                className={`w-full py-3 px-4 rounded-xl text-left flex items-center gap-3 transition-colors ${feedbackCategory === cat
                                                    ? "bg-indigo-500/20 border border-indigo-500/50 text-white"
                                                    : "bg-zinc-800 border border-zinc-700 text-gray-400 hover:text-white"
                                                    }`}
                                            >
                                                <span className="text-xl">{categoryLabels[cat].icon}</span>
                                                <span className="font-medium">{categoryLabels[cat].label}</span>
                                            </button>
                                        ))}
                                    </div>

                                    {/* メッセージ入力 */}
                                    <textarea
                                        value={feedbackMessage}
                                        onChange={(e) => setFeedbackMessage(e.target.value)}
                                        placeholder="詳細を入力してください..."
                                        rows={4}
                                        className="w-full px-4 py-3 rounded-xl bg-zinc-800 text-white placeholder-gray-500 border border-zinc-700 focus:outline-none focus:border-indigo-500 transition-colors resize-none"
                                    />

                                    {/* エラーコンテキスト表示 */}
                                    {errorContext && feedbackCategory === "error" && (
                                        <div className="mt-3 p-3 rounded-lg bg-red-500/10 border border-red-500/20">
                                            <p className="text-xs text-red-400 mb-1">自動収集されたエラー情報:</p>
                                            <p className="text-xs text-gray-400">{errorContext.errorMessage}</p>
                                        </div>
                                    )}

                                    {/* 送信ボタン */}
                                    <button
                                        onClick={sendFeedback}
                                        disabled={!feedbackMessage.trim() || isSendingFeedback}
                                        className="w-full mt-4 py-3 rounded-xl bg-gradient-to-r from-indigo-500 to-purple-600 text-white font-medium hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed"
                                    >
                                        {isSendingFeedback ? "送信中..." : "送信する"}
                                    </button>
                                </>
                            )}
                        </div>
                    )}
                </div>
            )}
        </>
    );
}

// エラー発生時に表示するヘルプボタン
export function ErrorHelpButton({
    onClick,
}: {
    onClick: () => void;
    errorMessage: string;
}) {
    return (
        <button
            onClick={onClick}
            className="
        ml-3 px-3 py-1.5 rounded-lg
        bg-gradient-to-r from-indigo-500/20 to-purple-600/20
        border border-indigo-500/30
        text-indigo-300 text-sm font-medium
        hover:from-indigo-500/30 hover:to-purple-600/30
        transition-all duration-200
        flex items-center gap-1.5
      "
        >
            <span>💬</span>
            <span>サポートに相談</span>
        </button>
    );
}
