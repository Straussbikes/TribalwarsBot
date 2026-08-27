# Tribal Wars Bot - Lista de Tarefas (TODO)

> **Regra de Manutenção:** Este ficheiro deve ser mantido atualizado a cada avanço no projeto. Sempre que uma funcionalidade for concluída ou modificada, marcar a respetiva caixa de seleção `[x]` e atualizar o registo em `PROJECT_STATE.md`.

---

## 📌 Fase 1: Fundação do Core Engine & Evasão de Rede
- [x] **Arquitetura Base & Configuração**
  - [x] Estrutura modular de pastas (`engine/core`, `engine/utils`, `engine/actions`, `engine/api`, `tests`).
  - [x] Definição de dependências em `pyproject.toml` e `requirements.txt`.
  - [x] Configuração de `.gitignore` para ignorar caches Python e ficheiros temporários.
- [x] **Camada de Rede & Mascaramento Criptográfico (TLS/JA3)**
  - [x] Cliente `TribalAccount` com `curl_cffi` (`AsyncSession` + `impersonate="chrome124"`).
  - [x] Headers móveis Android (`Sec-CH-UA-Mobile: ?1`, `Sec-CH-UA-Platform: "Android"`).
  - [x] Injeção dinâmica do cookie de sessão `sid` nos domínios do mundo e raiz.
  - [x] Forçamento do parâmetro `page=mobile` em todas as rotas GET/POST.
  - [x] Tratamento de erros HTTP, rate limiting (HTTP 429) e manutenção de servidores (502/503).
  - [x] Método `account.update_sid(new_sid)` para encerramento limpo e reconstrução atómica de sessão.
- [x] **Deteção de Anti-Bot & Gestão de Sessão**
  - [x] Interceção de marcadores anti-bot (`id="bot_protect"`, `name="bot_check"`) disparando `BotProtectionError`.
  - [x] Deteção de expiração de sessão / ecrã de boas-vindas disparando `SessionExpiredError`.
  - [x] **Autenticação Manual & Interceção de Rede (`sid`)**
    - [x] Intercetor de tráfego HTTP em tempo real (`request_sent` / `response_received`) no WebView2 para captura imediata de cookies `sid` (incluindo `HttpOnly`).
    - [x] Auto-persistência atómica do cookie `sid` no `config.json` perante rotação do servidor (`save_config_sid`).
    - [x] Rotina periódica suave de **Keep-Alive** no `TaskScheduler` (~15 min) para impedir expiração por inatividade.
    - [x] Botão rápido "🔑 Entrar / Login" no Cockpit para abertura da janela nativa.
    - [x] Banner informativo injetado no ecrã de login com botão interativo `[Entrei no Jogo →]`.
    - [x] Suíte de testes unitários dedicada (`tests/test_auth.py` com 7 testes).
- [x] **Temporização Humana & Micro-Jitters**
  - [x] Gerador de atrasos gaussianos truncados (`get_human_delay`).
  - [x] Micro-jitters mecânicos de toque em ecrã (`get_click_jitter`: 120ms a 380ms).
- [x] **Agendador de Tarefas com Fila de Prioridade**
  - [x] `TaskScheduler` assíncrono baseado em `asyncio.PriorityQueue`.
  - [x] Níveis de prioridade: `ALERT (0)` > `DEFENSE (10)` > `FARM (20)` > `SCAVENGE (30)` > `BUILD (40)` > `RECRUIT (50)` > `REFRESH (90)`.
  - [x] **Auto-pausa instantânea** perante alerta anti-bot com preservação da tarefa na fila.
  - [x] Suporte a preempção e retentativas com backoff exponencial.
- [x] **Testes do Core**
  - [x] 10 testes unitários cobrindo modelos, timing, parsers, account e scheduler.

---

## 📌 Fase 2: Módulos de Ações do Jogo (`game.php`)

### 2.1. Edifício Principal (`screen=main`)
- [x] Parsing de níveis de edifícios via `game_data.village.buildings` e fallback HTML.
- [x] Parsing da fila ativa de construção (`#buildqueue`) com extração de tempo e token de cancelamento.
- [x] Parsing de custos de melhoria, população e motivos de indisponibilidade (recursos, armazém, fazenda, requisitos).
- [x] Normalização de nomes de edifícios (português/inglês) e mapeamento canónico (`BuildingType`).
- [x] Árvore tecnológica de requisitos de edifícios (`BUILDING_REQUIREMENTS`).
- [x] Cálculo de **níveis virtuais** (`nível atual + construções pendentes na fila`).
- [x] Restrição de segurança de capacidade de fila (padrão de 2 construções sem custos extras).
- [x] Modelos de evolução pré-definidos (`RUSH_RESOURCES_TEMPLATE`, `BALANCED_TEMPLATE`, `MILITARY_RUSH_TEMPLATE`).
- [x] Controlador `MainBuildingManager` com disparo de `build` e `cancel` com token CSRF (`h`).
- [x] Rotina periódica contínua de auto-build com feedback imediato e ciclos humanos.
- [x] Sistema de configuração flexível via `config.json` e propriedade compatível `effective_building_plan`.
- [x] Suíte de testes unitários dedicada (12 testes do Edifício Principal + 2 de configuração).

### 2.2. Praça de Reunião & Gestão de Tropas (`screen=place`)
- [x] Parsing da contagem de tropas disponíveis na aldeia ativa (`spear`, `sword`, `axe`, `archer`, `spy`, `light`, `marcher`, `heavy`, `ram`, `catapult`, `knight`, `snob`).
- [x] Leitura de comandos em curso (tropas a atacar, apoiar ou a regressar à aldeia).
- [x] Módulo de envio de comandos (Ataque / Apoio) em 2 etapas:
  - [x] Etapa 1: Envio do formulário inicial com coordenadas de destino (`target_x`, `target_y` ou ID da aldeia) e contagem de tropas.
  - [x] Etapa 2: Confirmação do comando (`action=command&h=...`) com extração da duração da marcha e tipo de ataque.
- [x] Suíte de testes unitários para a Praça de Reunião (10 testes dedicados).

### 2.3. Micro-Farming Automatizado
- [x] Suporte a Assistente de Farm (`screen=am_farm`):
  - [x] Leitura da tabela de aldeias bárbaras vizinhas (`#plunder_list`).
  - [x] Leitura do estado dos relatórios (verde, amarelo, vermelho) e nível de muralha.
  - [x] Disparo automatizado dos modelos A e B com atrasos humanos entre toques (200ms - 550ms).
- [x] Fallback para Farming via Praça de Reunião (`screen=place`):
  - [x] Lista configurável de aldeias bárbaras por coordenadas ou raio de distância.
  - [x] Envio automático de micro-grupos de saque (ex.: 5 lanceiros ou 2 cavalarias leves).
- [x] Critérios de segurança: paragem imediata do farm caso as tropas sofram baixas (`skip_losses`) ou a muralha inimiga suba (`skip_wall`).
- [x] Suíte de testes unitários para Micro-Farming (6 testes dedicados).

### 2.4. Coleta de Recursos / Scavenging (`screen=place&mode=scavenge`)
- [ ] Leitura do estado de desbloqueio das 4 categorias de coleta (Lazy, Humble, Clever, Great).
- [ ] Parsing de grupos de coleta em andamento e contadores de tempo restante.
- [ ] **Algoritmo de Otimização de Coleta:** Cálculo proporcional da distribuição de tropas para retorno simultâneo.
- [ ] Disparo automático com timer e agendamento para reenvio.

### 2.5. Recrutamento Militar (Quartel, Estábulo, Oficina)
- [x] Parsing do ecrã do Quartel (`screen=barracks`), Estábulo (`screen=stable`) e Oficina (`screen=garage`).
- [x] Leitura das filas de recrutamento ativas e tempo de conclusão.
- [x] Configuração de metas de exército (ex.: lanceiros, espadachins, cavalaria leve).
- [x] Recrutamento inteligente em pequenos lotes contínuos para preservação de recursos.
- [x] Validação de limite de população livre da Fazenda antes de recrutar (`min_free_pop`).
- [x] Suíte de testes unitários para Recrutamento Militar (5 testes dedicados).

### 2.6. Academia & Cunha de Moedas (`screen=snob`)
- [ ] Leitura de moedas cunhadas / pacotes acumulados.
- [ ] Cunha automática de moedas quando o armazém estiver prestes a encher.
- [ ] Recrutamento automático de Nobres mediante configuração do utilizador.

### 2.7. Mercado & Balanceamento de Recursos (`screen=market`)
- [ ] Leitura de mercadores disponíveis e mercadores em trânsito.
- [ ] **Algoritmo de Balanceamento Automático de Recursos:**
  - [ ] Cálculo de médias e desvios de recursos entre todas as aldeias da mesma conta.
  - [ ] Identificação automática de aldeias doadoras (excedente ou risco de transbordamento de armazém) e aldeias recetoras (défice para construções ou recrutamento urgente).
  - [ ] Despacho automatizado de mercadores para transferência equilibrada de recursos entre aldeias.
- [ ] Criação de ofertas no mercado local para troca automática de recursos excedentes por recursos em carência.

### 2.8. Sistema de Defesa & Alarme de Ataques (Prioridade 0 / Alertas)
- [ ] Monitorização em tempo real de ataques a chegar à aldeia (`incomings`).
- [ ] Deteção da velocidade da unidade mais lenta atacante (estimativa de Nobre / Aríete).
- [ ] **Rotina de Auto-Dodge (Desvio de Tropas e Recursos):** Envio para aldeia bárbara 30s antes do impacto e cancelamento pós-impacto.
- [ ] Notificação sonora e visual de emergência.

### 2.9. Táticas de Combate & Sincronização ao Milissegundo (`screen=place`)
- [ ] **Sincronização com o Relógio do Servidor:**
  - [ ] Medição de latência de ida e volta (RTT) e cálculo contínuo de desvio (*server clock offset / drift*).
  - [ ] Ajuste dinâmico do agendador para disparo no instante exato `t_alvo - latency/2`.
- [ ] **Sniper de Nobres (Anti-Conquista):**
  - [ ] Identificação de comboios de nobres inimigos a caminho com extração dos tempos de chegada ao milissegundo.
  - [ ] Cálculo e disparo cirúrgico de apoios (da própria aldeia ou aldeias vizinhas) para intercalação entre o ataque de limpeza (*nuke*) e o primeiro nobre.
  - [ ] Tolerância de milissegundos configurável (ex.: janela de 50ms a 150ms).
- [ ] **Calculadora & Agendador de Backtime:**
  - [ ] Leitura da hora de retorno de tropas inimigas a partir de relatórios ou comandos visíveis.
  - [ ] Agendamento de contra-ataque de precisão para aterrar exatamente no mesmo segundo do regresso das tropas inimigas.
- [ ] **Comboio de Nobres Automatizado (Noble Train):**
  - [ ] Envio sequencial de 4 a 5 ataques com Nobre a partir da mesma aldeia com separação mínima de milissegundos permitida pelas regras do mundo (ex.: 50ms a 100ms).
  - [ ] Automação de distribuição de escolta (tropas de ataque distribuídas entre o primeiro nobre e os seguintes).
- [ ] **Fake Trains & Ataques Coordenados de Distração:**
  - [ ] Geração de ondas de ataques falsos (*fakes*) com aríetes/catapultas para simular nobres e dispersar a defesa inimiga.
- [ ] **Mecanismo de Cancelamento de Emergência (Fail-Safe):**
  - [ ] Verificação do milissegundo real de saída do comando após confirmação pelo servidor.
  - [ ] Cancelamento automático imediato do comando caso o desvio temporal exceda o limite de tolerância configurado.

### 2.10. Missões, Recompensas Diárias & Inventário (`screen=quest` / `screen=inventory`)
- [x] **Leitura e Extração de Missões do Sistema:**
  - [x] Parsing do estado das missões ativas e concluídas a partir do `game_data` e ecrãs dedicados (`screen=quest`).
  - [x] Identificação de tipos de recompensa (recursos, tropas imediatas, bónus temporários, bandeiras).
- [x] **Auto-Claim Inteligente de Recompensas:**
  - [x] Recolha automática de recompensas de missões concluídas com validação de capacidade do Armazém e Fazenda (para evitar desperdício de recursos ou população).
  - [x] Notificação de missões prontas para entrega e recompensas obtidas.
- [x] **Bónus Diário & Eventos:**
  - [x] Recolha automática do baú de login diário (*Daily Bonus*) no reset do servidor.
  - [x] Suporte a recolhas de recompensas gratuitas em eventos especiais e bónus sazonais.
- [x] **Gestão e Utilização de Itens do Inventário:**
  - [x] Parsing do inventário do jogador (`screen=inventory`).
  - [x] Ativação de itens do inventário estritamente mediante acionamento manual do utilizador (segurança garantida).
  - [x] Suíte de testes unitários dedicada (13 testes cobrindo missões, segurança de armazém/pop, baú diário e inventário manual).

### 2.11. Mapa Tático & Scanner de Bárbaras (`screen=map`)
- [x] **Extração e Leitura da Grelha do Mapa Oficial:**
  - [x] Parsing dos setores e tiles do mapa via requisições oficiais (`screen=map` e endpoints de mapa AJAX).
  - [x] Extração completa dos metadados de todas as aldeias visíveis: coordenadas `(X|Y)`, ID da aldeia, nome, jogador, tribo, pontos e bónus.
  - [x] Deteção e categorização de aldeias bárbaras / abandonadas e aldeias bónus.
- [x] **Scanner de Aldeias Bárbaras Próximas:**
  - [x] Descoberta automática de todas as aldeias bárbaras num raio configurável a partir da aldeia ativa.
  - [x] Cálculo de distância euclidiana exata e ordenação por proximidade.
  - [x] Persistência e cache local das bárbaras detetadas para evitar pedidos redundantes ao servidor.
- [x] **Farming Automatizado Baseado em Mapa (Map-Driven Farming):**
  - [x] Recuperação da lista em cache de aldeias bárbaras próximas mapeadas.
  - [x] Envio automático de micro-ataques de saque via Praça de Reunião (`screen=place`) com modelos configuráveis de tropas (ex.: 5 lanceiros ou 2 leves).
  - [x] Fila cíclica de ataques: reenvio automatizado assim que as tropas regressam à aldeia de origem.
  - [x] Filtros de segurança: exclusão automática de bárbaras com histórico recente de perdas ou muralha detetada.
  - [x] Suíte de testes unitários dedicada (8 testes cobrindo parsing de mapa, distância euclidiana, bárbaras/bónus, cache em disco e onda de saques).

### 2.12. Algoritmo de Arbitragem Económica & Orquestração (Construção vs. Recrutamento)
- [ ] **Filosofia "Fila Sempre Ativa":** Manter as filas do Edifício Principal e dos edifícios militares (Quartel, Estábulo, Oficina) permanentemente em execução contínua sem tempo ocioso.
- [ ] **Decisão Inteligente em Concorrência de Recursos:**
  - [ ] Monitorização dos temporizadores e tempos restantes de conclusão de cada fila ativa.
  - [ ] Priorização de emergência: se uma fila estiver prestes a esgotar o tempo restante, direcionar os recursos disponíveis prioritariamente para mantê-la ativa.
  - [ ] Recrutamento dinâmico em micro-lotes: recrutar quantidades menores de tropas (ex.: 2 a 5 unidades) para manter os edifícios militares a trabalhar sem canibalizar o custo do próximo nível de edifício planeado.
  - [ ] Projeção de fluxo de caixa em tempo real: cálculo preditivo baseado na taxa de produção horária da aldeia e recursos estimados a chegar de saques e transferências de mercadores.

---

## 📌 Fase 3: Camada Sidecar IPC & Gestão de Sessões (`engine/api/`)

- [x] **Servidor Local FastAPI & WebSockets**
  - [x] Execução em localhost com porta dinâmica e token efêmero de autenticação local (`.sidecar_auth.json`).
  - [x] Endpoints REST para comandos manuais, leitura de status, alteração de configurações e toggles de rotinas.
  - [x] Canal WebSocket bidirecional para streaming em tempo real de logs e status.
  - [x] Disparo de alerta de captcha anti-bot para o frontend (`CAPTCHA_ALERT`).
  - [x] Suíte de testes unitários para a API Sidecar (14 testes dedicados).
- [x] **Gestor de Contas & Multi-Aldeia**
  - [x] Persistência segura de perfis de conta com ofuscação/encriptação (`ProfileManager` em `profiles.json`).
  - [x] Suporte a proxy dedicado ou residencial por conta com diagnóstico ativo (`test_proxy_connection`).
  - [x] Extração de todas as aldeias da conta a partir do `game_data` (`extract_all_villages`).
  - [x] Alternância fluida de contexto entre múltiplas aldeias (`account.switch_village` e `POST /api/account/switch-village`).
  - [x] Seletor de aldeias integrado na interface gráfica (Dropdown no card da aldeia).
  - [x] Suíte de testes unitários dedicada (9 testes cobrindo perfis, multi-aldeia e proxies).
- [x] **Orquestrador Multi-Mundo Simultâneo:**
  - [x] Execução concorrente de múltiplos mundos em paralelo (ex.: `pt117`, `pt118`, mundos internacionais) no mesmo processo.
  - [x] Ciclo de vida desacoplado: instâncias dedicadas de `TribalAccount`, `TaskScheduler`, cookies de sessão e proxies independentes por mundo (`WorldInstance` e `MultiWorldManager`).
  - [x] Gestão centralizada de instâncias na Sidecar API com multiplexação de eventos WebSocket e rotas contextualizadas (`/api/worlds`, `/api/worlds/register`, `/api/worlds/switch`).
- [x] **Gestão Simultânea e Categorizada de Múltiplas Aldeias:**
  - [x] Execução assíncrona coordenada das rotinas de farm, construção e recrutamento para todas as aldeias da conta sem bloqueio mútuo (`MultiVillageCoordinator`).
  - [x] **Categorização de Aldeias (`⚔️ Ataque` / `🛡️ Defesa` / `⚖️ Balanceado`):**
    - [x] Atribuição de perfil por aldeia persistido em `config.json` (`villages[id].category`).
    - [x] Associação dinâmica de templates de construção específicos ao tipo de aldeia (Ataque foca `military_rush`; Defesa foca `balanced`/muralha; Balanceado foca `rush_resources`).
    - [x] Associação dinâmica de templates de recrutamento específicos ao tipo de aldeia (Ataque = Machados/Leves/Aríetes; Defesa = Lanças/Espadachins/Pesadas; Misto = Balanceado).
    - [x] Módulo analítico de balanceamento de recursos entre aldeias (identificação de doadoras vs recetoras e desvios médios).
    - [x] Suíte de testes unitários dedicada (2 testes com 7 asserções cobrindo multi-mundo, isolamento de sessões, categorização e balanceamento).

---

## 📌 Fase 4: Shell Desktop & Frontend Nativo (`frontend/`)

- [x] **Interface Gráfica (UI/UX Premium Cockpit)**
  - [x] Dashboard com visual moderno (Dark Mode, Glassmorphism, Google Fonts Outfit & Inter, paleta Neon Cyber).
  - [x] **HUD Timer de Alta Precisão:** Relógio digital no topo da aplicação exibindo horas, minutos, segundos e microssegundos (`HH:MM:SS.uuuuuu`) a 60 FPS com `requestAnimationFrame`.
  - [x] Visão geral da aldeia: cartões de recursos em tempo real, capacidade do Armazém e População livre.
  - [x] Fila de construção em tempo real com contagem decrescente ativa e estimativa de custos para o próximo edifício.
  - [x] Painel de controlo de módulos com botões de ação imediata (Pausar/Retomar, Construir Agora, Farm Agora, Recrutar Agora).
  - [x] Consola de logs ao vivo via streaming WebSocket com busca por texto, filtros de severidade, auto-scroll e limpeza.
  - [x] Painel de configurações visuais com gravação instantânea e recarregamento a quente no `config.json`.
- [x] **Shell Desktop Nativa Edge WebView2**
  - [x] Execução como aplicação desktop nativa via Edge WebView2 (`engine/desktop_launcher.py` ou `python -m engine.main --gui`).
  - [x] Servidor Sidecar serve a interface web diretamente em `http://127.0.0.1:8000/` (`python -m engine.main --api`).
  - [x] Estrutura do frontend (`frontend/`) 100% isolada e compatível para build final.
- [x] **Modal de Alerta & Resolução de Captchas Anti-Bot**
  - [x] Overlay modal de emergência ativado instantaneamente por evento WebSocket (`CAPTCHA_ALERT`) com aviso sonoro sintetizado.
  - [x] Botão para abertura direta da janela do jogo para resolução humana e botão para retoma automática do motor.
- [ ] **Painel de Métricas & Estatísticas de Eficiência (Dashboard HUD)**
  - [ ] Registo persistente de recursos farmados por hora e por dia (Madeira, Argila, Ferro e Total).
  - [ ] Gráfico visual de rendimento de farm ao longo do tempo (últimas 24h e 7 dias).
  - [ ] Contador acumulado de aldeias saqueadas e tropas recrutadas por unidade.
  - [ ] Histórico de comandos enviados e taxa de sucesso/baixas.
  - [ ] Endpoints dedicados na Sidecar API (`GET /api/stats/summary` e `GET /api/stats/history`) alimentando o frontend em tempo real.
- [x] **Visualizador de Mapa Réplica Interativo do Tribos (Frontend Cockpit)**
  - [x] Réplica visual fiel da grelha de mapa original do Tribal Wars (mesma disposição de coordenadas X|Y, réguas cartográficas, células discretas de terreno e ícones de aldeias).
  - [x] Navegação fluida: arrastar com o rato (*pan*), zoom com a roda ou botões (+/-), HUD D-pad direcional (▲, ◄, 🎯, ►, ▼), centralizar na aldeia ativa e busca rápida por coordenadas.
  - [x] Diferenciação visual clara: aldeias do jogador (ouro 🏰), aldeias de outros jogadores (ciano/azul 🛡️), aldeias bárbaras (slate 🛖) e aldeias bónus (púrpura ⭐).
  - [x] Tooltip e card interativo ao clicar numa aldeia: nome, jogador, tribo, pontos, distância euclidiana e botões diretos "Atacar / Farmar", "Centralizar" e "Copiar Coords".
  - [x] Camada de sobreposição tática (*overlay*): círculo de raio de farm configurado, linhas de setor (a cada 20 campos), fronteiras de continente (a cada 100 campos) e tag de continente (ex.: K45).
- [x] **Visão Geral Multi-Aldeia & Tabela de Recursos em Tempo Real (Cockpit UI)**
  - [x] Tabela/card consolidado listando todas as aldeias da conta ativa com coordenadas, recursos, armazém e população.
  - [x] Exibição em tempo real de recursos agregados (Madeira, Argila, Ferro Total) e contagem de aldeias.
  - [x] Análise integrada de balanceamento de recursos (aldeias doadoras de excedente vs aldeias recetoras de défice).
- [x] **Gestor Visual de Categorias de Aldeia (`⚔️ Ataque` / `🛡️ Defesa` / `⚖️ Balanceado`)**
  - [x] Controlo rápido na UI para alternar a categoria da aldeia com 1 clique (dropdown e badges estilizados).
  - [x] Associação e visualização dos templates de recrutamento e construção vinculados a cada aldeia conforme a categoria.
- [x] **Seletor e Navegação Multi-Mundo na Interface**
  - [x] Barra superior com abas de mundos ativos (`.world-chip`) para alternar a visualização e gestão do Cockpit entre mundos em execução concorrente.
  - [x] Modal para adicionar novos mundos concorrentes em tempo real com SID e proxy opcional.

---

## 📌 Fase 5: Empacotamento, Testes E2E & Release

- [ ] Empacotamento do executável Python isolado com PyInstaller.
- [ ] Build do instalador desktop nativo (`.msi` / `.exe`).
- [ ] Testes de robustez com reconexão automática em caso de quebra de rede.
- [ ] Documentação de utilização final e guia de configuração.
