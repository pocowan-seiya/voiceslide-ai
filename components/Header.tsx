"use client";

export function Header() {
    return (
        <header className="glass sticky top-0 z-50">
            <div className="container mx-auto px-4 py-4 flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <span className="text-2xl">🎬</span>
                    <span className="font-bold text-xl gradient-text">VoiSlide Movie</span>
                </div>

                <nav className="flex items-center gap-6">
                    {/* Navigation links removed as per request */}
                </nav>
            </div>
        </header>
    );
}
