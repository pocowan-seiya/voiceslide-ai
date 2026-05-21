"use client";

import { useCallback, useState } from "react";

interface FileUploaderProps {
    onFileSelect: (file: File) => void;
    selectedFile: File | null;
    disabled?: boolean;
}

const isValidAudioFile = (file: File) => {
    const validTypes = ["audio/mpeg", "audio/wav", "audio/mp3", "audio/x-wav", "audio/m4a", "audio/x-m4a", "audio/mp4"];
    return validTypes.includes(file.type) || file.name.endsWith(".mp3") || file.name.endsWith(".wav") || file.name.endsWith(".m4a");
};

export function FileUploader({ onFileSelect, selectedFile, disabled }: FileUploaderProps) {
    const [isDragOver, setIsDragOver] = useState(false);

    const handleDragOver = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        if (!disabled) {
            setIsDragOver(true);
        }
    }, [disabled]);

    const handleDragLeave = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragOver(false);
    }, []);

    const handleDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragOver(false);

        if (disabled) return;

        const files = e.dataTransfer.files;
        if (files.length > 0) {
            const file = files[0];
            if (isValidAudioFile(file)) {
                onFileSelect(file);
            }
        }
    }, [disabled, onFileSelect]);

    const handleFileInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
        const files = e.target.files;
        if (files && files.length > 0) {
            const file = files[0];
            if (isValidAudioFile(file)) {
                onFileSelect(file);
            }
        }
    }, [onFileSelect]);

    const formatFileSize = (bytes: number) => {
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    };

    return (
        <div className="w-full">
            <label
                className={`upload-zone flex flex-col items-center justify-center w-full h-64 rounded-xl cursor-pointer transition-all ${isDragOver ? "drag-over" : ""
                    } ${disabled ? "opacity-50 cursor-not-allowed" : ""}`}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
            >
                {selectedFile ? (
                    <div className="text-center">
                        <span className="text-6xl mb-4 block">🎵</span>
                        <p className="text-lg font-medium text-white mb-2">{selectedFile.name}</p>
                        <p className="text-sm text-zinc-400">{formatFileSize(selectedFile.size)}</p>
                        <p className="text-sm text-zinc-500 mt-4">別のファイルを選択するにはクリック</p>
                    </div>
                ) : (
                    <div className="text-center">
                        <span className="text-6xl mb-4 block opacity-50">🎙️</span>
                        <p className="text-lg font-medium text-zinc-300 mb-2">
                            音声ファイルをドラッグ&ドロップ
                        </p>
                        <p className="text-sm text-zinc-500">
                            またはクリックしてファイルを選択
                        </p>
                        <p className="text-xs text-zinc-600 mt-4">
                            対応形式: MP3, WAV, M4A
                        </p>
                    </div>
                )}

                <input
                    type="file"
                    accept=".mp3,.wav,.m4a,audio/mpeg,audio/wav,audio/m4a"
                    onChange={handleFileInput}
                    disabled={disabled}
                    className="hidden"
                />
            </label>
        </div>
    );
}
