"""
Tribal Wars Mobile Automation Engine - Cloud DB Sanitization Script
Script automatizado e seguro com confirmação via CLI para purgar o Cloud SQL:
1. Executa DELETE/TRUNCATE em cascata nas tabelas transacionais:
   'villages', 'game_worlds', 'game_accounts', 'app_users'.
2. Preserva OBRIGATORIAMENTE na tabela 'build_templates' apenas os 5 IDs oficiais:
   - 'ee02gd68de' (AI - Build Model)
   - 'zbhbufxza0q' (Construcao)
   - '4zyrtbsdxa' (Upar Barbara)
   - 'rtk1zhvuvtr' (Sprinter BR131)
   - '6goivjbmzbh' (Pontos Premium)
3. Faz reset a sequências/identities e garante a semeadura íntegra dos 5 modelos oficiais.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Garante raiz do projeto no sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import text
from engine.storage.cloud_db import CloudDatabase
from engine.config.templates import DEFAULT_BUILD_TEMPLATES, DEFAULT_BUILD_TEMPLATE_IDS


async def sanitize_cloud_db(force: bool = False, database_url: str = None) -> None:
    print("=" * 70)
    print("🛡️  TRIBALWARS BOT - SANITIZAÇÃO DE CLOUD SQL (POSTGRESQL)")
    print("=" * 70)

    db = CloudDatabase(database_url=database_url)
    print(f"🔌 Conectando ao Cloud SQL: {db.raw_url.split('@')[-1] if '@' in db.raw_url else db.raw_url}")

    if not force:
        print("\n⚠️  ATENÇÃO: Esta operação irá ELIMINAR PERMANENTEMENTE todos os dados de:")
        print("   - Utilizadores (app_users)")
        print("   - Contas de jogo e cofres (game_accounts)")
        print("   - Mundos vinculados (game_worlds)")
        print("   - Aldeias configuradas (villages)")
        print("   - Modelos customizados de construção (preservando apenas os 5 modelos oficiais)")
        confirm = input("\nTem a certeza absoluta de que deseja continuar? Digite 'PURGE' para confirmar: ")
        if confirm.strip() != "PURGE":
            print("❌ Operação abortada pelo utilizador.")
            await db.close()
            return

    print("\n⏳ A iniciar purga transacional...")

    # Garante que as tabelas existem antes da purga
    await db.init_models(drop_all=False)

    async with db.get_session() as session:
        # 1. Purgar tabelas transacionais em cascata
        print("🧹 [1/3] A limpar tabelas transacionais (villages, game_worlds, game_accounts, app_users)...")
        # No PostgreSQL, DELETE CASCADE através das Foreign Keys ou TRUNCATE CASCADE
        try:
            await session.execute(text("TRUNCATE TABLE villages, game_worlds, game_accounts, app_users RESTART IDENTITY CASCADE;"))
            print("   -> TRUNCATE TABLE ... RESTART IDENTITY CASCADE concluído com sucesso.")
        except Exception as e:
            print(f"   -> Fallback para DELETE ordenado devido a: {e}")
            await session.execute(text("DELETE FROM villages;"))
            await session.execute(text("DELETE FROM game_worlds;"))
            await session.execute(text("DELETE FROM game_accounts;"))
            await session.execute(text("DELETE FROM app_users;"))

        # 2. Sanitizar tabela build_templates (preservar estritamente os 5 IDs oficiais)
        print("🧹 [2/3] A purgar modelos de construção customizados e preservar os 5 oficiais...")
        from engine.storage.cloud_db import BuildTemplate
        from sqlalchemy import delete
        await session.execute(delete(BuildTemplate).where(BuildTemplate.id.not_in(DEFAULT_BUILD_TEMPLATE_IDS)))

        # 3. Garantir / Restaurar os 5 modelos padrão oficiais
        print("🛡️ [3/3] A verificar integridade dos 5 modelos oficiais de construção...")
        await session.commit()

    # Re-semeia e assegura consistência dos 5 modelos
    await db.build_template_repo.seed_defaults_if_needed()

    # Relatório final
    async with db.get_session() as session:
        users_cnt = (await session.execute(text("SELECT COUNT(*) FROM app_users"))).scalar()
        accs_cnt = (await session.execute(text("SELECT COUNT(*) FROM game_accounts"))).scalar()
        worlds_cnt = (await session.execute(text("SELECT COUNT(*) FROM game_worlds"))).scalar()
        villages_cnt = (await session.execute(text("SELECT COUNT(*) FROM villages"))).scalar()
        tpls = (await session.execute(text("SELECT id, name FROM build_templates ORDER BY id"))).fetchall()

    await db.close()

    print("\n" + "=" * 70)
    print("✅ SANITIZAÇÃO CONCLUÍDA COM SUCESSO!")
    print("=" * 70)
    print(f"• Utilizadores: {users_cnt}")
    print(f"• Contas de Jogo: {accs_cnt}")
    print(f"• Mundos: {worlds_cnt}")
    print(f"• Aldeias: {villages_cnt}")
    print(f"• Modelos de Construção Oficiais Preservados ({len(tpls)}):")
    for tid, tname in tpls:
        print(f"   - [{tid}] {tname}")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Purga e sanitização da base de dados Cloud SQL (PostgreSQL)")
    parser.add_argument("--force", "--yes", "-y", action="store_true", help="Ignora a confirmação interativa do terminal")
    parser.add_argument("--url", type=str, default=None, help="Connection string opcional da base de dados")
    args = parser.parse_args()

    asyncio.run(sanitize_cloud_db(force=args.force, database_url=args.url))


if __name__ == "__main__":
    main()
