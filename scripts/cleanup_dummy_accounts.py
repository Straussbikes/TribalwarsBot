import asyncio
from engine.storage.cloud_db import get_cloud_db
from sqlalchemy import text

async def cleanup_dummy():
    db = get_cloud_db()
    async with db.engine.begin() as conn:
        res = await conn.execute(text("DELETE FROM game_accounts WHERE game_username LIKE 'Jogador_%';"))
        print(f"Removed dummy accounts: {res.rowcount}")

if __name__ == "__main__":
    asyncio.run(cleanup_dummy())
