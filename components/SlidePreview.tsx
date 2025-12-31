"use client";

import { useState } from "react";

interface SlidePreviewProps {
    slides: any[];
    slideImages: string[];
    apiUrl: string;
    isProcessing: boolean;
    onApprove: () => void;
}

export function SlidePreview({ slides, slideImages, apiUrl, isProcessing, onApprove }: SlidePreviewProps) {
    const [currentSlide, setCurrentSlide] = useState(0);

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
