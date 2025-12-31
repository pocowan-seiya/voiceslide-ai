"use client";

import { useState, useEffect } from "react";

interface OutlineEditorProps {
    outline: any;
    isProcessing: boolean;
    onApprove: (editedOutline: any) => void;
}

export function OutlineEditor({ outline, isProcessing, onApprove }: OutlineEditorProps) {
    const [editedOutline, setEditedOutline] = useState(outline);

    useEffect(() => {
        setEditedOutline(outline);
    }, [outline]);

    if (isProcessing && !outline) {
        return (
            <div className="text-center py-12">
                <div className="text-6xl mb-4 animate-pulse">📋</div>
                <p className="text-xl">アウトラインを生成中...</p>
                <p className="text-zinc-400 mt-2">最適なスライド構成を考えています</p>
            </div>
        );
    }

    const slides = editedOutline?.outline || [];

    const updateSlide = (index: number, field: string, value: string) => {
        const updatedSlides = [...slides];
        updatedSlides[index] = { ...updatedSlides[index], [field]: value };
        setEditedOutline({ ...editedOutline, outline: updatedSlides });
    };

    const removeSlide = (index: number) => {
        const updatedSlides = slides.filter((_: any, i: number) => i !== index);
        setEditedOutline({ ...editedOutline, outline: updatedSlides });
    };

    const addSlide = () => {
        const newSlide = {
            slide_number: slides.length + 1,
            template_type: "key_points",
            title: "新しいスライド",
            key_message: "",
            suggested_content: "",
        };
        setEditedOutline({ ...editedOutline, outline: [...slides, newSlide] });
    };

    return (
        <div>
            <div className="flex items-center justify-between mb-6">
                <div>
                    <h2 className="text-2xl font-bold gradient-text">スライドアウトライン</h2>
                    <p className="text-zinc-400 mt-1">構成を確認・編集してください</p>
                </div>
                <div className="text-sm text-zinc-500">
                    スライド数: {slides.length}
                </div>
            </div>

            {/* Presentation Title */}
            <div className="mb-6 p-4 bg-zinc-900 rounded-xl">
                <label className="text-sm text-zinc-400 block mb-2">プレゼンタイトル</label>
                <input
                    type="text"
                    value={editedOutline?.presentation_title || ""}
                    onChange={(e) => setEditedOutline({ ...editedOutline, presentation_title: e.target.value })}
                    className="w-full bg-zinc-800 border border-zinc-700 rounded-lg p-3 text-white focus:outline-none focus:ring-2 focus:ring-cyan-500"
                />
            </div>

            {/* Slides List */}
            <div className="space-y-4 mb-6 max-h-96 overflow-y-auto">
                {slides.map((slide: any, index: number) => (
                    <div key={index} className="bg-zinc-900 rounded-xl p-4 border border-zinc-800">
                        <div className="flex items-center justify-between mb-3">
                            <div className="flex items-center gap-3">
                                <span className="w-8 h-8 bg-cyan-500 rounded-lg flex items-center justify-center font-bold text-sm">
                                    {index + 1}
                                </span>
                                <select
                                    value={slide.template_type || "key_points"}
                                    onChange={(e) => updateSlide(index, "template_type", e.target.value)}
                                    className="bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-sm"
                                >
                                    <option value="title">タイトル</option>
                                    <option value="flow">フロー図</option>
                                    <option value="three_columns">3カラム</option>
                                    <option value="four_steps">4ステップ</option>
                                    <option value="comparison">比較</option>
                                    <option value="content_image">コンテンツ+画像</option>
                                    <option value="key_points">要点リスト</option>
                                </select>
                            </div>
                            <button
                                onClick={() => removeSlide(index)}
                                className="text-red-400 hover:text-red-300 text-sm"
                            >
                                削除
                            </button>
                        </div>

                        <input
                            type="text"
                            value={slide.title || ""}
                            onChange={(e) => updateSlide(index, "title", e.target.value)}
                            className="w-full bg-zinc-800 border border-zinc-700 rounded-lg p-2 text-white mb-2 focus:outline-none focus:ring-2 focus:ring-cyan-500"
                            placeholder="スライドタイトル"
                        />

                        <textarea
                            value={slide.key_message || ""}
                            onChange={(e) => updateSlide(index, "key_message", e.target.value)}
                            className="w-full bg-zinc-800 border border-zinc-700 rounded-lg p-2 text-zinc-300 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-cyan-500"
                            placeholder="このスライドの核心メッセージ"
                            rows={2}
                        />
                    </div>
                ))}
            </div>

            <div className="flex items-center justify-between">
                <button
                    onClick={addSlide}
                    className="btn-secondary text-sm"
                >
                    + スライドを追加
                </button>

                <button
                    onClick={() => onApprove(editedOutline)}
                    disabled={isProcessing || slides.length === 0}
                    className="btn-primary"
                >
                    {isProcessing ? "処理中..." : "✓ 承認してスライドをデザイン"}
                </button>
            </div>
        </div>
    );
}
