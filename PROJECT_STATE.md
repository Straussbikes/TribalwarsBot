# Tribal Wars Bot - Estado do Projeto e Contexto Operacional

> **Propósito deste ficheiro:** Manter o histórico de progresso, decisões arquiteturais, mapa de ficheiros e diretrizes de desenvolvimento para que qualquer sessão de IA recupere o contexto instantaneamente com consumo mínimo de tokens e sem perda de continuidade.

**Última Atualização:** 2026-09-03  
**Estado Geral:** 100% Cloud-Native Concluído | Cloud SQL (PostgreSQL 18.6) via Neon Tech | Eliminação de I/O em disco local | Cofre Criptográfico AES-256-GCM (`TokenStorage` para `auth.dat`) | 5 Modelos Oficiais Imutáveis de Construção | Gestor Monousuário (`AccountSessionManager`) & Orquestrador Concorrente Multi-Mundo (`WorldWorkerOrchestrator`) | Bootstrap Gatekeeper (Bloqueio sem Cloud) | 316 Testes Unitários e de Integração Automatizados (100% OK)  
**Ambiente Validado:** Windows 11 / macOS 12+ / Python 3.11-3.14 / `curl_cffi` 0.16.2 / `fastapi` 0.141.1 / `uvicorn` 0.52.4 / `pywebview` 6.2 (Edge WebView2) / PostgreSQL 18.6 Cloud SQL / Git Branch: `main`

---

## 1. Visão Geral e Arquitetura

* **Conceito:** Cliente desktop autónomo para automação multi-mundo do jogo Tribal Wars (Tribos) com arquitetura distribuída 100% Cloud-Native.
* **Camada de Dados Cloud SQL (PostgreSQL 18.6):**
  * Conexão gerenciada em `engine/storage/cloud_db.py` com SSL/TLS mandatário (`sslmode=require&channel_binding=require`) no Neon Tech.
  * Hierarquia relacional estrita:
    * `app_users`: contas da aplicação com hash de password Argon2/bcrypt.
    * `game_accounts`: contas do jogo com cofre criptográfico AES-256-GCM para credenciais/SIDs.
    * `game_worlds`: mundos associados com estado de execução independente.
    * `villages`: aldeias sincronizadas com atribuição individual de modelo de construção (`active_build_model_id`).
    * `build_templates`: modelos de construção na cloud com os 5 modelos padrão oficiais do sistema.
* **Eliminação de Persistência Local (Zero I/O no Cliente):**
  * Remoção de quaisquer dependências de ficheiros `.db`, `.sqlite`, caches em disco (`.map_cache`, `.stats_cache`) ou `config.json`.
  * `AccountsDatabase` opera exclusivamente através de URI SQLite em memória partilhada (`file:twbot_memdb?mode=memory&cache=shared`) protegida por `threading.Lock`.
  * `ProfileManager` opera puramente em memória durante o runtime sem gerar ficheiros `profiles/*.json`.
  * **Único Ficheiro Local Permitido:** `auth.dat`, gerido exclusivamente pelo `TokenStorage` com encriptação AES-256-GCM (nonce de 96 bits) e eliminado no logout.
* **Modelos Oficiais de Construção Imutáveis:**
  * Constantes declaradas em `engine/config/templates.py`:
    1. `ee02gd68de` — **AI - Build Model**
    2. `zbhbufxza0q` — **Construcao**
    3. `4zyrtbsdxa` — **Upar Barbara**
    4. `rtk1zhvuvtr` — **Sprinter BR131**
    5. `6goivjbmzbh` — **Pontos Premium**
  * Auto-seed idempotente no Cloud SQL e preservação estrita contra deleções.
* **Exclusão Mútua & Orquestração Multi-Mundo:**
  * **`AccountSessionManager` (Singleton):** Garante que apenas 1 conta de jogo tem execução ativa por processo, usando `cancellation_token` para terminação limpa na alternância de contas.
  * **`WorldWorkerOrchestrator`:** Executa múltiplos mundos em paralelo sob a conta ativa, com instâncias desacopladas e isolamento de rate limits HTTP 429.
* **Bootstrap Gatekeeper (Bloqueio sem Cloud):**
  * `main.py` e `desktop_launcher.py` validam obrigatoriamente a conectividade com o Cloud SQL no arranque.
  * Proíbe modo offline silencioso: sem conexão ou sem autenticação válida, a automação do bot é travada imediatamente e o utilizador é direcionado para login.
* **Camada de Rede e Evasão:**
  * Emulação HTTP pura sobre a versão mobile (`page=mobile`) com `curl_cffi` (`impersonate="chrome124"`).
  * Jitter estocástico gaussiano em cliques e intervalos, evitando padrões robóticos.

---

## 2. Roadmap e Progresso das Fases

| Fase | Descrição | Status | Detalhes |
|---|---|---|---|
| **Fase 1** | **Fundação do Core & Rede** | ✅ Concluída | `TribalAccount`, `TaskScheduler`, parsers, anti-bot e evasão TLS/JA3/JA4. |
| **Fase 2** | **Módulos de Ações (`game.php`)** | ✅ Concluída | Auto-build, recrutamento, Praça de Reunião, AM Farm, radar de inativos, mapa tático, mercado e arbitragem económica. |
| **Fase 3** | **Arquitetura 100% Cloud-Native** | ✅ Concluída | Migração total para Cloud SQL PostgreSQL 18.6, cofre AES-256-GCM, hierarquia `AppUser` -> `GameAccount` -> `GameWorld` -> `Village`, eliminação de resquícios de I/O em disco, `TokenStorage` (`auth.dat`), Bootstrap Gatekeeper. |
| **Fase 4** | **Concorrência & Orquestração** | ✅ Concluída | `AccountSessionManager` (mutex monousuário), `WorldWorkerOrchestrator` (paralelismo multi-mundo e isolamento de rate limits), chips multi-mundo dinâmicos na interface. |
| **Fase 5** | **UI Cockpit & Autenticação Cloud** | ✅ Concluída | Persistência e comutação atómica de contas, atribuição de modelos por aldeia na Dashboard. |
| **Fase 6** | **Scripts de Sanitização e Purga** | ✅ Concluída | `scripts/sanitize_cloud_db.py` (purga transacional com preservação dos 5 modelos oficiais) e `scripts/purge_local_state.py` (purga local de caches e DBs legadas). |
| **Fase 7** | **Portal de Login Mandatório Pré-Hub** | ✅ Concluída | Ecrã primário exclusivo (`#app-portal-view`) para login/registo no programa. Ocultação total do Hub de Contas do Tribos, top-nav de automação e dados de jogo até autenticação com Cloud SQL. |
| **Fase 8** | **Persistência Total no Cloud SQL (`game_accounts`, `game_worlds`, `villages`)** | ✅ Concluída | Eliminação do desfasamento onde apenas `app_users` era gravado. Login no navegador integrado, criação manual de contas e leituras de aldeia (`fetch_all_villages_overview` / `refresh_state`) agora persistem ativamente e de forma relacional as contas, mundos e aldeias na base de dados Cloud SQL. |

---

## 3. Mapa de Ficheiros do Projeto

```text
TribalwarsBot/
├── PROJECT_STATE.md                     # [ESTE FICHEIRO] Estado consolidado e memória do projeto
├── GUIA_UTILIZADOR.md                   # Manual completo de operação para o utilizador
├── migrations/                          # Migrações Cloud SQL (PostgreSQL)
│   ├── 001_cloud_sql_init.sql           # DDL inicial da hierarquia relacional
│   └── 002_build_templates.sql          # Tabela de modelos de construção com auto-seed
├── scripts/                             # Scripts de Gestão e Manutenção
│   ├── sanitize_cloud_db.py             # Sanitização transacional Cloud SQL (preserva 5 modelos)
│   └── purge_local_state.py             # Purga de artefactos e caches locais do cliente
├── engine/                              # Python Core Engine
│   ├── storage/                         # Camada de Dados e Persistência
│   │   ├── cloud_db.py                  # CloudDatabase, repositórios CRUD e cofre AES-256-GCM
│   │   ├── token_storage.py             # TokenStorage: persistência encriptada de auth.dat
│   │   └── database.py                  # AccountsDatabase: SQLite em memória partilhada
│   ├── config/                          # Configurações do Bot
│   │   ├── settings.py                  # BotConfig sem I/O de disco
│   │   └── templates.py                 # 5 modelos padrão oficiais de construção imutáveis
│   ├── core/                            # Orquestração e Concorrência
│   │   ├── account_session_manager.py   # Singleton de exclusão mútua e troca atómica de contas
│   │   ├── world_worker_orchestrator.py # Workers multi-mundo concorrentes e isolamento de erros
│   │   ├── account.py                   # TribalAccount: requisições HTTP mobile, CSRF, parsing
│   │   ├── profile_manager.py           # Gestor de perfis em memória
│   │   └── scheduler.py                 # TaskScheduler com fila de prioridades e delays gaussianos
│   ├── actions/                         # Módulos de Jogo
│   │   ├── main_building.py             # Edifício Principal e auto-build por prioridades
│   │   ├── recruitment.py               # Recrutamento balanceado Quartel/Estábulo/Oficina
│   │   ├── farm.py                      # Assistente de Farm A/B e varredura de bárbaras
│   │   ├── place.py                     # Praça de Reunião e despacho de comandos
│   │   ├── scavenge.py                  # Coleta de recursos em 4 categorias
│   │   ├── snob.py                      # Academia, cunhagem e nobres
│   │   ├── defense.py                   # Alarme de ataques recebidos e esquiva (dodge)
│   │   ├── combat_tactics.py            # Táticas de ataque e snipagem
│   │   └── combat_sync.py               # Sincronização de relógio milissegundo
│   ├── api/                             # Camada REST / WebSocket Sidecar IPC
│   │   ├── server.py                    # Servidor FastAPI com /api/health e /api/auth-info
│   │   ├── routes.py                    # Endpoints REST (/api/auth/*, /api/accounts/*, etc.)
│   │   ├── context.py                   # EngineContext: orquestrador do sidecar
│   │   └── client.py                    # ApiClient para clientes remotos
│   ├── desktop_launcher.py              # Launcher Edge WebView2 com Bootstrap Gatekeeper
│   └── main.py                          # Ponto de entrada CLI/Desktop com validação Cloud
│
├── frontend/                            # Interface Gráfica Cockpit
│   ├── index.html                       # Layout, Account Hub, modal Cloud SQL e dashboard
│   ├── css/style.css                    # Design System Dark Glassmorphism e micro-animações
│   └── js/
│       ├── app.js                       # Controlador da UI, contas, mundos e modelos de aldeias
│       ├── api.js                       # Comunicação assíncrona com os endpoints do motor
│       └── websocket.js                 # Eventos em tempo real e telemetria
│
└── tests/                               # 316 testes unitários e de integração (100% OK)
```

---

## 4. Testes e Validação de Qualidade

* **Resultado da Suite Completa:**
  ```text
  ============================== 316 passed, 21 warnings in 41.52s ==============================
  ```
* **Cobertura Chave:**
  * Modelos relacionais e restrições de unicidade no Cloud SQL.
  * Cifra AES-256-GCM do cofre de credenciais e de `auth.dat`.
  * Hashing de senhas com Argon2 / bcrypt.
  * Exclusão mútua e troca atómica de contas (`AccountSessionManager`).
  * Concorrência paralela multi-mundo e isolamento de rate limits (`WorldWorkerOrchestrator`).
  * Endpoints REST de autenticação, contas, mundos e modelos de aldeias.
  * Auto-seeding e persistência dos 5 modelos oficiais de construção.
