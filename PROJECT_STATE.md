# Tribal Wars Bot - Estado do Projeto e Contexto Operacional

> **Propósito deste ficheiro:** Manter o histórico de progresso, decisões arquiteturais, mapa de ficheiros e diretrizes de desenvolvimento para que qualquer sessão de IA recupere o contexto instantaneamente com consumo mínimo de tokens e sem perda de continuidade.

**Última Atualização:** 2026-09-05  
**Estado Geral:** 100% Cloud-Native Concluído | Cloud SQL (PostgreSQL 18.6) via Neon Tech | Eliminação de I/O em disco local | Cofre Criptográfico AES-256-GCM (`TokenStorage` para `auth.dat`) | 5 Modelos Oficiais Imutáveis de Construção (Modelo *Construcao* com 256 passos sincronizado) | Auto-Login com cifra AES-256-GCM e tolerância a quedas de sessão | Gestor Monousuário (`AccountSessionManager`) & Orquestrador Concorrente Multi-Mundo (`WorldWorkerOrchestrator`) | Gestão Comercial de Licenças e Subscrições (`manage_clients.py`) | Pipeline de Build Standalone Comercial (GUI Pura, noconsole, Inno Setup 6, ~66 MB EXE / 182 MB Setup) | Distinção Estrita de Tropas da Aldeia (`own_troops`) vs Tropas na Aldeia (`troops_in_village`) no Recrutamento | 350 Testes Unitários e de Integração Automatizados (100% OK)  
**Ambiente Validado:** Windows 11 / macOS 12+ / Python 3.11-3.14 / `curl_cffi` 0.16.2 / `fastapi` 0.141.1 / `uvicorn` 0.52.4 / `pywebview` 6.2 (Edge WebView2) / PostgreSQL 18.6 Cloud SQL / Inno Setup 6 / Git Branch: `main`

---

## 1. Visão Geral e Arquitetura

* **Conceito:** Cliente desktop autónomo para automação multi-mundo do jogo Tribal Wars (Tribos) com arquitetura distribuída 100% Cloud-Native e distribuição comercial profissional.
* **Camada de Dados Cloud SQL (PostgreSQL 18.6):**
  * Conexão gerenciada em `engine/storage/cloud_db.py` com SSL/TLS mandatário (`sslmode=require&channel_binding=require`) no Neon Tech.
  * Hierarquia relacional estrita:
    * `app_users`: contas da aplicação com hash de password Argon2/bcrypt, controlo de subscrição (`expires_at`), estado ativo/suspenso (`is_active`), limite de contas (`max_accounts`) e notas comerciais (`notes`).
    * `game_accounts`: contas do jogo com cofre criptográfico AES-256-GCM para credenciais/SIDs/passwords.
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
    1. `ee02gd68de` — **AI - Build Model** (Equilibrado para Academia e Conquistas)
    2. `zbhbufxza0q` — **Construcao** (Sequência completa de 256 passos sincronizada no Cloud SQL e SQLite)
    3. `4zyrtbsdxa` — **Upar Barbara** (Maximização de recursos 30/30/30)
    4. `rtk1zhvuvtr` — **Sprinter BR131** (Corrida militar agressiva de início de mundo)
    5. `6goivjbmzbh` — **Pontos Premium** (Otimizado para farm e venda no mercado)
  * Dropdown dinâmico na aba Dashboard sincronizado em tempo de execução com o motor.
* **Sistema de Auto-Login & Restauro Transparente:**
  * `TribalWarsAuthHandler` em `engine/core/auth_handler.py`: realiza autenticação web real, extração de cookies e resolução de mundo.
  * Credenciais protegidas no cofre AES-256-GCM do Cloud SQL.
  * Deteção imediata de CAPTCHA sem loops destrutivos (pausa segura e alerta).
* **Exclusão Mútua & Orquestração Multi-Mundo:**
  * **`AccountSessionManager` (Singleton):** Garante que apenas 1 conta de jogo tem execução ativa por processo, usando `cancellation_token` para terminação limpa na alternância de contas.
  * **`WorldWorkerOrchestrator`:** Executa múltiplos mundos em paralelo sob a conta ativa, com instâncias desacopladas e isolamento de rate limits HTTP 429.
* **Bootstrap Gatekeeper & Gestão de Licenças:**
  * Valida conectividade com Cloud SQL e validade da licença (`is_active` e `expires_at`) no arranque e em todas as tentativas de login.
  * Bloqueio imediato com aviso amigável caso a subscrição esteja expirada ou suspensa.
  * Verificação do limite de contas associadas (`max_accounts`).
* **Packaging & Hardening Comercial (PyInstaller + Inno Setup):**
  * Executável compilado em modo puro GUI (`--noconsole` / `windowsgui`) com supressão de CMD residual via ctypes.
  * Redirecionamento de `sys.stdout` e `sys.stderr` para `SafeStreamWriter` protegendo contra falhas `NoneType`.
  * Logs operacionais direcionados silenciosamente para `%APPDATA%/TribalWarsBot/logs/tribalwars_bot.log` com `RotatingFileHandler` (5 MB, 3 backups).
  * Instalador nativo profissional Windows (`TribalWarsBot_Setup_v2.0.0.exe`) com ícone oficial, desinstalador limpo e atalho no Desktop.

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
| **Fase 8** | **Persistência Total no Cloud SQL (`game_accounts`, `game_worlds`, `villages`)** | ✅ Concluída | Persistência relacional de contas, mundos e aldeias na base de dados Cloud SQL com isolamento por `app_user_id`. |
| **Fase 9** | **Auto-Login & Restauro Transparente de Sessão HTTP** | ✅ Concluída | `TribalWarsAuthHandler` (`engine/core/auth_handler.py`), cofre seguro para passwords, suporte a auto-login na UI com botão de teste e deteção anti-loop de CAPTCHA. |
| **Fase 10** | **Saneamento Relacional & Desacoplamento de `default_main`** | ✅ Concluída | Eliminação de referências legadas a `"default_main"`, resolução estrita do UUID real da conta e integridade de chaves estrangeiras. |
| **Fase 11** | **Atualização e Sincronização do Modelo "Construcao"** | ✅ Concluída | Atualização integral da sequência de 256 passos em `templates.py`, SQLite e Cloud SQL; carregamento dinâmico de modelos reais no dropdown da Dashboard. |
| **Fase 12** | **Hardening do Executável & Instalador Inno Setup** | ✅ Concluída | Compilação com supressão de consola, sanitização de streams, logging rotativo em `%APPDATA%`, ícone Windows multi-resolução, gerador `TribalWarsBot_Setup_v2.0.0.exe` (182 MB) e pacote portátil (268 MB). |
| **Fase 13** | **Gestão Comercial de Licenças & Onboarding de Clientes** | ✅ Concluída | Campos comerciais em `app_users`, CLI administrativa `scripts/manage_clients.py` (criar, renovar, suspender, info), validação em runtime de expiração/suspensão e guia de distribuição [`GUIA_CLIENTE.md`]. |
| **Fase 14** | **Distinção Estrita de Tropas da Aldeia vs. Tropas na Aldeia** | ✅ Concluída | Extração oficial de contagens `own_units` (padrão `X/Y` no Quartel/Estábulo/Oficina e `screen=place&mode=units`), cálculo de metas militares baseado no exército total pertencente à aldeia (`own_troops`), blindagem contra sobre-recrutamento com tropas fora em ataque/farm/apoio e atualização do Cockpit. |
| **Fase 15** | **Auditoria de Código, Limpeza & Lançamento da Versão 1.2** | ✅ Concluída | Auditoria estrita e eliminação de código morto/stubs, alinhamento total Frontend-Backend (117 endpoints), tratamento explícito de exceções, 353 testes aprovados, compilação de produção e empacotamento com Inno Setup (`TribalWarsBot_Setup_v1.2.0.exe` e pacote portátil `TribalWarsBot_v1.2.0_Portable.zip`). |

---

## 3. Mapa de Ficheiros do Projeto

```text
TribalwarsBot/
├── PROJECT_STATE.md                     # [ESTE FICHEIRO] Estado consolidado e memória do projeto
├── GUIA_UTILIZADOR.md                   # Manual completo de operação para o utilizador
├── GUIA_CLIENTE.md                      # Guia rápido de 1 página para envio a novos clientes comerciais
├── TribalWarsBot.spec                   # Especificação PyInstaller (noconsole, hiddenimports, assets)
├── file_version_info.txt                # Metadados oficiais de versão do executável Windows
├── build_executable.py                  # Script de automação do build PyInstaller com validações
├── build_installer.py                   # Gerador automatizado do instalador Inno Setup e ZIP portátil
├── installer.iss                        # Script de compilação Inno Setup 6 (ícone, atalhos, lzma2)
├── assets/                              # Artefactos visuais e ícones
│   ├── icon.ico                         # Ícone oficial Windows (multi-camada 16x16 a 256x256)
│   └── icon_original.png                # Imagem original fornecida para geração do ícone
├── migrations/                          # Migrações Cloud SQL (PostgreSQL)
│   ├── 001_cloud_sql_init.sql           # DDL inicial da hierarquia relacional
│   └── 002_build_templates.sql          # Tabela de modelos de construção com auto-seed
├── scripts/                             # Scripts de Gestão e Manutenção
│   ├── manage_clients.py                # CLI administrativa de gestão de clientes e licenças
│   ├── sanitize_cloud_db.py             # Sanitização transacional Cloud SQL (preserva 5 modelos)
│   └── purge_local_state.py             # Purga de artefactos e caches locais do cliente
├── engine/                              # Python Core Engine
│   ├── storage/                         # Camada de Dados e Persistência
│   │   ├── cloud_db.py                  # CloudDatabase, repositórios CRUD, cofre AES-256-GCM e licenças
│   │   ├── token_storage.py             # TokenStorage: persistência encriptada de auth.dat
│   │   └── database.py                  # AccountsDatabase: SQLite em memória partilhada
│   ├── utils/                           # Utilitários de Runtime e Packaging
│   │   ├── paths.py                     # resource_path() e caminhos de sistema (%APPDATA%)
│   │   ├── runtime.py                   # SafeStreamWriter e supressão de consola
│   │   └── logging_setup.py             # setup_production_logging() com RotatingFileHandler
│   ├── config/                          # Configurações do Bot
│   │   ├── settings.py                  # BotConfig sem I/O de disco
│   │   └── templates.py                 # 5 modelos padrão oficiais de construção imutáveis
│   ├── core/                            # Orquestração e Concorrência
│   │   ├── account_session_manager.py   # Singleton de exclusão mútua e troca atómica de contas
│   │   ├── world_worker_orchestrator.py # Workers multi-mundo concorrentes e isolamento de erros
│   │   ├── auth_handler.py              # TribalWarsAuthHandler: auto-login e deteção de CAPTCHA
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
│   │   ├── server.py                    # Servidor FastAPI montando frontend com resource_path()
│   │   ├── routes.py                    # Endpoints REST (/api/auth/*, /api/accounts/*, etc.)
│   │   ├── context.py                   # EngineContext com validação de licença e auto-login
│   │   └── client.py                    # ApiClient para clientes remotos
│   ├── desktop_launcher.py              # Launcher Edge WebView2 com Bootstrap Gatekeeper
│   └── main.py                          # Ponto de entrada CLI/Desktop com validação Cloud
│
├── frontend/                            # Interface Gráfica Cockpit
│   ├── index.html                       # Layout, Account Hub, modal Cloud SQL, auto-login e dashboard
│   ├── css/style.css                    # Design System Dark Glassmorphism e micro-animações
│   └── js/
│       ├── app.js                       # Controlador da UI, contas, auto-login e modelos dinâmicos
│       ├── api.js                       # Comunicação assíncrona com os endpoints do motor
│       └── websocket.js                 # Eventos em tempo real e telemetria
│
└── tests/                               # 350 testes unitários e de integração (100% OK)
    ├── test_recruitment_own_troops.py   # Testes de tropas próprias da aldeia vs tropas na aldeia
    ├── test_auto_login.py               # Testes de cofre, autenticação web e auto-login
    ├── test_packaging_utils.py          # Testes de caminhos, streams e logging de produção
    ├── test_commercial_licensing.py     # Testes de licenças, expiração e limites de conta
    └── ...                              # Testes de core, combate, farm, defesa e API
```

---

## 4. Testes e Validação de Qualidade

* **Resultado da Suite Completa:**
  ```text
  ============================== 350 passed, 21 warnings in 60.73s ==============================
  ```
* **Cobertura Chave:**
  * Modelos relacionais, migrações automáticas e integridade de FKs no Cloud SQL.
  * Cifra AES-256-GCM de credenciais, palavras-passe de auto-login e de `auth.dat`.
  * Hashing de senhas com Argon2 / bcrypt.
  * Exclusão mútua e troca atómica de contas (`AccountSessionManager`).
  * Concorrência paralela multi-mundo e isolamento de rate limits (`WorldWorkerOrchestrator`).
  * Endpoints REST de autenticação, contas, mundos e modelos de aldeias.
  * Auto-seeding e persistência dos 5 modelos oficiais de construção (incluindo o modelo `Construcao` de 256 passos).
  * Hardening de packaging: `resource_path()`, `SafeStreamWriter` e logging de produção.
  * Gestão de licenças: suspensão manual, data de expiração, bloqueio em runtime e limites de contas.
  * Distinção rigorosa de tropas pertencentes à aldeia (`own_troops`) vs tropas presentes (`troops_in_village`), blindando o recrutamento contra ataques em curso ou apoios externos.
