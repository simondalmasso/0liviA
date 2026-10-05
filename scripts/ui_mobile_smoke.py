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
                await page.wait_for_timeout(50)
                assert not page_errors, (name, "page errors after drawer click", page_errors)
                await page.wait_for_function(
                    """() => {
                      const el = document.querySelector("#drawer");
                      if (!el || el.getAttribute("aria-hidden") !== "false") return false;
                      const box = el.getBoundingClientRect();
                      return box.left >= -1 && box.right <= window.innerWidth + 1;
                    }""",
                    timeout=2_000,
                )
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

                auth_page = await context.new_page()
                auth_errors: list[str] = []
                auth_page.on("pageerror", lambda exc: auth_errors.append(str(exc)))

                async def route_health(route):
                    await route.fulfill(
                        status=200,
                        content_type="application/json",
                        body=json.dumps(
                            {
                                "process_alive": True,
                                "api_mode": "canonical",
                                "provider_ready": False,
                                "registration_open": True,
                                "registration_protected": True,
                            }
                        ),
                    )

                async def route_sessions(route):
                    await route.fulfill(
                        status=401,
                        content_type="application/json",
                        body=json.dumps({"error": "unauthorized"}),
                    )

                await auth_page.route("**/healthz", route_health)
                await auth_page.route("**/api/sessions?limit=1", route_sessions)
                await auth_page.goto(
                    args.url + "#setup=mobile-smoke-one-shot",
                    wait_until="domcontentloaded",
                )
                await auth_page.wait_for_timeout(800)
                assert await auth_page.locator("#ownerLogin").get_attribute("aria-hidden") == "false"
                assert await auth_page.locator("#ownerAuthTitle").inner_text() == "Registrate"
                assert await auth_page.locator("#ownerRemember").is_checked()
                assert await auth_page.evaluate("location.hash") == ""

                auth_card = await rect(auth_page, ".auth-card")
                email = await rect(auth_page, "#ownerEmail")
                password = await rect(auth_page, "#ownerPassword")
                submit = await rect(auth_page, "#ownerAuthSubmit")
                for label, box in (
                    ("auth-card", auth_card),
                    ("auth-email", email),
                    ("auth-password", password),
                    ("auth-submit", submit),
                ):
                    assert box["left"] >= -1 and box["right"] <= width + 1, (name, label, box)
                    assert box["top"] >= -1 and box["bottom"] <= height + 1, (name, label, box)
                auth_widths = await auth_page.evaluate(
                    """() => ({
                      htmlWidth: document.documentElement.scrollWidth,
                      bodyWidth: document.body.scrollWidth
                    })"""
                )
                assert auth_widths["htmlWidth"] <= width + 1, (name, "auth html overflow", auth_widths)
                assert auth_widths["bodyWidth"] <= width + 1, (name, "auth body overflow", auth_widths)
                await auth_page.screenshot(path=str(args.output / f"{name}-register.png"), full_page=False)

                report["viewports"].append(
                    {
                        "name": name,
                        "viewport": [width, height],
                        "base": base,
                        "rail": rail,
                        "composer": composer,
                        "drawer": drawer,
                        "voice": voice,
                        "auth": {
                            "card": auth_card,
                            "email": email,
                            "password": password,
                            "submit": submit,
                        },
                        "page_errors": page_errors,
                        "auth_page_errors": auth_errors,
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
