"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import type { Project } from "@/lib/supabase/types";

const STEP_LABELS: Record<number, string> = {
  1: "音声待ち",
  2: "文字起こし済",
  3: "ブラッシュアップ済",
  4: "アウトライン生成済",
  5: "アウトライン改善済",
  6: "出力済",
  7: "スライド作成中",
  8: "スライド読込済",
  9: "AIマッピング済",
  10: "動画生成完了",
};

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);
  if (mins < 1) return "たった今";
  if (mins < 60) return `${mins}分前`;
  if (hours < 24) return `${hours}時間前`;
  return `${days}日前`;
}

function getDefaultProjectName(): string {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, "0");
  const d = String(now.getDate()).padStart(2, "0");
  return `${y}${m}${d}`;
}

export default function DashboardPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [userEmail, setUserEmail] = useState("");
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const router = useRouter();
  const supabase = createClient();

  useEffect(() => {
    const load = async () => {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) { router.push("/login"); return; }
      setUserEmail(user.email ?? "");

      const { data } = await supabase
        .from("projects")
        .select("*")
        .order("updated_at", { ascending: false });
      setProjects(data ?? []);
      setIsLoading(false);
    };
    load();
  }, []);

  const handleNewProject = async () => {
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) return;

    const { data, error } = await supabase
      .from("projects")
      .insert({ user_id: user.id, name: getDefaultProjectName() })
      .select()
      .single();

    if (!error && data) {
      router.push(`/?project=${data.id}`);
    }
  };

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm("このプロジェクトを削除しますか？")) return;
    setDeletingId(id);
    await supabase.from("projects").delete().eq("id", id);
    setProjects((prev) => prev.filter((p) => p.id !== id));
    setDeletingId(null);
  };

  const handleRename = async (id: string, newName: string) => {
    const trimmed = newName.trim();
    if (!trimmed) return;
    await supabase.from("projects").update({ name: trimmed }).eq("id", id);
    setProjects((prev) =>
      prev.map((p) => (p.id === id ? { ...p, name: trimmed } : p))
    );
  };

  const handleLogout = async () => {
    await supabase.auth.signOut();
    router.push("/login");
  };

  // Projects are already ordered by updated_at DESC from Supabase (see the
  // `.order("updated_at", { ascending: false })` in the load effect above),
  // so the most recently edited project is `projects[0]` regardless of
  // status. We used to split into "作業中" / "完成済み" sections, but that
  // buried the latest-edited project below the draft list whenever it got
  // promoted to completed — users lost track of which one they were on.
  // Now we show a single grid in pure recency order; the per-card status
  // badge ("完成" / step label) carries the distinction.

  return (
    <div className="min-h-screen bg-zinc-950 text-white">
      {/* Fixed bg */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-purple-900/10 rounded-full blur-3xl" />
        <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-blue-900/10 rounded-full blur-3xl" />
      </div>

      {/* Header */}
      <header className="relative z-10 border-b border-zinc-800 bg-zinc-950/80 backdrop-blur-xl">
        <div className="max-w-6xl mx-auto px-4 h-16 flex items-center justify-between">
          <h1 className="text-xl font-black">
            <span className="bg-clip-text text-transparent bg-gradient-to-r from-blue-400 via-purple-400 to-pink-400">
              VoiSlide Movie
            </span>
          </h1>
          <div className="flex items-center gap-4">
            <span className="text-sm text-zinc-400 hidden sm:block">{userEmail}</span>
            <button
              onClick={handleLogout}
              className="text-sm text-zinc-400 hover:text-white transition-colors"
            >
              ログアウト
            </button>
          </div>
        </div>
      </header>

      <main className="relative z-10 max-w-6xl mx-auto px-4 py-10">
        {/* Title + New button */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h2 className="text-3xl font-bold">マイスライド動画</h2>
            <p className="text-zinc-400 mt-1 text-sm">
              作業中のプロジェクトを続きから再開できます
            </p>
          </div>
          <button
            onClick={handleNewProject}
            className="flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 text-white font-semibold rounded-xl transition-all shadow-lg shadow-purple-900/20"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            新規作成
          </button>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-20">
            <svg className="animate-spin h-8 w-8 text-purple-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
            </svg>
          </div>
        ) : projects.length === 0 ? (
          <div className="text-center py-20">
            <div className="text-6xl mb-4">🎬</div>
            <p className="text-zinc-400 mb-6">まだプロジェクトがありません</p>
            <button
              onClick={handleNewProject}
              className="px-6 py-3 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 text-white font-semibold rounded-xl transition-all"
            >
              最初のプロジェクトを作成
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {projects.map((project) => (
              <ProjectCard
                key={project.id}
                project={project}
                onOpen={() => router.push(`/?project=${project.id}`)}
                onDelete={(e) => handleDelete(project.id, e)}
                onRename={(name) => handleRename(project.id, name)}
                isDeleting={deletingId === project.id}
              />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}

function ProjectCard({
  project,
  onOpen,
  onDelete,
  onRename,
  isDeleting,
}: {
  project: Project;
  onOpen: () => void;
  onDelete: (e: React.MouseEvent) => void;
  onRename: (name: string) => void;
  isDeleting: boolean;
}) {
  const [isEditing, setIsEditing] = useState(false);
  const [editName, setEditName] = useState(project.name);
  const isCompleted = project.status === "completed";
  const stepLabel = STEP_LABELS[project.step] ?? `ステップ ${project.step}`;

  const handleEditStart = (e: React.MouseEvent) => {
    e.stopPropagation();
    setEditName(project.name);
    setIsEditing(true);
  };

  const handleEditSave = (e: React.FormEvent | React.FocusEvent) => {
    e.preventDefault();
    if ("stopPropagation" in e) e.stopPropagation();
    const trimmed = editName.trim();
    if (trimmed && trimmed !== project.name) {
      onRename(trimmed);
    }
    setIsEditing(false);
  };

  const handleEditKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      setIsEditing(false);
      setEditName(project.name);
    }
  };

  return (
    <div
      onClick={onOpen}
      className="group relative bg-zinc-900/60 border border-zinc-800 hover:border-zinc-600 rounded-2xl p-5 cursor-pointer transition-all hover:bg-zinc-900/80"
    >
      {/* ステータスバッジ */}
      <div className="flex items-center justify-between mb-3">
        <span
          className={`text-xs font-medium px-2 py-1 rounded-full ${
            isCompleted
              ? "bg-green-500/20 text-green-400"
              : "bg-blue-500/20 text-blue-400"
          }`}
        >
          {isCompleted ? "完成" : stepLabel}
        </span>
        <button
          onClick={onDelete}
          className="opacity-0 group-hover:opacity-100 text-zinc-600 hover:text-red-400 transition-all p-1 rounded"
          disabled={isDeleting}
        >
          {isDeleting ? (
            <svg className="animate-spin w-4 h-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          ) : (
            <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          )}
        </button>
      </div>

      {/* プロジェクト名（編集可能） */}
      {isEditing ? (
        <form onSubmit={handleEditSave} onClick={(e) => e.stopPropagation()}>
          <input
            type="text"
            value={editName}
            onChange={(e) => setEditName(e.target.value)}
            onBlur={handleEditSave}
            onKeyDown={handleEditKeyDown}
            autoFocus
            className="w-full font-semibold text-white bg-zinc-800 border border-zinc-600 rounded-lg px-2 py-1 mb-1 outline-none focus:border-purple-500"
          />
        </form>
      ) : (
        <div className="flex items-center gap-1.5 mb-1">
          <h4 className="font-semibold text-white truncate">{project.name}</h4>
          <button
            onClick={handleEditStart}
            className="opacity-0 group-hover:opacity-100 text-zinc-500 hover:text-white transition-all p-0.5 rounded shrink-0"
            title="名前を変更"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
            </svg>
          </button>
        </div>
      )}

      {/* モード */}
      {project.workflow_mode && (
        <p className="text-xs text-zinc-500 mb-3">
          {project.workflow_mode === "full-ai" ? "フルAIモード" : "ハイブリッドモード"}
        </p>
      )}

      {/* プログレスバー */}
      {!isCompleted && (
        <div className="mb-3">
          <div className="w-full bg-zinc-800 rounded-full h-1">
            <div
              className="bg-gradient-to-r from-blue-500 to-purple-500 h-1 rounded-full transition-all"
              style={{
                width: `${Math.round(
                  (project.step / (project.workflow_mode === "full-ai" ? 6 : 10)) * 100
                )}%`,
              }}
            />
          </div>
        </div>
      )}

      {/* フッター */}
      <div className="flex items-center justify-between">
        <span className="text-xs text-zinc-600">{timeAgo(project.updated_at)}</span>
        <span className="text-xs font-medium text-purple-400 group-hover:text-purple-300 transition-colors">
          {isCompleted ? "開く →" : "続きから →"}
        </span>
      </div>
    </div>
  );
}
