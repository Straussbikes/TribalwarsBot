"""
Tribal Wars Bot - Commercial Build & Packaging Automation Pipeline
Executa a compilação do executável standalone sem consola (GUI pura) via PyInstaller.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path


def run_pipeline():
    root_dir = Path(__file__).resolve().parent
    dist_dir = root_dir / "dist"
    build_dir = root_dir / "build"
    spec_file = root_dir / "TribalWarsBot.spec"
    assets_dir = root_dir / "assets"
    icon_file = assets_dir / "icon.ico"
    version_file = root_dir / "file_version_info.txt"

    print("=" * 70)
    print(" [Tribal Wars Bot] Pipeline de Compilação Standalone (GUI Pura)")
    print(f" Raiz do Projeto: {root_dir}")
    print(f" Interpretador Python: {sys.executable}")
    print("=" * 70)

    # 1. Validação de pré-requisitos
    if not spec_file.exists():
        print(f"[ERRO] Ficheiro de especificação '{spec_file}' não encontrado.")
        sys.exit(1)

    if not version_file.exists():
        print(f"[ERRO] Ficheiro de metadados '{version_file}' não encontrado.")
        sys.exit(1)

    # 2. Garante que o ícone existe
    if not icon_file.exists():
        print("[AVISO] Ícone 'assets/icon.ico' não encontrado. A gerar ícone padrão...")
        assets_dir.mkdir(exist_ok=True)
        try:
            from PIL import Image, ImageDraw
            img = Image.new("RGBA", (256, 256), (15, 23, 42, 255))
            draw = ImageDraw.Draw(img)
            draw.ellipse([(16, 16), (240, 240)], outline=(6, 182, 212, 255), width=8)
            img.save(icon_file, format="ICO")
            print(" Ícone padrão gerado com sucesso.")
        except Exception as e:
            print(f"[AVISO] Não foi possível gerar ícone: {e}")

    # 3. Limpeza rigorosa de compilações anteriores
    if dist_dir.exists():
        print(" A limpar pasta de distribuição anterior (dist/)...")
        shutil.rmtree(dist_dir, ignore_errors=True)

    if build_dir.exists():
        print(" A limpar pasta de build temporária (build/)...")
        shutil.rmtree(build_dir, ignore_errors=True)

    # 4. Execução do PyInstaller
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        str(spec_file),
    ]

    print(f"\n[A EXECUTAR] {' '.join(cmd)}\n")
    proc = subprocess.run(cmd, cwd=str(root_dir))

    if proc.returncode != 0:
        print(f"\n[FALHA] PyInstaller encerrou com código de erro: {proc.returncode}")
        sys.exit(proc.returncode)

    # 5. Checklist de Validação Pós-Build
    exe_path = dist_dir / "TribalWarsBot" / "TribalWarsBot.exe"
    if not exe_path.exists():
        print(f"\n[ERRO] O executável esperado não foi encontrado em: {exe_path}")
        sys.exit(1)

    # Verifica integridade dos assets do frontend
    frontend_dest = dist_dir / "TribalWarsBot" / "_internal" / "frontend"
    if not frontend_dest.exists():
        frontend_dest = dist_dir / "TribalWarsBot" / "frontend"

    if not frontend_dest.exists() or not (frontend_dest / "index.html").exists():
        print("[Sincronização] A copiar pasta 'frontend' para a raiz da distribuição...")
        shutil.copytree(root_dir / "frontend", dist_dir / "TribalWarsBot" / "frontend", dirs_exist_ok=True)

    exe_size_mb = exe_path.stat().st_size / (1024 * 1024)
    print("\n" + "=" * 70)
    print(" COMPILAÇÃO CONCLUÍDA COM SUCESSO!")
    print("=" * 70)
    print(f" Binário Gerado: {exe_path}")
    print(f" Tamanho do Executável Principal: {exe_size_mb:.2f} MB")
    print(" Modo de Execução: GUI Windowed (console=False, sem terminal)")
    print(" Rotação de Logs: Silencioso em %APPDATA%/TribalWarsBot/logs/")
    print("=" * 70)


if __name__ == "__main__":
    run_pipeline()
