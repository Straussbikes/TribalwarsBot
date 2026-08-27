# Tribal Wars Bot - Estado do Projeto e Contexto Operacional

> **Propósito deste ficheiro:** Manter o histórico de progresso, decisões arquiteturais, mapa de ficheiros e diretrizes de desenvolvimento para que qualquer sessão de IA recupere o contexto instantaneamente com consumo mínimo de tokens e sem perda de continuidade.

**Última Atualização:** 2026-08-27  
**Estado Geral:** Fase 3 em Progresso (Servidor Local FastAPI, WebSockets e Sidecar IPC Concluídos)  
**Ambiente Validado:** Windows 11 / Python 3.14 / `curl_cffi` 0.16.2 / `fastapi` 0.141.1 / `uvicorn` 0.52.4 / Node.js v25.8.1

---

## 1. Visão Geral e Arquitetura

* **Conceito:** Cliente desktop autónomo (*estilo PS Evolution*) para automação do jogo Tribal Wars (Tribos).
* **Camada de Rede:** Emulação pura HTTP sobre a versão mobile (`page=mobile`), sem Chromium pesado, com consumo ultrabaixo de RAM/CPU.
* **Evasão de Assinaturas (TLS/JA3/JA4):** `curl_cffi` com `impersonate="chrome124"`, headers consistentes de Chrome Mobile Android (`Sec-CH-UA-Mobile: ?1`, `Sec-CH-UA-Platform: "Android"`).
* **Arquitetura de Processos (Sidecar Pattern):**
  * **Shell Desktop:** Tauri (Rust) para janela nativa, system tray e WebView popup para resolução manual de captchas.
  * **Core Engine:** Python (AsyncIO) rodando desacoplado como sidecar, orquestrando rede e agendamento.
  * **Comunicação IPC:** FastAPI / WebSockets locais em `127.0.0.1` com token efêmero de segurança gerado em `.sidecar_auth.json`.

---

## 2. Roadmap e Progresso das Fases

| Fase | Descrição | Status | Detalhes |
|---|---|---|---|
| **Fase 1** | **Fundação do Core & Rede** | ✅ Concluída | Estrutura modular, `TribalAccount`, `TaskScheduler`, parsers e 10 testes unitários. |
| **Fase 2** | **Módulos de Ações (`game.php`)** | 🔄 Em Curso | `main` (Edifício Principal), `place` (Praça), `farm` (Micro-Farming) e `recruitment` (Quartel/Estábulo/Oficina) concluídos. |
| **Fase 3** | **Camada Sidecar IPC & Sessões** | ✅ Concluída | FastAPI REST, WebSockets bidirecionais (logs, status, captcha), autenticação efêmera. |
| **Fase 4** | **Shell Desktop & Frontend Nativo** | ✅ Concluída | Cockpit moderno (Dark Glassmorphism), streaming WebSocket, WebView2 nativa e 59 testes unitários (100% OK). |
| **Fase 5** | **Empacotamento & Release** | 📋 Pendente | Empacotamento com PyInstaller / Tauri Bundler e instalador final. |


---

## 3. Mapa de Ficheiros do Projeto

```text
TribalwarsBot/
├── PROJECT_STATE.md                 # [ESTE FICHEIRO] Estado consolidado e memória do projeto
├── TODO.md                          # Checklist detalhado e acionável de todas as funcionalidades
├── README.md                        # Documentação pública e instruções rápidas
├── pyproject.toml                   # Configuração de empacotamento e dependências Python
├── requirements.txt                 # Dependências diretas (curl_cffi, pydantic, fastapi, uvicorn)
├── config.json                      # Configuração personalizável (mundo, sid, templates, fila, farm, recrutamento)
│
├── engine/                          # Python Core Engine
│   ├── core/                        # Núcleo da automação
│   │   ├── __init__.py              # Exporta classes e exceções principais
│   │   ├── account.py               # TribalAccount: AsyncSession, mobile headers, parsing, CSRF
│   │   ├── scheduler.py             # TaskScheduler: PriorityQueue, delays gaussianos, preempção
│   │   ├── models.py                # Resources, VillageData, PlayerData, TaskPriority, Task
│   │   └── exceptions.py            # BotProtectionError, SessionExpiredError, RateLimitError, etc.
│   ├── utils/                       # Utilitários de evasão e parsers
│   │   ├── __init__.py
│   │   ├── parsers.py               # Extração de game_data, CSRF, recursos, bot protect, níveis, fila, tropas, AF e treino
│   │   └── timing.py                # get_human_delay (gaussiano), get_click_jitter
│   ├── actions/                     # Handlers por ecrã (Fase 2)
│   │   ├── __init__.py              # Exporta MainBuildingManager, PlaceManager, FarmManager, RecruitmentManager
│   │   ├── main_building.py         # MainBuildingManager: leitura, níveis virtuais, auto-build, cancelamento
│   │   ├── place.py                 # PlaceManager: leitura de tropas, capacidade de saque, comandos em 2 etapas
│   │   ├── farm.py                  # FarmManager: Assistente de Farm (A/B), filtros de segurança, fallback Praça
│   │   └── recruitment.py           # RecruitmentManager: Quartel, Estábulo e Oficina em lotes graduais
│   ├── api/                         # Camada de comunicação Sidecar IPC com Tauri (Fase 3)
│   │   ├── __init__.py              # Exporta EngineContext, create_app, start_sidecar_server
│   │   ├── auth.py                  # Token efêmero criptográfico, verificação HTTP/WS e .sidecar_auth.json
│   │   ├── context.py               # EngineContext: orquestração de estado, scheduler, ações manuais e websockets
│   │   ├── websocket.py             # WebSocketLogHandler (streaming de logs) e endpoint /ws com broadcast
│   │   ├── routes.py                # Endpoints REST (/api/status, /api/config, /api/scheduler/*, /api/actions/*)
│   │   └── server.py                # create_app (CORS tauri://localhost) e start_sidecar_server (uvicorn)
│   ├── config/                      # Configurações e carregamento de perfis
│   │   ├── __init__.py
│   │   ├── settings.py              # BotConfig, BuildingConfig, FarmConfig, RecruitmentConfig, load_config
│   ├── desktop_launcher.py          # Desktop Launcher: janela nativa Edge WebView2 (pywebview)
│   └── main.py                      # Ponto de entrada CLI, Sidecar e Desktop (--gui, --api, --port)
│
├── frontend/                        # Frontend Cockpit Web & Desktop (HTML5 / Vanilla CSS / Vanilla JS)
│   ├── index.html                   # Estrutura do dashboard, cards, tabs e modal de captcha
│   ├── css/
│   │   └── style.css                # Design system Glassmorphism, dark mode e micro-animações
│   └── js/
│       ├── api.js                   # Cliente REST assíncrono para controle e configurações
│       ├── websocket.js             # Conexão WebSocket em tempo real e sintetizador sonoro
│       └── app.js                   # Controlador da interface, cronómetro e streaming de logs
│
├── tests/                           # Suíte de testes unitários automatizados (59 testes, 100% OK)
│   ├── __init__.py
│   ├── test_core.py                 # 10 testes cobrindo models, timing, parsers, account e scheduler
│   ├── test_main_building.py        # 12 testes cobrindo níveis, fila mobile/desktop, templates, auto-build e cancelamento
│   ├── test_config.py               # 2 testes cobrindo parsing de config.json e seleção de templates
│   ├── test_place.py                # 10 testes cobrindo tropas, capacidade de carga, comandos e envio em 2 etapas
│   ├── test_farm.py                 # 6 testes cobrindo Assistente de Farm, modelos A/B, filtros e fallback
│   ├── test_recruitment.py          # 5 testes cobrindo filas de treino, metas, lotes e reserva de população
│   └── test_api.py                  # 14 testes cobrindo auth, REST, WebSockets, auth-info e static files


│
└── mdfiles/
    └── contexto1.md                 # Contexto inicial da PoC
```

---

## 4. Regras e Decisões Técnicas Críticas

1. **Parâmetro `page=mobile`:** Obrigatório em **todas** as requisições GET/POST ao `game.php` para garantir a versão leve e consistência de headers.
2. **Token CSRF (`h`):** Extraído do `game_data.csrf` ou links da página; deve ser sempre injetado nas rotas POST e de comandos.
3. **Anti-Bot (`BotProtectionError`):**
   * Marcadores: `id="bot_protect"`, `name="bot_check"`, ou telas de desafio humano.
   * Comportamento: Disparo imediato da exceção, **pausa instantânea do `TaskScheduler`**, preservação da tarefa na fila e disparo imediato do evento WebSocket `CAPTCHA_ALERT` para o frontend abrir a janela de resolução manual.
4. **Comunicação Sidecar Segura:**
   * O servidor roda estritamente em `127.0.0.1`.
   * Acesso protegido por token gerado por `secrets.token_urlsafe(32)`. O ficheiro temporário `.sidecar_auth.json` comunica porta e credenciais ao Tauri e é eliminado no encerramento.
   * Suporte a WebSockets bidirecionais transmitindo logs formatados (`LOG`) e eventos de estado (`STATE_UPDATE`, `SCHEDULER_STATE`).
5. **Windows Event Loop Policy:** No Windows, utilizar `asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())` para compatibilidade estrita com os sockets do `curl_cffi`.

---

## 5. Como Validar o Estado Atual

Para rodar os testes automatizados da suíte completa (Fases 1, 2 e 3):
```powershell
python -m unittest discover tests -v
```
*Status esperado:* 56 testes, 0 falhas (`OK`), cobrindo modelos, delays gaussianos, parsers, anti-bot, account, scheduler, níveis virtuais, auto-build, configurações, praça de reunião (envio em 2 etapas), micro-farming, recrutamento militar e API Sidecar (REST + WebSockets).

Para testar o servidor Sidecar em execução real:
```powershell
python -m engine.main --api --port 8000
```
*Validado:* Inicia o motor e o servidor FastAPI em `http://127.0.0.1:8000`, gera `.sidecar_auth.json` e transmite logs e estado em tempo real para o frontend via WebSocket `/ws`.


---

## 4. Regras e Decisões Técnicas Críticas

1. **Parâmetro `page=mobile`:** Obrigatório em **todas** as requisições GET/POST ao `game.php` para garantir a versão leve e consistência de headers.
2. **Token CSRF (`h`):** Extraído do `game_data.csrf` ou links da página; deve ser sempre injetado nas rotas POST e de comandos.
3. **Anti-Bot (`BotProtectionError`):**
   * Marcadores: `id="bot_protect"`, `name="bot_check"`, ou telas de desafio humano.
   * Comportamento: Disparo imediato da exceção, **pausa instantânea do `TaskScheduler`**, preservação da tarefa na fila e disparo de eventos assíncronos para o utilizador resolver o captcha na WebView.
4. **Comandos Militares em 2 Etapas:** Sempre validar em 2 passos (`try=confirm` -> `action=command`), extraindo o hash de segurança do servidor (`chck`).
5. **Micro-Farming Seguro:**
   * Nunca disparar ataques simultâneos no mesmo milissegundo. Usar jitter de toque humano (200ms a 550ms) entre cliques na lista de saques.
   * Filtragem de segurança obrigatória: ignorar perdas (`skip_losses`) e ignorar aldeias com muralha ativa (`skip_wall`).
6. **Recrutamento Militar Inteligente:**
   * Cálculo de défice: `Needed = Target - (Home + Queue)`.
   * Produção em pequenos lotes (`batch_sizes`) para não estagnar os recursos da aldeia.
   * Proteção de população: suspende o treino se a população livre for inferior a `min_free_pop`.
7. **Temporização Realista:**
   * Nunca usar atrasos fixos (`sleep(5)` é proibido em produção).
   * Usar `get_human_delay(base, std_dev, min, max)` (distribuição normal truncada).
   * Adicionar micro-jitters mecânicos de toque em ecrã com `get_click_jitter()` (120ms - 380ms).
8. **Windows Event Loop Policy:** No Windows, utilizar `asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())` para compatibilidade estrita com os sockets do `curl_cffi`.

---

## 5. Como Validar o Estado Atual

Para rodar os testes automatizados da suíte completa (Fases 1 e 2):
```powershell
python -m unittest discover tests -v
```
*Status esperado:* 44 testes, 0 falhas (`OK`), cobrindo modelos, delays gaussianos, parsers, anti-bot, account, scheduler, níveis virtuais, auto-build, configurações, praça de reunião (envio em 2 etapas), micro-farming e recrutamento militar.

Para testar no jogo real (online):
```powershell
python -m engine.main
```
*Validado:* Conexão online estabelecida no mundo `pt117`, leitura de aldeia/recursos em tempo real, auto-build, auto-farm e recrutamento inteligente respeitando `config.json`.




