"use client";

import { useState, useRef } from "react";

interface VideoPreviewProps {
    jobId: string;
    apiUrl: string;
}

export function VideoPreview({ jobId, apiUrl }: VideoPreviewProps) {
    const [isPlaying, setIsPlaying] = useState(false);
    const videoRef = useRef<HTMLVideoElement>(null);

    const videoUrl = `${apiUrl}/api/download/${jobId}`;

    const handlePlayPause = () => {
        if (videoRef.current) {
            if (isPlaying) {
                videoRef.current.pause();
            } else {
                videoRef.current.play();
            }
            setIsPlaying(!isPlaying);
        }
    };

    return (
        <div className="relative video-container bg-black">
            <video
                ref={videoRef}
                src={videoUrl}
                className="w-full aspect-video"
                controls
                onPlay={() => setIsPlaying(true)}
                onPause={() => setIsPlaying(false)}
            >
                Your browser does not support the video tag.
            </video>

            {/* Overlay Play Button (shown when not playing) */}
            {!isPlaying && (
                <button
                    onClick={handlePlayPause}
                    className="absolute inset-0 flex items-center justify-center bg-black/30 hover:bg-black/40 transition-colors"
                >
                    <div className="w-20 h-20 rounded-full bg-white/20 backdrop-blur-sm flex items-center justify-center hover:scale-110 transition-transform">
                        <svg
                            className="w-10 h-10 text-white ml-1"
                            fill="currentColor"
                            viewBox="0 0 24 24"
                        >
                            <path d="M8 5v14l11-7z" />
                        </svg>
                    </div>
                </button>
            )}

            {/* Video Info */}
            <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/80 to-transparent p-4">
                <div className="flex items-center justify-between text-sm text-white/80">
                    <span>VoiSlide で生成</span>
                    <span>720p HD</span>
                </div>
            </div>
        </div>
    );
}
