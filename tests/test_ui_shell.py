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
    assert '--brand-logo:url("/logo-mark.svg")' in html
    assert 'data:image/png;base64' not in html
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
    assert ".app.is-landing .topbar{display:none}" in html
    assert ".app.is-landing{grid-template-rows:1fr}" in html
    assert "publicDemoActive=demoReady" in html

def test_deployment_smoke_tracks_live_monogram_home_not_removed_demo_cta():
    workflow = Path(".github/workflows/deploy-public-shell.yml").read_text(encoding="utf-8")
    assert "grep -Fq 'id=\"entryIntro\"'" in workflow
    assert "grep -Fq 'id=\"text\"'" in workflow
    assert "grep -Fq 'id=\"demoModelSelect\"'" in workflow
    assert "grep -Fq 'Probar 0liviA ahora'" not in workflow
    assert "confirm_account_no_overage:" in workflow
    assert 'test "${CONFIRM_ACCOUNT_NO_OVERAGE:-}" = "true"' in workflow
    assert '"release_sha": body.get("release_sha") == os.environ["RELEASE_SHA"]' in workflow


def test_home_monogram_gets_subtle_backlight_without_glowing_the_entire_shell():
    html = _shell()
    assert ".landing-mark,.intro-mark{filter:drop-shadow(0 0 7px rgba(255,255,255,.22)) drop-shadow(0 0 19px rgba(255,255,255,.09))}" in html
    assert ".rail-logo,.landing-mark" not in html
    assert "animation:intro-exit 3s" in html
    assert ".intro-overlay{display:none!important}" in html


def test_home_initial_view_is_independent_of_saved_chat_and_strict_bw():
    html = _shell()
    assert "let homeView=true;" in html
    assert "const landing=homeView||!chat||!chat.messages.length;" in html
    assert "renderMessagesInto(messagesEl,landing?null:chat)" in html
    assert "homeView=false;" in html
    assert "$('.rail-logo').onclick=()=>{homeView=true;renderMessages();closeDrawer()}" in html
    assert "greeting.textContent='Qué gusto verte, Simon.'" in html
    assert ".messages.landing .empty{position:absolute" in html
    assert ".composer-wrap.landing{top:calc(50% + 40px)" in html
    assert "  .composer-wrap.landing{top:calc(50% + 20px)}" in html
    assert '.rail-logo::before{content:"0"' not in html
    assert '.app.is-landing .composer-status,.app.is-landing .composer-icon{display:none}' in html
    assert ".rail{background:#000;border-color:#fff}" in html
    assert ".composer{background:#fff;border-color:#fff}" in html
    assert ".composer input,.composer-icon{color:#000}" in html
    assert ".user .bubble{background:#fff;color:#000}" in html
    assert "textInput.disabled=!available&&backendMode!=='public_shell'" in html


def test_chat_list_reopens_saved_history_instead_of_leaving_home_active():
    html = _shell()
    start = html.index("function renderChats(){")
    end = html.index("function renderConfig(){", start)
    section = html[start:end]
    assert "workspace.selectedChatId=chat.id;homeView=false;" in section
    assert "await saveState();renderAll();closeDrawer();" in section
    assert "'IA demo no disponible'" not in html[html.index("function updateComposerAvailability()"):html.index("function setCoreState(")]


def test_ui_never_replays_queued_model_requests_on_load_login_or_network_recovery():
    html = _shell()
    assert "syncQueued(" not in html
    assert "window.addEventListener('online',()=>syncQueued" not in html
    assert "await syncCanonicalWorkspace();syncQueued();" not in html
    assert "renderAll();await probeCore({force:true})" in html
    assert "async function sendChat(raw" in html
    assert "chat.messages.push(msg)" in html
    assert "window.addEventListener('online',()=>syncQueued({force:true}))" not in html


def test_pending_remote_request_is_always_marked_as_review_required():
    html = _shell()
    assert "Sin enviar · requiere revisión manual" in html
    assert "No se reintentará automáticamente" in html


def test_vector_brand_asset_is_crisp_at_any_dpi_and_has_no_remote_content():
    from xml.etree import ElementTree as ET
    html = _shell()
    svg = Path("web/logo-mark.svg").read_text(encoding="utf-8")
    root = ET.fromstring(svg)
    assert root.tag.endswith("svg")
    assert root.attrib["viewBox"] == "0 0 100 126"
    assert "data:image/png;base64" not in html
    assert "<image" not in svg
    assert "<script" not in svg
    assert "foreignObject" not in svg
    assert svg.count("http://") == 1
    assert "https://" not in svg
    assert "filter:drop-shadow(0 0 7px" in html
    assert 'id="entryIntro"' in html
