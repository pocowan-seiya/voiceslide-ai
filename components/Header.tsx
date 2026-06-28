"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

interface HeaderProps {
  lastSavedAt?: Date | null;
  isSaving?: boolean;
  projectName?: string;
  projectId?: string | null;
  /**
   * Optional async hook fired right before navigating back to /dashboard.
   * Lets the parent flush a final save (especially the just-generated slide
   * URLs) so the DB doesn't get left pointing at a previous session's job_id.
   * Errors are swallowed — we navigate either way so the UI never feels stuck.
   *
   * Return `false` to cancel the navigation (e.g. user clicked "No" on a
   * confirmation modal). Any other return value — including throwing —
   * still proceeds with the navigation.
   */
  onBeforeNavigate?: () => Promise<boolean | void> | boolean | void;
}

function timeAgoShort(date: Date): string {
  const diff = Date.now() - date.getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "たった今";
  if (mins < 60) return `${mins}分前`;
  return `${Math.floor(mins / 60)}時間前`;
}

export function Header({ lastSavedAt, isSaving, projectName, projectId, onBeforeNavigate }: HeaderProps) {
  const router = useRouter();
  const [isLeaving, setIsLeaving] = useState(false);

  const goDashboard = async (e: React.MouseEvent) => {
    e.preventDefault();
    if (isLeaving) return;
    setIsLeaving(true);
    try {
      if (onBeforeNavigate) {
        const result = await onBeforeNavigate();
        if (result === false) {
          // Parent asked us to stay (e.g. user cancelled a confirm modal).
          setIsLeaving(false);
          return;
        }
      }
    } catch (err) {
      console.error("[Header] onBeforeNavigate failed (navigating anyway):", err);
    }
    router.push("/dashboard");
  };

  return (
    <header className="glass sticky top-0 z-50">
      <div className="container mx-auto px-4 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          {projectId && (
            <a
              href="/dashboard"
              onClick={goDashboard}
              aria-busy={isLeaving}
              className="text-zinc-500 hover:text-white transition-colors p-1 -ml-1"
              title={isLeaving ? "保存しています..." : "ダッシュボードへ戻る"}
            >
              {isLeaving ? (
                <svg className="animate-spin w-5 h-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
              ) : (
                <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                </svg>
              )}
            </a>
          )}
          <span className="text-2xl">🎬</span>
          <div>
            <span className="font-bold text-xl gradient-text">VoiSlide Movie</span>
            {projectId && projectName && (
              <p className="text-xs text-zinc-500 leading-none mt-0.5">{projectName}</p>
            )}
          </div>
        </div>

        <div className="flex items-center gap-4">
          {/* 自動保存インジケーター */}
          {projectId && (
            <div className="flex items-center gap-1.5 text-xs text-zinc-500">
              {isSaving ? (
                <>
                  <svg className="animate-spin w-3 h-3" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  保存中...
                </>
              ) : lastSavedAt ? (
                <>
                  <svg xmlns="http://www.w3.org/2000/svg" className="w-3 h-3 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  {timeAgoShort(lastSavedAt)}に保存
                </>
              ) : null}
            </div>
          )}

          {!projectId && (
            <a
              href="/dashboard"
              className="text-sm text-zinc-400 hover:text-white transition-colors"
            >
              マイプロジェクト
            </a>
          )}
        </div>
      </div>
    </header>
  );
}
