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
    assert 'id="publicWelcome"' not in html
    assert 'id="publicDemoBtn"' not in html
    assert 'id="publicLoginBtn"' not in html
    assert "Probá 0liviA." not in html
    assert "Chat de muestra." not in html
    assert "Probar 0liviA ahora" not in html
    assert 'className="landing-mark"' in html
    assert 'id="publicStatus"' in html
    assert "costo no verificado" in html
    assert "Modo prueba IA" in html
    assert "publicDemoActive=demoReady" in html
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


def test_demo_errors_are_not_presented_as_model_answers():
    html = _shell()
    assert "m.status==='error'?' error'" in html
    assert "bubble.setAttribute('role','alert')" in html
    assert "text:'La demo no respondió. Reintentá en unos segundos.'" in html
    assert "status:'error',\n        provider:null," in html

    e2e = Path("tests-e2e/public-demo.e2e.ts").read_text(encoding="utf-8")
    assert "provider failure is an alert, never a successful AI answer" in e2e
    assert "assistant:not(.error)" in e2e
    assert "toHaveCount(0)" in e2e


def test_closed_drawer_hidden_at_all_widths_and_model_select_is_gate_driven():
    html = _shell()
    assert ".drawer{visibility:hidden;opacity:0" in html
    assert ".drawer.open{visibility:visible;opacity:1" in html
    assert "@media(min-width:721px) and (max-width:1100px)" in html
    assert 'id="demoModelSelect"' in html
    assert 'value="qwen" disabled' in html
    assert 'value="gemma" disabled' in html
    assert 'coreHealth?.demo_gemma_ready===true' in html
    assert "PUBLIC_DEMO_GEMMA_MODEL='Gemma 4 26B A4B'" in html
    assert "coreHealth?.demo_qwen_ready===true" in html
    assert "model:demoModelSelect.value" in html
    assert "function providerPresentation(name,model)" in html
    assert "{command:'/intel',label:" in html

def test_home_intro_is_time_bounded_and_accessible():
    html = _shell()
    assert 'id="entryIntro"' in html
    assert 'aria-hidden="true"' in html
    assert 'class="intro-mark"' in html
    assert "animation:intro-exit 3s" in html
    assert "@keyframes intro-exit" in html
    assert ".intro-overlay{pointer-events:none" in html
    assert "@media(prefers-reduced-motion:reduce)" in html
    assert ".intro-overlay{display:none!important}" in html
    assert ".app.is-landing .topbar{visibility:hidden}" in html
    assert ".shell:has(.app.is-landing) .rail-logo{opacity:0" in html
    assert "publicDemoActive=demoReady" in html
