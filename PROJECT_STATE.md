# Tribal Wars Bot - Estado do Projeto e Contexto Operacional

> **Propósito deste ficheiro:** Manter o histórico de progresso, decisões arquiteturais, mapa de ficheiros e diretrizes de desenvolvimento para que qualquer sessão de IA recupere o contexto instantaneamente com consumo mínimo de tokens e sem perda de continuidade.

**Última Atualização:** 2026-08-30 (Sessão Noturna)  
**Estado Geral:** Fases 1, 3 e 4 Concluídas | Base de Dados Local SQLite (`data/accounts.db`), Modelos de Tropas (`attack`, `defense`) e Modelo Padrão Único Oficial de Construção (`default_plan` com 268 passos) Persistidos no SQLite, Remoção Total de Modelos Legados, Divisão de Abas Militares ("Modelos de Tropas" & "Recrutamento"), Atribuição de Modelos no Multi-Aldeias, Rush de Prioridade Máxima para Vikings e CL, Desativação de Farm/Ataques | 218 Testes Unitários e de Integração Automatizados (100% OK)  
**Ambiente Validado:** macOS 12+ / Windows 11 / Python 3.11-3.14 / `curl_cffi` 0.16.2 / `fastapi` 0.141.1 / `uvicorn` 0.52.4 / `pywebview` 6.2 (Edge WebView2 & Cocoa WebKit) / Git Branch: `main`

---

## 1. Visão Geral e Arquitetura

* **Conceito:** Cliente desktop autónomo (*estilo PS Evolution*) para automação do jogo Tribal Wars (Tribos).
* **Camada de Persistência (SQLite Local):**
  * Base de dados local `data/accounts.db` gerida pela classe `AccountsDatabase` (`engine/storage/database.py`).
  * Tabela `accounts`: contas, credenciais, proxies, estratégias de construção e estado de sessão.
  * Tabela `building_templates`: persistência de planos de construção com `default_plan` (268 passos) como padrão global do sistema (`account_id IS NULL`, `is_default = 1`) e suporte a modelos customizados por conta.
  * Tabela `recruitment_models`: persistência de metas e lotes de 12 unidades militares com `attack` ("Ataque Full") e `defense` ("Defesa Full") como padrões globais do sistema (`account_id IS NULL`, `is_default = 1`) e modelos customizados.
  * Gestão de conexões via `contextmanager` atómico (auto-close) para libertação de locks no Windows.
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
* **Fluxo de Autenticação Manual & Interceção de Rede:**
  * Modo 100% manual e seguro: o utilizador faz login diretamente no ecrã nativo do Tribal Wars (resolvendo captchas humanos se surgirem).
  * **Intercetor de Rede em Tempo Real:** O WebView2 captura instantaneamente os cookies `sid` (incluindo `HttpOnly`) dos cabeçalhos HTTP (`request_sent` e `response_received`), persistindo no SQLite e renovando a sessão `curl_cffi` via `account.update_sid()`.

---

## 2. Roadmap e Progresso das Fases

| Fase | Descrição | Status | Detalhes |
|---|---|---|---|
| **Fase 1** | **Fundação do Core & Rede** | ✅ Concluída | Estrutura modular, `TribalAccount`, `TaskScheduler`, parsers, anti-bot e testes unitários. |
| **Fase 2** | **Módulos de Ações (`game.php`)** | 🔄 Em Curso | `main` (auto-build + filas + rush militar de Vikings/CL), `recruitment` (lotes graduais, filas ativas, comparador de exército), `quest`, `map`, `market` (balanceamento) e `economic_arbitrage` (Fila Sempre Ativa) concluídos. Scavenging, Snob e Defesa/Dodge planeados. |
| **Fase 3** | **Camada Sidecar IPC, SQLite & Multi-Conta** | ✅ Concluída | Base de dados SQLite (`data/accounts.db`), modelos de construção e recrutamento persistidos, arranque estrito Offline, Single-Active Session, FastAPI REST, WebSockets, autenticação efêmera, proxies, `MultiWorldManager` e `MultiVillageCoordinator`. |
| **Fase 4** | **Shell Desktop & Frontend Nativo** | 🔄 Em Expansão | Cockpit Dark Glassmorphism, Hub de Contas com badges Online/Offline, login direto no Tribos pelo navegador integrado, HUD timer, abas independentes de "Modelos de Tropas" e "Recrutamento", seleção de modelos no Multi-Aldeias, réplica do mapa 2D e monitor de filas. |
| **Fase 5** | **Empacotamento & Release** | 📋 Pendente | Empacotamento executável com PyInstaller e instalador desktop. |

---

## 3. Mapa de Ficheiros do Projeto

```text
TribalwarsBot/
├── PROJECT_STATE.md                 # [ESTE FICHEIRO] Estado consolidado e memória do projeto
├── TODO.md                          # Checklist detalhado e acionável de todas as funcionalidades
├── README.md                        # Documentação pública e instruções rápidas
├── pyproject.toml                   # Configuração de empacotamento e dependências Python
├── requirements.txt                 # Dependências diretas (curl_cffi, pydantic, fastapi, uvicorn, pywebview)
├── config.json                      # Configuração personalizável (mundo, sid, templates, fila, farm, recrutamento, arbitragem)
├── profiles.json                    # Perfis de contas encriptados (ProfileManager)
│
├── engine/                          # Python Core Engine
│   ├── platforms/                   # Camada de Abstração Multiplataforma (Windows / macOS / Linux)
│   │   ├── __init__.py              # get_platform_adapter (fábrica com deteção e cache)
│   │   ├── base.py                  # BasePlatformAdapter (contrato abstrato, anti-hijack de captchas)
│   │   ├── windows.py               # WindowsPlatformAdapter (Edge WebView2, interceptação de rede)
│   │   ├── darwin.py                # MacOSPlatformAdapter (WebKit/Cocoa, WKHTTPCookieStore, proteção de POST)
│   │   └── linux.py                 # LinuxPlatformAdapter (WebKit2GTK)
│   ├── core/                        # Núcleo da automação
│   │   ├── __init__.py              # Exporta classes e exceções principais
│   │   ├── account.py               # TribalAccount: AsyncSession, mobile headers, update_sid, parsing, CSRF, multi-aldeia
│   │   ├── auth_manager.py          # TribalAuthManager: extração de cookies, normalização e validação de SID
│   │   ├── profile_manager.py       # ProfileManager: múltiplos perfis (profiles.json), encriptação de senhas, proxy test
│   │   ├── scheduler.py             # TaskScheduler: PriorityQueue, delays gaussianos, auto-pausa anti-bot
│   │   ├── models.py                # Resources, VillageData, PlayerData, TaskPriority, Task
│   │   └── exceptions.py            # BotProtectionError, SessionExpiredError, RateLimitError, etc.
│   ├── utils/                       # Utilitários de evasão e parsers
│   │   ├── __init__.py
│   │   ├── parsers.py               # Extração de game_data, CSRF, recursos, bot protect, níveis, fila, tropas, AF e multi-aldeia
│   │   └── timing.py                # get_human_delay (gaussiano), get_click_jitter
│   ├── actions/                     # Handlers por ecrã (Fase 2)
│   │   ├── __init__.py              # Exporta MainBuildingManager, PlaceManager, FarmManager, RecruitmentManager, MarketManager, EconomicArbitrageManager
│   │   ├── main_building.py         # MainBuildingManager: leitura, níveis virtuais, auto-build, cancelamento
│   │   ├── place.py                 # PlaceManager: leitura de tropas, capacidade de saque, comandos em 2 etapas
│   │   ├── farm.py                  # FarmManager: Assistente de Farm (A/B), Radar de Bárbaras e alocação dinâmica de esquadrões (Item 2.3)
│   │   ├── recruitment.py           # RecruitmentManager: Quartel, Estábulo e Oficina em lotes graduais
│   │   ├── economic_arbitrage.py    # EconomicArbitrageManager: Filosofia "Fila Sempre Ativa" e projeção de fluxo de caixa (Item 2.12)
│   │   ├── quest.py                 # QuestManager: Missões, baú diário e inventário manual (Item 2.10)
│   │   ├── map.py                   # MapManager: Mapa Tático, Scanner de Bárbaras e Map-Driven Farming (Item 2.11)
│   │   ├── market.py                # MarketManager: Gestão do Mercado, Leitura de Mercadores, Balanceamento de Recursos e Ofertas (Item 2.7)
│   │   └── village_coordinator.py   # MultiVillageCoordinator: Orquestrador Multi-Aldeia com categorização e balanceamento
│   ├── api/                         # Camada de comunicação Sidecar IPC (Fase 3)
│   │   ├── __init__.py              # Exporta EngineContext, create_app, start_sidecar_server
│   │   ├── auth.py                  # Token efêmero criptográfico, verificação HTTP/WS e .sidecar_auth.json
│   │   ├── context.py               # EngineContext: orquestração de estado, arbitragem económica, radar farm e websockets
│   │   ├── websocket.py             # WebSocketLogHandler (streaming de logs) e endpoint /ws com broadcast
│   │   ├── routes.py                # Endpoints REST (/api/status, /api/arbitrage/*, /api/farm/radar/*, /api/profiles/*)
│   │   └── server.py                # create_app (CORS tauri://localhost) e start_sidecar_server (uvicorn)
│   ├── config/                      # Configurações e carregamento de perfis
│   │   ├── __init__.py
│   │   └── settings.py              # BotConfig, BuildingConfig, FarmConfig, RecruitmentConfig, ArbitrageConfig, load_config
│   ├── desktop_launcher.py          # Desktop Launcher: janela nativa, interceção adaptada ao SO e monitor de login
│   └── main.py                      # Ponto de entrada CLI, Sidecar e Desktop (--gui, --api, --port)
│
├── frontend/                        # Frontend Cockpit Web & Desktop (HTML5 / Vanilla CSS / Vanilla JS)
│   ├── index.html                   # Estrutura do dashboard, cards, HUD timer, modal de captcha e seletor multi-aldeia
│   ├── css/
│   │   └── style.css                # Design system Dark Glassmorphism, badges de precisão e micro-animações
│   └── js/
│       ├── api.js                   # Cliente REST assíncrono para controle, multi-aldeia, perfis e proxy
│       ├── websocket.js             # Conexão WebSocket em tempo real e sintetizador sonoro de alertas
│       └── app.js                   # Controlador da interface, cronómetro de alta resolução e streaming de logs
│
├── tests/                           # Suíte de testes unitários e de integração automatizados (218 testes, 100% OK)
│   ├── __init__.py
│   ├── test_core.py                 # 10 testes cobrindo models, timing, parsers, account e scheduler
│   ├── test_main_building.py        # 12 testes cobrindo níveis, fila mobile/desktop, auto-build e cancelamento
│   ├── test_config.py               # 2 testes cobrindo parsing de config.json e seleção de DEFAULT_BUILD_PLAN
│   ├── test_place.py                # 10 testes cobrindo tropas, capacidade de carga, comandos e envio em 2 etapas
│   ├── test_farm.py                 # 11 testes cobrindo Assistente de Farm, modelos A/B, filtros, alocação de esquadrões e radar contínuo
│   ├── test_recruitment.py          # 11 testes cobrindo filas de treino, metas, modelos, lotes dinâmicos e ordenação por custo
│   ├── test_arbitrage.py            # 7 testes cobrindo temporizadores, projeção de fluxo de caixa, concorrência e micro-lotes
│   ├── test_api.py                  # 22 testes cobrindo auth, REST, WebSockets, building/recruitment toggles, quest, map e arbitragem
│   ├── test_auth.py                 # 7 testes cobrindo extração de cookies, persistência e auto-login
│   ├── test_platform.py             # 6 testes cobrindo adaptadores Windows/macOS/Linux e anti-hijack
│   ├── test_profiles.py             # 4 testes cobrindo persistência de perfis e ofuscação de senhas
│   ├── test_multi_village.py        # 3 testes cobrindo extração multi-aldeia e alternância de contexto
│   ├── test_multi_world.py          # 2 testes cobrindo orquestração multi-mundo paralela
│   ├── test_village_coordinator.py  # 6 testes cobrindo categorização de aldeias e balanceamento de recursos
│   ├── test_market.py               # 12 testes cobrindo mercado, ofertas e rotinas de balanceamento
│   ├── test_stats.py                # 11 testes cobrindo histórico de farm, comandos, KPIs e persistência
│   ├── test_proxy.py                # 2 testes cobrindo diagnóstico ativo de proxies
│   ├── test_quest.py                # 13 testes cobrindo missões, segurança de armazém/pop, baú diário e inventário manual
│   ├── test_smith.py                # 4 testes cobrindo auto-pesquisa de tropas no Ferreiro
│   ├── test_map.py                  # 7 testes cobrindo parsing de mapa, distância euclidiana, bárbaras/bónus e cache
│   ├── test_templates_database.py   # 6 testes cobrindo persistência de templates de construção e modelos de recrutamento no SQLite
│   ├── test_account_config_persistence.py # 4 testes cobrindo persistência atómica de configurações por conta no SQLite
│   └── test_military_prerequisite_rush.py # 2 testes cobrindo rush de prioridade máxima para Vikings e Cavalaria Leve
```

---

## 4. Regras e Decisões Técnicas Críticas

1. **Parâmetro `page=mobile`:** Obrigatório em **todas** as requisições GET/POST ao `game.php` para garantir a versão leve e consistência de headers.
2. **Token CSRF (`h`):** Extraído do `game_data.csrf` ou links da página; deve ser sempre injetado nas rotas POST e de comandos.
3. **Anti-Bot (`BotProtectionError`):**
   * Marcadores: `id="bot_protect"`, `name="bot_check"`, ou telas de desafio humano.
   * Comportamento: Disparo imediato da exceção, **pausa instantânea do `TaskScheduler`**, preservação da tarefa na fila e disparo imediato do evento WebSocket `CAPTCHA_ALERT` para o frontend abrir a janela de resolução manual.
4. **Thread-Safety no WebView2:**
   * Em `pywebview` no Windows, métodos WinForms como `get_current_url()` ou reflexão em objetos .NET não devem ser acedidos diretamente fora da UI thread.
   * A extração de URL e injeção de scripts utiliza `evaluate_js()` protegido.
   * A captura de cookies utiliza o listener de eventos de tráfego de rede HTTP (`request_sent` / `response_received`), garantindo extração imediata e 100% estável de cookies `HttpOnly`.
5. **Renovação de Sessão (`update_sid`):**
   * Ao capturar um novo `sid`, a instância de `TribalAccount` fecha a sessão anterior e cria uma nova `AsyncSession` com os novos cookies injetados para todos os domínios do mundo e TLD.
6. **Comunicação Sidecar Segura:**
   * Servidor local estritamente em `127.0.0.1`.
   * Acesso protegido por token gerado por `secrets.token_urlsafe(32)`. O ficheiro temporário `.sidecar_auth.json` comunica porta e credenciais e é eliminado no encerramento da aplicação.

---

## 5. Como Validar o Estado Atual

Para rodar a suíte completa de 218 testes automatizados:
```powershell
python -m pytest
```
*Status esperado:* `218 passed, 19 warnings in ~11s - OK`.

Para iniciar a aplicação desktop completa com interface gráfica nativa:
```powershell
python -m engine.main --gui
```

---

## 6. Próximos Passos (Roadmap Imediato)

1. **Módulos Militares Avançados:** Scavenging (Coleta de Recursos) com cálculo ótimo de unidades por tempo e escalão.
2. **Defesa e Auto-Dodge:** Deteção de ataques a chegar com notificação sonoro-visual e esquiva automática de tropas com cancelamento a tempo.
3. **Empacotamento Executável (Fase 5):** Criação de pacote standalone (.exe) com PyInstaller.

