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
- [x] **Modelo Padrão Único Oficial de Construção (`default_plan` com 268 passos):** Integrado e persistido na base de dados SQLite (`building_templates`) com remoção total de modelos legados.
- [x] **Rush de Prioridade Máxima para Requisitos Militares:**
  - [x] Rush automático para desbloquear Vikings (`axe`) se o Quartel estiver parado por falta de requisitos.
  - [x] Rush automático para desbloquear Cavalaria Leve (`light`) se o Estábulo estiver parado por falta de requisitos.
- [x] Controlador `MainBuildingManager` com disparo de `build` e `cancel` com token CSRF (`h`).
- [x] Rotina periódica contínua de auto-build com feedback imediato e ciclos humanos.
- [x] **Controlo Modular de Auto-Construção:** Switch LIGADO/DESLIGADO, ajuste dinâmico de intervalo em segundos e fila máxima via REST e UI.
- [x] Monitorização em tempo real da fila ativa de construção com cronómetro regressivo e cancelamento direto.
- [x] Sistema de configuração flexível via `config.json` e propriedade compatível `effective_building_plan`.
- [x] Suíte de testes unitários dedicada (12 testes do Edifício Principal + 2 de configuração).

### 2.2. Praça de Reunião & Gestão de Tropas (`screen=place`)
- [x] Parsing da contagem de tropas disponíveis na aldeia ativa (`spear`, `sword`, `axe`, `archer`, `spy`, `light`, `marcher`, `heavy`, `ram`, `catapult`, `knight`, `snob`).
- [x] Leitura de comandos em curso (tropas a atacar, apoiar ou a regressar à aldeia).
- [x] Módulo de envio de comandos (Ataque / Apoio) em 2 etapas:
  - [x] Etapa 1: Envio do formulário inicial com coordenadas de destino (`target_x`, `target_y` ou ID da aldeia) e contagem de tropas.
  - [x] Etapa 2: Confirmação do comando (`action=command&h=...`) com extração da duração da marcha e tipo de ataque.
- [x] Suíte de testes unitários para a Praça de Reunião (10 testes dedicados).

### 2.3. Assistente de Saque & Micro-Farming Automatizado (`screen=am_farm`)
- [x] **Parsing Estruturado do Assistente de Saque Mobile (`screen=am_farm`):**
  - [x] Leitura da tabela de aldeias bárbaras mapeadas no Assistente de Saque.
  - [x] Extração de metadados por linha: ID da aldeia, coordenadas `(X|Y)`, distância euclidiana, último relatório de combate (ícone verde/amarelo/vermelho/azul), estado do saque (cheio vs parcial), nível de muralha reportado, deteção de ataques em trânsito e links diretos de ataque dos modelos A e B.
  - [x] Extração da configuração, custos e capacidade total de transporte de tropas dos modelos A e B definidos no jogo.
  - [x] **Configuração e Gravação de Modelos de Saque (Modelos A & B no Jogo):**
    - [x] Motor HTTP `save_am_farm_template` para persistir composições de tropas no Tribal Wars (`action=change_template`).
    - [x] Endpoint REST `POST /api/farm/templates` com broadcast WebSocket.
    - [x] Modal UI com abas Modelo A / B, grelha com ajuste de tropas por botões +/- ou teclado, presets de 1-clique (2 CL, 4 CL + 1 Espião, etc.) e cálculo de capacidade de carga em tempo real.
- [x] **Varredura Completa de Bárbaras em Raio de X Campos (Radius Barbarian Scanner & Farm):**
  - [x] Descoberta ativa de **todas** as aldeias bárbaras/abandonadas e bónus num raio configurável de X campos em torno da aldeia ativa (`max_distance`), combinando dados do Mapa (`screen=map`), dados do mundo em cache local (`village.txt`) e a lista do Assistente de Saque (`screen=am_farm`).
  - [x] **Ataque Automático de Cobertura Total:** Garantir que 100% das bárbaras detetadas no raio de X campos são atacadas e saqueadas ciclicamente.
  - [x] **Bootstrap de Novas Bárbaras (Praça de Reunião):** Para aldeias bárbaras dentro do raio que ainda não constam na tabela do Assistente de Saque (bárbaras recém-surgidas ou nunca antes atacadas), o bot dispara automaticamente um primeiro ataque via Praça de Reunião (`screen=place`) com a composição do Modelo A ou B, fazendo com que entrem imediatamente no pipeline do Assistente de Saque.
  - [x] **Fila Unificada de Saques:** Ordenação de todas as bárbaras do raio por distância euclidiana crescente, despachando ataques contínuos com base nas tropas disponíveis.
- [x] **Algoritmo de Despacho & Distribuição de Saques:**
  - [x] Seleção inteligente do modelo (A ou B) baseada na distância e no volume de saque reportado em ataques anteriores (`select_optimal_farm_template`).
  - [x] Verificação prévia de tropas disponíveis na aldeia ativa antes do envio de cada comando.
  - [x] **Prevenção de Colisões & Sobreposição:** Deteção de ataques em trânsito para a mesma aldeia bárbara (`has_attack_in_transit` e `_recent_farm_targets`) para evitar saturação ineficiente de tropas no mesmo alvo.
  - [x] **Evasão de Deteção com Jitter Humano:** Atrasos estocásticos gaussianos e micro-jitters configuráveis entre cada disparo de ataque (`get_gaussian_delay`).
- [x] **Agendamento no Motor Assíncrono:**
  - [x] Execução em fila de prioridade com nível `TaskPriority.FARM = 20` no `TaskScheduler`.
  - [x] Auto-pausa instantânea em caso de esgotamento de tropas, falta de alvos válidos ou interceção de alerta anti-bot.
  - [x] Suíte de testes unitários dedicada (parsers de `am_farm`, varredura em raio X, bootstrap via Praça, modelos A/B, prevenção de colisões e despacho com jitter).

### 2.4. Coleta de Recursos / Scavenging (`screen=place&mode=scavenge`)
- [x] Leitura do estado de desbloqueio das 4 categorias de coleta (Lazy, Humble, Clever, Great).
- [x] Parsing de grupos de coleta em andamento e contadores de tempo restante.
- [x] **Algoritmo de Otimização de Coleta:** Cálculo proporcional da distribuição de tropas ponderado pelo `loot_ratio` para retorno simultâneo.
- [x] Disparo automático com timer e agendamento para reenvio.
- [x] Auto-desbloqueio sequencial inteligente quando houver recursos suficientes.
- [x] Painel de Coleta de Recursos no Cockpit Frontend (`#tab-scavenge`) com cards interativos, badges e cronómetros decrescentes.
- [x] Suíte de testes unitários dedicada (6 testes em `tests/test_scavenge.py`).

### 2.5. Recrutamento Militar (Quartel, Estábulo, Oficina)
- [x] Parsing do ecrã do Quartel (`screen=barracks`), Estábulo (`screen=stable`) e Oficina (`screen=garage`).
- [x] Leitura das filas de recrutamento ativas e tempo de conclusão.
- [x] **Deteção Fiel de Unidades Desbloqueadas:** Filtro inteligente de unidades bloqueadas/não pesquisadas ou com inputs desabilitados para impedir submissão de ordens inválidas.
- [x] **Divisão de Abas no Cockpit:** Separação entre a gestão de **Modelos de Tropas** (`tab-troop-models`) e o monitor de **Recrutamento Ativo** (`tab-recruitment`).
- [x] **Modelos Padrão Globais no SQLite (`recruitment_models`):** `attack` ("Ataque Full") e `defense` ("Defesa Full") semeados globalmente (`account_id IS NULL`, `is_default = 1`) com suporte a criação, clonagem e gravação de modelos customizados.
- [x] **Atribuição Multi-Aldeias:** Seletor reativo de modelo militar por aldeia na tabela de aldeias com persistência imediata.
- [x] Recrutamento inteligente em lotes dinâmicos com verificação prévia de recursos disponíveis.
- [x] Priorização de treino por menor custo total de recursos (`Lanceiro` -> `Espião` -> `Espadachim/Bárbaro` -> `Arqueiro` -> `Cavalaria Leve` -> `Aríete` -> `Catapulta` -> `Cavalaria Pesada`).
- [x] Validação de limite de população livre da Fazenda antes de recrutar (`min_free_pop`).
- [x] **Limite Estrito de Fila Militar (`max_queue_elements = 3`):** Restrição a um máximo de 3 ordens ativas em simultâneo por edifício militar (Quartel, Estábulo, Oficina) para evitar reter recursos excessivos em filas longas e permitir gestão dinâmica de slots.
- [x] **Gestão do Ferreiro & Auto-Pesquisa de Tecnologias (`SmithManager` / `screen=smith`):**
  - [x] Parsing multi-estratégia de unidades por IDs, classes, imagens (`unit_axe.png`) e nomes localizados ("Bárbaro", "Viking", "Machado", "CL").
  - [x] Extração de custos de pesquisa e eliminação de falsos positivos de estado "pesquisado".
  - [x] **Prioridade Máxima para Vikings (`axe`) e Cavalaria Leve (`light`):** Disparo autónomo imediato da pesquisa assim que os pré-requisitos de edifícios e recursos forem alcançados.
  - [x] Emissão de `⚡ [PESQUISA INICIADA]` INFO log em tempo real no terminal e Cockpit.
- [x] **Controlo Modular de Auto-Recrutamento:** Switch LIGADO/DESLIGADO, ajuste dinâmico de intervalo em minutos e limites de população via REST e UI.
- [x] Monitorização em tempo real das **Filas Ativas de Treino** (Quartel, Estábulo, Oficina) com quantidade de tropas, hora de conclusão e cronómetro decrescente.
- [x] Comparador visual em tempo real de exército presente vs meta do modelo atribuído.
- [x] Suíte de testes unitários para Recrutamento Militar e Ferreiro (17 testes dedicados).

### 2.6. Academia & Cunha de Moedas (`screen=snob`)
- [x] Leitura de moedas cunhadas / pacotes acumulados (`parse_snob_screen`).
- [x] Cunha automática de moedas quando o armazém estiver prestes a encher (limite configurável via `SnobConfig`).
- [x] Cunha manual em lote (1, 5, Máx) e recrutamento de Nobres.
- [x] Painel da Academia & Moedas no Cockpit Frontend (`#tab-snob`) com telemetria, slider de armazém e ações rápidas.
- [x] Suíte de testes unitários dedicada (5 testes em `tests/test_snob.py`).

### 2.7. Mercado & Balanceamento de Recursos (`screen=market`)
- [x] Leitura de mercadores disponíveis e mercadores em trânsito.
- [x] **Algoritmo de Balanceamento Automático de Recursos:**
  - [x] Cálculo de médias e desvios de recursos entre todas as aldeias da mesma conta.
  - [x] Identificação automática de aldeias doadoras (excedente ou risco de transbordamento de armazém) e aldeias recetoras (défice para construções ou recrutamento urgente).
  - [x] Despacho automatizado de mercadores para transferência equilibrada de recursos entre aldeias (quantização de 1.000 por mercador e proteção contra transbordamento).
- [x] Criação de ofertas no mercado local para troca automática de recursos excedentes por recursos em carência.

### 2.8. Sistema de Defesa & Alarme de Ataques (Prioridade 0 / Alertas)
- [x] Monitorização em tempo real de ataques a chegar à aldeia (`incomings` via `game_data["player"]["incomings"]` e `screen=overview_villages&mode=incomings`).
- [x] Deteção da velocidade da unidade mais lenta atacante (discriminação euclidiana de Nobre 35m, Aríete 30m, Espada 22m, Machado 18m, etc.).
- [x] **Rotina de Auto-Dodge (Desvio de Tropas):** Envio prioritário (`TaskPriority.ALERT = 0`) para aldeia bárbara próxima a segundos do impacto e cancelamento seguro agendado pós-impacto (`cancel_at = impact + delay`).
- [x] Suporte a cancelamento manual imediato de comandos de esquiva e desvio manual sob comando.
- [x] Notificação sonora sintetizada (alarme de 2 tons com Web Audio API) e visual de emergência (banner flutuante de perigo, badge pulsante no header e crachás por unidade).
- [x] Cockpit Frontend dedicado: Painel de Defesa & Incomings com contagem em tempo real, cronómetros decrescentes, tabela de ataques e histórico de dodges em trânsito.
- [x] Suíte de testes unitários dedicada (`tests/test_defense.py` com 16 testes abrangendo parsers, velocidade, esquiva, cancelamento e API).

### 2.9. Táticas de Combate & Sincronização ao Milissegundo (`screen=place`)
- [x] **Sincronização com o Relógio do Servidor:**
  - [x] Medição de latência de ida e volta (RTT) e cálculo contínuo de desvio (*server clock offset / drift*) via EWMA (`ClockSynchronizer` em `engine/actions/combat_sync.py`).
  - [x] Ajuste dinâmico do agendador para disparo no instante exato `t_alvo - latency/2` com rotina híbrida sleep + spin-wait de CPU (`spin_wait_until`) para precisão sub-milissegundo (< 1ms).
- [x] **Sniper de Nobres (Anti-Conquista):**
  - [x] Identificação de comboios de nobres inimigos a caminho com extração dos tempos de chegada ao milissegundo.
  - [x] Cálculo e disparo cirúrgico de apoios (de aldeias vizinhas ou retorno de tropas canceladas da própria aldeia) para intercalação entre o ataque de limpeza (*nuke*) e o primeiro nobre.
  - [x] Tolerância de milissegundos configurável (ex.: janela de 50ms a 150ms).
- [x] **Calculadora & Agendador de Backtime:**
  - [x] Leitura da hora de retorno de tropas inimigas e cálculo de tempo de voo com base na unidade mais lenta de contra-ataque.
  - [x] Agendamento de contra-ataque de precisão milimétrica para aterrar exatamente no mesmo segundo do regresso das tropas inimigas.
- [x] **Comboio de Nobres Automatizado (Noble Train):**
  - [x] Envio sequencial de 3 a 5 ataques com Nobre a partir da mesma aldeia com separação mínima de milissegundos permitida pelas regras do mundo (ex.: 50ms a 100ms).
  - [x] Automação de distribuição de escolta (Nuke no primeiro ataque e 50 vikings + 20 CL nos nobres seguintes).
- [x] **Fake Trains & Ataques Coordenados de Distração:**
  - [x] Estrutura modular preparada para comboios de fakes com aríetes/catapultas para simular nobres e dispersar a defesa inimiga.
- [x] **Mecanismo de Cancelamento de Emergência (Fail-Safe):**
  - [x] Verificação do milissegundo real de saída dos comandos e medição do spread global.
  - [x] Cancelamento automático imediato de todos os comandos que chegaram a sair caso algum falhe ou a dispersão temporal exceda o limiar configurado (ex.: > 400ms).
- [x] **Cockpit Frontend & HUD de Milissegundo:**
  - [x] Telemetria em tempo real de RTT, Offset e Precisão de Disparo.
  - [x] Painel disparador de Noble Train com gaps configuráveis, calculadora interativa de Backtime, radar de Sniper e tabela de operações ativas.
- [x] **Suíte de Testes Unitários:**
  - [x] 14 testes dedicados cobrindo `ClockSynchronizer`, `CombatManager`, Fail-Safe, Backtime, Sniper e API REST (`tests/test_combat.py`), com 100% de sucesso (278 testes totais a passar).

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
- [x] **Filosofia "Fila Sempre Ativa":** Manter as filas do Edifício Principal e dos edifícios militares (Quartel, Estábulo, Oficina) permanentemente em execução contínua sem tempo ocioso.
- [x] **Decisão Inteligente em Concorrência de Recursos:**
  - [x] Monitorização dos temporizadores e tempos restantes de conclusão de cada fila ativa (`build_queue_time_left`, `military_queues_time_left`).
  - [x] Priorização de emergência: se uma fila estiver prestes a esgotar o tempo restante, direcionar os recursos disponíveis prioritariamente para mantê-la ativa.
  - [x] Recrutamento dinâmico em micro-lotes: recrutar quantidades menores de tropas (ex.: 2 a 5 unidades) para manter os edifícios militares a trabalhar sem canibalizar o custo do próximo nível de edifício planeado.
  - [x] Projeção de fluxo de caixa em tempo real: cálculo preditivo baseado na taxa de produção horária da aldeia e recursos estimados a chegar de saques e transferências de mercadores.
  - [x] Suíte de testes unitários dedicada (7 testes cobrindo temporizadores, projeção de caixa, concorrência, micro-lotes e agendamento).

### 2.13. Radar de Inativos & Inno-Farming (Análise Histórica de Crescimento & Varredura de Alvos)
- [x] **Módulo de Sincronização e Ingestão de Dados Públicos do Mundo (`WorldDataWorker`):**
  - [x] Download assíncrono e não-bloqueante dos dumps públicos oficiais (`village.txt`, `player.txt`, `ally.txt`) do servidor (`https://{domain}/map/`).
  - [x] Suporte a compressão HTTP gzip, ETag e verificação de cabeçalhos `If-Modified-Since` para evitar downloads redundantes.
  - [x] Armazenamento relacional e indexado em base de dados local SQLite (`data/world_data.db`) com criação de índices por coordenadas `(x, y)`, `player_id`, `points` e `timestamp`.
  - [x] Gestão de snapshots históricos com retenção configurável para análise de séries temporais.
- [x] **Algoritmo de Rastreamento de Crescimento e Deteção de Inatividade ($\Delta P$):**
  - [x] Cálculo da variação temporal de pontos: $\Delta P = P_{\text{atual}} - P_{\text{passado}}$ em janelas configuráveis ($\Delta t \in \{3, 7, 14\}$ dias).
  - [x] Classificação categórica de inatividade:
    * **Estagnação Total:** $\Delta P = 0$ em $\ge 3$ dias consecutivos.
    * **Regressão / Limpeza:** $\Delta P < 0$ (perda de edifícios/pontos por ataques).
    * **Crescimento Residual:** $\Delta P \le \text{limiar configurável}$ (ex.: $< 30$ pontos em 7 dias).
- [x] **Motor de Filtros Táticos & Seleção de Alvos:**
  - [x] Filtro por raio de distância euclidiana máxima em torno da aldeia ativa do utilizador (`max_distance`).
  - [x] Filtro por faixa de pontuação da aldeia/jogador (ex.: mínimo 300 pts, máximo 3.000 pts).
  - [x] Filtro por estado de tribo: sem tribo (`only_tribeless`), jogadores de tribos com 1 único membro (`include_single_member_tribes`) ou tribos comprovadamente inativas.
  - [x] Filtro de segurança: exclusão automática de membros de tribos aliadas ou pactos de não-agressão (`exclude_ally_ids`), jogadores excluídos (`exclude_player_ids`) e alvos em lista negra (`blacklist_coords`).
- [x] **Tabela Comparativa & Ações Rápidas de Farm:**
  - [x] Cálculo dinâmico do tempo de viagem e hora estimada de impacto de Cavalaria Leve (CL) e Espião (`calculate_unit_travel_times`).
  - [x] Ação rápida em 1-clique: "➕ Adicionar à Lista de Farm" (`export_targets_to_custom_farm`) ou "⚔️ Simular Ataque na Praça" (`create_attack_payload`).
  - [x] Suíte de testes unitários dedicada (ingestão de dumps, cálculo de $\Delta P$, filtros combinados e exportação de alvos em `tests/test_world_data.py`).

---

## 📌 Fase 3: Camada Sidecar IPC & Gestão Concorrente (`engine/api/`)

- [x] **Servidor Local FastAPI & WebSockets**
  - [x] Execução em localhost com porta dinâmica e token efêmero de autenticação local (`.sidecar_auth.json`).
  - [x] Endpoints REST para comandos manuais, leitura de status, alteração de configurações e toggles de rotinas.
  - [x] Canal WebSocket bidirecional para streaming em tempo real de logs e status.
  - [x] Disparo de alerta de captcha anti-bot para o frontend (`CAPTCHA_ALERT`).
  - [x] Suíte de testes unitários para a API Sidecar (14 testes dedicados).
- [x] **Endpoints REST & WebSockets do Assistente de Saque & Farm (`/api/farm/*`):**
  - [x] `GET /api/farm/status`: Retorna estado da rotina de farm, tropas na aldeia, ataques em curso e métricas do ciclo.
  - [x] `POST /api/farm/toggle`: Liga/desliga o ciclo automático de Assistente de Saque.
  - [x] `POST /api/farm/trigger`: Dispara uma ronda imediata de saques em segundo plano.
  - [x] `POST /api/farm/config`: Atualiza parâmetros do Assistente de Saque (templates A/B, raio máx, delays e prevenção de colisões).
  - [x] `GET /api/farm/targets`: Lista as aldeias bárbaras disponíveis com relatórios e status de envio.
- [x] **Endpoints REST & WebSockets do Radar de Inativos (`/api/radar/*`):**
  - [x] `GET /api/radar/inactives`: Retorna lista filtrada de alvos inativos ordenados por proximidade com $\Delta P$.
  - [x] `POST /api/radar/sync`: Dispara a atualização e sincronização dos ficheiros de dados do mundo em background.
  - [x] `GET /api/radar/sync-status`: Retorna o estado do download dos dumps públicos e hora da última sincronização.
  - [x] `POST /api/radar/targets/add`: Adiciona uma aldeia inativa à lista de farm personalizado da aldeia.
- [x] **Gestão Concorrente Multi-Aldeia (Mesmo Mundo)**
  - [x] Extração de todas as aldeias da conta a partir do `game_data` (`extract_all_villages`) e em lote via `overview_villages`.
  - [x] Alternância fluida de contexto entre múltiplas aldeias (`account.switch_village` e `POST /api/account/switch-village`).
  - [x] Execução assíncrona coordenada das rotinas de farm, construção e recrutamento para todas as aldeias da conta sem bloqueio mútuo (`MultiVillageCoordinator`).
  - [x] Configuração individualizada por aldeia no `config.json` (perfil Ofensivo/Defensivo/Balanceado, templates de tropas e edifícios).
  - [x] Módulo analítico de balanceamento de recursos entre aldeias (identificação de doadoras vs recetoras e desvios médios).
- [x] **Gestão Simultânea Multi-Mundo (Mundos Concorrentes)**
  - [x] Orquestrador de instâncias para execução simultânea de múltiplos mundos no mesmo processo (`MultiWorldManager` e `WorldInstance`).
  - [x] Isolamento de sessões de rede `TribalAccount`, schedulers e ficheiros de cookies/configuração por mundo.
  - [x] Suporte a instâncias em abas e seletor de mundo em tempo real no Dashboard Frontend (`/api/worlds`, `/api/worlds/register`, `/api/worlds/switch`).
- [x] **Gestor de Perfis, Base de Dados SQLite & Arranque Estrito Offline**
  - [x] Base de dados local SQLite transacional (`data/accounts.db`) para persistência de contas, cookies `sid`, credenciais, estratégias e timestamps.
  - [x] Arranque 100% desconectado por omissão: aplicação abre no Gestor de Contas com todas em `⚪ OFFLINE` e a Dashboard bloqueada.
  - [x] Bloqueio monousuário estrito (Single-Active Session Lock) garantindo 1 conta ativa por sessão com limpeza limpa de agendador e sockets.
  - [x] Hub de Gestão de Contas no Frontend com badges Online/Offline, login direto no Tribos pelo navegador integrado (`renewSession`) e criação/edição/eliminação atómica.
  - [x] Suporte a proxy dedicado ou residencial por conta com diagnóstico ativo (`test_proxy_connection`).
  - [x] Suíte de testes unitários dedicada cobrindo SQLite, perfis, ativação monousuário, multi-aldeia e proxies (204 testes 100% OK).
- [x] **Migração e Gestão de Modelos de Construção e Recrutamento para SQLite (`data/accounts.db`)**
  - [x] Schema para `building_templates` (`id`, `account_id`, `name`, `target_levels`, `priority_list`, `is_default`, `created_at`).
  - [x] Schema para `recruitment_models` (`id`, `account_id`, `name`, `units`, `batch_sizes`, `is_default`, `created_at`).
  - [x] Métodos CRUD no `AccountsDatabase` (`engine/storage/database.py`) e no `EngineContext`.
  - [x] Endpoints REST `/api/templates/building` e `/api/templates/recruitment` para criação, edição, clonagem e exclusão de modelos.
  - [x] Interface visual no Frontend para gerir, personalizar e associar modelos a aldeias/contas sem editar o `config.json`.

---

## 📌 Fase 4: Shell Desktop & Frontend Nativo (`frontend/`)

- [x] **Interface Gráfica (UI/UX Premium Cockpit)**
  - [x] Dashboard com visual moderno (Dark Mode, Glassmorphism, Google Fonts Outfit & Inter, paleta Neon Cyber).
  - [x] **HUD Timer de Alta Precisão:** Relógio digital no topo da aplicação exibindo horas, minutos, segundos e microssegundos (`HH:MM:SS.uuuuuu`) a 60 FPS com `requestAnimationFrame`.
  - [x] Visão geral da aldeia: cartões de recursos em tempo real, capacidade do Armazém e População livre.
  - [x] **Controlo Modular por Domínio & Filas em Tempo Real:**
    - [x] Barra superior simplificada com ações globais essenciais (Login, Atualizar, Missões, Pausar/Retomar e Farm).
    - [x] Aba Edifícios & Fila (`#tab-building`): Switch toggle para Ligar/Desligar Auto-Construção, seletor de intervalo, disparo imediato e monitor da fila ativa com contagem decrescente e cancelamento.
    - [x] Aba Recrutamento & Tropas (`#tab-military`): Switch toggle para Ligar/Desligar Auto-Recrutamento, seletor de intervalo, disparo imediato, templates 1-clique e card de Filas Ativas de Treino (Quartel, Estábulo, Oficina).
  - [x] Consola de logs ao vivo via streaming WebSocket com busca por texto, filtros de severidade, auto-scroll e limpeza.
  - [x] Painel de configurações visuais com gravação instantânea e recarregamento a quente no `config.json`.
- [x] **Nova Aba no Menu Lateral: "🌾 Assistente de Saque & Farm" (`#tab-farm-assistant`)**
  - [x] **Sub-Aba 1: "⚔️ Farm Bárbaras (AM Farm)":**
    * Switch toggle Ligar/Desligar envio automático de saques.
    * Painel de configuração: seletor de templates padrão (Modelo A vs Modelo B), raio de distância máxima, atraso aleatório mínimo/máximo entre ataques e opção de evitar ataques sobrepostos.
    * Tabela de aldeias bárbaras mapeadas com coordenadas, distância, tempo de CL, status do último relatório e botão manual de disparo.
    * Card de tropas na aldeia disponíveis para farm vs tropas em trânsito.
  - [x] **Sub-Aba 2: "📡 Radar de Inativos & Inno-Farming":**
    * Barra de filtros reativos: Raio máximo em campos, limite de pontuação do jogador (mín/máx), janela de inatividade ($\Delta t$: 3, 7 ou 14 dias), filtro "Apenas Sem Tribo" e pesquisa por jogador/coordenadas.
    * Botão de controlo: "🔄 Atualizar Dados do Mundo" com badge de timestamp da última sincronização.
    * Tabela comparativa de alvos inativos: Jogador, Tribo, Aldeia, Coordenadas `(X|Y)`, Pontos Atuais, Variação de Pontos ($\Delta P$), Distância Euclidiana, Tempo de Marcha de Cavalaria Leve (CL) e Ações Rápidas ("➕ Adicionar ao Farm" / "⚔️ Praça").
- [x] **Visualizador de Mapa Interativo Integrado (Embedded Game Map)**
  - [x] Renderização 2D nativa canvas da grelha de mapa do mundo/continente com suporte a zoom e arrasto direto no Cockpit.
  - [x] Destaque de aldeias próprias, bárbaras no raio de farm e aldeias de jogadores vizinhos.
  - [x] Ações rápidas de clique no mapa para envio de saque ou marcação de alvos.
- [x] **Shell Desktop Nativa Edge WebView2**
  - [x] Execução como aplicação desktop nativa via Edge WebView2 (`engine/desktop_launcher.py` ou `python -m engine.main --gui`).
  - [x] Servidor Sidecar serve a interface web diretamente em `http://127.0.0.1:8000/` (`python -m engine.main --api`).
  - [x] Estrutura do frontend (`frontend/`) 100% isolada e compatível para build final.
- [x] **Modal de Alerta & Resolução de Captchas Anti-Bot**
  - [x] Overlay modal de emergência ativado instantaneamente por evento WebSocket (`CAPTCHA_ALERT`) com aviso sonoro sintetizado.
  - [x] Botão para abertura direta da janela do jogo para resolução humana e botão para retoma automática do motor.
- [x] **Painel de Métricas & Estatísticas de Eficiência (Dashboard HUD)**
  - [x] Registo persistente de recursos farmados por hora e por dia (Madeira, Argila, Ferro e Total).
  - [x] Gráfico visual de rendimento de farm ao longo do tempo (últimas 24h e 7 dias com HTML5 Canvas nativo).
  - [x] Contador acumulado de aldeias saqueadas e tropas recrutadas por unidade.
  - [x] Histórico de comandos enviados e taxa de sucesso/baixas.
  - [x] Endpoints dedicados na Sidecar API (`GET /api/stats/summary`, `GET /api/stats/history`, `POST /api/stats/reset`) alimentando o frontend em tempo real e via WebSockets (`STATS_UPDATED`).
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
  - [x] **Aba Coleta de Recursos / Scavenging (`#tab-scavenge`)**
  - [x] Switch toggle para Ligar/Desligar envio automático de Coleta.
  - [x] Checkboxes de desbloqueio das 4 categorias: Categoria 1 (Lazy), Categoria 2 (Humble), Categoria 3 (Clever) e Categoria 4 (Great).
  - [x] Seletores de tropas elegíveis para coleta (Lanceiro, Espadachim, Bárbaro, Arqueiro, Cavalaria Leve) com inputs para reserva mínima não enviável.
  - [x] Monitor em tempo real: cards com estado das 4 expedições, tropas atualmente em trânsito e cronómetro decrescente de retorno.
  - [x] Botão de ação rápida: "⚡ Disparar Ronda Imediata de Coleta".

- [x] **Aba Operações Militares, Táticas & Timings (`#tab-combat`)**
  - [x] **Módulo Comboio de Nobres (Noble Train Builder):**
    * Formulário de ataque: Coordenadas alvo `(X|Y)`, aldeia de origem, seletor de número de nobres (4 ou 5) e divisão de escolta (tropas de limpeza no 1º nobre vs defesa residual nos restantes).
    * Input numérico de espaçamento entre nobres em milissegundos (ex.: 50ms a 100ms).
    * Disparador manual com medição em tempo real de latência de rede (*ping offset*).
  - [x] **Módulo Calculadora & Snipe Defensivo:**
    * Input de horário alvo exato com precisão de milissegundos (`HH:MM:SS.mmm`).
    * Lista de tropas e aldeias disponíveis com cálculo instantâneo da janela ideal de envio.
    * Funcionalidade *Cancel-Snipe*: botão para agendar ataque a bárbara e temporizador visual do segundo exato para cancelamento automático.

- [x] **Painel de Defesa & Alarme de Ataques Recebidos (Incomings HUD)**
  - [x] Banner flutuante de perigo e badge dinâmico no topo (`🚨 X Comandos a Chegar`) acionado por WebSocket.
  - [x] Tabela analítica de comandos recebidos: Origem, Destino, Hora de Chegada, Duração restante e Unidade mais lenta estimada (Espião, CL, Bárbaro/Espada, Aríete/Catapulta, Nobre).
  - [x] Switch toggle para **Auto-Dodge**: seletor de aldeia bárbara de escape e tempo de antecedência antes do impacto (ex.: desviar 30 segundos antes do ataque).

- [x] **Módulo Academia & Mercado Local (`#tab-snob` / `#tab-market`)**
  - [x] **Cunhagem de Moedas Automática:**
    * Switch toggle Ligar/Desligar cunhador automático.
    * Slider de limite percentual do armazém (ex.: cunhar assim que recursos excederem 85% da capacidade).
    * Contador de moedas cunhadas hoje e nobres atualmente disponíveis/em treino.
  - [x] **Gestor de Balanço e Ofertas de Mercado:**
    * Visualizador das rotas de mercadores ativas e hora de entrega.
    * Painel de criação rápida de ofertas para troca de recursos excedentes por recursos em défice.

- [x] **Visualizador de Inventário & Gestão de Itens (`#tab-inventory`)**
  - [x] Grelha com itens disponíveis no inventário da conta (ícone, nome do bónus, percentual e duração).
  - [x] Botão de ativação manual com modal de confirmação (garantindo que nenhum item é consumido sem intervenção explícita do utilizador).

---

## 📌 Fase 5: Empacotamento, Testes E2E & Release

- [x] Empacotamento do executável Python isolado com PyInstaller.
- [x] Build do instalador desktop nativo (`.msi` / `.exe`).
- [x] Testes de robustez com reconexão automática em caso de quebra de rede.
- [x] Documentação de utilização final e guia de configuração.

---

## 📌 Especificação Técnica de Dados & Contratos de Integração

### 1. Schemas de Dados Pydantic (Backend Python)

```python
from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class FarmModelTemplate(BaseModel):
    """Definição de tropas associadas a um modelo do Assistente de Saque (A ou B)."""
    template_id: str = Field(..., description="'A' ou 'B'")
    spear: int = 0
    sword: int = 0
    axe: int = 0
    archer: int = 0
    spy: int = 0
    light: int = 0
    marcher: int = 0
    heavy: int = 0
    knight: int = 0


class FarmConfig(BaseModel):
    """Configurações operacionais do módulo de Assistente de Saque & Farm."""
    enabled: bool = False
    default_template: str = Field("A", description="Modelo padrão ('A' ou 'B')")
    max_distance: float = Field(25.0, description="Raio máximo de distância euclidiana em campos (X campos)")
    scan_all_radius_barbarians: bool = Field(True, description="Varre ativamente e ataca TODAS as aldeias bárbaras no raio de X campos")
    bootstrap_unlisted_barbarians: bool = Field(True, description="Dispara ataque inicial via Praça para incluir bárbaras não catalogadas no AM Farm")
    min_interval_seconds: int = Field(180, description="Intervalo mínimo entre ciclos de varredura")
    max_interval_seconds: int = Field(420, description="Intervalo máximo entre ciclos de varredura")
    min_delay_per_attack_ms: int = Field(350, description="Atraso mínimo em ms entre envio de comandos individuais")
    max_delay_per_attack_ms: int = Field(950, description="Atraso máximo em ms entre envio de comandos individuais")
    avoid_concurrent_attacks: bool = Field(True, description="Evita enviar múltiplos ataques para a mesma bárbara em trânsito")
    stop_on_losses: bool = Field(True, description="Ignora aldeias bárbaras com relatório recente de perdas totais/amarelas")
    custom_targets: List[str] = Field(default_factory=list, description="Lista de coordenadas manuais fixas (ex.: '500|500')")


class FarmTargetRow(BaseModel):
    """Representação de um alvo disponível no Assistente de Saque."""
    village_id: int
    name: str
    x: int
    y: int
    distance: float
    last_report_color: str = Field("blue", description="'blue', 'green', 'yellow', 'red' ou 'none'")
    loot_status: str = Field("unknown", description="'full', 'partial', 'empty' ou 'unknown'")
    wall_level: Optional[int] = None
    has_attack_in_transit: bool = False
    is_in_am_farm: bool = True
    action_url_a: Optional[str] = None
    action_url_b: Optional[str] = None


class InactiveFilterParams(BaseModel):
    """Critérios de filtragem para a varredura do Radar de Inativos."""
    max_distance: float = Field(30.0, description="Raio euclidiano máximo em campos")
    min_points: int = Field(100, description="Pontuação mínima da aldeia")
    max_points: int = Field(5000, description="Pontuação máxima da aldeia")
    days_window: int = Field(7, description="Janela de análise temporal em dias (3, 7 ou 14)")
    max_growth_points: int = Field(0, description="Crescimento máximo de pontos aceitável no período (0 = estagnação total)")
    only_no_tribe: bool = Field(False, description="Filtra apenas jogadores sem tribo")
    exclude_allies: bool = Field(True, description="Exclui membros de tribos aliadas ou PNA")


class InactiveVillageTarget(BaseModel):
    """Alvo identificado pelo Radar de Inativos com métricas de crescimento e tempo de viagem."""
    village_id: int
    village_name: str
    x: int
    y: int
    player_id: int
    player_name: str
    tribe_id: int
    tribe_tag: Optional[str] = None
    current_points: int
    previous_points: int
    delta_points: int
    distance: float
    light_travel_time_seconds: int
    spy_travel_time_seconds: int
    is_in_farm_list: bool = False
    last_analyzed_at: datetime


class WorldDataSyncState(BaseModel):
    """Estado do worker de sincronização dos dumps públicos do mundo."""
    world: str
    is_syncing: bool = False
    last_sync_timestamp: Optional[float] = None
    total_villages_cached: int = 0
    total_players_cached: int = 0
    history_days_available: int = 0
    status_message: str = "Pronto"
```

---

### 2. Interfaces TypeScript / Frontend JavaScript

```typescript
export interface IFarmConfig {
  enabled: boolean;
  default_template: 'A' | 'B';
  max_distance: number;
  scan_all_radius_barbarians: boolean;
  bootstrap_unlisted_barbarians: boolean;
  min_interval_seconds: number;
  max_interval_seconds: number;
  min_delay_per_attack_ms: number;
  max_delay_per_attack_ms: number;
  avoid_concurrent_attacks: boolean;
  stop_on_losses: boolean;
  custom_targets: string[];
}

export interface IFarmTarget {
  village_id: number;
  name: string;
  coordinates: string; // '465|559'
  distance: number;
  last_report_color: 'blue' | 'green' | 'yellow' | 'red' | 'none';
  loot_status: 'full' | 'partial' | 'empty' | 'unknown';
  wall_level: number | null;
  has_attack_in_transit: boolean;
  travel_time_cl_str?: string;
}

export interface IInactiveRadarFilter {
  max_distance: number;
  min_points: number;
  max_points: number;
  days_window: 3 | 7 | 14;
  max_growth_points: number;
  only_no_tribe: boolean;
  exclude_allies: boolean;
  search_query?: string;
}

export interface IInactiveTarget {
  village_id: number;
  village_name: string;
  coordinates: string;
  player_id: number;
  player_name: string;
  tribe_id: number;
  tribe_tag: string | null;
  current_points: number;
  previous_points: number;
  delta_points: number;
  distance: number;
  light_travel_time_str: string; // '00:14:32'
  spy_travel_time_str: string;   // '00:09:41'
  is_in_farm_list: boolean;
}

export interface IWorldSyncStatus {
  world: string;
  is_syncing: boolean;
  last_sync_timestamp: number | null;
  last_sync_human_str: string;
  total_villages: number;
  total_players: number;
  history_days: number;
}
```

---

### 3. Matriz de Endpoints da API Local (FastAPI Sidecar IPC)

| Método | Endpoint | Descrição Operacional | Payload / Parâmetros |
|---|---|---|---|
| `GET` | `/api/farm/status` | Retorna status do ciclo, tropas prontas e alvos em trânsito | `world?: string` |
| `POST` | `/api/farm/toggle` | Liga ou desliga o módulo de envio automático de saques | `{ enabled: boolean }` |
| `POST` | `/api/farm/trigger` | Dispara execução assíncrona imediata de 1 ronda de saques | `{ force?: boolean }` |
| `POST` | `/api/farm/config` | Salva e atualiza parâmetros operacionais do Assistente de Saque | `FarmConfig` (JSON) |
| `GET` | `/api/farm/targets` | Lista as aldeias bárbaras mapeadas com status de relatórios | `radius?: float, limit?: int` |
| `GET` | `/api/radar/inactives` | Varre e retorna alvos inativos com base nos filtros informados | `InactiveFilterParams` (Query) |
| `POST` | `/api/radar/sync` | Dispara o worker assíncrono para download dos dados do mundo | `{ world?: string, force?: boolean }` |
| `GET` | `/api/radar/sync-status` | Consulta o progresso do download e idade da base local | `world?: string` |
| `POST` | `/api/radar/targets/add` | Adiciona uma coordenada de inativo à lista fixa de farm | `{ coords: string, name?: string }` |

---

### 4. Arquitetura do Worker de Sincronização de Dados do Mundo (`WorldDataWorker`)

1. **Agendamento Inteligente e Respeito à Largura de Banda:**
   - Execução programada a cada 6 ou 12 horas no arranque em segundo plano.
   - Requisição via `curl_cffi` com cabeçalho `Accept-Encoding: gzip` e validação de `If-Modified-Since` com base no `Last-Modified` do servidor oficial (`https://{domain}/map/village.txt`, `player.txt`, `ally.txt`).
2. **Armazenamento e Indexação Local (SQLite):**
   - Criação da tabela `world_villages` (`id`, `name`, `x`, `y`, `player_id`, `points`, `rank`) e `world_players` (`id`, `name`, `tribe_id`, `villages_count`, `points`, `rank`).
   - Tabela histórica `world_player_snapshots` (`player_id`, `points`, `villages_count`, `captured_at`) para permitir cálculo de $\Delta P$ histórico sem necessidade de reprocessar ficheiros brutos.
3. **Cálculo Eficiente de $\Delta P$:**
   - Consulta SQL direta indexada por `player_id` e janela temporal mais próxima de $t - \Delta t$.
   - Sem impacto em memória RAM (processamento streaming em chunks de 5.000 registos).

---

### 5. Critérios de Aceitação & Plano de Testes Automatizados

* **Assistente de Saque & Farm (`screen=am_farm`):**
  * `test_parse_am_farm_page`: Valida extração de bárbaras, modelos A/B, botões de ação e detecção de perdas/muralha.
  * `test_farm_dispatch_template_selection`: Garante que alvos com saque cheio recebem modelo adequado e alvos com perdas são ignorados se `stop_on_losses = True`.
  * `test_avoid_concurrent_attacks`: Valida que bárbaras com ataques em curso não recebem ordens duplicadas no mesmo ciclo.
  * `test_farm_delay_jitter`: Garante que os atrasos entre ataques individuais respeitam a faixa estocástica configurada.
* **Radar de Inativos & Inno-Farming:**
  * `test_world_data_sync_and_storage`: Testa o download, parsing de `player.txt` e gravação correta no SQLite local.
  * `test_inactive_delta_points_calculation`: Valida a fórmula $\Delta P = P_t - P_{t-\Delta t}$ com simulação de snapshots de 3, 7 e 14 dias.
  * `test_inactive_filters_application`: Valida combinação de filtros (raio euclidiano, faixa de pontos, sem tribo, exclusão de aliados).
  * `test_add_inactive_target_to_farm_list`: Valida persistência imediata do alvo selecionado no `config.json` e sincronização com a Praça/Assistente.

