# Tribal Wars Bot - Estado do Projeto e Contexto Operacional

> **Propósito deste ficheiro:** Manter o histórico de progresso, decisões arquiteturais, mapa de ficheiros e diretrizes de desenvolvimento para que qualquer sessão de IA recupere o contexto instantaneamente com consumo mínimo de tokens e sem perda de continuidade.

**Última Atualização:** 2026-09-02  
**Estado Geral:** Fases 1, 3 e 4 Concluídas | Assistente de Saque & Micro-Farming Completo (`screen=am_farm`), Editor Interativo de Modelos A & B no Jogo, Varredura Abrangente de Bárbaras em Raio X (AM Farm + Mapa + Cache local), Radar de Inativos & Inno-Farming com Coleta Contínua e Séries Temporais de Evolução de Jogadores no Raio X (ΔP 24h, 3d, 7d, tendências e modal de linha do tempo histórica em `world_data.db`), Sincronização Periódica em Background no `TaskScheduler` | 247 Testes Unitários e de Integração Automatizados (100% OK)  
**Ambiente Validado:** macOS 12+ / Windows 11 / Python 3.11-3.14 / `curl_cffi` 0.16.2 / `fastapi` 0.141.1 / `uvicorn` 0.52.4 / `pywebview` 6.2 (Edge WebView2 & Cocoa WebKit) / Git Branch: `main`

---

## 1. Visão Geral e Arquitetura

* **Conceito:** Cliente desktop autónomo (*estilo PS Evolution*) para automação do jogo Tribal Wars (Tribos).
* **Camada de Persistência (SQLite Local):**
  * Base de dados local de contas `data/accounts.db` gerida pela classe `AccountsDatabase` (`engine/storage/database.py`).
  * Base de dados local de dados de mundo e inativos `data/world_data.db` gerida por `WorldDataDatabase` (`engine/storage/world_data_db.py`).
  * Tabela `accounts`: contas, credenciais, proxies, estratégias de construção e estado de sessão.
  * Tabela `building_templates`: persistência de planos de construção com `default_plan` (268 passos) como padrão global do sistema (`account_id IS NULL`, `is_default = 1`) e suporte a modelos customizados por conta.
  * Tabela `recruitment_models`: persistência de metas e lotes de 12 unidades militares com `attack` ("Ataque Full") e `defense` ("Defesa Full") como padrões globais do sistema (`account_id IS NULL`, `is_default = 1`) e modelos customizados.
  * Gestão de conexões via `contextmanager` atómico (auto-close) para libertação de locks no Windows.
* **Assistente de Saque & Radar de Inativos (Fase 2.3 & 2.8):**
  * **Motor AM Farm (`FarmManager`):** Parsing estruturado de `screen=am_farm` abrangendo sub-linhas mobile (`report_X`), despacho nativo oficial via `POST ajaxaction=farm` com `{"target", "template_id", "source", "h"}` e fallback via GET, seleção ótima de modelo A vs B, filtros de perdas/muralha, prevenção de concorrência/colisões e micro-jitters estocásticos gaussianos.
  * **Editor de Modelos A e B no Jogo:** Motor HTTP `save_am_farm_template` com submissão direta do formulário oficial `action=edit_all` (`template[{id}][id]`, `template[{id}][new]`, `{unit}[{id}]`) com fallback a `action=change_template`, sincronização bidirecional em tempo real com a interface e cálculo de capacidade de carga.
  * **Varredura Completa de Bárbaras em Raio:** Combinação do AM Farm com o Mapa Tático (`screen=map`) e dados do mundo. Bárbaras não catalogadas recebem automaticamente um primeiro ataque de reconhecimento/saque via Praça de Reunião (*Auto-Bootstrap*), integrando-se no AM Farm.
  * **Radar de Inativos (`InactivityTracker`):** Descarregamento e processamento de snapshots oficiais (`village.txt`, `player.txt`, `ally.txt`), cálculo diferencial de crescimento de pontos ao longo de janelas temporais de X dias e filtros táticos para identificação de alvos inativos.
* **Ciclo de Vida Offline & Single-Active Session:**
  * O motor arranca **sempre em modo Standby/Offline** (`active_profile_id = None`), sem instanciar conexões de rede nem agendador.
  * O frontend abre **sempre no Gestor de Contas (Account Hub)** com todas as contas marcadas como `⚪ OFFLINE`.
  * Ativação manual com `▶ Conectar` fecha qualquer sessão anterior, adquire o lock monousuário, instancia `TribalAccount`, inicializa o agendador e desbloqueia a Dashboard.
  * Logout com `🚪 Sair` desconecta a sessão, esvazia filas e regressa ao Hub em modo Offline.
* **Camada de Rede:** Emulação pura HTTP sobre a versão mobile (`page=mobile`), sem instâncias pesadas de Chromium/Puppeteer, garantindo consumo ultrabaixo de RAM (<60MB) e CPU.
* **Evasão de Assinaturas (TLS/JA3/JA4):** `curl_cffi` com `impersonate="chrome124"`, cabeçalhos consistentes de Chrome Mobile Android (`Sec-CH-UA-Mobile: ?1`, `Sec-CH-UA-Platform: "Android"`).
* **Arquitetura de Processos (Sidecar Pattern):**
  * **Shell Desktop:** Janela nativa Windows Edge WebView2 (`pywebview`) servindo interface Cockpit moderna com isolamento de threads.
  * **Core Engine:** Motor Python assíncrono (`asyncio`) desacoplado, orquestrando rede, agendamento de tarefas e keep-alive.
  * **Comunicação IPC:** FastAPI / WebSockets locais em `127.0.0.1` com token efêmero de segurança gerado em `.sidecar_auth.json`.

---

## 2. Roadmap e Progresso das Fases

| Fase | Descrição | Status | Detalhes |
|---|---|---|---|
| **Fase 1** | **Fundação do Core & Rede** | ✅ Concluída | Estrutura modular, `TribalAccount`, `TaskScheduler`, parsers, anti-bot e testes unitários. |
| **Fase 2** | **Módulos de Ações (`game.php`)** | 🔄 Em Curso | `main` (auto-build + rush militar), `recruitment` (lotes, filas ativas, comparador), `smith` (auto-pesquisa prioritária de Vikings/CL), `place` (comandos em 2 etapas), `am_farm` (saque rápido, editor de modelos A/B, varredura em raio, auto-bootstrap), `radar` (radar de inativos), `quest`, `map`, `market` e `economic_arbitrage` concluídos. Scavenging, Snob e Defesa/Dodge planeados. |
| **Fase 3** | **Camada Sidecar IPC, SQLite & Multi-Conta** | ✅ Concluída | Bases de dados SQLite (`data/accounts.db` e `data/world_data.db`), modelos de construção, recrutamento e farm persistidos, arranque estrito Offline, Single-Active Session, FastAPI REST, WebSockets, autenticação efêmera, proxies, `MultiWorldManager` e `MultiVillageCoordinator`. |
| **Fase 4** | **Shell Desktop & Frontend Nativo** | 🔄 Em Expansão | Cockpit Dark Glassmorphism, Hub de Contas, login direto no Tribos pelo navegador integrado, HUD timer, abas de "Modelos de Tropas", "Recrutamento", "Assistente de Saque & Farm" (com sub-abas AM Farm & Radar de Inativos e Editor Modal de Modelos), mapa 2D interativo e monitor de filas. |
| **Fase 5** | **Empacotamento & Release** | 📋 Pendente | Empacotamento executável com PyInstaller e instalador desktop. |

---

## 3. Mapa de Ficheiros do Projeto

```text
TribalwarsBot/
├── PROJECT_STATE.md                 # [ESTE FICHEIRO] Estado consolidado e memória do projeto
├── engine/                          # Python Core Engine
│   ├── storage/                     # Camada de Persistência SQLite
│   │   ├── database.py              # AccountsDatabase: gestão de contas, templates de construção e recrutamento (data/accounts.db)
│   │   └── world_data_db.py         # WorldDataDatabase: snapshots oficiais do mundo e histórico de inativos (data/world_data.db)
│   ├── core/                        # Núcleo da automação
│   │   ├── account.py               # TribalAccount: AsyncSession, mobile headers, update_sid, parsing, CSRF, multi-aldeia
│   │   ├── auth_manager.py          # TribalAuthManager: extração de cookies, normalização e validação de SID
│   │   ├── profile_manager.py       # ProfileManager: múltiplos perfis (profiles.json), encriptação de senhas, proxy test
│   │   ├── scheduler.py             # TaskScheduler: PriorityQueue, delays gaussianos, auto-pausa anti-bot
│   │   ├── models.py                # Resources, VillageData, PlayerData, TaskPriority, Task
│   │   └── exceptions.py            # BotProtectionError, SessionExpiredError, RateLimitError, etc.
│   ├── utils/                       # Utilitários de evasão e parsers
│   │   ├── parsers.py               # Extração de game_data, CSRF, recursos, bot protect, níveis, fila, tropas, AM Farm, mapa e multi-aldeia
│   │   └── timing.py                # get_human_delay (gaussiano), get_click_jitter, get_gaussian_delay
│   ├── actions/                     # Handlers por ecrã (Fase 2)
│   │   ├── main_building.py         # MainBuildingManager: leitura, níveis virtuais, auto-build, cancelamento e rush militar
│   │   ├── place.py                 # PlaceManager: leitura de tropas, capacidade de saque, comandos em 2 etapas e logs de despacho
│   │   ├── farm.py                  # FarmManager: Assistente de Farm (A/B), Editor de Modelos, Varredura em Raio, Auto-Bootstrap
│   │   ├── inactivity_tracker.py    # InactivityTracker: Motor do Radar de Inativos, sincronização de mundo e deteção diferencial
│   │   ├── recruitment.py           # RecruitmentManager: Quartel, Estábulo e Oficina em lotes graduais
│   │   ├── smith.py                 # SmithManager: Gestão do Ferreiro, tecnologias militares e auto-pesquisa prioritária (Vikings/CL)
│   │   ├── economic_arbitrage.py    # EconomicArbitrageManager: Filosofia "Fila Sempre Ativa" e projeção de fluxo de caixa
│   │   ├── map.py                   # MapManager: Mapa Tático, get_tactical_map, Scanner de Bárbaras e Map-Driven Farming
│   │   └── village_coordinator.py   # MultiVillageCoordinator: Orquestrador Multi-Aldeia com categorização e balanceamento
│   ├── api/                         # Camada de comunicação Sidecar IPC (Fase 3)
│   │   ├── context.py               # EngineContext: orquestração de estado, farm, radar de inativos, templates e websockets
│   │   ├── routes.py                # Endpoints REST (/api/status, /api/farm/*, /api/radar/*, /api/profiles/*)
│   │   └── server.py                # create_app (CORS tauri://localhost) e start_sidecar_server (uvicorn)
│   └── main.py                      # Ponto de entrada CLI, Sidecar e Desktop (--gui, --api, --port)
│
├── frontend/                        # Frontend Cockpit Web & Desktop
│   ├── index.html                   # Estrutura do dashboard, cards, HUD timer, aba Farm Assistant com sub-abas e modais
│   ├── css/
│   │   └── style.css                # Design system Dark Glassmorphism, sub-tabs, farm dots, badges e micro-animações
│   └── js/
│       ├── api.js                   # Cliente REST assíncrono para controle, farm, radar, templates e multi-aldeia
│       └── app.js                   # Controlador da interface, AM Farm sub-tabs, radar controller, templates modal e logs
│
├── tests/                           # Suíte de testes unitários e de integração (248 testes, 100% OK)
│   ├── test_farm.py                 # 17 testes cobrindo Assistente de Farm, modelos A/B, varredura em raio, bootstrap e radar contínuo
│   ├── test_api_farm.py             # 8 testes cobrindo endpoints REST de farm (/api/farm/status, /api/farm/targets, /api/farm/templates, /api/radar/*)
│   ├── test_place.py                # 12 testes cobrindo Praça de Reunião, comandos em 2 etapas, parsing de confirmação e evasão de error_box invisível
│   └── test_world_data.py           # 8 testes cobrindo persistência, tracking diferencial de inativos e evolução temporal de jogadores no world_data.db
```

---

## 4. Regras e Decisões Técnicas Críticas

1. **Parâmetro `page=mobile`:** Obrigatório em todas as requisições GET/POST ao `game.php`.
2. **Token CSRF (`h`):** Extraído do `game_data.csrf`; deve ser injetado nas rotas POST e comandos.
3. **Anti-Bot:** Em caso de `BotProtectionError`, o `TaskScheduler` pausa instantaneamente e dispara `CAPTCHA_ALERT` via WebSocket.
4. **Thread-Safety no WebView2:** Acesso protegido via `evaluate_js()` e listeners de rede assíncronos.
5. **Comunicação Sidecar Segura:** Servidor `127.0.0.1` protegido por token `secrets.token_urlsafe(32)` em `.sidecar_auth.json`.

---

## 5. Como Validar o Estado Atual

Para rodar a suíte completa de 248 testes automatizados:
```powershell
python -m pytest
```
*Status esperado:* `248 passed, 19 warnings in ~17s - OK`.

Para iniciar a aplicação desktop completa com interface gráfica nativa:
```powershell
python -m engine.main --gui
```

---

## 6. Próximos Passos (Roadmap Imediato)

1. **Módulos Militares Avançados:** Scavenging (Coleta de Recursos) com cálculo ótimo de unidades por tempo e escalão.
2. **Defesa e Auto-Dodge:** Deteção de ataques a chegar com notificação sonoro-visual e esquiva automática de tropas com cancelamento a tempo.
3. **Empacotamento Executável (Fase 5):** Criação de pacote standalone (.exe) com PyInstaller.

