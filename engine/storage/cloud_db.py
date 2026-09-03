"""
TribalWarsBot - Cloud SQL (PostgreSQL) Data Layer
Camada de persistência relacional assíncrona, gestão de utilizadores da aplicação,
hierarquia GameAccount -> GameWorld -> Village e cofre criptográfico AES-256-GCM.
"""

from __future__ import annotations

import asyncio
import base64
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import ssl
from typing import Any, AsyncGenerator, Dict, List, Optional
import uuid

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    LargeBinary,
    String,
    UniqueConstraint,
    select,
    update,
    delete,
    text,
)
from engine.config.templates import DEFAULT_BUILD_TEMPLATES, DEFAULT_BUILD_TEMPLATE_IDS
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, relationship

logger = logging.getLogger("TribalWarsBot.CloudDB")

# URL de Conexão Padrão (Cloud SQL PostgreSQL / Neon)
DEFAULT_POSTGRES_URL = (
    "postgresql://neondb_owner:npg_2xBFH8GqKVby@ep-lingering-wind-b1c8raew-pooler.c-5.eu-central-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
)


# ==============================================================================
# 1. Hashing Seguro de Passwords (Argon2 com fallback Bcrypt)
# ==============================================================================
def hash_password(password: str) -> str:
    """Gera hash seguro da password usando Argon2 ou bcrypt."""
    try:
        from argon2 import PasswordHasher
        ph = PasswordHasher()
        return ph.hash(password)
    except ImportError:
        import bcrypt
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Verifica se a password corresponde ao hash armazenado."""
    if not password or not password_hash:
        return False
    try:
        if password_hash.startswith("$argon2"):
            from argon2 import PasswordHasher
            from argon2.exceptions import VerifyMismatchError
            ph = PasswordHasher()
            try:
                return ph.verify(password_hash, password)
            except VerifyMismatchError:
                return False
        else:
            import bcrypt
            return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception as e:
        logger.warning(f"Erro na verificação de password: {e}")
        return False


# ==============================================================================
# 2. Cofre Criptográfico AES-256-GCM (CredentialsVault)
# ==============================================================================
class CredentialsVault:
    """
    Cofre para encriptação/desencriptação de credenciais e tokens de sessão (SID)
    utilizando cifra simétrica autenticada AES-256-GCM.
    """

    def __init__(self, key: Optional[bytes] = None):
        if key:
            self._key = key
        else:
            env_key = os.environ.get("APP_VAULT_KEY")
            if env_key:
                try:
                    self._key = base64.b64decode(env_key)
                except Exception:
                    self._key = env_key.encode("utf-8")[:32].ljust(32, b"0")
            else:
                # Ficheiro local de chave de máquina
                key_file = Path("data/.vault_key")
                if key_file.exists():
                    try:
                        self._key = base64.b64decode(key_file.read_text().strip())
                    except Exception:
                        self._key = AESGCM.generate_key(bit_length=256)
                        key_file.parent.mkdir(parents=True, exist_ok=True)
                        key_file.write_text(base64.b64encode(self._key).decode("utf-8"))
                else:
                    self._key = AESGCM.generate_key(bit_length=256)
                    key_file.parent.mkdir(parents=True, exist_ok=True)
                    key_file.write_text(base64.b64encode(self._key).decode("utf-8"))

        if len(self._key) != 32:
            self._key = self._key[:32].ljust(32, b"0")

        self._aesgcm = AESGCM(self._key)

    @property
    def key_b64(self) -> str:
        return base64.b64encode(self._key).decode("utf-8")

    def encrypt(self, data: Dict[str, Any]) -> bytes:
        """Serializa o dicionário em JSON e encripta com AES-256-GCM (retorna nonce + ciphertext)."""
        nonce = os.urandom(12)
        plaintext = json.dumps(data).encode("utf-8")
        ciphertext = self._aesgcm.encrypt(nonce, plaintext, None)
        return nonce + ciphertext

    def decrypt(self, vault_bytes: bytes) -> Dict[str, Any]:
        """Desencripta o buffer com AES-256-GCM e retorna o dicionário decifrado."""
        if not vault_bytes or len(vault_bytes) < 28:
            return {}
        nonce = vault_bytes[:12]
        ciphertext = vault_bytes[12:]
        try:
            plaintext = self._aesgcm.decrypt(nonce, ciphertext, None)
            return json.loads(plaintext.decode("utf-8"))
        except Exception as e:
            logger.error(f"Falha ao desencriptar cofre com AES-256-GCM: {e}")
            raise ValueError("Não foi possível desencriptar as credenciais do cofre.") from e


# ==============================================================================
# 3. Modelos Declarativos SQLAlchemy
# ==============================================================================
class Base(DeclarativeBase):
    pass


class AppUser(Base):
    """Utilizador da aplicação (autenticação desktop / cloud)."""
    __tablename__ = "app_users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    license_type = Column(String(50), nullable=False, default="standard")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relações
    game_accounts = relationship("GameAccount", back_populates="app_user", cascade="all, delete-orphan")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "email": self.email,
            "license_type": self.license_type,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class GameAccount(Base):
    """Conta de jogador no Tribal Wars vinculada ao AppUser."""
    __tablename__ = "game_accounts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    app_user_id = Column(String(36), ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False, index=True)
    game_username = Column(String(100), nullable=False, index=True)
    credentials_vault = Column(LargeBinary, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("app_user_id", "game_username", name="uq_user_game_username"),
    )

    # Relações
    app_user = relationship("AppUser", back_populates="game_accounts")
    game_worlds = relationship("GameWorld", back_populates="game_account", cascade="all, delete-orphan")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "app_user_id": self.app_user_id,
            "game_username": self.game_username,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class GameWorld(Base):
    """Mundo de jogo associado a uma GameAccount."""
    __tablename__ = "game_worlds"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    game_account_id = Column(String(36), ForeignKey("game_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    world_code = Column(String(20), nullable=False, index=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("game_account_id", "world_code", name="uq_account_world"),
    )

    # Relações
    game_account = relationship("GameAccount", back_populates="game_worlds")
    villages = relationship("Village", back_populates="game_world", cascade="all, delete-orphan")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "game_account_id": self.game_account_id,
            "world_code": self.world_code,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Village(Base):
    """Aldeia individual sob gestão num mundo específico."""
    __tablename__ = "villages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    game_world_id = Column(String(36), ForeignKey("game_worlds.id", ondelete="CASCADE"), nullable=False, index=True)
    village_game_id = Column(Integer, nullable=False, index=True)
    village_name = Column(String(100), nullable=False)
    coord_x = Column(Integer, nullable=False)
    coord_y = Column(Integer, nullable=False)
    active_build_model_id = Column(String(100), nullable=True)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("game_world_id", "village_game_id", name="uq_world_village_game_id"),
    )

    # Relações
    game_world = relationship("GameWorld", back_populates="villages")

    @property
    def coordinates(self) -> str:
        return f"{self.coord_x}|{self.coord_y}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "game_world_id": self.game_world_id,
            "village_game_id": self.village_game_id,
            "village_name": self.village_name,
            "coord_x": self.coord_x,
            "coord_y": self.coord_y,
            "coordinates": f"{self.coord_x}|{self.coord_y}",
            "active_build_model_id": self.active_build_model_id,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class BuildTemplate(Base):
    """Modelo padrão ou customizado de construção em Cloud SQL."""
    __tablename__ = "build_templates"

    id = Column(String(50), primary_key=True)
    name = Column(String(100), nullable=False)
    target_levels = Column(JSON, nullable=False)
    priority_list = Column(JSON, nullable=False)
    is_default = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "target_levels": self.target_levels,
            "priority_list": self.priority_list,
            "is_default": self.is_default,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ==============================================================================
# 4. Gestão de Conexão com Cloud SQL e Motor Assíncrono
# ==============================================================================
class CloudDatabase:
    """Gestor de conexão assíncrona com Cloud SQL (PostgreSQL) com suporte a pool e SSL."""

    def __init__(self, database_url: Optional[str] = None):
        raw_url = database_url or os.environ.get("DATABASE_URL") or DEFAULT_POSTGRES_URL
        self.raw_url = raw_url
        self.engine: AsyncEngine = self._build_engine(raw_url)
        self.session_factory = async_sessionmaker(bind=self.engine, expire_on_commit=False, class_=AsyncSession)
        self.vault = CredentialsVault()
        self.build_template_repo = BuildTemplateRepository(self)

    def _build_engine(self, raw_url: str) -> AsyncEngine:
        url = raw_url.strip()
        connect_args: Dict[str, Any] = {}

        if url.startswith("postgresql://") or url.startswith("postgres://"):
            # Converte para postgresql+asyncpg
            clean_url = url.replace("postgres://", "postgresql://", 1)
            # Remove parâmetros de query do URL para passar via connect_args / ssl
            base_part = clean_url.split("?")[0]
            async_url = base_part.replace("postgresql://", "postgresql+asyncpg://", 1)
            
            # Configuração SSL para Cloud SQL / Neon
            ssl_ctx = ssl.create_default_context()
            connect_args["ssl"] = ssl_ctx
            connect_args["server_settings"] = {"application_name": "TribalWarsBot"}
            return create_async_engine(
                async_url,
                connect_args=connect_args,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True,
                echo=False,
            )
        elif "sqlite" in url:
            from sqlalchemy.pool import StaticPool
            return create_async_engine(
                url,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
                echo=False,
            )
        else:
            return create_async_engine(url, pool_pre_ping=True, echo=False)

    async def init_db(self, drop_all: bool = False) -> None:
        """Cria as tabelas declarativas na base de dados Cloud SQL se não existirem."""
        async with self.engine.begin() as conn:
            if drop_all:
                await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        await self.build_template_repo.seed_defaults_if_needed()
        logger.info("[CloudDB] Tabelas verificadas/criadas com sucesso no PostgreSQL.")

    init_models = init_db

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Context manager assíncrono que fornece uma sessão e fecha-a ao terminar."""
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        if hasattr(self, "_bound_loop") and self._bound_loop is not None and self._bound_loop.is_closed():
            self.engine = self._build_engine(self.raw_url)
            self.session_factory = async_sessionmaker(bind=self.engine, expire_on_commit=False, class_=AsyncSession)
            self._bound_loop = current_loop
            if "sqlite" in self.raw_url:
                async with self.engine.begin() as conn:
                    await conn.run_sync(Base.metadata.create_all)
        elif current_loop is not None and not getattr(self, "_bound_loop", None):
            self._bound_loop = current_loop

        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def close(self) -> None:
        """Fecha o pool de conexões do motor assíncrono."""
        await self.engine.dispose()


# Instância global padrão do CloudDatabase
_global_cloud_db: Optional[CloudDatabase] = None


def get_cloud_db(database_url: Optional[str] = None) -> CloudDatabase:
    global _global_cloud_db
    if _global_cloud_db is None or (database_url and _global_cloud_db.raw_url != database_url):
        _global_cloud_db = CloudDatabase(database_url=database_url)
    return _global_cloud_db


# ==============================================================================
# 5. Repositórios CRUD para a Hierarquia
# ==============================================================================
class AppUserRepository:
    def __init__(self, db: CloudDatabase):
        self.db = db

    async def create_user(self, email: str, password: str, license_type: str = "standard") -> AppUser:
        pwd_hash = hash_password(password)
        async with self.db.get_session() as session:
            user = AppUser(email=email.strip().lower(), password_hash=pwd_hash, license_type=license_type)
            session.add(user)
            await session.flush()
            await session.refresh(user)
            return user

    async def get_by_email(self, email: str) -> Optional[AppUser]:
        async with self.db.get_session() as session:
            res = await session.execute(select(AppUser).where(AppUser.email == email.strip().lower()))
            return res.scalar_one_or_none()

    async def get_by_id(self, user_id: str) -> Optional[AppUser]:
        async with self.db.get_session() as session:
            res = await session.execute(select(AppUser).where(AppUser.id == user_id))
            return res.scalar_one_or_none()

    async def authenticate(self, email: str, password: str) -> Optional[AppUser]:
        user = await self.get_by_email(email)
        if not user:
            return None
        if verify_password(password, user.password_hash):
            return user
        return None


class GameAccountRepository:
    def __init__(self, db: CloudDatabase):
        self.db = db
        self.vault = db.vault

    async def create_or_update(
        self,
        app_user_id: str,
        game_username: str,
        credentials_data: Dict[str, Any],
    ) -> GameAccount:
        vault_bytes = self.vault.encrypt(credentials_data)
        username = game_username.strip()
        async with self.db.get_session() as session:
            res = await session.execute(
                select(GameAccount).where(
                    GameAccount.app_user_id == app_user_id,
                    GameAccount.game_username == username,
                )
            )
            existing = res.scalar_one_or_none()
            if existing:
                existing.credentials_vault = vault_bytes
                await session.flush()
                await session.refresh(existing)
                return existing
            else:
                acc = GameAccount(
                    app_user_id=app_user_id,
                    game_username=username,
                    credentials_vault=vault_bytes,
                )
                session.add(acc)
                await session.flush()
                await session.refresh(acc)
                return acc

    async def get_by_user_and_username(self, app_user_id: str, game_username: str) -> Optional[GameAccount]:
        async with self.db.get_session() as session:
            res = await session.execute(
                select(GameAccount).where(
                    GameAccount.app_user_id == app_user_id,
                    GameAccount.game_username == game_username.strip(),
                )
            )
            return res.scalar_one_or_none()

    async def get_by_id(self, account_id: str) -> Optional[GameAccount]:
        async with self.db.get_session() as session:
            res = await session.execute(select(GameAccount).where(GameAccount.id == account_id))
            return res.scalar_one_or_none()

    async def list_by_user(self, app_user_id: str) -> List[GameAccount]:
        async with self.db.get_session() as session:
            res = await session.execute(
                select(GameAccount).where(GameAccount.app_user_id == app_user_id).order_by(GameAccount.created_at.desc())
            )
            return list(res.scalars().all())

    async def delete_account(self, account_id: str) -> bool:
        async with self.db.get_session() as session:
            res = await session.execute(delete(GameAccount).where(GameAccount.id == account_id))
            return res.rowcount > 0

    def decrypt_credentials(self, account: GameAccount) -> Dict[str, Any]:
        """Desencripta o cofre da conta retornando o dicionário original."""
        return self.vault.decrypt(account.credentials_vault)


class GameWorldRepository:
    def __init__(self, db: CloudDatabase):
        self.db = db

    async def get_or_create(self, game_account_id: str, world_code: str, is_active: bool = True) -> GameWorld:
        w_code = world_code.strip().lower()
        async with self.db.get_session() as session:
            res = await session.execute(
                select(GameWorld).where(
                    GameWorld.game_account_id == game_account_id,
                    GameWorld.world_code == w_code,
                )
            )
            existing = res.scalar_one_or_none()
            if existing:
                return existing
            gw = GameWorld(game_account_id=game_account_id, world_code=w_code, is_active=is_active)
            session.add(gw)
            await session.flush()
            await session.refresh(gw)
            return gw

    async def list_by_account(self, game_account_id: str) -> List[GameWorld]:
        async with self.db.get_session() as session:
            res = await session.execute(
                select(GameWorld).where(GameWorld.game_account_id == game_account_id).order_by(GameWorld.world_code.asc())
            )
            return list(res.scalars().all())

    async def toggle_active(self, game_account_id: str, world_code: str, is_active: bool) -> Optional[GameWorld]:
        w_code = world_code.strip().lower()
        async with self.db.get_session() as session:
            res = await session.execute(
                select(GameWorld).where(
                    GameWorld.game_account_id == game_account_id,
                    GameWorld.world_code == w_code,
                )
            )
            gw = res.scalar_one_or_none()
            if gw:
                gw.is_active = is_active
                await session.flush()
                await session.refresh(gw)
            return gw


class VillageRepository:
    def __init__(self, db: CloudDatabase):
        self.db = db

    async def upsert_village(
        self,
        game_world_id: str,
        village_game_id: int,
        village_name: str,
        coord_x: int,
        coord_y: int,
        active_build_model_id: Optional[str] = None,
    ) -> Village:
        async with self.db.get_session() as session:
            res = await session.execute(
                select(Village).where(
                    Village.game_world_id == game_world_id,
                    Village.village_game_id == village_game_id,
                )
            )
            v = res.scalar_one_or_none()
            if v:
                v.village_name = village_name
                v.coord_x = coord_x
                v.coord_y = coord_y
                if active_build_model_id is not None:
                    v.active_build_model_id = active_build_model_id
                v.updated_at = datetime.now(timezone.utc)
                await session.flush()
                await session.refresh(v)
                return v
            else:
                new_v = Village(
                    game_world_id=game_world_id,
                    village_game_id=village_game_id,
                    village_name=village_name,
                    coord_x=coord_x,
                    coord_y=coord_y,
                    active_build_model_id=active_build_model_id or "default_plan",
                )
                session.add(new_v)
                await session.flush()
                await session.refresh(new_v)
                return new_v

    async def list_by_world(self, game_world_id: str) -> List[Village]:
        async with self.db.get_session() as session:
            res = await session.execute(
                select(Village).where(Village.game_world_id == game_world_id).order_by(Village.village_name.asc())
            )
            return list(res.scalars().all())

    async def update_build_model(self, village_id: str, active_build_model_id: str) -> Optional[Village]:
        async with self.db.get_session() as session:
            res = await session.execute(select(Village).where(Village.id == village_id))
            v = res.scalar_one_or_none()
            if v:
                v.active_build_model_id = active_build_model_id
                v.updated_at = datetime.now(timezone.utc)
                await session.flush()
                await session.refresh(v)
            return v


class BuildTemplateRepository:
    """Repositório assíncrono para modelos de construção oficiais e customizados em Cloud SQL."""

    def __init__(self, db: CloudDatabase):
        self.db = db

    async def seed_defaults_if_needed(self) -> None:
        """Assegura a existência dos 5 modelos oficiais de construção no Cloud SQL."""
        async with self.db.get_session() as session:
            for tpl in DEFAULT_BUILD_TEMPLATES:
                res = await session.execute(select(BuildTemplate).where(BuildTemplate.id == tpl["id"]))
                existing = res.scalar_one_or_none()
                if not existing:
                    new_t = BuildTemplate(
                        id=tpl["id"],
                        name=tpl["name"],
                        target_levels=tpl["target_levels"],
                        priority_list=tpl["priority_list"],
                        is_default=True,
                    )
                    session.add(new_t)
                else:
                    existing.name = tpl["name"]
                    existing.target_levels = tpl["target_levels"]
                    existing.priority_list = tpl["priority_list"]
                    existing.is_default = True
            await session.flush()

    async def list_all(self) -> List[BuildTemplate]:
        """Lista todos os modelos de construção salvos ou retorna constantes imutáveis."""
        async with self.db.get_session() as session:
            res = await session.execute(select(BuildTemplate).order_by(BuildTemplate.created_at.asc()))
            templates = list(res.scalars().all())
            if not templates:
                return [
                    BuildTemplate(
                        id=t["id"],
                        name=t["name"],
                        target_levels=t["target_levels"],
                        priority_list=t["priority_list"],
                        is_default=t.get("is_default", True),
                    )
                    for t in DEFAULT_BUILD_TEMPLATES
                ]
            return templates

    async def get_by_id(self, template_id: str) -> Optional[BuildTemplate]:
        async with self.db.get_session() as session:
            res = await session.execute(select(BuildTemplate).where(BuildTemplate.id == template_id))
            tpl = res.scalar_one_or_none()
            if not tpl:
                for mem_t in DEFAULT_BUILD_TEMPLATES:
                    if mem_t["id"] == template_id:
                        return BuildTemplate(
                            id=mem_t["id"],
                            name=mem_t["name"],
                            target_levels=mem_t["target_levels"],
                            priority_list=mem_t["priority_list"],
                            is_default=mem_t.get("is_default", True),
                        )
            return tpl

    async def save(self, data: Dict[str, Any]) -> BuildTemplate:
        async with self.db.get_session() as session:
            t_id = data.get("id") or f"custom_{uuid.uuid4().hex[:8]}"
            res = await session.execute(select(BuildTemplate).where(BuildTemplate.id == t_id))
            existing = res.scalar_one_or_none()
            if existing:
                existing.name = data.get("name", existing.name)
                existing.target_levels = data.get("target_levels", existing.target_levels)
                existing.priority_list = data.get("priority_list", existing.priority_list)
                await session.flush()
                await session.refresh(existing)
                return existing
            else:
                new_t = BuildTemplate(
                    id=t_id,
                    name=data.get("name", "Modelo Customizado"),
                    target_levels=data.get("target_levels", {}),
                    priority_list=data.get("priority_list", []),
                    is_default=False,
                )
                session.add(new_t)
                await session.flush()
                await session.refresh(new_t)
                return new_t

    async def delete(self, template_id: str) -> bool:
        if template_id in DEFAULT_BUILD_TEMPLATE_IDS:
            raise ValueError("Não é permitido eliminar modelos oficiais padrão do sistema.")
        async with self.db.get_session() as session:
            res = await session.execute(select(BuildTemplate).where(BuildTemplate.id == template_id))
            existing = res.scalar_one_or_none()
            if existing:
                await session.delete(existing)
                return True
            return False
