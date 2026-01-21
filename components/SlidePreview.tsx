"use client";

import { useState } from "react";

interface SlidePreviewProps {
    slides: any[];
    slideImages: string[];
    apiUrl: string;
    isProcessing: boolean;
    onApprove: () => void;
    jobId?: string;  // Added for image regeneration
    geminiKey?: string;  // Optional API key
}

export function SlidePreview({ slides, slideImages, apiUrl, isProcessing, onApprove, jobId, geminiKey }: SlidePreviewProps) {
    const [currentSlide, setCurrentSlide] = useState(0);
    const [imageFeedback, setImageFeedback] = useState("");
    const [isRegenerating, setIsRegenerating] = useState(false);
    const [showFeedbackInput, setShowFeedbackInput] = useState(false);

    const handleRegenerateImage = async () => {
        if (!jobId || !imageFeedback.trim()) return;

        setIsRegenerating(true);
        try {
            const response = await fetch(`${apiUrl}/api/slides/${jobId}/regenerate-image`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...(geminiKey ? { 'X-Gemini-Key': geminiKey } : {})
                },
                body: JSON.stringify({
                    slide_number: currentSlide + 1,
                    feedback: imageFeedback
                })
            });

            if (response.ok) {
                // Force refresh the image by updating the URL with a new timestamp
                const result = await response.json();
                // Trigger a re-render by updating slide (parent component should handle this)
                window.location.reload();  // Simple approach for now
            } else {
                const error = await response.json();
                alert(`画像再生成エラー: ${error.detail || 'Unknown error'}`);
            }
        } catch (error) {
            console.error('Image regeneration failed:', error);
            alert('画像の再生成に失敗しました');
        } finally {
            setIsRegenerating(false);
            setImageFeedback("");
            setShowFeedbackInput(false);
        }
    };

    if (isProcessing && slideImages.length === 0) {
        return (
            <div className="text-center py-12">
                <div className="text-6xl mb-4 animate-pulse">🎨</div>
                <p className="text-xl">スライドをデザイン中...</p>
                <p className="text-zinc-400 mt-2">プロフェッショナルなデザインを生成しています</p>
            </div>
        );
    }

    return (
        <div>
            <div className="flex items-center justify-between mb-6">
                <div>
                    <h2 className="text-2xl font-bold gradient-text">スライドプレビュー</h2>
                    <p className="text-zinc-400 mt-1">生成されたスライドを確認してください</p>
                </div>
                <div className="text-sm text-zinc-500">
                    {currentSlide + 1} / {slideImages.length} スライド
                </div>
            </div>

            {/* Slide Viewer */}
            <div className="bg-zinc-900 rounded-xl p-4 mb-6">
                <div className="aspect-video bg-black rounded-lg overflow-hidden mb-4">
                    {slideImages[currentSlide] && (
                        <img
                            src={`${apiUrl}${slideImages[currentSlide]}`}
                            alt={`Slide ${currentSlide + 1}`}
                            className="w-full h-full object-contain"
                        />
                    )}
                </div>

                {/* Navigation */}
                <div className="flex items-center justify-center gap-4">
                    <button
                        onClick={() => setCurrentSlide(Math.max(0, currentSlide - 1))}
                        disabled={currentSlide === 0}
                        className="btn-secondary text-sm disabled:opacity-30"
                    >
                        ← 前へ
                    </button>

                    <div className="flex gap-2">
                        {slideImages.map((_, index) => (
                            <button
                                key={index}
                                onClick={() => setCurrentSlide(index)}
                                className={`w-3 h-3 rounded-full transition-colors ${index === currentSlide ? 'bg-cyan-500' : 'bg-zinc-600 hover:bg-zinc-500'
                                    }`}
                            />
                        ))}
                    </div>

                    <button
                        onClick={() => setCurrentSlide(Math.min(slideImages.length - 1, currentSlide + 1))}
                        disabled={currentSlide === slideImages.length - 1}
                        className="btn-secondary text-sm disabled:opacity-30"
                    >
                        次へ →
                    </button>
                </div>
            </div>

            {/* Thumbnails */}
            <div className="grid grid-cols-6 gap-2 mb-6 max-h-32 overflow-y-auto">
                {slideImages.map((url, index) => (
                    <button
                        key={index}
                        onClick={() => setCurrentSlide(index)}
                        className={`aspect-video bg-zinc-800 rounded overflow-hidden border-2 transition-colors ${index === currentSlide ? 'border-cyan-500' : 'border-transparent hover:border-zinc-600'
                            }`}
                    >
                        <img
                            src={`${apiUrl}${url}`}
                            alt={`Thumbnail ${index + 1}`}
                            className="w-full h-full object-cover"
                        />
                    </button>
                ))}
            </div>

            {/* Current Slide Info */}
            {slides[currentSlide] && (
                <div className="bg-zinc-900 rounded-xl p-4 mb-6">
                    <div className="flex items-center gap-2 mb-2">
                        <span className="px-2 py-1 bg-cyan-500/20 text-cyan-400 rounded text-xs">
                            {slides[currentSlide].template_type}
                        </span>
                    </div>
                    <h3 className="font-semibold text-lg">{slides[currentSlide].title}</h3>
                    {slides[currentSlide].subtitle && (
                        <p className="text-zinc-400 text-sm mt-1">{slides[currentSlide].subtitle}</p>
                    )}
                </div>
            )}

            {/* Image Regeneration UI */}
            {jobId && (
                <div className="bg-zinc-900 rounded-xl p-4 mb-6">
                    <div className="flex items-center justify-between mb-3">
                        <h4 className="font-semibold text-sm text-zinc-300">🎨 画像を再生成</h4>
                        <button
                            onClick={() => setShowFeedbackInput(!showFeedbackInput)}
                            className="text-xs text-cyan-400 hover:text-cyan-300"
                        >
                            {showFeedbackInput ? "閉じる" : "フィードバックを入力"}
                        </button>
                    </div>

                    {showFeedbackInput && (
                        <div className="space-y-3">
                            <textarea
                                value={imageFeedback}
                                onChange={(e) => setImageFeedback(e.target.value)}
                                placeholder="例: もっと明るく、キャラクターを増やして、背景をシンプルに..."
                                className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-white placeholder-zinc-500 focus:border-cyan-500 focus:outline-none"
                                rows={2}
                            />
                            <div className="flex gap-2">
                                <button
                                    onClick={handleRegenerateImage}
                                    disabled={isRegenerating || !imageFeedback.trim()}
                                    className="flex-1 px-4 py-2 bg-gradient-to-r from-cyan-500 to-purple-500 text-white rounded-lg text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed hover:from-cyan-400 hover:to-purple-400 transition-all"
                                >
                                    {isRegenerating ? "再生成中..." : "🔄 この画像を再生成"}
                                </button>
                            </div>
                            <p className="text-xs text-zinc-500">
                                ※ イラストモードの画像のみ再生成できます
                            </p>
                        </div>
                    )}
                </div>
            )}

            <div className="flex justify-end">
                <button
                    onClick={onApprove}
                    disabled={isProcessing}
                    className="btn-primary"
                >
                    {isProcessing ? "処理中..." : "✓ 承認して動画を生成"}
                </button>
            </div>
        </div>
    );
}
