from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright


VIEWPORTS = (
    ("mobile-360x800", 360, 800),
    ("mobile-430x900", 430, 900),
)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="0liviA mobile UI geometry smoke.")
    p.add_argument("url")
    p.add_argument("output", type=Path)
    return p


async def rect(page, selector: str) -> dict[str, float]:
    return await page.locator(selector).evaluate(
        """el => {
          const r = el.getBoundingClientRect();
          return {left:r.left, top:r.top, right:r.right, bottom:r.bottom,
                  width:r.width, height:r.height};
        }"""
    )


async def main() -> int:
    args = parser().parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    report: dict[str, object] = {"url": args.url, "viewports": []}

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        try:
            for name, width, height in VIEWPORTS:
                context = await browser.new_context(
                    viewport={"width": width, "height": height},
                    device_scale_factor=1,
                    is_mobile=True,
                    has_touch=True,
                )
                page = await context.new_page()
                page_errors: list[str] = []
                page.on("pageerror", lambda exc: page_errors.append(str(exc)))
                await page.goto(args.url, wait_until="domcontentloaded")
                await page.wait_for_timeout(800)

                base = await page.evaluate(
                    """() => ({
                      innerWidth: window.innerWidth,
                      innerHeight: window.innerHeight,
                      htmlWidth: document.documentElement.scrollWidth,
                      bodyWidth: document.body.scrollWidth
                    })"""
                )
                assert base["htmlWidth"] <= width + 1, (name, "html overflow", base)
                assert base["bodyWidth"] <= width + 1, (name, "body overflow", base)

                rail = await rect(page, ".rail")
                composer = await rect(page, "#composer")
                assert rail["left"] >= -1 and rail["right"] <= width + 1, (name, "rail", rail)
                assert composer["left"] >= -1 and composer["right"] <= width + 1, (name, "composer-x", composer)
                assert composer["top"] >= 0 and composer["bottom"] <= height + 1, (name, "composer-y", composer)

                await page.locator('.rail-btn[data-side="session"]').click()
                await page.wait_for_timeout(180)
                drawer = await rect(page, "#drawer")
                assert drawer["left"] >= -1 and drawer["right"] <= width + 1, (name, "drawer-x", drawer)
                assert drawer["top"] >= -1 and drawer["bottom"] <= height + 1, (name, "drawer-y", drawer)
                drawer_widths = await page.evaluate(
                    """() => ({
                      htmlWidth: document.documentElement.scrollWidth,
                      bodyWidth: document.body.scrollWidth
                    })"""
                )
                assert drawer_widths["htmlWidth"] <= width + 1, (name, "drawer html overflow", drawer_widths)
                assert drawer_widths["bodyWidth"] <= width + 1, (name, "drawer body overflow", drawer_widths)
                await page.screenshot(path=str(args.output / f"{name}-session.png"), full_page=False)

                await page.locator("#drawerClose").click()
                await page.locator("#voiceBtn").click()
                await page.wait_for_timeout(180)
                voice = await rect(page, "#voiceLive")
                assert voice["left"] >= -1 and voice["right"] <= width + 1, (name, "voice-x", voice)
                assert voice["top"] >= -1 and voice["bottom"] <= height + 1, (name, "voice-y", voice)
                assert await page.locator("#voiceLive").get_attribute("aria-hidden") == "false"
                voice_widths = await page.evaluate(
                    """() => ({
                      htmlWidth: document.documentElement.scrollWidth,
                      bodyWidth: document.body.scrollWidth
                    })"""
                )
                assert voice_widths["htmlWidth"] <= width + 1, (name, "voice html overflow", voice_widths)
                assert voice_widths["bodyWidth"] <= width + 1, (name, "voice body overflow", voice_widths)
                await page.screenshot(path=str(args.output / f"{name}-voice.png"), full_page=False)

                report["viewports"].append(
                    {
                        "name": name,
                        "viewport": [width, height],
                        "base": base,
                        "rail": rail,
                        "composer": composer,
                        "drawer": drawer,
                        "voice": voice,
                        "page_errors": page_errors,
                    }
                )
                await context.close()
        finally:
            await browser.close()

    (args.output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
