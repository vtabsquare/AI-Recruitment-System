import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from '../App.jsx';

describe('AI Recruitment System - UI/UX Tests', () => {
  beforeEach(() => {
    sessionStorage.clear();
    window.history.replaceState(null, '', '/');
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        text: async () => JSON.stringify({ success: true, data: [] }),
      })
    );
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // Helper to log in as a specific role
  async function loginAs(role = 'manager', name = 'Test User') {
    const user = userEvent.setup();
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        text: async () =>
          JSON.stringify({
            success: true,
            access_token: `${role}-valid-token`,
            staff: { role, full_name: name },
            data: [],
          }),
      })
    );
    render(<App />);
    await user.click(screen.getByRole('button', { name: /open menu/i }));
    await user.click(screen.getByText(role === 'manager' ? 'Manager Login' : 'HR Login'));
    await user.type(screen.getByPlaceholderText(/enter your company email/i), `${role}@vtab.com`);
    await user.type(screen.getByPlaceholderText(/enter your password/i), 'secret123');
    await user.click(screen.getByRole('button', { name: /enter portal/i }));
    return user;
  }

  // =========================================================================
  // 1. HOME SCREEN & INITIAL RENDER
  // =========================================================================
  describe('1. Home Screen & Branding', () => {
    it('renders company brand name and AI agent subtitle in the header', () => {
      render(<App />);
      expect(screen.getByText('VTAB SQUARE')).toBeInTheDocument();
      expect(screen.getByText('VTAB AI AGENT')).toBeInTheDocument();
      expect(screen.getByText(/AI SYSTEM ONLINE/i)).toBeInTheDocument();
    });

    it('renders the hero section with headline and mission statement', () => {
      render(<App />);
      expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(/intelligent hiring/i);
      expect(
        screen.getByText(/VTAB AI coordinates recruitment from application to onboarding/i)
      ).toBeInTheDocument();
    });

    it('renders the primary "ASK VTAB AI" action button', () => {
      render(<App />);
      const askButton = screen.getByRole('button', { name: /open candidate ai assistant/i });
      expect(askButton).toBeInTheDocument();
      expect(askButton).toHaveTextContent(/ASK VTAB AI/i);
    });

    it('renders the 3 key recruitment intelligence pillars in the footer', () => {
      render(<App />);
      expect(screen.getByText('Resume intelligence')).toBeInTheDocument();
      expect(screen.getByText('Interview orchestration')).toBeInTheDocument();
      expect(screen.getByText('Human-led decisions')).toBeInTheDocument();
    });

    it('has the skip-to-main-content target id="main-content" on the main element', () => {
      const { container } = render(<App />);
      const main = container.querySelector('#main-content');
      expect(main).toBeInTheDocument();
    });
  });

  // =========================================================================
  // 2. NAVIGATION & DRAWER INTERACTION
  // =========================================================================
  describe('2. Navigation Menu & Drawer', () => {
    it('renders the menu trigger button with correct accessibility attributes', () => {
      render(<App />);
      const trigger = screen.getByRole('button', { name: /open menu/i });
      expect(trigger).toBeInTheDocument();
      expect(trigger).toHaveAttribute('aria-expanded', 'false');
      expect(trigger).toHaveAttribute('aria-controls', 'site-navigation');
    });

    it('opens the navigation drawer dialog when menu button is clicked', async () => {
      const user = userEvent.setup();
      render(<App />);
      const trigger = screen.getByRole('button', { name: /open menu/i });

      await user.click(trigger);

      expect(trigger).toHaveAttribute('aria-expanded', 'true');
      const dialog = screen.getByRole('dialog', { name: /navigation menu/i });
      expect(dialog).toBeInTheDocument();
      expect(dialog).toHaveAttribute('aria-modal', 'true');
      expect(dialog).toHaveAttribute('id', 'site-navigation');
    });

    it('closes the drawer when the close (×) button is clicked', async () => {
      const user = userEvent.setup();
      render(<App />);
      await user.click(screen.getByRole('button', { name: /open menu/i }));

      const closeButton = screen.getByRole('button', { name: /close navigation menu/i });
      expect(closeButton).toBeInTheDocument();
      await user.click(closeButton);

      expect(screen.queryByRole('dialog', { name: /navigation menu/i })).not.toBeInTheDocument();
      expect(screen.getByRole('button', { name: /open menu/i })).toHaveAttribute(
        'aria-expanded',
        'false'
      );
    });

    it('navigates to Manager Login when "Manager Login" is clicked from drawer', async () => {
      const user = userEvent.setup();
      render(<App />);
      await user.click(screen.getByRole('button', { name: /open menu/i }));

      const managerCard = screen.getByText('Manager Login');
      await user.click(managerCard);

      expect(screen.getByRole('heading', { name: /manager portal/i })).toBeInTheDocument();
      expect(
        screen.getByText(/interview evaluation & hiring approvals/i)
      ).toBeInTheDocument();
    });

    it('navigates to HR Login when "HR Login" is clicked from drawer', async () => {
      const user = userEvent.setup();
      render(<App />);
      await user.click(screen.getByRole('button', { name: /open menu/i }));

      const hrCard = screen.getByText('HR Login');
      await user.click(hrCard);

      expect(screen.getByRole('heading', { name: /hr operations/i })).toBeInTheDocument();
      expect(
        screen.getByText(/verification, offer letters & onboarding/i)
      ).toBeInTheDocument();
    });

    it('navigates back to home when clicking the brand button in header', async () => {
      const user = userEvent.setup();
      render(<App />);
      await user.click(screen.getByRole('button', { name: /open menu/i }));
      await user.click(screen.getByText('Manager Login'));
      expect(screen.getByRole('heading', { name: /manager portal/i })).toBeInTheDocument();

      const brandButton = screen.getByRole('button', { name: /vtab square/i });
      await user.click(brandButton);

      expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(/intelligent hiring/i);
    });

    it('navigates back to home when clicking "Home" from the navigation drawer', async () => {
      const user = userEvent.setup();
      render(<App />);
      await user.click(screen.getByRole('button', { name: /open menu/i }));
      await user.click(screen.getByText('Manager Login'));
      expect(screen.getByRole('heading', { name: /manager portal/i })).toBeInTheDocument();

      // Open drawer again and click Home
      await user.click(screen.getByRole('button', { name: /open menu/i }));
      await user.click(screen.getByRole('button', { name: /⌂ home/i }));

      expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(/intelligent hiring/i);
    });
  });

  // =========================================================================
  // 3. LOGIN FORM & AUTHENTICATION
  // =========================================================================
  describe('3. Login Form & Authentication', () => {
    async function navigateToLogin(role = 'manager') {
      const user = userEvent.setup();
      render(<App />);
      await user.click(screen.getByRole('button', { name: /open menu/i }));
      await user.click(screen.getByText(role === 'manager' ? 'Manager Login' : 'HR Login'));
      return user;
    }

    it('renders the login form with required fields and submit button', async () => {
      await navigateToLogin('manager');
      expect(screen.getByPlaceholderText(/enter your company email/i)).toBeInTheDocument();
      expect(screen.getByPlaceholderText(/enter your password/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /enter portal/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /forgot password\?/i })).toBeInTheDocument();
    });

    it('shows validation error when submitting with empty email or password', async () => {
      const user = await navigateToLogin('manager');
      const submitBtn = screen.getByRole('button', { name: /enter portal/i });

      await user.click(submitBtn);

      const alert = screen.getByRole('alert');
      expect(alert).toBeInTheDocument();
      expect(alert).toHaveTextContent(/enter both your company email and password/i);
    });

    it('shows loading state while authenticating and disables submit button', async () => {
      let resolvePromise;
      const slowPromise = new Promise((resolve) => {
        resolvePromise = resolve;
      });

      vi.stubGlobal(
        'fetch',
        vi.fn().mockImplementation(() => slowPromise)
      );

      const user = await navigateToLogin('manager');
      await user.type(screen.getByPlaceholderText(/enter your company email/i), 'manager@vtab.com');
      await user.type(screen.getByPlaceholderText(/enter your password/i), 'secret123');

      const submitBtn = screen.getByRole('button', { name: /enter portal/i });
      await user.click(submitBtn);

      expect(screen.getByRole('button', { name: /authenticating\.\.\./i })).toBeDisabled();

      resolvePromise({
        ok: true,
        text: async () =>
          JSON.stringify({
            success: true,
            access_token: 'fake-token',
            staff: { role: 'manager', full_name: 'Test Manager' },
          }),
      });
    });

    it('displays error alert when login API fails', async () => {
      vi.stubGlobal(
        'fetch',
        vi.fn().mockResolvedValue({
          ok: false,
          status: 401,
          text: async () => JSON.stringify({ detail: 'Invalid email or password.' }),
        })
      );

      const user = await navigateToLogin('manager');
      await user.type(screen.getByPlaceholderText(/enter your company email/i), 'wrong@vtab.com');
      await user.type(screen.getByPlaceholderText(/enter your password/i), 'wrongpass');

      await user.click(screen.getByRole('button', { name: /enter portal/i }));

      const alert = await screen.findByRole('alert');
      expect(alert).toHaveTextContent(/invalid email or password/i);
    });

    it('displays error alert when staff account role does not match portal type', async () => {
      vi.stubGlobal(
        'fetch',
        vi.fn().mockResolvedValue({
          ok: true,
          status: 200,
          text: async () =>
            JSON.stringify({
              success: true,
              access_token: 'hr-token',
              staff: { role: 'hr', full_name: 'HR User' },
            }),
        })
      );

      const user = await navigateToLogin('manager');
      await user.type(screen.getByPlaceholderText(/enter your company email/i), 'hr@vtab.com');
      await user.type(screen.getByPlaceholderText(/enter your password/i), 'secret123');

      await user.click(screen.getByRole('button', { name: /enter portal/i }));

      const alert = await screen.findByRole('alert');
      expect(alert).toHaveTextContent(/registered as hr, not manager/i);
    });

    it('successfully logs in and navigates to Manager Portal for manager role', async () => {
      vi.stubGlobal(
        'fetch',
        vi.fn().mockResolvedValue({
          ok: true,
          status: 200,
          text: async () =>
            JSON.stringify({
              success: true,
              access_token: 'valid-manager-token',
              staff: { role: 'manager', full_name: 'John Manager' },
              data: [],
            }),
        })
      );

      const user = await navigateToLogin('manager');
      await user.type(screen.getByPlaceholderText(/enter your company email/i), 'john@vtab.com');
      await user.type(screen.getByPlaceholderText(/enter your password/i), 'validpass123');

      await user.click(screen.getByRole('button', { name: /enter portal/i }));

      await waitFor(() => {
        expect(screen.getByText('MANAGER PORTAL')).toBeInTheDocument();
        expect(screen.getByRole('heading', { level: 1, name: 'Candidate Queue' })).toBeInTheDocument();
      });

      expect(sessionStorage.getItem('vtab_session')).toContain('valid-manager-token');
    });

    it('returns to Home when "← Back to AI OS" button is clicked', async () => {
      const user = await navigateToLogin('manager');
      const backBtn = screen.getByRole('button', { name: /← back to ai os/i });

      await user.click(backBtn);

      expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(/intelligent hiring/i);
    });
  });

  // =========================================================================
  // 4. FORGOT PASSWORD FLOW
  // =========================================================================
  describe('4. Forgot Password Flow', () => {
    async function navigateToForgotPassword() {
      const user = userEvent.setup();
      render(<App />);
      await user.click(screen.getByRole('button', { name: /open menu/i }));
      await user.click(screen.getByText('Manager Login'));
      await user.click(screen.getByRole('button', { name: /forgot password\?/i }));
      return user;
    }

    it('renders the forgot password form with email input and submit button', async () => {
      await navigateToForgotPassword();
      expect(screen.getByRole('heading', { name: /reset password/i })).toBeInTheDocument();
      expect(screen.getByPlaceholderText(/enter your company email/i)).toBeInTheDocument();
      expect(
        screen.getByRole('button', { name: /send reset instructions/i })
      ).toBeInTheDocument();
    });

    it('shows validation error when submitted with empty email', async () => {
      const user = await navigateToForgotPassword();
      const submitBtn = screen.getByRole('button', { name: /send reset instructions/i });

      await user.click(submitBtn);
      expect(screen.getByRole('alert')).toHaveTextContent(
        /please enter your registered staff email address/i
      );
    });

    it('shows validation error when submitted with invalid email format', async () => {
      const user = await navigateToForgotPassword();
      const submitBtn = screen.getByRole('button', { name: /send reset instructions/i });

      // Valid HTML5 email syntax so form submits, but fails the component's strict domain regex
      await user.type(screen.getByPlaceholderText(/enter your company email/i), 'staff@invalid');
      await user.click(submitBtn);
      expect(screen.getByRole('alert')).toHaveTextContent(/please enter a valid email address/i);
    });

    it('shows success message with role="status" after successful request', async () => {
      vi.stubGlobal(
        'fetch',
        vi.fn().mockResolvedValue({
          ok: true,
          status: 200,
          text: async () => JSON.stringify({ success: true }),
        })
      );

      const user = await navigateToForgotPassword();
      await user.type(screen.getByPlaceholderText(/enter your company email/i), 'staff@vtab.com');
      await user.click(screen.getByRole('button', { name: /send reset instructions/i }));

      const statusMsg = await screen.findByRole('status');
      expect(statusMsg).toHaveTextContent(/password reset instructions have been sent/i);
      expect(screen.getByRole('button', { name: /return to login/i })).toBeInTheDocument();
    });

    it('navigates back to login when "← Back to Login" is clicked', async () => {
      const user = await navigateToForgotPassword();
      await user.click(screen.getByRole('button', { name: /← back to login/i }));

      expect(screen.getByRole('heading', { name: /manager portal/i })).toBeInTheDocument();
    });
  });

  // =========================================================================
  // 5. CANDIDATE AI WORKFLOW
  // =========================================================================
  describe('5. Candidate AI Workflow', () => {
    it('navigates to Candidate AI screen when "ASK VTAB AI" button is clicked', async () => {
      const user = userEvent.setup();
      render(<App />);
      await user.click(screen.getByRole('button', { name: /open candidate ai assistant/i }));

      expect(
        screen.getByRole('main', { name: /candidate ai assistant/i })
      ).toBeInTheDocument();
      expect(screen.getByRole('heading', { name: /how can i help\?/i })).toBeInTheDocument();
      expect(screen.getByRole('log', { name: /chat messages/i })).toBeInTheDocument();
    });

    it('renders suggested questions with accessible names', async () => {
      const user = userEvent.setup();
      render(<App />);
      await user.click(screen.getByRole('button', { name: /open candidate ai assistant/i }));

      const suggestionsGroup = screen.getByRole('group', { name: /suggested questions/i });
      expect(suggestionsGroup).toBeInTheDocument();

      const suggestionBtns = screen.getAllByRole('button', { name: /^ask:/i });
      expect(suggestionBtns.length).toBeGreaterThan(0);
    });

    it('sends question and displays answer when typing and submitting message', async () => {
      vi.stubGlobal(
        'fetch',
        vi.fn().mockResolvedValue({
          ok: true,
          status: 200,
          text: async () =>
            JSON.stringify({
              answer: 'We offer flexible hybrid work options.',
            }),
        })
      );

      const user = userEvent.setup();
      render(<App />);
      await user.click(screen.getByRole('button', { name: /open candidate ai assistant/i }));

      const input = screen.getByPlaceholderText(/ask a candidate-related question\.\.\./i);
      await user.type(input, 'What are the remote work options?');

      const sendBtn = screen.getByRole('button', { name: /send message/i });
      await user.click(sendBtn);

      expect(screen.getByText('What are the remote work options?')).toBeInTheDocument();

      await waitFor(() => {
        expect(screen.getByText('We offer flexible hybrid work options.')).toBeInTheDocument();
      });
    });

    it('sends question when clicking a suggested question button', async () => {
      vi.stubGlobal(
        'fetch',
        vi.fn().mockResolvedValue({
          ok: true,
          status: 200,
          text: async () =>
            JSON.stringify({
              answer: 'Applications are typically reviewed within 48 hours.',
            }),
        })
      );

      const user = userEvent.setup();
      render(<App />);
      await user.click(screen.getByRole('button', { name: /open candidate ai assistant/i }));

      const suggestionBtns = screen.getAllByRole('button', { name: /^ask:/i });
      await user.click(suggestionBtns[0]);

      await waitFor(() => {
        expect(
          screen.getByText('Applications are typically reviewed within 48 hours.')
        ).toBeInTheDocument();
      });
    });

    it('navigates back to Home when "← AI OS" button is clicked', async () => {
      const user = userEvent.setup();
      render(<App />);
      await user.click(screen.getByRole('button', { name: /open candidate ai assistant/i }));

      await user.click(screen.getByRole('button', { name: /← ai os/i }));

      expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(/intelligent hiring/i);
    });
  });

  // =========================================================================
  // 6. PORTAL DASHBOARD & SESSION MANAGEMENT
  // =========================================================================
  describe('6. Portal Dashboard & Session Management', () => {
    it('renders Manager Portal dashboard after successful login', async () => {
      await loginAs('manager', 'Interview Manager');
      await waitFor(() => {
        expect(screen.getByText('MANAGER PORTAL')).toBeInTheDocument();
        expect(screen.getByRole('heading', { level: 1, name: 'Candidate Queue' })).toBeInTheDocument();
      });
    });

    it('renders portal sidebar with semantic navigation and aria-current on active item', async () => {
      await loginAs('manager', 'Interview Manager');
      await waitFor(() => {
        const nav = screen.getByRole('navigation', { name: /manager portal navigation/i });
        expect(nav).toBeInTheDocument();

        const candidateQueueBtn = screen.getByRole('button', { name: /candidate queue/i });
        expect(candidateQueueBtn).toHaveAttribute('aria-current', 'page');

        const feedbackBtn = screen.getByRole('button', { name: /interview feedback/i });
        expect(feedbackBtn).not.toHaveAttribute('aria-current');
      });
    });

    it('switches active tab when a navigation item is clicked', async () => {
      const user = await loginAs('manager', 'Interview Manager');

      const feedbackBtn = await screen.findByRole('button', { name: /interview feedback/i });
      await user.click(feedbackBtn);

      expect(feedbackBtn).toHaveAttribute('aria-current', 'page');
      expect(screen.getByRole('heading', { level: 1, name: 'Interview Feedback' })).toBeInTheDocument();
    });

    it('logs the user out and clears session when "Exit portal" is clicked', async () => {
      const user = await loginAs('manager', 'Interview Manager');

      const exitBtn = await screen.findByRole('button', { name: /exit portal and return to home/i });
      await user.click(exitBtn);

      // Verify redirected to Home
      expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(/intelligent hiring/i);

      // Verify sessionStorage cleared
      expect(sessionStorage.getItem('vtab_session')).toBeNull();
    });

    it('renders HR Portal dashboard with offer approvals after logging in as HR', async () => {
      await loginAs('hr', 'HR Lead');

      await waitFor(() => {
        expect(screen.getByText('HR PORTAL')).toBeInTheDocument();
        expect(screen.getByRole('heading', { level: 1, name: 'Offer Approvals' })).toBeInTheDocument();
        expect(screen.getByRole('navigation', { name: /hr portal navigation/i })).toBeInTheDocument();
      });
    });
  });

  // =========================================================================
  // 7. ACCESSIBILITY & REGRESSION DEFENSE
  // =========================================================================
  describe('7. Accessibility & Regression Defense', () => {
    it('maintains aria-live="polite" on chat status and message log', async () => {
      const user = userEvent.setup();
      render(<App />);
      await user.click(screen.getByRole('button', { name: /open candidate ai assistant/i }));

      const chatLog = screen.getByRole('log', { name: /chat messages/i });
      expect(chatLog).toHaveAttribute('aria-live', 'polite');
    });

    it('maintains aria-hidden="true" on decorative ambient background elements', () => {
      const { container } = render(<App />);
      const ambient = container.querySelector('.ambient');
      expect(ambient).toHaveAttribute('aria-hidden', 'true');
    });

    it('provides accessible names for icon-only action buttons', () => {
      render(<App />);
      expect(screen.getByRole('button', { name: /open menu/i })).toBeInTheDocument();
      expect(
        screen.getByRole('button', { name: /open candidate ai assistant/i })
      ).toBeInTheDocument();
    });
  });

  // =========================================================================
  // 8. RESET PASSWORD RECOVERY FLOW
  // =========================================================================
  describe('8. Reset Password Recovery Flow', () => {
    it('renders ResetPassword form when URL hash contains recovery type and token', () => {
      window.history.replaceState(null, '', '/#type=recovery&access_token=test-reset-token');
      render(<App />);

      expect(screen.getByRole('heading', { name: /new password/i })).toBeInTheDocument();
      expect(screen.getByPlaceholderText(/at least 6 characters/i)).toBeInTheDocument();
      expect(screen.getByPlaceholderText(/re-enter your new password/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /update password/i })).toBeInTheDocument();
    });

    it('shows validation error when password is less than 6 characters', async () => {
      window.history.replaceState(null, '', '/#type=recovery&access_token=test-reset-token');
      const user = userEvent.setup();
      render(<App />);

      const submitBtn = screen.getByRole('button', { name: /update password/i });
      await user.type(screen.getByPlaceholderText(/at least 6 characters/i), '123');
      await user.type(screen.getByPlaceholderText(/re-enter your new password/i), '123');
      await user.click(submitBtn);

      expect(screen.getByRole('alert')).toHaveTextContent(/at least 6 characters long/i);
    });

    it('shows validation error when passwords do not match', async () => {
      window.history.replaceState(null, '', '/#type=recovery&access_token=test-reset-token');
      const user = userEvent.setup();
      render(<App />);

      const submitBtn = screen.getByRole('button', { name: /update password/i });
      await user.type(screen.getByPlaceholderText(/at least 6 characters/i), 'newPassword123');
      await user.type(screen.getByPlaceholderText(/re-enter your new password/i), 'differentPassword');
      await user.click(submitBtn);

      expect(screen.getByRole('alert')).toHaveTextContent(/passwords do not match/i);
    });

    it('successfully updates password and shows success state', async () => {
      window.history.replaceState(null, '', '/#type=recovery&access_token=test-reset-token');
      vi.stubGlobal(
        'fetch',
        vi.fn().mockResolvedValue({
          ok: true,
          status: 200,
          text: async () => JSON.stringify({ success: true }),
        })
      );

      const user = userEvent.setup();
      render(<App />);

      await user.type(screen.getByPlaceholderText(/at least 6 characters/i), 'newSecret123');
      await user.type(screen.getByPlaceholderText(/re-enter your new password/i), 'newSecret123');
      await user.click(screen.getByRole('button', { name: /update password/i }));

      const statusMsg = await screen.findByRole('status');
      expect(statusMsg).toHaveTextContent(/your password has been reset successfully/i);
      expect(screen.getByRole('button', { name: /proceed to login/i })).toBeInTheDocument();
    });

    it('navigates back to Home when "← Back to Home" is clicked in reset password view', async () => {
      window.history.replaceState(null, '', '/#type=recovery&access_token=test-reset-token');
      const user = userEvent.setup();
      render(<App />);

      await user.click(screen.getByRole('button', { name: /← back to home/i }));

      expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(/intelligent hiring/i);
    });

    it('displays warning alert and disabled inputs when visiting /reset-password without a token', () => {
      window.history.replaceState(null, '', '/reset-password');
      render(<App />);

      expect(screen.getByRole('heading', { name: /new password/i })).toBeInTheDocument();
      expect(screen.getByText(/no active password reset token was detected/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /request fresh reset link/i })).toBeInTheDocument();
      expect(screen.getByPlaceholderText(/at least 6 characters/i)).toBeDisabled();
      expect(screen.getByRole('button', { name: /update password/i })).toBeDisabled();
    });

    it('navigates to Forgot Password screen when "REQUEST FRESH RESET LINK" is clicked', async () => {
      window.history.replaceState(null, '', '/reset-password');
      const user = userEvent.setup();
      render(<App />);

      await user.click(screen.getByRole('button', { name: /request fresh reset link/i }));
      expect(screen.getByRole('heading', { name: /reset password/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /send reset instructions/i })).toBeInTheDocument();
    });

    it('correctly extracts access token from double-hashed URL and enables form', () => {
      window.history.replaceState(null, '', '/#type=recovery#access_token=token-from-double-hash');
      render(<App />);

      expect(screen.getByRole('heading', { name: /new password/i })).toBeInTheDocument();
      expect(screen.queryByText(/no active password reset token was detected/i)).not.toBeInTheDocument();
      expect(screen.getByPlaceholderText(/at least 6 characters/i)).not.toBeDisabled();
      expect(screen.getByRole('button', { name: /update password/i })).not.toBeDisabled();
    });
  });

  // =========================================================================
  // 9. CANDIDATE DOCUMENT PORTAL ROUTING
  // =========================================================================
  describe('9. Candidate Document Portal Routing', () => {
    it('detects /documents?token=... URL and renders the document submission view', () => {
      window.history.replaceState(null, '', '/documents?token=secure-doc-token');
      render(<App />);

      expect(screen.getByText(/secure document request/i)).toBeInTheDocument();
      expect(screen.getByText(/validating your secure submission link/i)).toBeInTheDocument();
    });
  });

  // =========================================================================
  // 10. ERROR HANDLING & NETWORK RESILIENCY
  // =========================================================================
  describe('10. Error Handling & Network Resiliency', () => {
    it('displays fallback error message when network request throws unexpectedly', async () => {
      vi.stubGlobal(
        'fetch',
        vi.fn().mockRejectedValue(new Error('Network connection lost'))
      );

      const user = userEvent.setup();
      render(<App />);
      await user.click(screen.getByRole('button', { name: /open menu/i }));
      await user.click(screen.getByText('Manager Login'));

      await user.type(screen.getByPlaceholderText(/enter your company email/i), 'manager@vtab.com');
      await user.type(screen.getByPlaceholderText(/enter your password/i), 'secret123');
      await user.click(screen.getByRole('button', { name: /enter portal/i }));

      const alert = await screen.findByRole('alert');
      expect(alert).toHaveTextContent(/network connection lost/i);
    });
  });
});
