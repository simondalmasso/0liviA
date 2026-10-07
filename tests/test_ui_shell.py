from __future__ import annotations

from pathlib import Path


def _shell() -> str:
    return Path("web/index.html").read_text(encoding="utf-8")


def test_monochrome_shell_stays_dependency_free_and_low_weight():
    html = _shell()
    assert len(html.encode("utf-8")) < 96_000
    assert '<meta name="theme-color" content="#000000">' in html
    assert "font-family:system-ui" in html
    assert "linear-gradient(" not in html
    assert "radial-gradient(" not in html
    assert "backdrop-filter" not in html
    assert "<script src=" not in html
    assert 'rel="stylesheet"' not in html
    assert "setInterval(" not in html


def test_unified_navigation_and_composer_contract():
    html = _shell()
    assert 'id="modeChat"' not in html
    assert 'id="modeWork"' not in html
    assert "setPrimaryMode(" not in html
    assert html.count('class="rail-label"') >= 6
    assert 'class="composer-icon" type="button" data-side="library"' in html
    assert 'id="voiceBtn" class="composer-icon"' in html
    assert "Listo cuando quieras." in html


def test_public_home_and_login_are_spanish_and_demo_is_explicit():
    html = _shell()
    assert 'id="publicWelcome"' in html
    assert 'id="publicDemoBtn"' in html
    assert 'id="publicLoginBtn"' not in html
    assert "Probar 0liviA ahora" in html
    assert "Tu IA personal." in html
    assert "Privada y rápida." in html
    assert "Modo prueba IA" in html
    assert "publicDemoActive=false" in html
    assert "publicWelcome.hidden=!(isPublic&&!publicDemoActive)" in html
    assert "PUBLIC_DEMO_ENDPOINT='/api/demo-chat'" in html
    assert "PUBLIC_DEMO_MODEL='GLM 4.7 Flash'" in html
    assert "PUBLIC_DEMO_PROVIDER='workers-ai-demo'" in html
    assert "https://text.pollinations.ai" not in html
    assert "function redactDemoText" in html
    assert "Ese comando necesita el Core privado." in html
    assert 'class="brand-mini"' in html
    assert 'class="auth-mark brand-auth"' in html
    assert '--brand-logo:url("data:image/png;base64,' in html
    assert "<title>0liviA — Tu IA personal</title>" in html
