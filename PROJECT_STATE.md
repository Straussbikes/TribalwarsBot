# Tribal Wars Bot - Estado do Projeto e Contexto Operacional

> **Propósito deste ficheiro:** Manter o histórico de progresso, decisões arquiteturais, mapa de ficheiros e diretrizes de desenvolvimento para que qualquer sessão de IA recupere o contexto instantaneamente com consumo mínimo de tokens e sem perda de continuidade.

**Última Atualização:** 2026-08-27  
**Estado Geral:** Fase 2 em Progresso (Edifício Principal, Praça de Reunião e Micro-Farming Concluídos)  
**Ambiente Validado:** Windows 11 / Python 3.14 / `curl_cffi` 0.16.2 / Node.js v25.8.1

---

## 1. Visão Geral e Arquitetura

* **Conceito:** Cliente desktop autónomo (*estilo PS Evolution*) para automação do jogo Tribal Wars (Tribos).
* **Camada de Rede:** Emulação pura HTTP sobre a versão mobile (`page=mobile`), sem Chromium pesado, com consumo ultrabaixo de RAM/CPU.
* **Evasão de Assinaturas (TLS/JA3/JA4):** `curl_cffi` com `impersonate="chrome124"`, headers consistentes de Chrome Mobile Android (`Sec-CH-UA-Mobile: ?1`, `Sec-CH-UA-Platform: "Android"`).
* **Arquitetura de Processos (Sidecar Pattern):**
  * **Shell Desktop:** Tauri (Rust) para janela nativa, system tray e WebView popup para resolução manual de captchas.
  * **Core Engine:** Python (AsyncIO) rodando desacoplado como sidecar, orquestrando rede e agendamento.
  * **Comunicação IPC:** FastAPI / WebSockets locais com token efêmero.

---

## 2. Roadmap e Progresso das Fases

| Fase | Descrição | Status | Detalhes |
|---|---|---|---|
| **Fase 1** | **Fundação do Core & Rede** | ✅ Concluída | Estrutura modular, `TribalAccount`, `TaskScheduler`, parsers e 10 testes unitários. |
| **Fase 2** | **Módulos de Ações (`game.php`)** | 🔄 Em Curso | `main` (Edifício Principal), `place` (Praça de Reunião) e `farm` (Micro-Farming) concluídos. Total de 39 testes unitários. Próximos: `scavenge` e `barracks`. |
| **Fase 3** | **Camada Sidecar IPC & Sessões** | 📋 Pendente | Servidor local FastAPI/WebSocket, autenticação local, persistência multi-conta. |
| **Fase 4** | **Frontend Tauri & Integração** | 📋 Pendente | Shell desktop Tauri v2, interface de logs, controlos e WebView de captcha. |

---

## 3. Mapa de Ficheiros do Projeto

```text
TribalwarsBot/
├── PROJECT_STATE.md                 # [ESTE FICHEIRO] Estado consolidado e memória do projeto
├── TODO.md                          # Checklist detalhado e acionável de todas as funcionalidades
├── README.md                        # Documentação pública e instruções rápidas
├── pyproject.toml                   # Configuração de empacotamento e dependências Python
├── requirements.txt                 # Dependências diretas (curl_cffi, pydantic, fastapi, uvicorn)
├── config.json                      # Configuração personalizável (mundo, sid, templates, fila, farm)
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
│   │   ├── parsers.py               # Extração de game_data, CSRF, recursos, bot protect, níveis, fila, tropas, confirmações e AF
│   │   └── timing.py                # get_human_delay (gaussiano), get_click_jitter
│   ├── actions/                     # Handlers por ecrã (Fase 2)
│   │   ├── __init__.py              # Exporta MainBuildingManager, PlaceManager, FarmManager, templates e tipos
│   │   ├── main_building.py         # MainBuildingManager: leitura, níveis virtuais, auto-build, cancelamento
│   │   ├── place.py                 # PlaceManager: leitura de tropas, capacidade de saque, comandos em 2 etapas
│   │   └── farm.py                  # FarmManager: Assistente de Farm (A/B), filtros de segurança, fallback Praça
│   ├── api/                         # Camada de comunicação IPC com Tauri (Fase 3)
│   │   └── __init__.py
│   ├── config/                      # Configurações e carregamento de perfis
│   │   ├── __init__.py
│   │   └── settings.py              # BotConfig, BuildingConfig, FarmConfig, load_config a partir de config.json
│   └── main.py                      # Ponto de entrada CLI com carregamento dinâmico de config.json
│
├── tests/                           # Suíte de testes unitários automatizados (39 testes, 100% OK)
│   ├── __init__.py
│   ├── test_core.py                 # 10 testes cobrindo models, timing, parsers, account e scheduler
│   ├── test_main_building.py        # 11 testes cobrindo níveis, fila, templates, auto-build e cancelamento
│   ├── test_config.py               # 2 testes cobrindo parsing de config.json e seleção de templates
│   ├── test_place.py                # 10 testes cobrindo tropas, capacidade de carga, comandos e envio em 2 etapas
│   └── test_farm.py                 # 6 testes cobrindo Assistente de Farm, modelos A/B, filtros e fallback
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
   * Comportamento: Disparo imediato da exceção, **pausa instantânea do `TaskScheduler`**, preservação da tarefa na fila e disparo de eventos assíncronos para o utilizador resolver o captcha na WebView.
4. **Comandos Militares em 2 Etapas:** Sempre validar em 2 passos (`try=confirm` -> `action=command`), extraindo o hash de segurança do servidor (`chck`).
5. **Micro-Farming Seguro:**
   * Nunca disparar ataques simultâneos no mesmo milissegundo. Usar jitter de toque humano (200ms a 550ms) entre cliques na lista de saques.
   * Filtragem de segurança obrigatória: ignorar perdas (`skip_losses`) e ignorar aldeias com muralha ativa (`skip_wall`).
6. **Temporização Realista:**
   * Nunca usar atrasos fixos (`sleep(5)` é proibido em produção).
   * Usar `get_human_delay(base, std_dev, min, max)` (distribuição normal truncada).
   * Adicionar micro-jitters mecânicos de toque em ecrã com `get_click_jitter()` (120ms - 380ms).
7. **Windows Event Loop Policy:** No Windows, utilizar `asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())` para compatibilidade estrita com os sockets do `curl_cffi`.

---

## 5. Como Validar o Estado Atual

Para rodar os testes automatizados da suíte completa (Fases 1 e 2):
```powershell
python -m unittest discover tests -v
```
*Status esperado:* 39 testes, 0 falhas (`OK`), cobrindo modelos, delays gaussianos, parsers, anti-bot, account, scheduler, níveis virtuais, auto-build, configurações, praça de reunião (envio em 2 etapas) e micro-farming (Assistente de Farm e filtros).

Para testar no jogo real (online):
```powershell
python -m engine.main
```
*Validado:* Conexão online estabelecida no mundo `pt117`, leitura de aldeia/recursos em tempo real, auto-build e rotina de auto-farm respeitando `config.json`.



