"""
Task 10 — Accessibility Test Suite
===================================
Static-analysis tests that validate WCAG 2.2 AA accessibility improvements
applied to the React frontend. No browser or Selenium required.

Each test reads the source files directly and checks for the expected
accessibility attributes / patterns.

Run:  python scratch/test_task10_accessibility.py
"""

import os
import re
import subprocess
import sys
import unittest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND = os.path.join(ROOT, "Frontend")
SRC = os.path.join(FRONTEND, "src")
APP_JSX = os.path.join(SRC, "App.jsx")
APP_CSS = os.path.join(SRC, "App.css")
INDEX_HTML = os.path.join(FRONTEND, "index.html")
BACKEND_APP = os.path.join(ROOT, "Backend", "app.py")


def read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class TestA10_HtmlLang(unittest.TestCase):
    """A: <html lang="en"> present in index.html"""

    def test_html_lang_en(self):
        content = read(INDEX_HTML)
        self.assertIn(
            'lang="en"',
            content,
            "index.html must have lang=\"en\" on the <html> element",
        )


class TestA10_SkipLink(unittest.TestCase):
    """B: Skip-to-main-content link in index.html"""

    def test_skip_link_present(self):
        content = read(INDEX_HTML)
        self.assertIn(
            'href="#main-content"',
            content,
            "index.html must contain a skip link with href=\"#main-content\"",
        )

    def test_skip_link_class(self):
        content = read(INDEX_HTML)
        self.assertIn(
            'class="skip-link"',
            content,
            "Skip link must have class=\"skip-link\"",
        )


class TestA10_FocusVisibleCSS(unittest.TestCase):
    """C: :focus-visible CSS rule in App.css"""

    def test_focus_visible_rule(self):
        content = read(APP_CSS)
        self.assertIn(
            ":focus-visible",
            content,
            "App.css must define a :focus-visible rule for keyboard focus rings",
        )

    def test_focus_visible_outline(self):
        content = read(APP_CSS)
        # Confirm an outline property appears in the focus-visible block
        idx = content.find(":focus-visible")
        self.assertGreater(idx, -1)
        snippet = content[idx : idx + 120]
        self.assertIn("outline", snippet, ":focus-visible rule must set an outline")

    def test_skip_link_css(self):
        content = read(APP_CSS)
        self.assertIn(
            ".skip-link",
            content,
            "App.css must define .skip-link styles",
        )


class TestA10_AriaModalOnDialogs(unittest.TestCase):
    """D: Modals have role="dialog" and aria-modal="true" """

    def setUp(self):
        self.jsx = read(APP_JSX)

    def test_role_dialog_present(self):
        count = self.jsx.count('role="dialog"')
        self.assertGreaterEqual(
            count,
            2,
            "App.jsx must have at least 2 elements with role=\"dialog\" "
            "(manager review modal + HR offer review modal)",
        )

    def test_aria_modal_present(self):
        count = self.jsx.count('aria-modal="true"')
        self.assertGreaterEqual(
            count,
            3,
            "App.jsx must have at least 3 aria-modal=\"true\" attributes "
            "(nav drawer + manager modal + HR modal)",
        )

    def test_nav_drawer_dialog(self):
        self.assertIn(
            'aria-label="Navigation menu"',
            self.jsx,
            "Side navigation drawer must have aria-label=\"Navigation menu\"",
        )


class TestA10_CloseButtonLabel(unittest.TestCase):
    """E: Icon-only close button has aria-label"""

    def test_close_button_aria_label(self):
        jsx = read(APP_JSX)
        self.assertIn(
            'aria-label="Close navigation menu"',
            jsx,
            "The × close button in the navigation drawer must have aria-label",
        )


class TestA10_ChatAriaLive(unittest.TestCase):
    """F: Chat messages container has aria-live="polite" and role="log" """

    def setUp(self):
        self.jsx = read(APP_JSX)

    def test_aria_live_polite(self):
        count = self.jsx.count('aria-live="polite"')
        self.assertGreaterEqual(
            count,
            1,
            "App.jsx must have at least one aria-live=\"polite\" for the chat interface",
        )

    def test_role_log(self):
        self.assertIn(
            'role="log"',
            self.jsx,
            "Chat messages container must have role=\"log\"",
        )

    def test_send_button_aria_label(self):
        self.assertIn(
            'aria-label="Send message"',
            self.jsx,
            "The icon-only chat submit button (↑) must have aria-label=\"Send message\"",
        )

    def test_input_aria_label(self):
        self.assertIn(
            'aria-label="Type your question"',
            self.jsx,
            "Chat input must have aria-label=\"Type your question\"",
        )


class TestA10_AlertRoles(unittest.TestCase):
    """G: Error containers use role="alert" """

    def test_role_alert_present(self):
        jsx = read(APP_JSX)
        count = jsx.count('role="alert"')
        self.assertGreaterEqual(
            count,
            3,
            "App.jsx must have at least 3 role=\"alert\" attributes "
            "(login error, portal error, and others added in Task 6)",
        )


class TestA10_StatusRoles(unittest.TestCase):
    """H: Success / status containers use role="status" """

    def test_role_status_present(self):
        jsx = read(APP_JSX)
        count = jsx.count('role="status"')
        self.assertGreaterEqual(
            count,
            1,
            "App.jsx must have at least one role=\"status\" attribute "
            "(success messages in ForgotPassword / ResetPassword)",
        )


class TestA10_AriaCurrentNav(unittest.TestCase):
    """I: Portal navigation uses aria-current="page" """

    def test_aria_current_page(self):
        jsx = read(APP_JSX)
        self.assertIn(
            'aria-current',
            jsx,
            "Portal nav buttons must use aria-current for the active item",
        )

    def test_aria_current_page_value(self):
        jsx = read(APP_JSX)
        self.assertIn(
            '"page"',
            jsx,
            'aria-current must be set to "page" for the active nav item',
        )


class TestA10_AriaBusyLoading(unittest.TestCase):
    """J: Loading states have aria-busy="true" """

    def test_aria_busy(self):
        jsx = read(APP_JSX)
        self.assertIn(
            'aria-busy="true"',
            jsx,
            "Loading state containers must have aria-busy=\"true\"",
        )


class TestA10_TimeDateTime(unittest.TestCase):
    """K: <time> elements in AuditLogs use dateTime attribute"""

    def test_datetime_attribute(self):
        jsx = read(APP_JSX)
        self.assertIn(
            "dateTime",
            jsx,
            "AuditLogs <time> element must have a dateTime attribute",
        )

    def test_datetime_iso(self):
        jsx = read(APP_JSX)
        self.assertIn(
            "toISOString()",
            jsx,
            "dateTime attribute must use toISOString() for machine-readable format",
        )


class TestA10_MainContentId(unittest.TestCase):
    """L: Skip link target id="main-content" is present in screens"""

    def test_main_content_id(self):
        jsx = read(APP_JSX)
        count = jsx.count('id="main-content"')
        self.assertGreaterEqual(
            count,
            4,
            "App.jsx must have at least 4 elements with id=\"main-content\" "
            "(Home, Login, ForgotPassword, ResetPassword, CandidateAI, PortalLayout)",
        )


class TestA10_AriaHiddenDecorative(unittest.TestCase):
    """M: Decorative elements have aria-hidden="true" """

    def test_aria_hidden_present(self):
        jsx = read(APP_JSX)
        count = jsx.count('aria-hidden="true"')
        self.assertGreaterEqual(
            count,
            3,
            "App.jsx must hide multiple decorative elements with aria-hidden=\"true\"",
        )


class TestA10_MenuAriaExpanded(unittest.TestCase):
    """N: Menu trigger button uses aria-expanded"""

    def test_aria_expanded(self):
        jsx = read(APP_JSX)
        self.assertIn(
            "aria-expanded",
            jsx,
            "Hamburger menu trigger must have aria-expanded attribute",
        )

    def test_aria_controls(self):
        jsx = read(APP_JSX)
        self.assertIn(
            'aria-controls="site-navigation"',
            jsx,
            "Menu trigger must have aria-controls pointing to the navigation element",
        )


class TestA10_NavElement(unittest.TestCase):
    """O: Portal sidebar uses semantic <nav> element"""

    def test_nav_element(self):
        jsx = read(APP_JSX)
        self.assertIn(
            "<nav ",
            jsx,
            "Portal navigation must use a semantic <nav> element",
        )

    def test_nav_aria_label(self):
        jsx = read(APP_JSX)
        # nav should have an aria-label
        self.assertIn(
            'aria-label={role === "manager"',
            jsx,
            "Portal <nav> must have a role-specific aria-label",
        )


class TestA10_FrontendBuild(unittest.TestCase):
    """P: Frontend build still passes after all accessibility changes"""

    def test_npm_build(self):
        import shutil
        if not shutil.which("npm") or not os.path.exists(os.path.join(FRONTEND, "node_modules")):
            self.skipTest("npm or Frontend/node_modules not available in this environment; Frontend build is validated in the Frontend CI job.")
        result = subprocess.run(
            ["npm", "run", "build"],
            cwd=FRONTEND,
            capture_output=True,
            text=True,
            timeout=120,
            shell=True,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"Frontend build failed:\nSTDOUT:\n{result.stdout[-3000:]}\nSTDERR:\n{result.stderr[-2000:]}",
        )


class TestA10_BackendCompile(unittest.TestCase):
    """Q: Backend app.py still compiles cleanly"""

    def test_py_compile(self):
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", BACKEND_APP],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"Backend/app.py compile failed: {result.stderr}",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
