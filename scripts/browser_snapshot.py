from __future__ import annotations

import argparse
import asyncio
import ipaddress
import json
import re
import socket
from pathlib import Path
from urllib.parse import urlsplit

from playwright.async_api import Route, async_playwright

from olivia.web import WebReadError, validate_public_url


MAX_REQUESTS = 100
MAX_TEXT_CHARS = 30_000
MAX_LINKS = 40


def _all_public_addresses(host: str) -> bool:
    try:
        records = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except OSError:
        return False
    addresses = {record[4][0] for record in records}
    if not addresses:
        return False
    for address in addresses:
        try:
            if not ipaddress.ip_address(address).is_global:
                return False
        except ValueError:
            return False
    return True


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--objective", default="")
    parser.add_argument("--output", default="browser-result.json")
    parser.add_argument("--screenshot", default="browser-shot.png")
    args = parser.parse_args()

    try:
        start_url = validate_public_url(args.url)
    except WebReadError as exc:
        raise SystemExit(f"invalid public URL: {exc}") from exc

    request_count = 0

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome", headless=True)
        context = await browser.new_context(
            service_workers="block",
            java_script_enabled=True,
            ignore_https_errors=False,
            accept_downloads=False,
        )
        page = await context.new_page()

        async def guard(route: Route) -> None:
            nonlocal request_count
            request_count += 1
            if request_count > MAX_REQUESTS:
                await route.abort("blockedbyclient")
                return

            request = route.request
            raw = request.url
            scheme = urlsplit(raw).scheme.lower()
            if scheme in {"data", "blob", "about"}:
                await route.continue_()
                return
            if scheme not in {"http", "https"}:
                await route.abort("blockedbyclient")
                return
            try:
                normalized = validate_public_url(raw)
            except WebReadError:
                await route.abort("blockedbyclient")
                return
            host = urlsplit(normalized).hostname or ""
            if not await asyncio.to_thread(_all_public_addresses, host):
                await route.abort("blockedbyclient")
                return
            if request.resource_type in {"media", "websocket"}:
                await route.abort("blockedbyclient")
                return
            await route.continue_()

        await context.route("**/*", guard)

        try:
            response = await page.goto(
                start_url,
                wait_until="domcontentloaded",
                timeout=20_000,
            )
            await page.wait_for_timeout(1_500)
            final_url = validate_public_url(page.url)
            final_host = urlsplit(final_url).hostname or ""
            if not await asyncio.to_thread(_all_public_addresses, final_host):
                raise RuntimeError("final URL is not globally routable")

            title = (await page.title())[:300]
            try:
                text = await page.locator("body").inner_text(timeout=5_000)
            except Exception:
                text = ""
            text = re.sub(r"[ \t\f\v]+", " ", text)
            text = re.sub(r"\n\s*\n+", "\n\n", text).strip()
            truncated = len(text) > MAX_TEXT_CHARS
            text = text[:MAX_TEXT_CHARS]

            links = await page.locator("a[href]").evaluate_all(
                """els => els.slice(0, 80).map(a => ({
                  text: (a.innerText || a.textContent || '').trim().slice(0, 200),
                  url: a.href
                }))"""
            )
            safe_links = []
            for item in links:
                if len(safe_links) >= MAX_LINKS:
                    break
                try:
                    href = validate_public_url(str(item.get("url") or ""))
                except WebReadError:
                    continue
                safe_links.append({
                    "text": str(item.get("text") or "")[:200],
                    "url": href,
                })

            try:
                await page.screenshot(
                    path=args.screenshot,
                    full_page=False,
                    animations="disabled",
                    timeout=8_000,
                )
                screenshot = args.screenshot
            except Exception:
                screenshot = None

            status = response.status if response is not None else None
            payload = {
                "requested_url": start_url,
                "final_url": final_url,
                "status": status,
                "title": title,
                "text": text,
                "truncated": truncated,
                "links": safe_links,
                "request_count": request_count,
                "objective": str(args.objective or "")[:4_000],
                "screenshot": screenshot,
            }
            Path(args.output).write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        finally:
            await context.close()
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
