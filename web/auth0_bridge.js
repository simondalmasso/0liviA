// Auth0 PKCE for the optional public shell. No access token is persisted.
(() => {
  "use strict";
  const KEY = "olivia:auth0:pkce:v1";
  let config = null, token = "", owner = false, error = "";
  function b64url(bytes) {
    return btoa(String.fromCharCode(...bytes)).replace(/\+/g,"-").replace(/\//g,"_").replace(/=+$/,"");
  }
  function random(n) { const x = new Uint8Array(n); crypto.getRandomValues(x); return b64url(x); }
  function valid(c) {
    if (!c || c.enabled !== true || typeof c.client_id !== "string" ||
        !/^[A-Za-z0-9_-]{10,128}$/.test(c.client_id) ||
        typeof c.issuer !== "string" || typeof c.audience !== "string") return false;
    try {
      const u = new URL(c.issuer);
      return u.protocol === "https:" && u.hostname.endsWith(".auth0.com") &&
        u.pathname === "/" && !u.search && !u.hash && c.issuer === u.origin + "/" &&
        /^https:\/\/[A-Za-z0-9.-]+\/[A-Za-z0-9._/-]+$/.test(c.audience);
    } catch { return false; }
  }
  function callbackAndClean() {
    const url = new URL(location.href);
    if (["code","state","error","error_description"].some(k => url.searchParams.has(k))) {
      history.replaceState(null,"",location.pathname + location.hash);
    }
    return url;
  }
  function idNonce(jwt) {
    if (typeof jwt !== "string") return null;
    const parts = jwt.split(".");
    if (parts.length !== 3 || !/^[A-Za-z0-9_-]{1,12000}$/.test(parts[1])) return null;
    try {
      const b = parts[1].replace(/-/g,"+").replace(/_/g,"/");
      return JSON.parse(atob(b+"=".repeat((4-b.length%4)%4))).nonce || null;
    } catch { return null; }
  }
  async function start() {
    if (!config) throw Error("Google todavía no está configurado.");
    const state = random(24), nonce = random(24), verifier = random(48);
    const digest = await crypto.subtle.digest("SHA-256",new TextEncoder().encode(verifier));
    const challenge = b64url(new Uint8Array(digest));
    sessionStorage.setItem(KEY,JSON.stringify({state,nonce,verifier,created:Date.now()}));
    const u = new URL("authorize",config.issuer);
    for (const [key,value] of Object.entries({
      response_type:"code",client_id:config.client_id,
      redirect_uri:location.origin+location.pathname,
      scope:"openid profile email",audience:config.audience,
      code_challenge:challenge,code_challenge_method:"S256",state,nonce
    })) u.searchParams.set(key,value);
    location.assign(u.href);
  }
  async function complete(url) {
    if (!url.searchParams.has("code") && !url.searchParams.has("error")) return;
    const raw = sessionStorage.getItem(KEY);
    sessionStorage.removeItem(KEY); // At most one token exchange.
    if (!config || !raw || url.searchParams.has("error")) throw Error("Google: acceso cancelado o inválido.");
    let p;
    try { p = JSON.parse(raw); } catch { throw Error("Estado OAuth inválido."); }
    if (p.state !== url.searchParams.get("state") || !/^[A-Za-z0-9_-]{64}$/.test(p.verifier||"") ||
        typeof p.nonce !== "string" || p.nonce.length < 20 ||
        !Number.isFinite(p.created) || Date.now()<p.created ||
        Date.now()-p.created>600000) throw Error("Sesión expirada. Volvé a entrar.");
    const code = url.searchParams.get("code");
    if (!code || code.length>4096) throw Error("Código de acceso inválido.");
    const resp = await fetch(new URL("oauth/token",config.issuer),{
      method:"POST",credentials:"omit",redirect:"error",
      headers:{"content-type":"application/x-www-form-urlencoded"},
      body:new URLSearchParams({
        grant_type:"authorization_code",client_id:config.client_id,
        code,code_verifier:p.verifier,
        redirect_uri:location.origin+location.pathname
      })
    });
    if (!resp.ok) throw Error("Google: no se pudo validar la sesión.");
    const data = await resp.json();
    if (data.token_type!=="Bearer" || typeof data.access_token!=="string" ||
        !/^[A-Za-z0-9._-]{30,8192}$/.test(data.access_token) ||
        idNonce(data.id_token)!==p.nonce) throw Error("Token de identidad inválido.");
    // Only the server's signed JWT/JWKS + privately enrolled owner grant access.
    const gate = await fetch("/api/auth/owner-status",{
      headers:{Authorization:"Bearer "+data.access_token},credentials:"same-origin",cache:"no-store"
    });
    if (!gate.ok) {
      // Only server-defined stage codes, never JWT or private claim contents.
      const messages = {
        token_shape:"Formato de token API inválido.",
        jwt_header:"Cabecera JWT no compatible: revisar tipo y algoritmo.",
        jwt_claims:"Claims JWT rechazadas: revisar issuer, audiencia o fechas.",
        jwks_key:"La firma usa una clave que no aparece en JWKS.",
        jwt_signature:"La firma del JWT no pudo verificarse.",
        jwks_validation:"Fallo consultando o validando las claves públicas JWKS.",
        jwks_fetch:"El Worker no puede consultar JWKS de Auth0.",
        jwks_response:"La respuesta JWKS de Auth0 no es válida.",
        jwks_crypto:"Falló la importación o validación criptográfica JWKS."
      };
      let reason = "";
      if (gate.status === 401) {
        try {
          const details = await gate.json();
          if (typeof details?.auth_stage === "string" &&
              Object.prototype.hasOwnProperty.call(messages, details.auth_stage))
            reason = messages[details.auth_stage];
        } catch {}
      }
      throw Error(gate.status===403
        ? "Esta cuenta Google no es propietaria de 0liviA."
        : gate.status===401
          ? (reason || "No se pudo verificar la firma o las claims del token API.")
          : gate.status===503
            ? "La configuración privada del propietario no está completa."
            : "No se pudo comprobar la sesión Google. Volvé a intentarlo.");
    }
    token = data.access_token; owner = true;
  }
  async function init(publicShell) {
    if (!publicShell) { token = "";owner = false;return; }
    const url = callbackAndClean(); // Remove code/state from address before token exchange.
    try {
      const r = await fetch("/api/auth/public-config",{cache:"no-store"});
      const c = r.ok ? await r.json() : null;
      config = valid(c) ? c : null;
      await complete(url);
    } catch(e) {
      token = "";owner = false;error = String(e?.message||"No disponible");
    }
  }
  function showLogin() {
    const card = document.getElementById("ownerLogin");
    const form = document.getElementById("ownerLoginForm");
    for (const id of ["ownerEmail","ownerPassword","ownerAuthSubmit"])
      document.getElementById(id).hidden=true;
    document.getElementById("ownerRemember").closest("label").hidden=true;
    document.getElementById("ownerAuthTitle").textContent="Acceso Google";
    document.getElementById("ownerAuthCopy").textContent=config
      ? "Sólo el propietario autorizado puede utilizar la IA privada."
      : "El acceso Google todavía no está configurado.";
    let btn = document.getElementById("oliviaGoogleLogin");
    if (!btn) {
      btn=document.createElement("button");
      btn.id="oliviaGoogleLogin";btn.type="button";btn.className="auth-submit";
      btn.textContent="Continuar con Google";
      form.insertBefore(btn,document.getElementById("ownerLoginError"));
      btn.addEventListener("click",()=>start().catch(e=>{
        document.getElementById("ownerLoginError").textContent=e.message;
      }));
    }
    btn.hidden=!config;
    document.getElementById("ownerLoginError").textContent=error;
    card.classList.add("open");card.setAttribute("aria-hidden","false");
  }
  function authorization(){return owner&&token?"Bearer "+token:"";}
  async function postDemo(path,messages,model,signal){
    if(path!=="/api/demo-chat")throw Error("Ruta de modelo no autorizada.");
    const bearer=authorization();
    if(!bearer)throw Error("Entrá con Google para usar la IA privada.");
    return fetch(path,{
      method:"POST",credentials:"same-origin",
      headers:{"Content-Type":"application/json",Authorization:bearer},
      body:JSON.stringify({messages,model}),signal
    });
  }
  window.OliviaOwnerAuth={
    init,showLogin,postDemo,isOwner:()=>owner&&!!token,
    authorization,
    invalidate:()=>{token="";owner=false;}
  };
})();
