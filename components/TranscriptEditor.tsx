"use client";

import { useState } from "react";

interface TranscriptEditorProps {
    transcript: string;
    isProcessing: boolean;
    onApprove: (editedTranscript: string) => void;
}

export function TranscriptEditor({ transcript, isProcessing, onApprove }: TranscriptEditorProps) {
    const [editedTranscript, setEditedTranscript] = useState(transcript);

    if (isProcessing && !transcript) {
        return (
            <div className="text-center py-12">
                <div className="text-6xl mb-4 animate-pulse">🎙️</div>
                <p className="text-xl">文字起こし中...</p>
                <p className="text-zinc-400 mt-2">音声を分析しています</p>
            </div>
        );
    }

    return (
        <div>
            <div className="flex items-center justify-between mb-6">
                <div>
                    <h2 className="text-2xl font-bold gradient-text">文字起こし結果</h2>
                    <p className="text-zinc-400 mt-1">内容を確認・編集してください</p>
                </div>
                <div className="text-sm text-zinc-500">
                    文字数: {editedTranscript.length}
                </div>
            </div>

            <div className="mb-6">
                <textarea
                    value={editedTranscript}
                    onChange={(e) => setEditedTranscript(e.target.value)}
                    className="w-full h-80 bg-zinc-900 border border-zinc-700 rounded-xl p-4 text-white resize-none focus:outline-none focus:ring-2 focus:ring-cyan-500"
                    placeholder="文字起こし結果がここに表示されます..."
                />
            </div>

            <div className="flex items-center justify-between">
                <p className="text-sm text-zinc-500">
                    💡 誤字脱字の修正や、不要な部分の削除ができます
                </p>
                <button
                    onClick={() => onApprove(editedTranscript)}
                    disabled={isProcessing || !editedTranscript}
                    className="btn-primary"
                >
                    {isProcessing ? "処理中..." : "✓ 承認してアウトラインを生成"}
                </button>
            </div>
        </div>
    );
}
