"use client";

interface ProgressTrackerProps {
    currentStep: number;
    stepName: string;
    progress: number;
}

const steps = [
    { id: 1, name: "アップロード", icon: "📤" },
    { id: 2, name: "文字起こし", icon: "📝" },
    { id: 3, name: "スライド生成", icon: "🎨" },
    { id: 4, name: "動画合成", icon: "🎬" },
];

export function ProgressTracker({ currentStep, stepName, progress }: ProgressTrackerProps) {
    return (
        <div className="w-full">
            {/* Step Indicators */}
            <div className="flex justify-between mb-8">
                {steps.map((step, index) => {
                    const isCompleted = currentStep > step.id;
                    const isActive = currentStep === step.id;
                    const isPending = currentStep < step.id;

                    return (
                        <div key={step.id} className="flex flex-col items-center relative">
                            {/* Connector Line */}
                            {index < steps.length - 1 && (
                                <div
                                    className={`absolute top-5 left-1/2 w-full h-0.5 ${isCompleted ? "bg-green-500" : "bg-zinc-700"
                                        }`}
                                    style={{ transform: "translateX(50%)" }}
                                />
                            )}

                            {/* Step Circle */}
                            <div
                                className={`step-indicator z-10 ${isCompleted ? "completed" : isActive ? "active animate-pulse-glow" : "pending"
                                    }`}
                            >
                                {isCompleted ? (
                                    <span className="text-lg">✓</span>
                                ) : (
                                    <span className="text-lg">{step.icon}</span>
                                )}
                            </div>

                            {/* Step Label */}
                            <span
                                className={`mt-2 text-sm font-medium ${isCompleted ? "text-green-400" : isActive ? "text-white" : "text-zinc-500"
                                    }`}
                            >
                                {step.name}
                            </span>
                        </div>
                    );
                })}
            </div>

            {/* Progress Bar */}
            <div className="progress-bar mb-4">
                <div
                    className={`progress-fill ${progress >= 100 ? "bg-green-500" : "animate-shimmer"}`}
                    style={{ width: `${progress}%` }}
                />
            </div>

            {/* Current Step Info */}
            <div className="flex items-center justify-between text-sm">
                <span className="text-zinc-400">{stepName}</span>
                <span className="font-mono text-zinc-300">{progress}%</span>
            </div>

            {/* Estimated Time */}
            {progress < 100 && (
                <p className="text-center text-zinc-500 text-sm mt-4">
                    処理中です。しばらくお待ちください...
                </p>
            )}
        </div>
    );
}
