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
    """Repositório de persistência SQLite em memória para compatibilidade com testes legados."""

    def __init__(self, db_path: Optional[Union[str, Path]] = None):
        if db_path is None:
            self.db_path = "file:twbot_memdb?mode=memory&cache=shared"
            import threading
            self._lock = threading.Lock()
            self._is_memory = True
            self._mem_conn = sqlite3.connect(self.db_path, uri=True, check_same_thread=False)
            self._mem_conn.row_factory = sqlite3.Row
        else:
            import threading
            self._lock = threading.Lock()
            self.db_path = str(db_path)
            self._is_memory = False
            if self.db_path != ":memory:" and not self.db_path.startswith("file:"):
                Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
            self._mem_conn = None

        self._init_db()

    @contextmanager
    def _get_connection(self):
        """Abre uma conexão com o SQLite com row_factory ativado e fecha-a de forma limpa."""
        if hasattr(self, "_mem_conn") and self._mem_conn:
            with self._lock:
                yield self._mem_conn
            return

        is_uri = "file:" in str(self.db_path)
        conn = sqlite3.connect(str(self.db_path), timeout=10.0, uri=is_uri, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            try:
                conn.close()
            except Exception as e:
                logger.debug(f"Aviso ao fechar conexão SQLite: {e}")

    def _init_db(self) -> None:
        """Cria as tabelas necessárias caso não existam e efetua a semeadura de dados padrão."""
        with self._get_connection() as conn:
            # 1. Tabela de Contas
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
                    build_order_strategy TEXT DEFAULT 'default_plan',
                    farm_presets TEXT DEFAULT '[]',
                    config_data TEXT DEFAULT '{}',
                    keep_alive INTEGER DEFAULT 1,
                    is_active INTEGER DEFAULT 0,
                    last_used REAL DEFAULT 0.0,
                    created_at REAL NOT NULL
                )
            """)

            # 2. Tabela de Modelos de Construção (Building Templates)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS building_templates (
                    id TEXT PRIMARY KEY,
                    account_id TEXT,
                    name TEXT NOT NULL,
                    target_levels TEXT DEFAULT '{}',
                    priority_list TEXT DEFAULT '[]',
                    is_default INTEGER DEFAULT 0,
                    created_at REAL NOT NULL
                )
            """)

            # 3. Tabela de Modelos de Recrutamento (Recruitment Models)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS recruitment_models (
                    id TEXT PRIMARY KEY,
                    account_id TEXT,
                    name TEXT NOT NULL,
                    units TEXT DEFAULT '{}',
                    batch_sizes TEXT DEFAULT '{}',
                    is_default INTEGER DEFAULT 0,
                    created_at REAL NOT NULL
                )
            """)

            # Migração de colunas caso a tabela accounts já existisse
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(accounts)")
            cols = [col[1] for col in cursor.fetchall()]
            if "username" not in cols:
                conn.execute("ALTER TABLE accounts ADD COLUMN username TEXT DEFAULT ''")
            if "password_enc" not in cols:
                conn.execute("ALTER TABLE accounts ADD COLUMN password_enc TEXT DEFAULT ''")
            if "keep_alive" not in cols:
                conn.execute("ALTER TABLE accounts ADD COLUMN keep_alive INTEGER DEFAULT 1")
            if "config_data" not in cols:
                conn.execute("ALTER TABLE accounts ADD COLUMN config_data TEXT DEFAULT '{}'")

            self._seed_default_templates(conn)
            conn.commit()

    def _seed_default_templates(self, conn: sqlite3.Connection) -> None:
        """Semeia os modelos padrão oficiais do sistema (Construção e Recrutamento) na base de dados SQLite."""
        cursor = conn.cursor()
        now = time.time()

        # 1. Limpeza de modelos legados de construção
        cursor.execute("DELETE FROM building_templates WHERE id IN ('rush_resources', 'balanced', 'military_rush')")

        # 2. Semeadura/Atualização do Modelo Padrão Oficial de Construção (config.json)
        from engine.actions.main_building import DEFAULT_BUILD_PLAN

        t_levels: Dict[str, int] = {}
        for b_name, b_lvl in DEFAULT_BUILD_PLAN:
            t_levels[b_name] = max(t_levels.get(b_name, 0), b_lvl)

        cursor.execute("SELECT id FROM building_templates WHERE id = 'default_plan'")
        if not cursor.fetchone():
            conn.execute("""
                INSERT INTO building_templates (
                    id, account_id, name, target_levels, priority_list, is_default, created_at
                ) VALUES ('default_plan', NULL, 'Plano Padrão de Construção', ?, ?, 1, ?)
            """, (
                json.dumps(t_levels),
                json.dumps(DEFAULT_BUILD_PLAN),
                now,
            ))
            logger.debug("Modelo padrão oficial de construção ('default_plan') assegurado na cache em memória.")
        else:
            conn.execute("""
                UPDATE building_templates
                SET account_id = NULL, name = 'Plano Padrão de Construção', target_levels = ?, priority_list = ?, is_default = 1
                WHERE id = 'default_plan'
            """, (
                json.dumps(t_levels),
                json.dumps(DEFAULT_BUILD_PLAN),
            ))

        # 3. Semeadura/Garantia dos Modelos Padrão de Tropas (Ataque Full e Defesa Full)
        from engine.config.settings import DEFAULT_ATTACK_MODEL, DEFAULT_DEFENSE_MODEL

        default_batch = {
            "spear": 10,
            "sword": 10,
            "axe": 10,
            "archer": 5,
            "spy": 5,
            "light": 5,
            "marcher": 5,
            "heavy": 5,
            "ram": 2,
            "catapult": 2,
            "knight": 1,
            "snob": 1,
        }

        defaults_rec = [
            {
                "id": "attack",
                "name": "Ataque Full",
                "units": DEFAULT_ATTACK_MODEL,
                "batch_sizes": default_batch,
                "is_default": 1,
            },
            {
                "id": "defense",
                "name": "Defesa Full",
                "units": DEFAULT_DEFENSE_MODEL,
                "batch_sizes": default_batch,
                "is_default": 1,
            },
        ]

        for rec in defaults_rec:
            cursor.execute("SELECT id FROM recruitment_models WHERE id = ?", (rec["id"],))
            if not cursor.fetchone():
                conn.execute("""
                    INSERT INTO recruitment_models (
                        id, account_id, name, units, batch_sizes, is_default, created_at
                    ) VALUES (?, NULL, ?, ?, ?, ?, ?)
                """, (
                    rec["id"],
                    rec["name"],
                    json.dumps(rec["units"]),
                    json.dumps(rec["batch_sizes"]),
                    rec["is_default"],
                    now,
                ))
            else:
                conn.execute("""
                    UPDATE recruitment_models
                    SET is_default = 1
                    WHERE id = ? AND is_default = 0
                """, (rec["id"],))

        logger.debug("Modelos padrão de tropas (Ataque e Defesa) assegurados na cache em memória para todas as contas.")

    # ==========================================
    # GESTÃO DE CONTAS (ACCOUNTS)
    # ==========================================

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
                    acc["farm_presets"] = json.loads(acc["farm_presets"]) if acc.get("farm_presets") else []
                except Exception:
                    acc["farm_presets"] = []
                try:
                    acc["config_data"] = json.loads(acc["config_data"]) if acc.get("config_data") else {}
                except Exception:
                    acc["config_data"] = {}
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
                acc["farm_presets"] = json.loads(acc["farm_presets"]) if acc.get("farm_presets") else []
            except Exception:
                acc["farm_presets"] = []
            try:
                acc["config_data"] = json.loads(acc["config_data"]) if acc.get("config_data") else {}
            except Exception:
                acc["config_data"] = {}
            acc["sid"] = acc["session_cookie"]
            return acc

    def get_account_config(self, account_id: str) -> Dict[str, Any]:
        """Obtém o dicionário de configurações do bot agregado à conta."""
        acc = self.get_account(account_id)
        if acc and isinstance(acc.get("config_data"), dict):
            return acc["config_data"]
        return {}

    def save_account_config(self, account_id: str, config_dict: Dict[str, Any]) -> bool:
        """Atualiza e persiste as configurações do bot agregadas a uma conta no SQLite."""
        if not account_id:
            return False
        current_cfg = self.get_account_config(account_id)
        merged_cfg = {**current_cfg, **config_dict}
        cfg_json = json.dumps(merged_cfg)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE accounts SET config_data = ? WHERE id = ?", (cfg_json, account_id))
            conn.commit()
            return cursor.rowcount > 0

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
        strategy = data.get("build_order_strategy") or data.get("template") or "default_plan"
        farm_presets = data.get("farm_presets") or []
        farm_presets_json = json.dumps(farm_presets) if isinstance(farm_presets, (list, dict)) else str(farm_presets)
        
        config_data = data.get("config_data") or {}
        config_data_json = json.dumps(config_data) if isinstance(config_data, dict) else str(config_data)
        
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
                    build_order_strategy, farm_presets, config_data, keep_alive,
                    is_active, last_used, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    config_data = CASE WHEN excluded.config_data != '{}' THEN excluded.config_data ELSE accounts.config_data END,
                    keep_alive = excluded.keep_alive,
                    is_active = excluded.is_active,
                    last_used = excluded.last_used
            """, (
                acc_id, name, world_domain, world, domain, sid,
                username, password_enc, village_id, proxy,
                strategy, farm_presets_json, config_data_json, keep_alive,
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
                acc["farm_presets"] = json.loads(acc["farm_presets"]) if acc.get("farm_presets") else []
            except Exception:
                acc["farm_presets"] = []
            try:
                acc["config_data"] = json.loads(acc["config_data"]) if acc.get("config_data") else {}
            except Exception:
                acc["config_data"] = {}
            acc["sid"] = acc["session_cookie"]
            return acc

    def migrate_from_sources(
        self,
        profiles_dir: Optional[Path] = None,
        initial_config: Optional[Any] = None,
    ) -> int:
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

        # 2. Se ainda assim estiver vazio e initial_config tiver dados explicitamente fornecidos
        if migrated_count == 0 and initial_config:
            cfg_dict = {}
            if hasattr(initial_config, "to_dict"):
                cfg_dict = initial_config.to_dict()
            elif isinstance(initial_config, dict):
                cfg_dict = initial_config

            cfg_sid = getattr(initial_config, "sid", "") if initial_config else cfg_dict.get("sid", "")
            cfg_world = getattr(initial_config, "world", "pt117") if initial_config else cfg_dict.get("world", "pt117")
            init_data = {
                "id": "default_main",
                "name": f"Conta {cfg_world.upper()}",
                "world_domain": f"{cfg_world}.tribalwars.com.pt",
                "session_cookie": cfg_sid or "",
                "is_active": 0,  # Inicialmente offline
                "build_order_strategy": cfg_dict.get("building", {}).get("template", "default_plan") if isinstance(cfg_dict.get("building"), dict) else "default_plan",
                "config_data": cfg_dict,
            }
            self.save_account(init_data)
            migrated_count += 1

        logger.info(f"Migração inicial concluída: {migrated_count} contas importadas para SQLite.")
        return migrated_count

    # ==========================================
    # GESTÃO DE MODELOS DE CONSTRUÇÃO (BUILDING_TEMPLATES)
    # ==========================================

    def list_building_templates(self, account_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Lista todos os modelos de construção.
        Se account_id for fornecido, retorna os globais (account_id IS NULL) + os da conta específica.
        Se account_id for 'all', retorna todos os registos sem filtro.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if account_id and account_id != "all":
                cursor.execute("""
                    SELECT * FROM building_templates
                    WHERE account_id IS NULL OR account_id = '' OR account_id = ?
                    ORDER BY is_default DESC, name ASC
                """, (account_id,))
            else:
                cursor.execute("""
                    SELECT * FROM building_templates
                    ORDER BY is_default DESC, name ASC
                """)
            rows = cursor.fetchall()
            templates = []
            for r in rows:
                tmpl = dict(r)
                tmpl["is_default"] = bool(tmpl.get("is_default", 0))
                try:
                    tmpl["target_levels"] = json.loads(tmpl["target_levels"]) if tmpl.get("target_levels") else {}
                except Exception:
                    tmpl["target_levels"] = {}
                try:
                    tmpl["priority_list"] = json.loads(tmpl["priority_list"]) if tmpl.get("priority_list") else []
                except Exception:
                    tmpl["priority_list"] = []
                templates.append(tmpl)
            return templates

    def get_building_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        """Obtém um modelo de construção específico pelo ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM building_templates WHERE id = ?", (template_id,))
            row = cursor.fetchone()
            if not row:
                return None
            tmpl = dict(row)
            tmpl["is_default"] = bool(tmpl.get("is_default", 0))
            try:
                tmpl["target_levels"] = json.loads(tmpl["target_levels"]) if tmpl.get("target_levels") else {}
            except Exception:
                tmpl["target_levels"] = {}
            try:
                tmpl["priority_list"] = json.loads(tmpl["priority_list"]) if tmpl.get("priority_list") else []
            except Exception:
                tmpl["priority_list"] = []
            return tmpl

    def save_building_template(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Cria ou atualiza um modelo de construção no SQLite."""
        tmpl_id = data.get("id") or str(uuid.uuid4())
        account_id = data.get("account_id") or None
        name = data.get("name") or "Novo Modelo de Construção"
        
        target_levels = data.get("target_levels", {})
        priority_list = data.get("priority_list", [])

        # Se target_levels não foi enviado, mas priority_list sim, calcula automaticamente
        if not target_levels and priority_list:
            target_levels = {}
            for item in priority_list:
                if isinstance(item, (list, tuple)) and len(item) == 2:
                    b_id, b_lvl = item[0], item[1]
                    target_levels[str(b_id)] = max(target_levels.get(str(b_id), 0), int(b_lvl))

        target_levels_json = json.dumps(target_levels) if isinstance(target_levels, dict) else str(target_levels)
        priority_list_json = json.dumps(priority_list) if isinstance(priority_list, list) else str(priority_list)
        is_default = 1 if data.get("is_default") else 0
        created_at = float(data.get("created_at") or time.time())

        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO building_templates (
                    id, account_id, name, target_levels, priority_list, is_default, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    account_id = excluded.account_id,
                    name = excluded.name,
                    target_levels = excluded.target_levels,
                    priority_list = excluded.priority_list,
                    is_default = excluded.is_default
            """, (
                tmpl_id, account_id, name, target_levels_json, priority_list_json, is_default, created_at
            ))
            conn.commit()

        logger.info(f"Modelo de construção '{name}' ({tmpl_id}) persistido no SQLite.")
        return self.get_building_template(tmpl_id)

    def delete_building_template(self, template_id: str) -> bool:
        """Remove um modelo de construção da base de dados (protegendo defaults do sistema)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM building_templates WHERE id = ? AND is_default = 0", (template_id,))
            conn.commit()
            return cursor.rowcount > 0

    def clone_building_template(
        self,
        template_id: str,
        new_name: Optional[str] = None,
        account_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Clona um modelo de construção existente para criar uma variante personalizada."""
        orig = self.get_building_template(template_id)
        if not orig:
            return None

        clone_id = f"{template_id}_copy_{uuid.uuid4().hex[:6]}"
        clone_data = {
            "id": clone_id,
            "account_id": account_id if account_id is not None else orig.get("account_id"),
            "name": new_name or f"{orig['name']} (Cópia)",
            "target_levels": orig["target_levels"],
            "priority_list": orig["priority_list"],
            "is_default": False,
            "created_at": time.time(),
        }
        return self.save_building_template(clone_data)

    # ==========================================
    # GESTÃO DE MODELOS DE RECRUTAMENTO (RECRUITMENT_MODELS)
    # ==========================================

    def list_recruitment_models(self, account_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Lista todos os modelos de tropas de recrutamento.
        Se account_id for fornecido, retorna os globais (account_id IS NULL) + os da conta específica.
        Se account_id for 'all', retorna todos os registos.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if account_id and account_id != "all":
                cursor.execute("""
                    SELECT * FROM recruitment_models
                    WHERE account_id IS NULL OR account_id = '' OR account_id = ?
                    ORDER BY is_default DESC, name ASC
                """, (account_id,))
            else:
                cursor.execute("""
                    SELECT * FROM recruitment_models
                    ORDER BY is_default DESC, name ASC
                """)
            rows = cursor.fetchall()
            models = []
            for r in rows:
                m = dict(r)
                m["is_default"] = bool(m.get("is_default", 0))
                try:
                    m["units"] = json.loads(m["units"]) if m.get("units") else {}
                except Exception:
                    m["units"] = {}
                try:
                    m["batch_sizes"] = json.loads(m["batch_sizes"]) if m.get("batch_sizes") else {}
                except Exception:
                    m["batch_sizes"] = {}
                # Se for attack ou defense, garante que os campos padrão não ficam vazios
                if m.get("id") == "attack":
                    from engine.config.settings import DEFAULT_ATTACK_MODEL
                    full_units = DEFAULT_ATTACK_MODEL.copy()
                    full_units.update(m["units"])
                    m["units"] = full_units
                elif m.get("id") == "defense":
                    from engine.config.settings import DEFAULT_DEFENSE_MODEL
                    full_units = DEFAULT_DEFENSE_MODEL.copy()
                    full_units.update(m["units"])
                    m["units"] = full_units
                models.append(m)
            return models

    def get_recruitment_model(self, model_id: str) -> Optional[Dict[str, Any]]:
        """Obtém um modelo de recrutamento específico pelo ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM recruitment_models WHERE id = ?", (model_id,))
            row = cursor.fetchone()
            if not row:
                return None
            m = dict(row)
            m["is_default"] = bool(m.get("is_default", 0))
            try:
                m["units"] = json.loads(m["units"]) if m.get("units") else {}
            except Exception:
                m["units"] = {}
            try:
                m["batch_sizes"] = json.loads(m["batch_sizes"]) if m.get("batch_sizes") else {}
            except Exception:
                m["batch_sizes"] = {}

            if m.get("id") == "attack":
                from engine.config.settings import DEFAULT_ATTACK_MODEL
                full_units = DEFAULT_ATTACK_MODEL.copy()
                full_units.update(m["units"])
                m["units"] = full_units
            elif m.get("id") == "defense":
                from engine.config.settings import DEFAULT_DEFENSE_MODEL
                full_units = DEFAULT_DEFENSE_MODEL.copy()
                full_units.update(m["units"])
                m["units"] = full_units
            return m

    def save_recruitment_model(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Cria ou atualiza um modelo de recrutamento de tropas no SQLite."""
        m_id = data.get("id") or str(uuid.uuid4())
        account_id = data.get("account_id") or None
        name = data.get("name") or "Novo Modelo de Tropas"
        
        units = data.get("units", {})
        batch_sizes = data.get("batch_sizes", {})

        units_json = json.dumps(units) if isinstance(units, dict) else str(units)
        batch_sizes_json = json.dumps(batch_sizes) if isinstance(batch_sizes, dict) else str(batch_sizes)
        is_default = 1 if data.get("is_default") else 0
        created_at = float(data.get("created_at") or time.time())

        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO recruitment_models (
                    id, account_id, name, units, batch_sizes, is_default, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    account_id = excluded.account_id,
                    name = excluded.name,
                    units = excluded.units,
                    batch_sizes = excluded.batch_sizes,
                    is_default = excluded.is_default
            """, (
                m_id, account_id, name, units_json, batch_sizes_json, is_default, created_at
            ))
            conn.commit()

        logger.info(f"Modelo de recrutamento '{name}' ({m_id}) persistido no SQLite.")
        return self.get_recruitment_model(m_id)

    def delete_recruitment_model(self, model_id: str) -> bool:
        """Remove um modelo de recrutamento da base de dados (protegendo defaults do sistema)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM recruitment_models WHERE id = ? AND is_default = 0", (model_id,))
            conn.commit()
            return cursor.rowcount > 0

    def clone_recruitment_model(
        self,
        model_id: str,
        new_name: Optional[str] = None,
        account_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Clona um modelo de recrutamento para criar uma variação personalizada."""
        orig = self.get_recruitment_model(model_id)
        if not orig:
            return None

        clone_id = f"{model_id}_copy_{uuid.uuid4().hex[:6]}"
        clone_data = {
            "id": clone_id,
            "account_id": account_id if account_id is not None else orig.get("account_id"),
            "name": new_name or f"{orig['name']} (Cópia)",
            "units": orig["units"],
            "batch_sizes": orig["batch_sizes"],
            "is_default": False,
            "created_at": time.time(),
        }
        return self.save_recruitment_model(clone_data)
