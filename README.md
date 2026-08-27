# Tribal Wars Mobile Automation Engine (Standalone Client)

Cliente desktop autónomo, modular e de baixo consumo de recursos para o jogo Tribal Wars (versão mobile/`page=mobile`), focado em evasão de assinaturas de rede (TLS/JA3/JA4) via `curl_cffi` e simulação de comportamento humano.

---

## 📁 Estrutura do Repositório

```text
TribalwarsBot/
├── engine/                          # Python Core Engine
│   ├── api/                         # Camada de comunicação IPC / FastAPI com Tauri
│   ├── core/                        # Núcleo da automação
│   │   ├── account.py               # Classe base TribalAccount (curl_cffi AsyncSession)
│   │   ├── exceptions.py            # Hierarquia de exceções (BotProtection, SessionExpired, etc.)
│   │   ├── models.py                # Modelos de dados (Resources, VillageData, Task, TaskPriority)
│   │   └── scheduler.py             # Motor asyncio.PriorityQueue com preempção e pausas de segurança
│   ├── actions/                     # Ações por ecrã (main, place, barracks, scavenge)
│   ├── utils/                       # Parsers HTML/game_data e temporização gaussiana
│   │   ├── parsers.py               # Extração de game_data, CSRF token e deteção de bot
│   │   └── timing.py                # Atrasos normais/gaussianos e micro-jitters humanos
│   ├── config/                      # Gestão de perfis e contas
│   └── main.py                      # Ponto de entrada / CLI runner
│
├── src-tauri/                       # Backend Desktop Nativo (Rust / Tauri v2)
│   └── (Estrutura de gestão de janelas, sidecar Python e WebView para captcha)
│
├── src-ui/                          # Frontend Desktop (Dashboard React/Svelte)
│
├── tests/                           # Suíte de testes unitários
│   └── test_core.py                 # Testes de modelos, timing, parsers, account e scheduler
│
├── pyproject.toml                   # Configuração de projeto e dependências Python
└── requirements.txt
```

---

## 🚀 Como Executar os Testes

Para executar toda a suíte de testes unitários:

```powershell
python -m unittest discover tests
```

---

## 🛡️ Evasão de Assinaturas e Segurança Anti-Bot

1. **Fingerprint TLS/JA3/JA4:** Uso de `curl_cffi` com `impersonate="chrome124"` mascarando o aperto de mão criptográfico TLS.
2. **Headers Móveis Estritos:** `Sec-CH-UA-Mobile: ?1`, `Sec-CH-UA-Platform: "Android"`, `page=mobile`.
3. **Temporização Não-Determinística:** Delays com distribuição gaussiana truncada (`get_human_delay`) e micro-jitters tácteis (`get_click_jitter`).
4. **Pausa Imediata em Anti-Bot:** Ao detetar elementos de captcha (`id="bot_protect"`, `name="bot_check"`), a fila de tarefas é pausada instantaneamente para proteger a conta.
