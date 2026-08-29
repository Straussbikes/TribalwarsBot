from contextlib import contextmanager
from datetime import datetime
import json
import logging
from pathlib import Path
import sqlite3
import time
from typing import Any, Dict, List, Optional
import uuid

logger = logging.getLogger("TribalWarsBot.Database")


class AccountsDatabase:
    """Repositório de persistência SQLite para gestão de contas do Tribal Wars."""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            data_dir = Path(__file__).resolve().parent.parent.parent / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = data_dir / "accounts.db"
        else:
            self.db_path = Path(db_path)
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_db()

    @contextmanager
    def _get_connection(self):
        """Abre uma conexão com o SQLite com row_factory ativado e fecha-a de forma limpa."""
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def _init_db(self) -> None:
        """Cria as tabelas necessárias caso não existam."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS accounts (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    world_domain TEXT NOT NULL,
                    world TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    session_cookie TEXT DEFAULT '',
                    village_id INTEGER,
                    username TEXT DEFAULT '',
                    password_enc TEXT DEFAULT '',
                    proxy TEXT,
                    build_order_strategy TEXT DEFAULT 'rush_resources',
                    farm_presets TEXT DEFAULT '[]',
                    keep_alive INTEGER DEFAULT 1,
                    is_active INTEGER DEFAULT 0,
                    last_used REAL DEFAULT 0.0,
                    created_at REAL NOT NULL
                )
            """)
            # Migração de colunas caso a tabela já existisse
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(accounts)")
            cols = [col[1] for col in cursor.fetchall()]
            if "username" not in cols:
                conn.execute("ALTER TABLE accounts ADD COLUMN username TEXT DEFAULT ''")
            if "password_enc" not in cols:
                conn.execute("ALTER TABLE accounts ADD COLUMN password_enc TEXT DEFAULT ''")
            if "keep_alive" not in cols:
                conn.execute("ALTER TABLE accounts ADD COLUMN keep_alive INTEGER DEFAULT 1")
            conn.commit()

    def list_accounts(self) -> List[Dict[str, Any]]:
        """Lista todas as contas guardadas na base de dados."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM accounts ORDER BY last_used DESC, created_at DESC")
            rows = cursor.fetchall()
            accounts = []
            for r in rows:
                acc = dict(r)
                acc["is_active"] = bool(acc.get("is_active", 0))
                acc["keep_alive"] = bool(acc.get("keep_alive", 1))
                try:
                    acc["farm_presets"] = json.loads(acc["farm_presets"]) if acc["farm_presets"] else []
                except Exception:
                    acc["farm_presets"] = []
                acc["sid"] = acc["session_cookie"]
                accounts.append(acc)
            return accounts

    def get_account(self, account_id: str) -> Optional[Dict[str, Any]]:
        """Obtém uma conta específica pelo ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM accounts WHERE id = ?", (account_id,))
            row = cursor.fetchone()
            if not row:
                return None
            acc = dict(row)
            acc["is_active"] = bool(acc.get("is_active", 0))
            acc["keep_alive"] = bool(acc.get("keep_alive", 1))
            try:
                acc["farm_presets"] = json.loads(acc["farm_presets"]) if acc["farm_presets"] else []
            except Exception:
                acc["farm_presets"] = []
            acc["sid"] = acc["session_cookie"]
            return acc

    def save_account(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Cria ou atualiza um perfil de conta na base de dados."""
        acc_id = data.get("id") or str(uuid.uuid4())
        name = data.get("name") or "Nova Conta"
        world_domain = data.get("world_domain") or data.get("world") or "pt117.tribalwars.com.pt"
        
        # Extrai mundo e domínio
        if "." in world_domain:
            parts = world_domain.split(".", 1)
            world = parts[0].strip().lower()
            domain = parts[1].strip().lower()
        else:
            world = world_domain.strip().lower()
            domain = data.get("domain") or "tribalwars.com.pt"

        sid = data.get("session_cookie") or data.get("sid") or ""
        username = data.get("username") or ""
        password_enc = data.get("password_enc") or ""
        village_id = data.get("village_id")
        if village_id is not None:
            try:
                village_id = int(village_id)
            except (ValueError, TypeError):
                village_id = None

        proxy = data.get("proxy") or None
        strategy = data.get("build_order_strategy") or data.get("template") or "rush_resources"
        farm_presets = data.get("farm_presets") or []
        farm_presets_json = json.dumps(farm_presets) if isinstance(farm_presets, (list, dict)) else str(farm_presets)
        keep_alive = 1 if data.get("keep_alive", True) else 0
        is_active = 1 if data.get("is_active") else 0

        raw_last = data.get("last_used")
        if isinstance(raw_last, (int, float)):
            last_used = float(raw_last)
        elif isinstance(raw_last, str) and raw_last.strip():
            try:
                last_used = datetime.fromisoformat(raw_last).timestamp()
            except Exception:
                try:
                    last_used = float(raw_last)
                except Exception:
                    last_used = 0.0
        else:
            last_used = 0.0

        raw_created = data.get("created_at")
        if isinstance(raw_created, (int, float)):
            created_at = float(raw_created)
        elif isinstance(raw_created, str) and raw_created.strip():
            try:
                created_at = datetime.fromisoformat(raw_created).timestamp()
            except Exception:
                try:
                    created_at = float(raw_created)
                except Exception:
                    created_at = time.time()
        else:
            created_at = time.time()

        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO accounts (
                    id, name, world_domain, world, domain, session_cookie,
                    username, password_enc, village_id, proxy,
                    build_order_strategy, farm_presets, keep_alive,
                    is_active, last_used, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    world_domain = excluded.world_domain,
                    world = excluded.world,
                    domain = excluded.domain,
                    session_cookie = excluded.session_cookie,
                    username = excluded.username,
                    password_enc = excluded.password_enc,
                    village_id = excluded.village_id,
                    proxy = excluded.proxy,
                    build_order_strategy = excluded.build_order_strategy,
                    farm_presets = excluded.farm_presets,
                    keep_alive = excluded.keep_alive,
                    is_active = excluded.is_active,
                    last_used = excluded.last_used
            """, (
                acc_id, name, world_domain, world, domain, sid,
                username, password_enc, village_id, proxy,
                strategy, farm_presets_json, keep_alive,
                is_active, last_used, created_at
            ))
            conn.commit()

        logger.info(f"Conta '{name}' ({acc_id}) guardada na base de dados SQLite.")
        return self.get_account(acc_id)

    def delete_account(self, account_id: str) -> bool:
        """Remove uma conta da base de dados."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
            conn.commit()
            return cursor.rowcount > 0

    def set_active_account(self, account_id: str) -> Optional[Dict[str, Any]]:
        """Garante bloqueio monousuário: ativa 1 conta e desativa todas as restantes."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Desativa todas
            cursor.execute("UPDATE accounts SET is_active = 0")
            # Ativa a selecionada
            now = time.time()
            cursor.execute("UPDATE accounts SET is_active = 1, last_used = ? WHERE id = ?", (now, account_id))
            conn.commit()

        return self.get_account(account_id)

    def deactivate_all_accounts(self) -> None:
        """Coloca todas as contas em estado Offline (usado no arranque e logout)."""
        with self._get_connection() as conn:
            conn.execute("UPDATE accounts SET is_active = 0")
            conn.commit()
        logger.info("Todas as contas foram colocadas em estado Offline na base de dados.")

    def get_active_account(self) -> Optional[Dict[str, Any]]:
        """Retorna a conta atualmente ativa, se existir."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM accounts WHERE is_active = 1 LIMIT 1")
            row = cursor.fetchone()
            if not row:
                return None
            acc = dict(row)
            acc["is_active"] = True
            try:
                acc["farm_presets"] = json.loads(acc["farm_presets"]) if acc["farm_presets"] else []
            except Exception:
                acc["farm_presets"] = []
            acc["sid"] = acc["session_cookie"]
            return acc

    def migrate_from_sources(self, profiles_dir: Optional[Path] = None, initial_config: Optional[Any] = None) -> int:
        """Migra perfis JSON legados ou definições do config.json se a base de dados estiver vazia."""
        accounts = self.list_accounts()
        if len(accounts) > 0:
            return 0  # Já existem contas na base de dados

        migrated_count = 0

        # 1. Migra ficheiros em profiles/*.json
        if profiles_dir and Path(profiles_dir).exists():
            for p_file in Path(profiles_dir).glob("*.json"):
                try:
                    with open(p_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, dict) and (data.get("name") or data.get("world_domain")):
                        data["id"] = data.get("id") or p_file.stem
                        data["is_active"] = 0  # Inicialmente offline
                        self.save_account(data)
                        migrated_count += 1
                except Exception as e:
                    logger.warning(f"Erro ao migrar perfil JSON '{p_file}': {e}")

        # 2. Se ainda assim estiver vazio e o config tiver dados
        if migrated_count == 0 and initial_config and getattr(initial_config, "world", None):
            cfg_sid = getattr(initial_config, "sid", "") or ""
            cfg_world = getattr(initial_config, "world", "pt117")
            init_data = {
                "id": "default_main",
                "name": f"Conta {cfg_world.upper()}",
                "world_domain": f"{cfg_world}.tribalwars.com.pt",
                "session_cookie": cfg_sid,
                "is_active": 0,  # Inicialmente offline
                "build_order_strategy": getattr(getattr(initial_config, "building", None), "template", "rush_resources"),
            }
            self.save_account(init_data)
            migrated_count += 1

        logger.info(f"Migração inicial concluída: {migrated_count} contas importadas para SQLite.")
        return migrated_count
