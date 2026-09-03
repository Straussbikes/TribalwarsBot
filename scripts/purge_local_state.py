"""
Tribal Wars Mobile Automation Engine - Local State Purge Script
Remove qualquer rasto de persistência local, caches e ficheiros de testes anteriores:
1. Elimina pastas de runtime da aplicação em %APPDATA%, %LOCALAPPDATA% e ~/.config.
2. Varre o repositório/workspace e remove ficheiros residuais como:
   *.sqlite, *.db, session.json, cookies.pkl, accounts.json, debug.log, auth_token.txt e .vault_key legados.
3. Deixa a máquina pronta para uma execução limpa e estritamente cloud-native.
"""

import argparse
import os
from pathlib import Path
import shutil
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def purge_system_appdata():
    """Elimina pastas de cache e runtime do sistema."""
    print("🧹 [1/2] A verificar e eliminar pastas de runtime do sistema...")
    candidates = []

    if sys.platform == "win32":
        local_app = os.environ.get("LOCALAPPDATA")
        roaming_app = os.environ.get("APPDATA")
        user_home = Path.home()

        if local_app:
            candidates.append(Path(local_app) / "TribalWarsBot")
            candidates.append(Path(local_app) / "TribalDesktop")
        if roaming_app:
            candidates.append(Path(roaming_app) / "TribalWarsBot")
        candidates.append(user_home / ".tribalwarsbot")
    else:
        user_home = Path.home()
        candidates.append(user_home / ".config" / "tribalwarsbot")
        candidates.append(user_home / ".local" / "share" / "tribalwarsbot")

    removed_count = 0
    for folder in candidates:
        if folder.exists() and folder.is_dir():
            try:
                shutil.rmtree(folder)
                print(f"   -> Removido diretório de sistema: {folder}")
                removed_count += 1
            except Exception as e:
                print(f"   -> Aviso ao remover {folder}: {e}")

    if removed_count == 0:
        print("   -> Nenhuma pasta de runtime de sistema encontrada.")


def purge_workspace_artifacts():
    """Varre o workspace e elimina ficheiros e bases de dados legadas."""
    print("🧹 [2/2] A varrer o repositório e remover ficheiros locais legados...")

    file_patterns = [
        "*.sqlite",
        "*.db",
        "session.json",
        "cookies.pkl",
        "accounts.json",
        "debug.log",
        "auth_token.txt",
        ".vault_key",
        "*.log",
    ]

    # Pastas e ficheiros a procurar especificamente
    specific_paths = [
        PROJECT_ROOT / "data" / "accounts.db",
        PROJECT_ROOT / "data" / "world_data.db",
        PROJECT_ROOT / "data" / ".vault_key",
        PROJECT_ROOT / "session.json",
        PROJECT_ROOT / "cookies.pkl",
        PROJECT_ROOT / "accounts.json",
        PROJECT_ROOT / "debug.log",
        PROJECT_ROOT / ".map_cache",
        PROJECT_ROOT / ".stats_cache",
    ]

    removed_files = 0

    # 1. Ficheiros específicos
    for p in specific_paths:
        if p.exists():
            try:
                if p.is_dir():
                    shutil.rmtree(p)
                    print(f"   -> Removida pasta de cache: {p.relative_to(PROJECT_ROOT)}")
                else:
                    p.unlink()
                    print(f"   -> Removido ficheiro: {p.relative_to(PROJECT_ROOT)}")
                removed_files += 1
            except Exception as e:
                print(f"   -> Aviso ao remover {p}: {e}")

    # 2. Busca recursiva por padrões legados (exceto em .git, node_modules e .gemini)
    ignore_dirs = {".git", "node_modules", ".gemini", ".system_generated"}

    for root, dirs, files in os.walk(PROJECT_ROOT):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        for f in files:
            f_lower = f.lower()
            should_remove = False
            if f_lower.endswith((".sqlite", ".db", ".pkl")):
                should_remove = True
            elif f_lower in ("session.json", "accounts.json", "debug.log", "auth_token.txt"):
                should_remove = True

            if should_remove:
                file_path = Path(root) / f
                try:
                    file_path.unlink()
                    print(f"   -> Removido: {file_path.relative_to(PROJECT_ROOT)}")
                    removed_files += 1
                except Exception as e:
                    print(f"   -> Aviso ao remover {file_path}: {e}")

    print(f"   -> Total de {removed_files} artefactos locais removidos.")


def main():
    parser = argparse.ArgumentParser(description="Purga de artefactos locais e ficheiros de persistência legada")
    parser.add_argument("--force", "--yes", "-y", action="store_true", help="Ignora a confirmação interativa")
    args = parser.parse_args()

    print("=" * 70)
    print("🛡️  TRIBALWARS BOT - PURGA DE ARTEFACTOS LOCAIS")
    print("=" * 70)

    if not args.force:
        confirm = input("Deseja purgar todos os ficheiros de cache, SQLite e logs locais? (s/n): ")
        if confirm.strip().lower() not in ("s", "sim", "y", "yes"):
            print("❌ Operação abortada.")
            return

    purge_system_appdata()
    purge_workspace_artifacts()

    print("\n" + "=" * 70)
    print("✅ PURGA DE ARTEFACTOS LOCAIS CONCLUÍDA!")
    print("   O ambiente está limpo e 100% cloud-native.")
    print("=" * 70)


if __name__ == "__main__":
    main()
