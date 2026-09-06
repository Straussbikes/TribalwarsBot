"""
Testes unitários para persistência de avoid_concurrent_attacks e reenvio compassado com cooldown por aldeia.
"""

import time
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from engine.actions.farm import FarmManager, FarmTarget
from engine.config.settings import BotConfig, FarmConfig, parse_config_dict


class TestFarmCooldownAndConcurrency(unittest.IsolatedAsyncioTestCase):
    def test_persistence_of_avoid_concurrent_attacks_and_cooldown(self):
        """Valida que avoid_concurrent_attacks=False e target_cooldown_minutes persistem corretamente."""
        data = {
            "world": "pt117",
            "farm": {
                "enabled": True,
                "avoid_concurrent_attacks": False,
                "target_cooldown_minutes": 5.0,
                "max_distance": 20.0,
            },
        }

        config = parse_config_dict(data)
        self.assertFalse(config.farm.avoid_concurrent_attacks)
        self.assertFalse(config.farm.skip_active_targets)
        self.assertEqual(config.farm.target_cooldown_minutes, 5.0)

        # Verifica serialização via to_dict
        serialized = config.to_dict()
        self.assertFalse(serialized["farm"]["avoid_concurrent_attacks"])
        self.assertFalse(serialized["farm"]["skip_active_targets"])
        self.assertEqual(serialized["farm"]["target_cooldown_minutes"], 5.0)

        # Reconstrói a partir do to_dict
        reconstructed = BotConfig.from_dict(serialized)
        self.assertFalse(reconstructed.farm.avoid_concurrent_attacks)
        self.assertEqual(reconstructed.farm.target_cooldown_minutes, 5.0)

    @patch("engine.actions.farm.get_gaussian_delay", return_value=0.0)
    async def test_avoid_concurrent_attacks_true_blocks_targets_in_transit(self, mock_delay):
        """Quando avoid_concurrent_attacks=True, alvos com ataque em trânsito são estritamente ignorados."""
        farm_cfg = FarmConfig(
            avoid_concurrent_attacks=True,
            target_cooldown_minutes=10.0,
        )
        manager = FarmManager()

        account = MagicMock()
        account.world = "pt117"
        account.current_village_id = 12345

        # Cria aldeia bárbara que já tem tropas a caminho
        target = FarmTarget(
            target_id="101",
            target_name="Aldeia Bárbara",
            target_coords="500|500",
            distance=2.0,
            has_attack_in_transit=True,
            is_in_am_farm=True,
            loot_status="full",
            template_a_id="btn_a_101",
            template_b_id="btn_b_101",
        )

        manager.get_am_farm_state = AsyncMock(
            return_value=MagicMock(
                template_a_troops={"light": 5},
                template_b_troops={"light": 10},
                haul_capacities={"a": 400, "b": 800},
            )
        )
        manager.send_am_farm_attack = AsyncMock(return_value=True)

        with patch.object(manager, "discover_all_radius_barbarians", AsyncMock(return_value=[target])):
            res = await manager.run_comprehensive_radius_farm_cycle(
                account=account,
                village_id=12345,
                config=farm_cfg,
            )

        # Não deve enviar nenhum ataque porque o alvo já possui ataque a caminho
        self.assertEqual(res["total_attacks"], 0)
        self.assertEqual(res["skipped_in_transit"], 1)
        manager.send_am_farm_attack.assert_not_called()

    @patch("engine.actions.farm.get_gaussian_delay", return_value=0.0)
    async def test_avoid_concurrent_attacks_false_allows_re_attack_after_cooldown(self, mock_delay):
        """Quando avoid_concurrent_attacks=False, permite re-atacar alvo em trânsito se o cooldown já passou."""
        farm_cfg = FarmConfig(
            avoid_concurrent_attacks=False,
            target_cooldown_minutes=5.0, # 5 minutos de cooldown
        )
        manager = FarmManager()

        account = MagicMock()
        account.world = "pt117"
        account.current_village_id = 12345

        target = FarmTarget(
            target_id="101",
            target_name="Aldeia Bárbara",
            target_coords="500|500",
            distance=2.0,
            has_attack_in_transit=True, # Já tem ataque a caminho
            is_in_am_farm=True,
            loot_status="full",
            template_a_id="btn_a_101",
            template_b_id="btn_b_101",
            template_a_available=True,
            template_b_available=True,
        )

        manager.get_am_farm_state = AsyncMock(
            return_value=MagicMock(
                template_a_troops={"light": 5},
                template_b_troops={"light": 10},
                haul_capacities={"a": 400, "b": 800},
            )
        )
        manager.send_am_farm_attack = AsyncMock(return_value=True)

        # 1. Simula que o alvo foi atacado há 6 minutos (cooldown de 5 min já expirou)
        manager._target_last_farmed["500|500"] = time.time() - 360.0

        with patch.object(manager, "discover_all_radius_barbarians", AsyncMock(return_value=[target])):
            res = await manager.run_comprehensive_radius_farm_cycle(
                account=account,
                village_id=12345,
                config=farm_cfg,
            )

        # Deve enviar ataque com sucesso
        self.assertEqual(res["total_attacks"], 1)
        self.assertEqual(res["skipped_in_transit"], 0)
        manager.send_am_farm_attack.assert_called_once()

    @patch("engine.actions.farm.get_gaussian_delay", return_value=0.0)
    async def test_avoid_concurrent_attacks_false_respects_cooldown(self, mock_delay):
        """Quando avoid_concurrent_attacks=False, NÃO ataca se ainda não tiver decorrido o cooldown."""
        farm_cfg = FarmConfig(
            avoid_concurrent_attacks=False,
            target_cooldown_minutes=10.0, # 10 min
        )
        manager = FarmManager()

        account = MagicMock()
        account.world = "pt117"
        account.current_village_id = 12345

        target = FarmTarget(
            target_id="101",
            target_name="Aldeia Bárbara",
            target_coords="500|500",
            distance=2.0,
            has_attack_in_transit=True,
            is_in_am_farm=True,
            loot_status="full",
            template_a_id="btn_a_101",
            template_b_id="btn_b_101",
        )

        manager.get_am_farm_state = AsyncMock(
            return_value=MagicMock(
                template_a_troops={"light": 5},
                template_b_troops={"light": 10},
                haul_capacities={"a": 400, "b": 800},
            )
        )
        manager.send_am_farm_attack = AsyncMock(return_value=True)

        # Simula que foi atacada há apenas 2 minutos (cooldown de 10 min ainda ativo)
        manager._target_last_farmed["500|500"] = time.time() - 120.0

        with patch.object(manager, "discover_all_radius_barbarians", AsyncMock(return_value=[target])):
            res = await manager.run_comprehensive_radius_farm_cycle(
                account=account,
                village_id=12345,
                config=farm_cfg,
            )

        # Deve pular porque está em cooldown
        self.assertEqual(res["total_attacks"], 0)
        self.assertEqual(res["skipped_in_transit"], 1)
        manager.send_am_farm_attack.assert_not_called()


if __name__ == "__main__":
    unittest.main()
