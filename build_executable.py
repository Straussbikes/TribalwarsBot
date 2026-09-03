"""
Script de automação de build para compilação do Tribal Wars Bot com PyInstaller.
"""

import os
from pathlib import Path
import shutil
import subprocess
import sys

def main():
    root_dir = Path(__file__).resolve().parent
    dist_dir = root_dir / "dist"
    build_dir = root_dir / "build"
    spec_file = root_dir / "TribalWarsBot.spec"

    print("=" * 65)
    print("[Build] A iniciar compilacao do Tribal Wars Bot...")
    print(f"Diretorio Raiz: {root_dir}")
    print("=" * 65)

    if not spec_file.exists():
        print(f"Erro: Ficheiro de especificacao '{spec_file}' nao encontrado.")
        sys.exit(1)

    # Limpeza preventiva de builds antigas
    if dist_dir.exists():
        print("A limpar diretorio 'dist' anterior...")
        shutil.rmtree(dist_dir, ignore_errors=True)
    if build_dir.exists():
        print("A limpar diretorio 'build' anterior...")
        shutil.rmtree(build_dir, ignore_errors=True)

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        str(spec_file),
    ]

    print(f"A executar comando: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(root_dir))

    if result.returncode != 0:
        print("\n[Build] Erro na compilacao do PyInstaller.")
        sys.exit(result.returncode)

    output_exe = dist_dir / "TribalWarsBot" / "TribalWarsBot.exe"
    if not output_exe.exists():
        print(f"\n[Build] Executavel nao encontrado no destino esperado: {output_exe}")
        sys.exit(1)

    dest_frontend = dist_dir / "TribalWarsBot" / "frontend"
    if not dest_frontend.exists():
        print("A sincronizar pasta frontend/ na raiz da distribuicao...")
        shutil.copytree(root_dir / "frontend", dest_frontend)

    exe_size_mb = output_exe.stat().st_size / (1024 * 1024)
    print("\n" + "=" * 65)
    print("[Build Concluido com Sucesso!]")
    print(f"Executavel gerado: {output_exe}")
    print(f"Tamanho do executavel: {exe_size_mb:.2f} MB")
    print("=" * 65)


if __name__ == "__main__":
    main()
