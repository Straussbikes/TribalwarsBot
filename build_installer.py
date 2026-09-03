"""
Script de automação para geração do instalador nativo e pacote de release do Tribal Wars Bot.
Gera o instalador Inno Setup (.exe) se o compilador estiver presente,
e cria o pacote portátil de distribuição (.zip) com script de atalho para o Desktop.
"""

import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

APP_VERSION = "2.0.0"

def find_iscc() -> Path | None:
    """Procura pelo compilador Inno Setup (ISCC.exe) no PATH e nos diretórios habituais."""
    # 1. No PATH do sistema
    iscc_path = shutil.which("iscc") or shutil.which("ISCC.exe")
    if iscc_path:
        return Path(iscc_path)

    # 2. Caminhos habituais em sistemas Windows
    standard_paths = [
        Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")) / "Inno Setup 6" / "ISCC.exe",
        Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Inno Setup 6" / "ISCC.exe",
        Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")) / "Inno Setup 5" / "ISCC.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe",
    ]

    for p in standard_paths:
        if p.exists():
            return p
    return None


def create_desktop_shortcut_script(target_dir: Path) -> None:
    """Cria um script .bat simples e fiável para gerar o atalho no Ambiente de Trabalho."""
    bat_content = """@echo off
chcp 65001 > nul
echo ================================================================
echo   A criar atalho do Tribal Wars Bot no Ambiente de Trabalho...
echo ================================================================

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ws = New-Object -ComObject WScript.Shell; ^
   $desktop = [Environment]::GetFolderPath('Desktop'); ^
   $s = $ws.CreateShortcut(\\"$desktop\\Tribal Wars Bot.lnk\\"); ^
   $s.TargetPath = \\"%~dp0TribalWarsBot.exe\\"; ^
   $s.WorkingDirectory = \\"%~dp0\\"; ^
   $s.Description = 'Tribal Wars Bot - Desktop Automation'; ^
   $s.Save()"

if %ERRORLEVEL% equ 0 (
    echo [OK] Atalho criado com sucesso no seu Ambiente de Trabalho!
) else (
    echo [AVISO] Nao foi possivel criar o atalho automaticamente.
)
pause
"""
    shortcut_bat = target_dir / "Criar_Atalho_Ambiente_Trabalho.bat"
    shortcut_bat.write_text(bat_content, encoding="utf-8")
    print(f"[Pacote] Script de atalho gerado: {shortcut_bat.name}")


def create_portable_zip(source_dir: Path, output_zip: Path) -> None:
    """Compacta a pasta dist/TribalWarsBot num ficheiro zip autónomo."""
    print(f"[Pacote] A gerar pacote portatil ZIP: {output_zip.name}...")
    if output_zip.exists():
        output_zip.unlink()

    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                file_path = Path(root) / file
                archive_name = Path("TribalWarsBot") / file_path.relative_to(source_dir)
                zf.write(file_path, archive_name)

    size_mb = output_zip.stat().st_size / (1024 * 1024)
    print(f"[Pacote] Pacote ZIP gerado com sucesso: {output_zip} ({size_mb:.2f} MB)")


def main():
    root_dir = Path(__file__).resolve().parent
    dist_dir = root_dir / "dist"
    app_dir = dist_dir / "TribalWarsBot"
    exe_path = app_dir / "TribalWarsBot.exe"
    iss_file = root_dir / "installer.iss"

    print("=" * 65)
    print(f"  Tribal Wars Bot v{APP_VERSION} - Gerador de Release & Instalador")
    print("=" * 65)

    if not exe_path.exists():
        print(f"Erro: O executavel '{exe_path}' nao foi encontrado.")
        print("Execute primeiro 'python build_executable.py' para compilar o executavel.")
        sys.exit(1)

    # 1. Cria o utilitário de atalho no diretório distribuível
    create_desktop_shortcut_script(app_dir)

    # 2. Cria o pacote portátil ZIP
    zip_path = dist_dir / f"TribalWarsBot_v{APP_VERSION}_Portable.zip"
    create_portable_zip(app_dir, zip_path)

    # 3. Compilação do instalador Inno Setup se ISCC estiver instalado
    iscc = find_iscc()
    if iscc:
        print(f"\n[Instalador] Compilador Inno Setup detetado: {iscc}")
        print("[Instalador] A compilar TribalWarsBot_Setup_v2.0.0.exe...")
        res = subprocess.run([str(iscc), str(iss_file)], cwd=str(root_dir))
        if res.returncode == 0:
            setup_exe = dist_dir / f"TribalWarsBot_Setup_v{APP_VERSION}.exe"
            if setup_exe.exists():
                size_mb = setup_exe.stat().st_size / (1024 * 1024)
                print(f"[Instalador] Instalador nativo gerado: {setup_exe} ({size_mb:.2f} MB)")
        else:
            print("[Instalador] Aviso: Falha na compilacao com Inno Setup.")
    else:
        print("\n[Instalador] Nota: Inno Setup (ISCC.exe) nao esta instalado no sistema.")
        print(f"[Instalador] O script '{iss_file.name}' esta configurado e pronto a ser compilado")
        print("caso instale o Inno Setup (https://jrsoftware.org/isdl.php).")
        print(f"[Instalador] Para utilizacao imediata, o pacote portatil '{zip_path.name}' contem todos os ficheiros.")

    print("\n" + "=" * 65)
    print("[Concluido] Artefactos de distribuicao prontos na pasta 'dist/'!")
    print("=" * 65)


if __name__ == "__main__":
    main()
