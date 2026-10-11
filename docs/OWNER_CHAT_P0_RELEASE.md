# P0 — Liberación del primer chat autenticado de 0liviA

Contrato operativo de la PR #114. Esta guía **no autoriza** por sí misma inferencia, despliegue ni gastos. El Core Python con memoria y SQLite sigue siendo un producto separado del demo Worker.

## Qué se integró offline

- Frontend: Auth0 Google SPA con Authorization Code + PKCE S256, state y nonce. El access token se conserva sólo en memoria de la pestaña.
- Worker: `GET /api/auth/public-config` expone únicamente los parámetros **públicos** de la SPA, o `{enabled:false}` sin configuración válida.
- Worker: `GET /api/auth/owner-status` exige access token RS256/JWKS con issuer/audience exactos, identidad Google verificada y enrolamiento privado. Anónimos: HTTP 401; Google no-owner autenticado: HTTP 403.
- El envío a `POST /api/demo-chat` adjunta bearer desde el módulo autenticado. El Worker revalida JWT **antes** de `COST_GUARD` o `env.AI.run`.
- El login y las cookies del Core Python legacy se preservan para el backend canónico; este cambio **no convierte el demo en Core**.
- Los tests de navegador ya no simulan que un invitado recibe un turno IA exitoso; ahora verifican el bloqueo del botón y ausencia de llamadas.

## Configuración privada necesaria (NO copiar valores en GitHub/issues/logs)

1. Auth0: tenant del dominio Auth0 por defecto, aplicación **Single Page Application**, Google social connection, login de código + PKCE. Callback exacto, logout y Allowed Web Origins asociados al origen HTTPS publicado.
2. Auth0 Action: añadir claims con namespace `https://0livia.app/claims/` al **access token de la API**, con `provider=google-oauth2`, `google_sub`, `email`, `email_verified` y `session_version`, obtenidos de datos de identidad fiables. No utilizar email/rol indicado por el cliente; no copiar secretos en un Action público.
3. Cloudflare Worker: guardar como secretos privados `OLIVIA_AUTH0_ISSUER`, `OLIVIA_AUTH0_AUDIENCE`, `OLIVIA_OWNER_AUTH0_SUB`, `OLIVIA_OWNER_GOOGLE_SUB`, `OLIVIA_OWNER_GOOGLE_EMAIL`, `OLIVIA_OWNER_SESSION_VERSION` y `OLIVIA_OWNER_REVOKED_BEFORE`. Deben coincidir con el enrolamiento privado; no asignar OWNER al primer usuario. `OLIVIA_AUTH0_CLIENT_ID` es identificador **público** de SPA y se configura como variable de despliegue.
4. Antes de permitir modelo: certificar en la **cuenta Cloudflare efectiva** el plan Workers Free, no-overage y admisión de GLM 4.7 Flash en ese plan. El contador de 25 solicitudes **no prueba** el límite global de neurons. Un plan Paid, duda de facturación, trial o modelo sin cuota certificada implica **no activar**.
5. Ejecutar los tests offline del commit exacto: `node --test tests/node/test_cloudflare_worker.mjs`, `node --check web/auth0_bridge.js`, `pytest -q`, auditoría estática y E2E de invitado. No sustituir esos resultados por una prueba simulada de chat funcional.

## Gate de despliegue y pruebas HTTP (orden estricto)

- La publicación dinámica `deploy-public-shell.yml` es manual y exige aprobación independiente de cuenta/no-overage, variables Auth0 y SHA canónico; configura `OLIVIA_STATIC_ONLY=0` explícitamente, pero **no** efectúa canary con credenciales prestadas.
- Los smokes de producción sin bearer esperan **401** en `/api/chat` y `/api/demo-chat` sin consumir proveedores. Un 200 anónimo obliga a parar y revertir a estático.
- El flujo de Qwen queda congelado, sin disparador `push`, despliegue ni canary. No habilitar GPT-OSS/Gemma/Muse ni agentes en esta liberación.
- Tras validar plan y login **en el navegador del propietario**, ejecutar por aprobación puntual **un único turno GLM auténtico**: respuesta textual no vacía, modelo identificado correctamente, sin error y con costos comprobados. No usar ese canary como prueba de memoria del Core.
- Probar un Google distinto y un visitante: 403/401 en HTTP directo; demostrar contadores de `AI.run=0`, `COST_GUARD=0` y cero lecturas del Core para usuarios sin autorización. Confirmar expiración/logout, no-replay, dispositivos y cobertura de sesión. No pegar tokens ni respuestas privadas en evidencias públicas.
- La reversión no es automática: si falla el release, mantener la liberación **BLOCKED**, ejecutar la vía manual `deploy-public-static.yml` con una aprobación de reversión independiente y confirmar el SHA/flags de `/healthz`.

## Bloqueos que la PR no resuelve

- No se ha acreditado todavía el plan real de Cloudflare ni completado el login Auth0 productivo.
- El Core Python de OCI (#43) sigue sin despliegue SSH certificado; la memoria duradera y los backups **no se acreditan** con el demo.
- El almacenamiento local legacy de la UI no está aislado por identidades Google en un navegador compartido; antes de invitar a usuarios debe deshabilitarse o aislarse por cuenta. No declarar privacidad multiusuario completa sólo por proteger la API.
- La prueba offline y un Worker publicado sin inferencia no prueban funcionamiento end-to-end. Reportar por separado F0 seguridad, F1 respuesta real, F2 costo, F3 evidencia.

Seguimiento: [mandato #97](https://github.com/simondalmasso/0liviA/issues/97), [OCI #43](https://github.com/simondalmasso/0liviA/issues/43), [PR #114](https://github.com/simondalmasso/0liviA/pull/114).
