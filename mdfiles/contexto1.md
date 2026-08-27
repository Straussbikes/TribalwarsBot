# Projeto: Tribal Wars Mobile Automation Engine (Standalone Client)

### 1. Visão Geral e Objetivo
Desenvolvimento de uma aplicação desktop autónoma (estilo *PS Evolution*)[cite: 1] para automação do jogo Tribal Wars (Tribos)[cite: 1]. 
A arquitetura baseia-se na emulação de rede HTTP direta sobre a versão mobile (`page=mobile`)[cite: 1], garantindo consumo ultrabaixo de recursos (sem instanciar browsers Chromium pesados)[cite: 1] e evasão avançada de assinaturas de rede (TLS/JA3/JA4)[cite: 1].

---

### 2. Stack Tecnológica
* **GUI / Shell Desktop:** Tauri (Rust + React/Svelte) ou WebView isolada para resolução manual de captchas e login[cite: 1].
* **Core Engine:** Python (AsyncIO)[cite: 1] integrado como *sidecar* ou serviço local.
* **Camada de Rede:** `curl_cffi` (impersonate Chrome Mobile para spoofing consistente de headers e TLS fingerprinting)[cite: 1].
* **Data Extraction / Parsing:** Regex direcionado e parsers rápidos (BeautifulSoup / Selectolax) para extração de dados do JavaScript (`game_data`) e do HTML[cite: 1].

---

### 3. Progresso Atual e Testes Validados (PoC)

* **Autenticação:** Validação bem-sucedida da injeção do cookie de autenticação `sid` correspondente ao subdomínio ativo (`pt117.tribalwars.com.pt`).
* **Evasão & Conexão:** Comunicação estabelecida com sucesso simulando um dispositivo móvel (`Sec-CH-UA-Mobile: ?1`, Android/Chrome)[cite: 1].
* **Parsing de Dados em Tempo Real:** 
  * O motor já extrai com precisão o token CSRF (`game_data.csrf` / parâmetro `h=...`), essencial para envio de comandos e formulários[cite: 1].
  * Leitura em tempo real dos recursos da aldeia (`wood`, `stone`, `iron`), capacidade do armazém (`storage_max`) e população (`pop`/`pop_max`).
* **Deteção Anti-Bot:** Mecanismo preliminar implementado para intercetar o ecrã de verificação humana (`id="bot_protect"`, `name="bot_check"`) e pausar o fluxo para intervenção do utilizador[cite: 1].

---

### 4. Próximos Passos de Desenvolvimento
1. **Módulo de Fila de Tarefas (Async Priority Queue):** Estruturar o agendamento de tarefas divididas por prioridade (Alertas/Defesa > Farm > Scavenging > Construção/Recrutamento) com intervalos de atraso aleatórios (distribuição gaussiana)[cite: 1].
2. **Implementação de Ações (Endpoints `game.php`):**
   * **Edifício Principal (`screen=main`):** Fila de construção e evolução de edifícios[cite: 1].
   * **Praça de Reunião (`screen=place`):** Leitura de tropas, envio de comandos de farm e rotina de *Scavenging* (recolha de recursos)[cite: 1].
   * **Quartel (`screen=barracks`):** Recrutamento de unidades[cite: 1].
3. **Gestão de Sessão & Multi-Conta:** Persistência de ficheiros de configuração por conta (cookies, proxies dedicados, IDs de aldeia)[cite: 1].