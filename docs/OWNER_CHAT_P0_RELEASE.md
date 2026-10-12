# P0 — Liberación del primer chat autenticado de 0liviA

Contrato operativo de la PR #114. Esta guía **no autoriza** por sí misma inferencia, despliegue ni gastos. El Core Python con memoria y SQLite sigue siendo un producto separado del demo Worker.

## ACEPTACIÓN DEL PROPIETARIO: FAIL — producción no funciona

**Estado verificado el 2026-10-11 a partir de una captura del propietario y GET de red:** la URL pública del Worker muestra «Chat IA no conectado», botón Enviar inhabilitado y ninguna respuesta real; `/healthz` indicó `release_sha=7e33c19d5410f94fa29e5d62a85a132da2ce755b`, `static_only=true`, `demo_provider_ready=false`, `demo_inference_enabled=false`; `/auth0_bridge.js` devolvió 404 y `/api/auth/public-config` devolvió 401. **REAL OWNER CHAT = FAIL, independientemente de Python/seguridad/E2E/móvil en verde.**

**Prohibido rotular «funciona», «arreglada» o «production PASS»** porque `/healthz` dé 200, la UI abra, o el navegador responda con un GLM *mock*. Esta sección sólo podrá cambiar a `REAL OWNER CHAT = PASS` una vez cumplidas **todas** las pruebas siguientes en la URL pública, con evidencia sanitizada:

1. El SHA exacto publicado en `/healthz` corresponde al commit fusionado en `main` y el release **dinámico** está habilitado sólo para GLM 4.7 Flash, con Qwen/Gemma OFF y sin fallback facturable.
2. La cuenta efectiva del Worker está acreditada Workers Free con **USD 0 / no overage**; no AI Gateway Unified Billing ni Paid; preflight Billing Read separado PASS, sin publicar tokens ni datos contables privados.
3. Auth0 está configurado realmente como tenant/Google SPA/API/Action, `/auth0_bridge.js` existe, `/api/auth/public-config` tiene `enabled=true`, y el propietario inscrito inicia sesión con Google de verdad; no se admite el primer visitante como owner.
4. **Sólo con aprobación explícita del propietario para el turno real**, este pulsa Enviar, se registra un único `POST /api/demo-chat` autenticado a GLM y recibe **texto no vacío y no simulado**. No reintentar un POST cuyo resultado sea incierto. Registrar sólo SHA, estados, nombre de modelo y ausencia de errores, no mensajes ni credenciales.
5. Usuario sin sesión: 401; Google distinto: 403; ambos con **0 AI.run y 0 CostGuard**. Cierre de sesión y recarga no devuelven acceso a datos del propietario.

**Si cualquiera falla, la aceptación permanece FAIL**; no anunciar DONE, no pagar ni reducir restricciones para aparentar un 200. La reversión estática es manual y requiere su propia autorización. Core OCI y memoria persistente del issue #43 tienen estado independiente, incluso después de un posible PASS del demo.



## Qué se integró offline

- Frontend: Auth0 Google SPA con Authorization Code + PKCE S256, state y nonce. El access token se conserva sólo en memoria de la pestaña.
- Worker: `GET /api/auth/public-config` expone únicamente los parámetros **públicos** de la SPA, o `{enabled:false}` sin configuración válida.
- Worker: `GET /api/auth/owner-status` exige access token RS256/JWKS con issuer/audience exactos, identidad Google verificada y enrolamiento privado. Anónimos: HTTP 401; Google no-owner autenticado: HTTP 403.
- El envío a `POST /api/demo-chat` adjunta bearer desde el módulo autenticado. El Worker revalida JWT **antes** de `COST_GUARD` o `env.AI.run`.
- El login y las cookies del Core Python legacy se preservan para el backend canónico; este cambio **no convierte el demo en Core**.
- Los tests de navegador ya no simulan que un invitado recibe un turno IA exitoso; ahora verifican el bloqueo del botón y ausencia de llamadas.

## Configuración privada necesaria (NO copiar valores en GitHub/issues/logs)

1. Auth0: tenant del dominio Auth0 por defecto, aplicación **Single Page Application**, Google social connection, login de código + PKCE. Callback exacto, logout y Allowed Web Origins asociados al origen HTTPS publicado.
2. Auth0 Action: código de referencia versionado en `auth0/actions/owner_google_claims.cjs` y probado offline en `tests/node/test_auth0_action.mjs`. Crear manualmente un **Post Login Action** con esos cinco claims bajo `https://0livia.app/claims/` únicamente para Google verificado, audiencia `https://0livia.app/api` y SPA exacta. El Action requiere **dos secretos privados configurados en Auth0**: `OLIVIA_AUTH0_SPA_CLIENT_ID` (identificador público de la SPA, restringido a esa aplicación) y `OLIVIA_OWNER_SESSION_VERSION` (mismo valor privado que el Worker). Sin alguno, no emitirá claims. El Action no confiere OWNER: el Worker valida `sub`, Google sub, correo verificado y versión contra el enrolamiento privado. **NO instalar/activar el Action ni registrar identidades desde test mocks** sin verificar la configuración privada y realizar una prueba de aceptación; no pegar valores en el repo ni en CI.
3. Cloudflare Worker: guardar como secretos privados `OLIVIA_AUTH0_ISSUER`, `OLIVIA_AUTH0_AUDIENCE`, `OLIVIA_OWNER_AUTH0_SUB`, `OLIVIA_OWNER_GOOGLE_SUB`, `OLIVIA_OWNER_GOOGLE_EMAIL`, `OLIVIA_OWNER_SESSION_VERSION` y `OLIVIA_OWNER_REVOKED_BEFORE`. Deben coincidir con el enrolamiento privado; no asignar OWNER al primer usuario. `OLIVIA_AUTH0_CLIENT_ID` es identificador **público** de SPA y se configura como variable de despliegue.
4. Antes de permitir modelo: certificar en la **cuenta Cloudflare efectiva** el plan Workers Free, no-overage y admisión de GLM 4.7 Flash en ese plan.
   - **Gate económico independiente de Auth0:** el Dashboard/Support Center debe confirmar suscripción Free y el total **a nivel de suscripción** de Actions desplegadas y enlazadas + Forms creados dentro de la cuota gratuita, no sólo dentro del tenant de 0liviA. La prueba de 22 días ofrece capacidades de evaluación adicionales y **no acredita** que esas capacidades queden disponibles al finalizar. Auth0 explica que excedencias de Actions/Forms sostenidas pueden motivar upgrade automático; no aceptar upgrades. Dado que el API de cuota no está conectado al workflow, `confirm_auth0_free_quota` es una **declaración manual explícita con default false, no una certificación automática**. Sin confirmación, no desplegar ni ejecutar GLM. Referencias oficiales: https://support.auth0.com/center/s/article/managing-auth0-actions-and-forms-quota-exceedance-notifications y https://support.auth0.com/center/s/article/Question-regarding-the-Free-and-the-Trial-plan. El contador de 25 solicitudes **no prueba** el límite global de neurons. Un plan Paid, duda de facturación, trial o modelo sin cuota certificada implica **no activar**.
5. Ejecutar los tests offline del commit exacto: `node --test tests/node/test_cloudflare_worker.mjs`, `node --check web/auth0_bridge.js`, `pytest -q`, auditoría estática y E2E de invitado. No sustituir esos resultados por una prueba simulada de chat funcional.

## Gate de despliegue y pruebas HTTP (orden estricto)

- **Nuevo gate de release:** el smoke HTTP cache-busted debe recibir `/auth0_bridge.js` con el módulo Google, `/api/auth/public-config` con `enabled=true` e issuer/Auth0/audiencia, y `/api/auth/owner-status` anónimo=401; todos GET, sin modelo ni bearer. La validación de propietario real en navegador sigue pendiente de autorización aparte.
- La publicación dinámica `deploy-public-shell.yml` es manual y exige aprobación independiente de cuenta/no-overage, **prueba read-only de suscripción Workers Free vinculada al mismo `CLOUDFLARE_ACCOUNT_ID` de Wrangler**, variables Auth0 y SHA canónico; configura `OLIVIA_STATIC_ONLY=0` explícitamente y fuerza Qwen/Gemma a OFF incluso si hay variables históricas, pero **no** efectúa canary con credenciales prestadas.
- **Preflight de identidad pre-despliegue:** `wrangler secret list --name 0livia --format json` lee únicamente nombres y tipos de los siete secretos Auth0/Google del propietario; `scripts/verify_owner_secret_names.py` exige todos antes de permitir cualquier publicación dinámica. No revela los valores. Si el token de deploy no puede listar o falta uno, el workflow termina **BLOCKED** antes de desplegar. La mera presencia no comprueba que sus valores sean correctos: el canary autenticado continúa siendo necesario.
- La comprobación privada de plan requiere el secreto GitHub Actions `CLOUDFLARE_BILLING_READ_TOKEN`: token Cloudflare limitado a **Account → Billing → Read** y al mismo account ID; `CLOUDFLARE_API_TOKEN` conserva exclusivamente los permisos necesarios de despliegue. El token de Billing Read sólo se inyecta en el paso de preflight, no en Wrangler. Si falta, si la API rechaza permisos (403), o si el listado está incompleto, **BLOCKED antes de desplegar**. No otorgar Billing Write, no introducir tokens en PR/issues/logs y no conceder permiso de gasto.
- Los smokes de producción sin bearer esperan **401** en `/api/chat` y `/api/demo-chat` sin consumir proveedores. Un 200 anónimo obliga a parar y revertir a estático.
- El flujo de Qwen queda congelado, sin disparador `push`, despliegue ni canary. No habilitar GPT-OSS/Gemma/Muse ni agentes en esta liberación.
- Tras validar plan y login **en el navegador del propietario**, ejecutar por aprobación puntual **un único turno GLM auténtico**: respuesta textual no vacía, modelo identificado correctamente, sin error y con costos comprobados. No usar ese canary como prueba de memoria del Core.
- Probar un Google distinto y un visitante: 403/401 en HTTP directo; demostrar contadores de `AI.run=0`, `COST_GUARD=0` y cero lecturas del Core para usuarios sin autorización. Confirmar expiración/logout, no-replay, dispositivos y cobertura de sesión. No pegar tokens ni respuestas privadas en evidencias públicas.
- La reversión no es automática: si falla el release, mantener la liberación **BLOCKED**, ejecutar la vía manual `deploy-public-static.yml` con una aprobación de reversión independiente y confirmar el SHA/flags de `/healthz`.

## Bloqueos que la PR no resuelve

- **Workers Free (0 US$/mes) comprobado el 2026-10-11:** el panel autenticado mostró `Gratuito → 0 US$ → Plan actual`; documentación Cloudflare: 10.000 neurons gratuitas diarias, exceso bloqueado en Workers Free, GLM 4.7 Flash admitido. No se han verificado aún el login Auth0 productivo, la cuenta vinculada a los secretos de despliegue ni una respuesta real. Volver a verificar el plan antes de un release externo.
- El Core Python de OCI (#43) sigue sin despliegue SSH certificado; la memoria duradera y los backups **no se acreditan** con el demo.
- El almacenamiento local legacy de la UI no está aislado por identidades Google en un navegador compartido; antes de invitar a usuarios debe deshabilitarse o aislarse por cuenta. No declarar privacidad multiusuario completa sólo por proteger la API.
- La prueba offline y un Worker publicado sin inferencia no prueban funcionamiento end-to-end. Reportar por separado F0 seguridad, F1 respuesta real, F2 costo, F3 evidencia.

Seguimiento: [mandato #97](https://github.com/simondalmasso/0liviA/issues/97), [OCI #43](https://github.com/simondalmasso/0liviA/issues/43), [PR #114](https://github.com/simondalmasso/0liviA/pull/114).
