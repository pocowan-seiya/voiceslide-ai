/**
 * VoiceSlide AI - Basic smoke tests
 * Verifies React components render without crashing.
 */

import React from "react";
import { render, screen } from "@testing-library/react";
import { Header } from "@/components/Header";

describe("Header component", () => {
  it("renders without crashing", () => {
    render(<Header />);
    expect(screen.getByText("VoiSlide Movie")).toBeInTheDocument();
  });
});
