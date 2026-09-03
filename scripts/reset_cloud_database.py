"""
Tribal Wars Bot - Cloud Database Fresh Start Reset Script
Limpa todos os dados da base de dados Cloud SQL (PostgreSQL Neon)
e o token de sessão local em auth.dat para um arranque 100% novo.
"""

import asyncio
import os
import sys
from pathlib import Path

# Ajusta path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.storage.cloud_db import get_cloud_db
from engine.storage.token_storage import token_storage
from sqlalchemy import text


async def reset_database():
    print("==================================================")
    print("Tribal Wars Bot - Fresh Start Database Reset")
    print("==================================================")

    db = get_cloud_db()
    masked_url = db.raw_url.split("@")[-1] if "@" in db.raw_url else db.raw_url
    print(f"Conexão Cloud SQL: {masked_url}")

    # 1. Truncate tabelas relacionais com CASCADE
    async with db.engine.begin() as conn:
        print("\n[1/4] A limpar tabelas relacionais no Cloud SQL (PostgreSQL)...")
        await conn.execute(text("TRUNCATE TABLE villages, game_worlds, game_accounts, app_users CASCADE;"))
        print("      -> villages: limpo")
        print("      -> game_worlds: limpo")
        print("      -> game_accounts: limpo")
        print("      -> app_users: limpo")

        print("\n[2/4] A limpar modelos de construção customizados (preservando os 5 oficiais)...")
        await conn.execute(text("""
            DELETE FROM build_templates 
            WHERE id NOT IN ('ee02gd68de', 'zbhbufxza0q', '4zyrtbsdxa', 'rtk1zhvuvtr', '6goivjbmzbh');
        """))
        print("      -> Modelos customizados removidos.")

    # 2. Semear e verificar os 5 modelos oficiais
    print("\n[3/4] A assegurar os 5 modelos oficiais imutáveis...")
    await db.build_template_repo.seed_defaults_if_needed()
    print("      -> ee02gd68de (AI - Build Model)")
    print("      -> zbhbufxza0q (Construcao)")
    print("      -> 4zyrtbsdxa (Upar Barbara)")
    print("      -> rtk1zhvuvtr (Sprinter BR131)")
    print("      -> 6goivjbmzbh (Pontos Premium)")

    # 3. Limpar token de sessão local
    print("\n[4/4] A limpar sessão local (auth.dat)...")
    token_storage.clear_token()
    print(f"      -> {token_storage.auth_file_path} removido/limpo.")

    # 4. Verificar contagens finais
    async with db.get_session() as session:
        v_count = (await session.execute(text("SELECT COUNT(*) FROM villages"))).scalar()
        gw_count = (await session.execute(text("SELECT COUNT(*) FROM game_worlds"))).scalar()
        ga_count = (await session.execute(text("SELECT COUNT(*) FROM game_accounts"))).scalar()
        u_count = (await session.execute(text("SELECT COUNT(*) FROM app_users"))).scalar()
        bt_count = (await session.execute(text("SELECT COUNT(*) FROM build_templates"))).scalar()

        print("\n==================================================")
        print("RESUMO DO FRESH START:")
        print(f"  - Utilizadores da App (app_users):    {u_count}")
        print(f"  - Contas de Jogo (game_accounts):     {ga_count}")
        print(f"  - Mundos de Jogo (game_worlds):       {gw_count}")
        print(f"  - Aldeias (villages):                 {v_count}")
        print(f"  - Modelos de Construção Oficiais:     {bt_count}")
        print("==================================================")
        print("Base de dados limpa com sucesso para um Fresh Start!\n")

    await db.close()


if __name__ == "__main__":
    asyncio.run(reset_database())
