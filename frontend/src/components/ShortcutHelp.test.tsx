import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { useAppStore } from "../store/appStore";
import { ShortcutHelp } from "./ShortcutHelp";

describe("ShortcutHelp", () => {
  afterEach(() => useAppStore.setState({ shortcutHelpOpen: false }));

  it("renders nothing when closed", () => {
    useAppStore.setState({ shortcutHelpOpen: false });
    const { container } = render(<ShortcutHelp />);
    expect(container).toBeEmptyDOMElement();
  });

  it("lists the shortcuts when open", () => {
    useAppStore.setState({ shortcutHelpOpen: true });
    render(<ShortcutHelp />);

    expect(screen.getByRole("dialog", { name: "Skróty klawiszowe" })).toBeInTheDocument();
    expect(screen.getByText("Przejdź do wyszukiwarki")).toBeInTheDocument();
    expect(screen.getByText("Przełącz: Stacje synoptyczne")).toBeInTheDocument();
  });

  it("closes via the close button", () => {
    useAppStore.setState({ shortcutHelpOpen: true });
    render(<ShortcutHelp />);

    fireEvent.click(screen.getByLabelText("Zamknij"));

    expect(useAppStore.getState().shortcutHelpOpen).toBe(false);
  });

  it("closes on backdrop click", () => {
    useAppStore.setState({ shortcutHelpOpen: true });
    render(<ShortcutHelp />);

    fireEvent.click(screen.getByRole("dialog", { name: "Skróty klawiszowe" }));

    expect(useAppStore.getState().shortcutHelpOpen).toBe(false);
  });

  it("does not close when clicking inside the dialog content", () => {
    useAppStore.setState({ shortcutHelpOpen: true });
    render(<ShortcutHelp />);

    fireEvent.click(screen.getByText("Skróty klawiszowe"));

    expect(useAppStore.getState().shortcutHelpOpen).toBe(true);
  });
});
