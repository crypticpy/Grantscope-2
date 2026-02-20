/**
 * Login Page Unit Tests
 *
 * Tests the Login component for:
 * - Rendering visible labels above form inputs
 * - Proper label-input associations via htmlFor/id
 * - Form submission behavior
 * - Error display
 * - Loading state
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Login from "../Login";

// ============================================================================
// Mock Setup
// ============================================================================

const mockSignIn = vi.fn();

vi.mock("../../hooks/useAuthContext", () => ({
  useAuthContext: () => ({
    signIn: mockSignIn,
    signOut: vi.fn(),
    user: null,
    loading: false,
  }),
}));

// ============================================================================
// Tests
// ============================================================================

describe("Login", () => {
  beforeEach(() => {
    mockSignIn.mockReset();
  });

  describe("Visible Labels", () => {
    it("renders visible email label above input", () => {
      render(<Login />);

      const emailLabel = screen.getByText("Email address");
      expect(emailLabel).toBeInTheDocument();
      // Label should NOT have sr-only class (should be visible)
      expect(emailLabel).not.toHaveClass("sr-only");
    });

    it("renders visible password label above input", () => {
      render(<Login />);

      const passwordLabel = screen.getByText("Password");
      expect(passwordLabel).toBeInTheDocument();
      // Label should NOT have sr-only class (should be visible)
      expect(passwordLabel).not.toHaveClass("sr-only");
    });

    it("email label has correct styling following WorkstreamForm pattern", () => {
      render(<Login />);

      const emailLabel = screen.getByText("Email address");
      expect(emailLabel).toHaveClass("block");
      expect(emailLabel).toHaveClass("text-sm");
      expect(emailLabel).toHaveClass("font-medium");
    });

    it("password label has correct styling following WorkstreamForm pattern", () => {
      render(<Login />);

      const passwordLabel = screen.getByText("Password");
      expect(passwordLabel).toHaveClass("block");
      expect(passwordLabel).toHaveClass("text-sm");
      expect(passwordLabel).toHaveClass("font-medium");
    });
  });

  describe("Label-Input Associations", () => {
    it("email label is properly associated with email input via htmlFor/id", () => {
      render(<Login />);

      const emailLabel = screen.getByText("Email address");
      const emailInput = screen.getByLabelText("Email address");

      expect(emailLabel).toHaveAttribute("for", "email-address");
      expect(emailInput).toHaveAttribute("id", "email-address");
    });

    it("password label is properly associated with password input via htmlFor/id", () => {
      render(<Login />);

      const passwordLabel = screen.getByText("Password");
      const passwordInput = screen.getByLabelText("Password");

      expect(passwordLabel).toHaveAttribute("for", "password");
      expect(passwordInput).toHaveAttribute("id", "password");
    });

    it("clicking email label focuses email input", async () => {
      const user = userEvent.setup();
      render(<Login />);

      const emailLabel = screen.getByText("Email address");
      await user.click(emailLabel);

      const emailInput = screen.getByLabelText("Email address");
      expect(emailInput).toHaveFocus();
    });

    it("clicking password label focuses password input", async () => {
      const user = userEvent.setup();
      render(<Login />);

      const passwordLabel = screen.getByText("Password");
      await user.click(passwordLabel);

      const passwordInput = screen.getByLabelText("Password");
      expect(passwordInput).toHaveFocus();
    });
  });

  describe("Form Rendering", () => {
    it("renders page title", () => {
      render(<Login />);

      expect(screen.getAllByText("GrantScope2").length).toBeGreaterThan(0);
    });

    it("renders subtitle", () => {
      render(<Login />);

      expect(
        screen.getAllByText(
          "AI-Powered Grant Intelligence for the City of Austin",
        ).length,
      ).toBeGreaterThan(0);
    });

    it("renders email input with correct type", () => {
      render(<Login />);

      const emailInput = screen.getByLabelText("Email address");
      expect(emailInput).toHaveAttribute("type", "email");
    });

    it("renders password input with correct type", () => {
      render(<Login />);

      const passwordInput = screen.getByLabelText("Password");
      expect(passwordInput).toHaveAttribute("type", "password");
    });

    it("renders sign in button", () => {
      render(<Login />);

      expect(
        screen.getByRole("button", { name: "Sign in" }),
      ).toBeInTheDocument();
    });

    it("renders inputs with required attribute", () => {
      render(<Login />);

      const emailInput = screen.getByLabelText("Email address");
      const passwordInput = screen.getByLabelText("Password");

      expect(emailInput).toBeRequired();
      expect(passwordInput).toBeRequired();
    });

    it("inputs have rounded-md corners (not stacked style)", () => {
      render(<Login />);

      const emailInput = screen.getByLabelText("Email address");
      const passwordInput = screen.getByLabelText("Password");

      expect(emailInput).toHaveClass("rounded-md");
      expect(passwordInput).toHaveClass("rounded-md");
    });
  });

  describe("Form Submission", () => {
    it("calls signIn with email and password on form submit", async () => {
      const user = userEvent.setup();
      mockSignIn.mockResolvedValueOnce(undefined);
      render(<Login />);

      const emailInput = screen.getByLabelText("Email address");
      const passwordInput = screen.getByLabelText("Password");
      const submitButton = screen.getByRole("button", { name: "Sign in" });

      await user.type(emailInput, "test@example.com");
      await user.type(passwordInput, "password123");
      await user.click(submitButton);

      await waitFor(() => {
        expect(mockSignIn).toHaveBeenCalledWith(
          "test@example.com",
          "password123",
        );
      });
    });

    it("prevents default form submission", async () => {
      const user = userEvent.setup();
      mockSignIn.mockResolvedValueOnce(undefined);
      render(<Login />);

      const emailInput = screen.getByLabelText("Email address");
      const passwordInput = screen.getByLabelText("Password");

      await user.type(emailInput, "test@example.com");
      await user.type(passwordInput, "password123");

      const form = emailInput.closest("form");
      expect(form).toBeInTheDocument();

      // Submit via button click
      const submitButton = screen.getByRole("button", { name: "Sign in" });
      await user.click(submitButton);

      // If form submission wasn't prevented, page would reload and component would unmount
      expect(screen.getByLabelText("Email address")).toBeInTheDocument();
    });
  });

  describe("Loading State", () => {
    it("disables submit button while loading", async () => {
      const user = userEvent.setup();
      // Create a promise that we can control
      let resolveSignIn: () => void;
      const signInPromise = new Promise<void>((resolve) => {
        resolveSignIn = resolve;
      });
      mockSignIn.mockReturnValueOnce(signInPromise);

      render(<Login />);

      const emailInput = screen.getByLabelText("Email address");
      const passwordInput = screen.getByLabelText("Password");
      const submitButton = screen.getByRole("button", { name: "Sign in" });

      await user.type(emailInput, "test@example.com");
      await user.type(passwordInput, "password123");
      await user.click(submitButton);

      // Button should be disabled while loading
      await waitFor(() => {
        expect(screen.getByRole("button")).toBeDisabled();
      });

      // Resolve the promise
      resolveSignIn!();

      // Button should be enabled again after loading
      await waitFor(() => {
        expect(screen.getByRole("button", { name: "Sign in" })).toBeEnabled();
      });
    });

    it("shows loading spinner while signing in", async () => {
      const user = userEvent.setup();
      let resolveSignIn: () => void;
      const signInPromise = new Promise<void>((resolve) => {
        resolveSignIn = resolve;
      });
      mockSignIn.mockReturnValueOnce(signInPromise);

      render(<Login />);

      const emailInput = screen.getByLabelText("Email address");
      const passwordInput = screen.getByLabelText("Password");
      const submitButton = screen.getByRole("button", { name: "Sign in" });

      await user.type(emailInput, "test@example.com");
      await user.type(passwordInput, "password123");
      await user.click(submitButton);

      // Should show "Signing in..." text
      await waitFor(() => {
        expect(screen.getByText("Signing in...")).toBeInTheDocument();
      });

      // Resolve the promise
      resolveSignIn!();

      // Should show "Sign in" text again
      await waitFor(() => {
        expect(
          screen.getByRole("button", { name: "Sign in" }),
        ).toBeInTheDocument();
      });
    });
  });

  describe("Error Display", () => {
    it("displays error message when signIn fails", async () => {
      const user = userEvent.setup();
      mockSignIn.mockRejectedValueOnce(new Error("Invalid credentials"));

      render(<Login />);

      const emailInput = screen.getByLabelText("Email address");
      const passwordInput = screen.getByLabelText("Password");
      const submitButton = screen.getByRole("button", { name: "Sign in" });

      await user.type(emailInput, "test@example.com");
      await user.type(passwordInput, "wrongpassword");
      await user.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText("Invalid credentials")).toBeInTheDocument();
      });
    });

    it("displays generic error when no message provided", async () => {
      const user = userEvent.setup();
      mockSignIn.mockRejectedValueOnce(new Error());

      render(<Login />);

      const emailInput = screen.getByLabelText("Email address");
      const passwordInput = screen.getByLabelText("Password");
      const submitButton = screen.getByRole("button", { name: "Sign in" });

      await user.type(emailInput, "test@example.com");
      await user.type(passwordInput, "wrongpassword");
      await user.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText("Failed to sign in")).toBeInTheDocument();
      });
    });

    it('error alert has role="alert" for accessibility', async () => {
      const user = userEvent.setup();
      mockSignIn.mockRejectedValueOnce(new Error("Error"));

      render(<Login />);

      const emailInput = screen.getByLabelText("Email address");
      const passwordInput = screen.getByLabelText("Password");
      const submitButton = screen.getByRole("button", { name: "Sign in" });

      await user.type(emailInput, "test@example.com");
      await user.type(passwordInput, "wrongpassword");
      await user.click(submitButton);

      await waitFor(() => {
        expect(screen.getByRole("alert")).toBeInTheDocument();
      });
    });

    it("clears error on new submission attempt", async () => {
      const user = userEvent.setup();
      // First call fails, second succeeds
      mockSignIn
        .mockRejectedValueOnce(new Error("Invalid credentials"))
        .mockResolvedValueOnce(undefined);

      render(<Login />);

      const emailInput = screen.getByLabelText("Email address");
      const passwordInput = screen.getByLabelText("Password");
      const submitButton = screen.getByRole("button", { name: "Sign in" });

      // First submission - should show error
      await user.type(emailInput, "test@example.com");
      await user.type(passwordInput, "wrongpassword");
      await user.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText("Invalid credentials")).toBeInTheDocument();
      });

      // Second submission - error should be cleared
      await user.click(submitButton);

      await waitFor(() => {
        expect(
          screen.queryByText("Invalid credentials"),
        ).not.toBeInTheDocument();
      });
    });
  });

  describe("Input Value Changes", () => {
    it("updates email value on input", async () => {
      const user = userEvent.setup();
      render(<Login />);

      const emailInput = screen.getByLabelText("Email address");
      await user.type(emailInput, "test@example.com");

      expect(emailInput).toHaveValue("test@example.com");
    });

    it("updates password value on input", async () => {
      const user = userEvent.setup();
      render(<Login />);

      const passwordInput = screen.getByLabelText("Password");
      await user.type(passwordInput, "mypassword");

      expect(passwordInput).toHaveValue("mypassword");
    });
  });
});
