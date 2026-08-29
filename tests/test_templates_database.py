"""
Testes unitários e de integração para a Migração de Modelos de Construção
e Recrutamento para SQLite (data/accounts.db).
"""

import os
import tempfile
import pytest
from fastapi.testclient import TestClient

from engine.storage.database import AccountsDatabase
from engine.api.context import EngineContext
from engine.api.server import create_app
from engine.config.settings import BotConfig


@pytest.fixture
def temp_db():
    """Cria uma base de dados SQLite temporária para isolamento dos testes."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = AccountsDatabase(db_path=path)
    yield db
    if os.path.exists(path):
        os.remove(path)


def test_seed_default_building_templates(temp_db):
    """Verifica se os templates padrão de construção são semeados automaticamente."""
    templates = temp_db.list_building_templates()
    assert len(templates) >= 3
    ids = [t["id"] for t in templates]
    assert "rush_resources" in ids
    assert "balanced" in ids
    assert "military_rush" in ids

    rush = temp_db.get_building_template("rush_resources")
    assert rush is not None
    assert rush["is_default"] is True
    assert len(rush["priority_list"]) > 0


def test_seed_default_recruitment_models(temp_db):
    """Verifica se os modelos padrão de recrutamento (Ataque e Defesa) são semeados."""
    models = temp_db.list_recruitment_models()
    assert len(models) >= 2
    ids = [m["id"] for m in models]
    assert "attack" in ids
    assert "defense" in ids

    atk = temp_db.get_recruitment_model("attack")
    assert atk is not None
    assert atk["is_default"] is True
    assert atk["units"]["axe"] > 0
    assert atk["units"]["light"] > 0


def test_building_template_crud_and_clone(temp_db):
    """Testa criação, leitura, atualização, clonagem e exclusão de templates de construção."""
    # 1. Criação
    new_template = {
        "id": "custom_rush",
        "name": "Rush Personalizado",
        "priority_list": [["wood", 1], ["stone", 1], ["iron", 1], ["main", 2]],
        "target_levels": {"wood": 1, "stone": 1, "iron": 1, "main": 2},
        "is_default": False,
    }
    saved = temp_db.save_building_template(new_template)
    assert saved["id"] == "custom_rush"
    assert saved["name"] == "Rush Personalizado"

    # 2. Leitura
    fetched = temp_db.get_building_template("custom_rush")
    assert fetched is not None
    assert len(fetched["priority_list"]) == 4

    # 3. Atualização
    new_template["name"] = "Rush Personalizado v2"
    new_template["priority_list"].append(["storage", 2])
    updated = temp_db.save_building_template(new_template)
    assert updated["name"] == "Rush Personalizado v2"
    assert len(updated["priority_list"]) == 5

    # 4. Clonagem
    cloned = temp_db.clone_building_template("custom_rush", new_name="Rush Clonado")
    assert cloned["name"] == "Rush Clonado"
    assert cloned["id"] != "custom_rush"
    assert len(cloned["priority_list"]) == 5

    # 5. Exclusão
    deleted = temp_db.delete_building_template("custom_rush")
    assert deleted is True
    assert temp_db.get_building_template("custom_rush") is None

    # Templates padrão não podem ser deletados
    del_default = temp_db.delete_building_template("rush_resources")
    assert del_default is False


def test_recruitment_model_crud_and_clone(temp_db):
    """Testa criação, leitura, atualização, clonagem e exclusão de modelos de tropas."""
    # 1. Criação
    custom_model = {
        "id": "nuke_fast",
        "name": "Nuke Rápido",
        "units": {"axe": 6000, "light": 3000, "ram": 250},
        "batch_sizes": {"axe": 20, "light": 10, "ram": 2},
        "is_default": False,
    }
    saved = temp_db.save_recruitment_model(custom_model)
    assert saved["id"] == "nuke_fast"

    # 2. Leitura
    fetched = temp_db.get_recruitment_model("nuke_fast")
    assert fetched is not None
    assert fetched["units"]["axe"] == 6000
    assert fetched["batch_sizes"]["axe"] == 20

    # 3. Atualização
    custom_model["units"]["axe"] = 6500
    updated = temp_db.save_recruitment_model(custom_model)
    assert updated["units"]["axe"] == 6500

    # 4. Clonagem
    cloned = temp_db.clone_recruitment_model("nuke_fast", new_name="Nuke Rápido v2")
    assert cloned["name"] == "Nuke Rápido v2"
    assert cloned["units"]["axe"] == 6500

    # 5. Exclusão
    deleted = temp_db.delete_recruitment_model("nuke_fast")
    assert deleted is True
    assert temp_db.get_recruitment_model("nuke_fast") is None

    # Modelo padrão não pode ser deletado
    del_default = temp_db.delete_recruitment_model("attack")
    assert del_default is False


def test_botconfig_dynamic_template_resolution(temp_db):
    """Verifica se BotConfig resolve templates e modelos dinamicamente do SQLite."""
    # Salva template customizado no SQLite
    temp_db.save_building_template({
        "id": "sqlite_special_rush",
        "name": "SQLite Special Rush",
        "priority_list": [["barracks", 5], ["wall", 10]],
    })

    # Salva modelo de recrutamento customizado no SQLite
    temp_db.save_recruitment_model({
        "id": "sqlite_special_def",
        "name": "SQLite Special Def",
        "units": {"spear": 5000, "sword": 5000, "heavy": 800},
    })

    cfg = BotConfig(building={"template": "sqlite_special_rush"}, recruitment={"default_model": "sqlite_special_def"})

    # Resolução de plano de construção
    plan = cfg.get_active_build_plan("sqlite_special_rush", db=temp_db)
    assert len(plan) == 2
    assert plan[0] == ("barracks", 5)
    assert plan[1] == ("wall", 10)

    # Resolução de metas de tropas
    targets = cfg.get_village_recruitment_targets(model_name="sqlite_special_def", db=temp_db)
    assert targets.get("spear") == 5000
    assert targets.get("heavy") == 800


def test_api_building_templates_endpoints(temp_db):
    """Testa os endpoints REST de templates de construção."""
    context = EngineContext(config=BotConfig(), db=temp_db)
    token = "test_token_12345"
    app = create_app(context, token=token, attach_log_handler=False)
    client = TestClient(app, headers={"Authorization": f"Bearer {token}"})

    # 1. Listar templates
    resp = client.get("/api/templates/building")
    assert resp.status_code == 200
    data = resp.json()
    assert "templates" in data
    assert len(data["templates"]) >= 3

    # 2. Criar template
    create_payload = {
        "id": "api_test_template",
        "name": "Template Criado via API",
        "priority_list": [["main", 5], ["barracks", 5]],
    }
    resp = client.post("/api/templates/building", json=create_payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"

    # 3. Obter template
    resp = client.get("/api/templates/building/api_test_template")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Template Criado via API"

    # 4. Atualizar template
    update_payload = {
        "name": "Template API Atualizado",
        "priority_list": [["main", 6]],
    }
    resp = client.put("/api/templates/building/api_test_template", json=update_payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"

    # 5. Clonar template
    resp = client.post("/api/templates/building/api_test_template/clone", json={"new_name": "Clone API"})
    assert resp.status_code == 200
    cloned_id = resp.json()["template"]["id"]
    assert cloned_id != "api_test_template"

    # 6. Deletar template
    resp = client.delete("/api/templates/building/api_test_template")
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"

    # 7. Buscar deletado retorna 404
    resp = client.get("/api/templates/building/api_test_template")
    assert resp.status_code == 404


def test_api_recruitment_templates_endpoints(temp_db):
    """Testa os endpoints REST de modelos de recrutamento."""
    context = EngineContext(config=BotConfig(), db=temp_db)
    token = "test_token_12345"
    app = create_app(context, token=token, attach_log_handler=False)
    client = TestClient(app, headers={"Authorization": f"Bearer {token}"})

    # 1. Listar modelos
    resp = client.get("/api/templates/recruitment")
    assert resp.status_code == 200
    data = resp.json()
    assert "models" in data
    assert len(data["models"]) >= 2

    # 2. Criar modelo
    create_payload = {
        "id": "api_model_test",
        "name": "Modelo API",
        "units": {"axe": 4000, "light": 2000},
        "batch_sizes": {"axe": 15, "light": 8},
    }
    resp = client.post("/api/templates/recruitment", json=create_payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"

    # 3. Obter modelo
    resp = client.get("/api/templates/recruitment/api_model_test")
    assert resp.status_code == 200
    assert resp.json()["units"]["axe"] == 4000

    # 4. Clonar modelo
    resp = client.post("/api/templates/recruitment/api_model_test/clone", json={"new_name": "Clone Rec API"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"
    cloned_id = resp.json()["model"]["id"]

    # 5. Deletar modelo
    resp = client.delete("/api/templates/recruitment/api_model_test")
    assert resp.status_code == 200

    # 6. Deletar clone
    resp = client.delete(f"/api/templates/recruitment/{cloned_id}")
    assert resp.status_code == 200
