import "@testing-library/jest-dom";

// Default mock for Next.js navigation hooks so components that call
// useRouter()/useSearchParams() (e.g. Header's back-to-dashboard button)
// render in tests without an App Router provider being mounted.
//
// IMPORTANT: useRouter() must return the SAME object every call, otherwise
// tests can't capture the push mock and assert against it (each component
// render would see a different jest.fn). Defining the singleton here means
// any test can `import { useRouter } from "next/navigation"` and assert on
// the returned router's methods.
jest.mock("next/navigation", () => {
  const router = {
    push: jest.fn(),
    replace: jest.fn(),
    back: jest.fn(),
    forward: jest.fn(),
    refresh: jest.fn(),
    prefetch: jest.fn(),
  };
  return {
    useRouter: () => router,
    useSearchParams: () => new URLSearchParams(),
    usePathname: () => "/",
  };
});
