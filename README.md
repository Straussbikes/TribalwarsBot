# Tribal Wars Mobile Automation Engine (v2.0.0 Desktop Standalone)

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Tests Passing](https://img.shields.io/badge/tests-299%20passed-brightgreen.svg)]()
[![Platform](https://img.shields.io/badge/platform-Windows%2010%2F11-lightgrey.svg)]()
[![License](https://img.shields.io/badge/license-MIT-green.svg)]()

Cliente desktop nativo, autónomo e de alto desempenho para automação e gestão tática do jogo **Tribal Wars** (Tribos). Projetado para operar via interface móvel (`page=mobile`), utiliza evasão avançada de impressões digitais TLS/JA3/JA4 através de `curl_cffi`, temporização gaussiana com micro-jitters humanos e integração visual via **Edge WebView2** com **FastAPI + WebSockets**.

---

## ⚡ Destaques & Capacidades Operacionais

1. **Evasão Avançada & Segurança Anti-Bot:**
   - Mascaramento criptográfico de TLS/JA3/JA4 (`impersonate="chrome124"`).
   - Headers móveis estritos (`Sec-CH-UA-Mobile: ?1`, `Sec-CH-UA-Platform: "Android"`).
   - Atrasos de reação humana modelados por distribuição gaussiana truncada e micro-jitters táteis.
   - Resolução de captcha assistida: pausa imediata das filas de tarefas, alarme sonoro integrado e abertura de janela nativa Edge WebView2 para resolução humana com 1 clique.
   - Resiliência de rede com reconexão automática (`max_network_retries=3`) e restabelecimento transparente de sessão em caso de instabilidade de Wi-Fi ou ISP.

2. **Gestão Económica & Infraestrutura:**
   - **Edifício Principal:** Filas de construção prioritárias por templates, desbloqueio de pré-requisitos em modo *rush*, cancelamento preventivo e redução de tempos.
   - **Recrutamento Balanceado:** Proporções automáticas para modelos ofensivos e defensivos (Quartel, Estábulo e Oficina) com paragem inteligente no limite de população.
   - **Coleta de Recursos (Scavenging):** Distribuição matemática ótima de tropas entre as 4 categorias de expedição (Preguiçosa, Humilde, Inteligente e Pesada) com monitor em tempo real e botão de disparo imediato.
   - **Assistente de Saque & Farm de Bárbaras:** Varredura radial automática de aldeias bárbaras num raio configurável, prevenção de ataques concorrentes, paragem preventiva em caso de perdas amarelas/vermelhas e inclusão automática de bárbaras não catalogadas via Praça de Reuniões.

3. **Operações Militares, Snipes & Táticas:**
   - **Comboio de Nobres (Noble Train Builder):** Criação de comboios de 4 ou 5 nobres com espaçamento milimétrico (ex.: 50ms a 100ms), divisão tática de escolta (limpeza no 1º nobre) e compensação de latência de rede (*ping offset*).
   - **Calculadora & Snipe Defensivo:** Cálculo instantâneo da janela ideal de envio para inserção de defesa num milissegundo exato (`HH:MM:SS.mmm`).
   - **Cancel-Snipe:** Agendamento de ataque a aldeia bárbara e cálculo do momento exato para cancelamento com retorno cirúrgico milimétrico à aldeia.
   - **Painel Incomings HUD & Auto-Dodge:** Monitorização de ataques recebidos em tempo real com alarme sonoro militar, identificação da unidade mais lenta atacante e desvio automático de tropas (Auto-Dodge) para bárbaras antes do impacto.

4. **Academia, Mercado & Inventário:**
   - **Cunhagem de Moedas Automática:** Ativação por limite percentual do armazém com monitor diário.
   - **Mercado & Balanço de Recursos:** Criação e gestão de ofertas de troca e rotas comerciais.
   - **Inventário:** Catálogo de bónus e ativação manual segura com modal de confirmação.

---

## 📁 Arquitetura do Repositório

```text
TribalwarsBot/
├── engine/                          # Núcleo Python da Automação
│   ├── main.py                      # Ponto de entrada CLI e orquestrador
│   ├── desktop_launcher.py          # Launcher Desktop nativo com Edge WebView2 (pywebview)
│   ├── api/                         # Sidecar IPC (FastAPI + WebSockets em tempo real)
│   │   ├── server.py                # Fábrica FastAPI, CORS, autenticação e montagem do frontend
│   │   ├── routes.py                # Endpoints REST para todas as operações
│   │   ├── websocket.py             # Streaming de telemetria, logs e alarmes acústicos
│   │   └── context.py               # Contexto compartilhado do motor
│   ├── core/                        # Motor da Conta e Escalonador
│   │   ├── account.py               # TribalAccount com curl_cffi e reconexão automática
│   │   ├── scheduler.py             # Fila de prioridades com preempção e pausas de segurança
│   │   ├── models.py                # Dataclasses de aldeias, recursos, tarefas e tropas
│   │   └── stats.py                 # Telemetria estatística e persistência de métricas
│   ├── actions/                     # Ações específicas por ecrã do jogo
│   │   ├── main_building.py         # Gestão de edifícios e filas de construção
│   │   ├── recruitment.py           # Recrutamento balanceado de tropas
│   │   ├── farm.py                  # Assistente de saque e farm radial
│   │   ├── scavenge.py              # Algoritmo de coleta balanceada
│   │   ├── combat_tactics.py        # Comboios de nobres, snipes e cancel-snipes
│   │   ├── combat_sync.py           # Sincronização de relógio e medição de ping
│   │   ├── defense.py               # Monitor de incomings e auto-dodge
│   │   ├── snob.py                  # Cunhagem automática de moedas
│   │   ├── market.py                # Balanço e ofertas de mercado
│   │   └── inventory.py             # Visualizador e ativador de itens
│   ├── storage/                     # Persistência de dados
│   │   ├── database.py              # Base de dados de contas (SQLite)
│   │   └── world_database.py        # Base de dados de aldeias e mundos (SQLite)
│   └── utils/                       # Parsers HTML e temporização gaussiana
│
├── frontend/                        # Dashboard Web / Desktop nativo
│   ├── index.html                   # Interface gráfica SPA com design escuro moderno
│   ├── css/style.css                # Sistema de design modular e componentes visuais
│   └── js/                          # Lógica de interface
│       ├── app.js                   # Controlador da interface gráfica e abas
│       ├── api.js                   # Cliente REST assíncrono
│       └── websocket.js             # Gestor de WebSockets com reconexão exponencial
│
├── dist/                            # Executáveis e instaladores compilados
│   ├── TribalWarsBot/               # Diretório distribuível com TribalWarsBot.exe
│   └── TribalWarsBot_v2.0.0_Portable.zip # Pacote ZIP portátil pronto a usar
│
├── tests/                           # Suíte exaustiva de testes automatizados (299 testes)
├── TribalWarsBot.spec               # Especificação PyInstaller para build nativo Windows
├── build_executable.py              # Script de compilação com PyInstaller
├── build_installer.py               # Script de geração do pacote de release e instalador
├── installer.iss                    # Script do compilador Inno Setup
└── GUIA_UTILIZADOR.md               # Manual completo de utilização em Português
```

---

## 🚀 Como Executar

### Opção 1: Executável Nativo Windows (Recomendado)

Não requer Python instalado. Descompacte `TribalWarsBot_v2.0.0_Portable.zip` ou navegue para `dist/TribalWarsBot/`:

1. Execute **`TribalWarsBot.exe`** (duplo clique).
   - Inicia o motor em background e abre a janela desktop nativa via Microsoft Edge WebView2.
2. Opcional: Execute **`Criar_Atalho_Ambiente_Trabalho.bat`** para criar um atalho no seu Ambiente de Trabalho.

### Opção 2: A partir do Código-Fonte (Modo Desenvolvedor)

Certifique-se de ter Python 3.10+ instalado:

```powershell
# 1. Instalar dependências
pip install -r requirements.txt

# 2. Iniciar a aplicação Desktop com GUI
python engine/main.py --desktop

# 3. Ou iniciar apenas o servidor API/Web (aceda em http://127.0.0.1:8000)
python engine/main.py --api --port 8000
```

---

## 🧪 Executar a Suíte de Testes Automatizados

O projeto inclui **299 testes unitários e de integração** cobrindo todos os módulos, parsers, reconexão de rede e lógica militar:

```powershell
python -m pytest
```

---

## 📦 Compilar Nova Versão do Executável

Para compilar novamente o executável e gerar os artefactos de release:

```powershell
# 1. Compilar o executável com PyInstaller
python build_executable.py

# 2. Gerar o pacote portátil ZIP e script de atalho (e instalador Inno Setup se instalado)
python build_installer.py
```

---

## 📖 Documentação Adicional

Consulte o manual de utilizador detalhado em [**GUIA_UTILIZADOR.md**](GUIA_UTILIZADOR.md) para instruções passo a passo de configuração de contas, modelos de tropas, estratégias de farm e boas práticas anti-ban.
