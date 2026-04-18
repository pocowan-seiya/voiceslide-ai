/**
 * Header navigation regression test.
 *
 * Bug context: clicking the back-to-dashboard arrow used to be a plain
 * `<a href="/dashboard">` — a hard navigation that aborted in-flight Supabase
 * writes. As a result, slide URLs generated right before the click were
 * never persisted to the DB, so the next project restore landed in a
 * "0 slides" state.
 *
 * Fix: Header now accepts an `onBeforeNavigate` async callback and awaits
 * it before doing a Next.js client-side `router.push`. These tests pin
 * down that contract so a future refactor doesn't accidentally revert to
 * a hard navigation.
 */

import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { Header } from "@/components/Header";
import { useRouter } from "next/navigation";

// jest.setup.ts already mocks next/navigation; we just grab a typed handle to
// the same `push` mock so we can assert against it. (The mock factory in
// jest.setup.ts returns a stable jest.fn() per call, so we call useRouter()
// once outside the component to capture it.)
const pushMock = (useRouter() as { push: jest.Mock }).push;

beforeEach(() => {
  pushMock.mockClear();
});

describe("Header back-to-dashboard navigation", () => {
  it("does NOT render the back arrow without a projectId (nothing to save)", () => {
    render(<Header />);
    expect(screen.queryByTitle(/ダッシュボードへ戻る/)).not.toBeInTheDocument();
    expect(screen.queryByTitle(/保存しています/)).not.toBeInTheDocument();
  });

  it("renders the back arrow when a projectId is provided", () => {
    render(<Header projectId="proj-1" projectName="Test" />);
    expect(screen.getByTitle("ダッシュボードへ戻る")).toBeInTheDocument();
  });

  it("awaits onBeforeNavigate, then router.push to /dashboard", async () => {
    let savedAt = 0;
    let pushedAt = 0;
    const onBeforeNavigate = jest.fn(() =>
      new Promise<void>((resolve) =>
        setTimeout(() => {
          savedAt = Date.now();
          resolve();
        }, 30)
      )
    );
    pushMock.mockImplementation(() => {
      pushedAt = Date.now();
    });

    render(
      <Header projectId="proj-1" projectName="Test" onBeforeNavigate={onBeforeNavigate} />
    );

    fireEvent.click(screen.getByTitle("ダッシュボードへ戻る"));

    await waitFor(() => expect(pushMock).toHaveBeenCalledWith("/dashboard"));
    expect(onBeforeNavigate).toHaveBeenCalledTimes(1);
    // The save MUST resolve before navigation fires
    expect(savedAt).toBeGreaterThan(0);
    expect(pushedAt).toBeGreaterThanOrEqual(savedAt);
  });

  it("still navigates if onBeforeNavigate throws (don't trap the user)", async () => {
    const onBeforeNavigate = jest.fn().mockRejectedValue(new Error("save failed"));

    render(
      <Header projectId="proj-1" projectName="Test" onBeforeNavigate={onBeforeNavigate} />
    );

    fireEvent.click(screen.getByTitle("ダッシュボードへ戻る"));

    await waitFor(() => expect(pushMock).toHaveBeenCalledWith("/dashboard"));
  });

  it("navigates immediately when no onBeforeNavigate is supplied", async () => {
    render(<Header projectId="proj-1" projectName="Test" />);

    fireEvent.click(screen.getByTitle("ダッシュボードへ戻る"));

    await waitFor(() => expect(pushMock).toHaveBeenCalledWith("/dashboard"));
  });

  it("ignores rapid double-clicks while a save is in-flight", async () => {
    let resolveSave!: () => void;
    const onBeforeNavigate = jest.fn(
      () => new Promise<void>((resolve) => { resolveSave = resolve; })
    );

    render(
      <Header projectId="proj-1" projectName="Test" onBeforeNavigate={onBeforeNavigate} />
    );

    const link = screen.getByTitle(/ダッシュボード/);
    fireEvent.click(link);
    fireEvent.click(link);  // double-click while save in-flight
    fireEvent.click(link);

    expect(onBeforeNavigate).toHaveBeenCalledTimes(1);
    resolveSave();
    await waitFor(() => expect(pushMock).toHaveBeenCalledTimes(1));
  });
});
