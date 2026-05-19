"""Login, session save/load, and validity check for Xianyu (goofish.com)."""

from pathlib import Path

from playwright.async_api import async_playwright, BrowserContext

SESSION_FILE = Path(__file__).parent.parent / "session" / "storage_state.json"
LOGIN_URL = "https://www.goofish.com/"


async def login_and_save() -> None:
    """Open a visible browser for the user to log in, then save the session."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto(LOGIN_URL)

        # Poll cookies until login is detected (up to 5 minutes)
        # unb = user id cookie, only set after successful login
        for _ in range(300):
            await page.wait_for_timeout(1000)
            cookies = await context.cookies()
            names = {c["name"] for c in cookies}
            if "unb" in names and "_m_h5_tk" in names:
                break

        SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
        await context.storage_state(path=str(SESSION_FILE))
        await browser.close()


async def load_context(playwright) -> BrowserContext:
    """Load a browser context from the saved session file."""
    browser = await playwright.chromium.launch(
        headless=True,
        args=["--disable-blink-features=AutomationControlled"],
    )
    context = await browser.new_context(
        storage_state=str(SESSION_FILE),
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
    )
    return context


def session_exists() -> bool:
    return SESSION_FILE.exists()


async def check_session_valid(context: BrowserContext) -> bool:
    """Check if the saved session is still valid by verifying login state."""
    page = await context.new_page()
    try:
        await page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=15000)
        cookies = await context.cookies()
        cookie_names = {c["name"] for c in cookies}
        # Must have both a token and unb (user id) — just having cookie2 isn't enough
        has_token = "_m_h5_tk" in cookie_names
        has_unb = "unb" in cookie_names
        return has_token and has_unb
    except Exception:
        return False
    finally:
        await page.close()
