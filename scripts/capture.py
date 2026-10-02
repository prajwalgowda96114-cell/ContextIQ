"""Playwright script to capture deck screenshots 01 to 03 for ContextIQ."""
import asyncio
import pathlib
from playwright.async_api import async_playwright

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCREENSHOTS_DIR = ROOT.parent / "docs" / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)


async def capture_screenshots():
    print("Starting Playwright browser for demo screenshot capture...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            device_scale_factor=2
        )
        page = await context.new_page()

        # 1. Capture Screenshot 01: Upload (New Incident Page)
        print("Navigating to http://127.0.0.1:8000...")
        await page.goto("http://127.0.0.1:8000", wait_until="networkidle")
        await page.wait_for_timeout(1000)

        # Click 'New Incident' tab
        await page.click("#nav-upload")
        await page.wait_for_timeout(500)

        # Load Demo Incident A preset
        await page.click("#btn-load-demo-a")
        await page.wait_for_timeout(800)

        screenshot_01 = SCREENSHOTS_DIR / "01-upload.png"
        await page.screenshot(path=str(screenshot_01))
        print(f"Captured Screenshot 01 -> {screenshot_01}")

        # 2. Capture Screenshot 02: Live Analysis (Incident Intelligence Stream)
        # Click Analyze
        await page.click("#btn-analyze-incident")
        await page.wait_for_timeout(1200)

        screenshot_02 = SCREENSHOTS_DIR / "02-live-analysis.png"
        await page.screenshot(path=str(screenshot_02))
        print(f"Captured Screenshot 02 -> {screenshot_02}")

        # 3. Capture Screenshot 03: Decision & Why (Finished Decision View)
        # Wait for pipeline to finish validating evidence
        await page.wait_for_timeout(3500)

        screenshot_03 = SCREENSHOTS_DIR / "03-decision-why.png"
        await page.screenshot(path=str(screenshot_03))
        print(f"Captured Screenshot 03 -> {screenshot_03}")

        await browser.close()
        print("Screenshot capture completed successfully!")


if __name__ == "__main__":
    asyncio.run(capture_screenshots())
