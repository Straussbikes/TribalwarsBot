"""
Tribal Wars Mobile Automation Engine - Core
"""

from engine.core.exceptions import (
    ActionFailedError,
    BotProtectionError,
    GameMaintenanceError,
    NetworkTimeoutError,
    RateLimitError,
    SessionExpiredError,
    TribalWarsException,
)
from engine.core.models import (
    PlayerData,
    Resources,
    Task,
    TaskPriority,
    VillageData,
)
def __getattr__(name: str):
    if name == "TribalAccount":
        from engine.core.account import TribalAccount
        return TribalAccount
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
from engine.core.profile_manager import (
    AccountProfile,
    ProfileManager,
    deobfuscate_password,
    obfuscate_password,
    test_proxy_connection,
)
from engine.core.scheduler import TaskScheduler

__all__ = [
    "TribalAccount",
    "ProfileManager",
    "AccountProfile",
    "obfuscate_password",
    "deobfuscate_password",
    "test_proxy_connection",
    "TaskScheduler",


    "Task",
    "TaskPriority",
    "Resources",
    "VillageData",
    "PlayerData",
    "TribalWarsException",
    "BotProtectionError",
    "SessionExpiredError",
    "GameMaintenanceError",
    "RateLimitError",
    "ActionFailedError",
    "NetworkTimeoutError",
]

