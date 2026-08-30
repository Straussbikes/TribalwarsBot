"""
Testes Unitários para o Gestor de Perfis de Conta e Encriptação (ProfileManager)
"""

import json
from pathlib import Path
import tempfile
import unittest

from engine.core.profile_manager import (
    AccountProfile,
    ProfileManager,
    deobfuscate_password,
    obfuscate_password,
)


class TestProfileManager(unittest.TestCase):
    """Testes de criação, persistência e alternância de perfis."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.profiles_dir = Path(self.temp_dir.name) / "profiles"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_password_obfuscation_symmetry(self):
        """Valida que a ofuscação e desofuscação de senhas é simétrica e reversível."""
        original = "!MinhaSuperSenha123#$"
        obfuscated = obfuscate_password(original)
        self.assertTrue(obfuscated.startswith("enc:"))
        self.assertNotEqual(original, obfuscated)

        restored = deobfuscate_password(obfuscated)
        self.assertEqual(original, restored)

    def test_create_and_save_profile_isolated_files(self):
        """Valida a criação e persistência atómica de um perfil em ficheiro individual profiles/{id}.json."""
        manager = ProfileManager(self.profiles_dir)
        prof = AccountProfile(
            id="pt117_main",
            name="Conta Principal",
            world_domain="pt117.tribalwars.com.pt",
            session_cookie="test_sid_123",
            village_id=6810,
            username="jogador_pt",
            proxy="http://1.2.3.4:8080",
            build_order_strategy="default_plan",
            is_active=True,
        )
        prof.password = "secret_pass"

        manager.add_or_update_profile(prof)
        profile_file = self.profiles_dir / "pt117_main.json"
        self.assertTrue(profile_file.exists())

        # Recarrega noutra instância
        manager2 = ProfileManager(self.profiles_dir)
        loaded = manager2.get_profile("pt117_main")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.name, "Conta Principal")
        self.assertEqual(loaded.world, "pt117")
        self.assertEqual(loaded.domain, "tribalwars.com.pt")
        self.assertEqual(loaded.session_cookie, "test_sid_123")
        self.assertEqual(loaded.sid, "test_sid_123")
        self.assertEqual(loaded.village_id, 6810)
        self.assertEqual(loaded.build_order_strategy, "default_plan")
        self.assertEqual(loaded.password, "secret_pass")
        self.assertEqual(loaded.proxy, "http://1.2.3.4:8080")
        self.assertTrue(loaded.is_active)

    def test_switch_active_profile(self):
        """Valida a alternância de perfil ativo com desativação do anterior."""
        manager = ProfileManager(self.profiles_dir)
        p1 = AccountProfile(id="p1", name="Conta 1", world="pt117", is_active=True)
        p2 = AccountProfile(id="p2", name="Conta 2", world="pt118", is_active=False)
        manager.add_or_update_profile(p1)
        manager.add_or_update_profile(p2)

        self.assertEqual(manager.get_active_profile().id, "p1")

        manager.set_active_profile("p2")
        self.assertEqual(manager.get_active_profile().id, "p2")
        self.assertFalse(manager.get_profile("p1").is_active)
        self.assertTrue(manager.get_profile("p2").is_active)

    def test_delete_profile(self):
        """Valida a remoção segura de um perfil e eliminação do ficheiro JSON."""
        manager = ProfileManager(self.profiles_dir)
        p = AccountProfile(id="temp", name="Temporária")
        manager.add_or_update_profile(p)
        self.assertIn("temp", manager.profiles)
        self.assertTrue((self.profiles_dir / "temp.json").exists())

        manager.delete_profile("temp")
        self.assertNotIn("temp", manager.profiles)
        self.assertFalse((self.profiles_dir / "temp.json").exists())


if __name__ == "__main__":
    unittest.main()

