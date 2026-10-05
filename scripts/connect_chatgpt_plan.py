from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from olivia.chatgpt_oauth import ChatGPTOAuthError, authorize_local


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Conecta un plan ChatGPT elegible a 0liviA sin API key."
    )
    home = Path.home() / ".config" / "0livia"
    p.add_argument(
        "--profile",
        type=Path,
        default=home / "chatgpt-plan.json",
        help="perfil OAuth protegido a crear/renovar",
    )
    p.add_argument(
        "--host-id",
        type=Path,
        default=home / "chatgpt-host-id",
        help="identificador estable de este host",
    )
    p.add_argument("--port", type=int, default=1455)
    p.add_argument(
        "--no-browser",
        action="store_true",
        help="imprime la URL en vez de abrir el navegador",
    )
    return p


async def run(args: argparse.Namespace) -> int:
    profile, models = await authorize_local(
        profile_path=args.profile,
        host_id_path=args.host_id,
        port=args.port,
        open_browser=not args.no_browser,
    )
    print(f"ChatGPT conectado: {profile.get('email') or 'cuenta validada'}")
    print(f"Perfil: {args.profile.expanduser()}")
    recommended = profile.get("recommended_model")
    if recommended:
        print(f"Modelo recomendado disponible: {recommended}")
    if models:
        shown = ", ".join(item["slug"] for item in models[:8])
        print(f"Modelos visibles: {shown}")
    print(
        "No compartas este archivo. Para un Core remoto, transferilo por SSH "
        "al profile_path configurado y conservá permisos 0600."
    )
    return 0


def main() -> int:
    args = parser().parse_args()
    if not (1 <= args.port <= 65535):
        parser().error("--port debe estar entre 1 y 65535")
    try:
        return asyncio.run(run(args))
    except KeyboardInterrupt:
        print("Cancelado.")
        return 130
    except ChatGPTOAuthError as exc:
        print(f"No se pudo conectar ChatGPT: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
