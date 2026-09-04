# Guia do Utilizador & Manual de Operação - Tribal Wars Bot v2.0.0

Este guia contém todas as instruções necessárias para instalar, configurar e operar com segurança o **Tribal Wars Bot** no seu computador.

---

## 📋 Índice

1. [Requisitos do Sistema](#1-requisitos-do-sistema)
2. [Instalação e Primeiro Arranque](#2-instalação-e-primeiro-arranque)
3. [Autenticação & Bypass Assistido de Captcha](#3-autenticação--bypass-assistido-de-captcha)
4. [Gestão de Perfis & Contas](#4-gestão-de-perfis--contas)
5. [Guia de Operação por Módulo](#5-guia-de-operação-por-módulo)
   - [5.1 Edifício Principal & Filas de Construção](#51-edifício-principal--filas-de-construção)
   - [5.2 Recrutamento de Tropas Balanceado](#52-recrutamento-de-tropas-balanceado)
   - [5.3 Assistente de Saque & Farm de Bárbaras](#53-assistente-de-saque--farm-de-bárbaras)
   - [5.4 Coleta de Recursos (Scavenging)](#54-coleta-de-recursos-scavenging)
   - [5.5 Comboio de Nobres (Noble Train Builder)](#55-comboio-de-nobres-noble-train-builder)
   - [5.6 Calculadora & Snipe Defensivo (com Cancel-Snipe)](#56-calculadora--snipe-defensivo-com-cancel-snipe)
   - [5.7 Painel Incomings & Auto-Dodge de Defesa](#57-painel-incomings--auto-dodge-de-defesa)
   - [5.8 Academia & Cunhagem de Moedas](#58-academia--cunhagem-de-moedas)
   - [5.9 Mercado & Balanço de Recursos](#59-mercado--balanço-de-recursos)
   - [5.10 Visualizador & Ativação de Inventário](#510-visualizador--ativação-de-inventário)
6. [Resiliência de Rede & Proxies](#6-resiliência-de-rede--proxies)
7. [Boas Práticas de Segurança Anti-Ban](#7-boas-práticas-de-segurança-anti-ban)
8. [Perguntas Frequentes & Resolução de Problemas](#8-perguntas-frequentes--resolução-de-problemas)

---

## 1. Requisitos do Sistema

- **Sistema Operativo:** Windows 10 (versão 1809 ou superior) ou Windows 11 (64-bit).
- **Microsoft Edge WebView2 Runtime:** Pré-instalado por padrão no Windows 10/11 atualizado. Caso necessário, está disponível gratuitamente no site da Microsoft.
- **Espaço em Disco:** ~300 MB livres.
- **Memória RAM:** Mínimo de 512 MB disponíveis para o bot.

---

## 2. Instalação e Primeiro Arranque

### Opção A: Versão Portátil (Sem Instalação)
1. Extraia o ficheiro `TribalWarsBot_v2.0.0_Portable.zip` para uma pasta à sua escolha (por exemplo: `C:\Jogos\TribalWarsBot`).
2. Abra a pasta extraída e dê duplo clique em **`Criar_Atalho_Ambiente_Trabalho.bat`** se desejar ter um atalho no seu Ambiente de Trabalho.
3. Dê duplo clique no executável **`TribalWarsBot.exe`** para iniciar a aplicação.

### Opção B: Instalador Automático
1. Caso tenha o instalador `TribalWarsBot_Setup_v2.0.0.exe`, dê duplo clique para iniciar o assistente de instalação em Português.
2. Siga os passos na tela e selecione a criação do ícone no Ambiente de Trabalho.

Ao iniciar, a janela da aplicação abrirá exibindo o Dashboard escuro de controlo e o terminal de logs em tempo real.

---

## 3. Autenticação & Bypass Assistido de Captcha

O bot utiliza o cookie de autenticação de sessão `sid` oficial da sua conta.

### Método 1: Login Visual Assistido (Recomendado)
1. No menu superior da aplicação, clique no botão **"🌐 Iniciar Sessão no Jogo"**.
2. Uma janela nativa do Microsoft Edge será aberta com o site oficial do Tribal Wars.
3. Introduza normalmente o seu nome de utilizador e palavra-passe e selecione o mundo desejado (ex.: Mundo 117).
4. Se surgir um desafio de verificação bot / captcha, resolva-o diretamente nessa janela com o rato.
5. Assim que a sua aldeia carregar na janela, clique no botão verde **"Concluir Login"** no topo da janela.
6. O bot captura os cookies criptografados da sessão de forma 100% segura e fecha a janela do navegador, ativando imediatamente a automação.

### Método 2: Inserção Manual do Cookie SID
1. Se preferir, obtenha o cookie `sid` através das ferramentas de desenvolvedor do seu navegador habitual (`F12` > *Application* ou *Armazenamento* > *Cookies* > `sid`).
2. Cole o valor do cookie no campo correspondente no painel de contas e clique em **"Guardar"**.

---

## 4. Gestão de Perfis & Contas

- **Múltiplos Mundos e Contas:** O bot suporta alternar entre perfis de diferentes mundos (ex.: `pt117`, `pt118`, `br125`).
- **Persistência Segura:** As credenciais e configurações de cada perfil são gravadas na base de dados local SQLite (`data/accounts.db`), ficando permanentemente salvas mesmo ao fechar a aplicação ou reiniciar o computador.
- **Seletor Rápido:** No topo do ecrã, utilize o menu de seleção para trocar de aldeia ou de conta ativa a qualquer momento.

---

## 5. Guia de Operação por Módulo

### 5.1 Edifício Principal & Filas de Construção
- **Templates de Construção:** Escolha perfis pré-definidos (ex.: *Económico*, *Militar Agressivo*, *Defensivo*) ou defina níveis personalizados para cada edifício.
- **Modo Rush de Pré-Requisitos:** Quando ativado, se desejar construir a Academia ou o Quartel, o bot prioriza automaticamente os edifícios pré-requisitos necessários (ex.: Edifício Principal 20, Ferreiro 20, Mercado 10).
- **Redução de Tempos & Cancelamento:** O bot calcula os custos de cada ordem e evita bloquear a fila quando há escassez de recursos.

### 5.2 Recrutamento de Tropas Balanceado
- **Aba `#tab-recruitment`:** Defina a proporção ideal de tropas para a sua aldeia (ex.: 5000 Lanceiros, 5000 Espadachins para defesa, ou 6000 Bárbaros e 2800 Cavalaria Leve para ataque).
- **Lotes Inteligentes:** O recrutamento é feito em lotes contínuos para manter os edifícios militares ocupados 24/7 sem esgotar o armazém de uma só vez.
- **Teto de População:** O bot respeita o limite percentual configurado para a Fazenda (ex.: parar ao atingir 95% da população máxima).

### 5.3 Assistente de Saque & Farm de Bárbaras
- **Aba `#tab-farm` e `#tab-settings`:**
  - **Presets Rápidos de Ritmo (Anti-Timeout):**
    - 🛡️ **Furtivo / Seguro (Recomendado):** Intervalo entre rondas de 120s a 240s e atraso de 500ms a 1100ms entre saques individuais. Elimina timeouts de rede causados por tarpitting / proteções da InnoGames.
    - ⚖️ **Equilibrado:** Intervalo de 90s a 180s com 400ms a 900ms por ataque.
    - ⚡ **Acelerado:** Intervalo de 45s a 90s com 350ms a 700ms por ataque.
  - **Modelos A e B:** Configure a composição exata de tropas enviadas por clique (ex.: Modelo A = 2 Cavalaria Leve; Modelo B = 5 Bárbaros + 1 Espião).
  - **Raio de Varredura:** Defina o raio máximo em campos (ex.: 25 campos de distância).
  - **Ataques Simultâneos:** Ative `Evitar Ataques Concorrentes` para não enviar tropas para aldeias que já tenham comandos a caminho.
  - **Filtro de Perdas:** Ao ativar `Parar em Perdas`, o bot ignora aldeias cujo último relatório tenha perdas amarelas ou vermelhas até nova espionagem.
  - **Inclusão de Bárbaras Novas:** O bot descobre automaticamente bárbaras no mapa que ainda não estejam na lista do Assistente de Saque e realiza o ataque inaugural via Praça de Reuniões.

### 5.4 Coleta de Recursos (Scavenging)
- **Aba `#tab-scavenge`:**
  - **Distribuição Balanceada:** O bot calcula a fórmula matemática oficial para que as 4 expedições de coleta (Preguiçosa, Humilde, Inteligente e Pesada) regressem exatamente ao mesmo tempo, maximizando o ganho de recursos por hora.
  - **Reserva Mínima:** Defina tropas de defesa que nunca devem ser enviadas para coleta para garantir a segurança da aldeia.
  - **Disparo Manual ou Automático:** Utilize o botão *"⚡ Disparar Ronda Imediata"* ou deixe o temporizador em segundo plano agir automaticamente.

### 5.5 Comboio de Nobres (Noble Train Builder)
- **Aba `#tab-combat` > Módulo Comboio de Nobres:**
  - Insira as coordenadas alvo `(X|Y)`.
  - Escolha o número de nobres (4 ou 5 nobres).
  - Configure o espaçamento em milissegundos (ex.: 50ms a 100ms).
  - Ative a divisão de escolta: o 1º nobre leva a tropa de limpeza ofensiva; os nobres seguintes levam apenas escolta mínima de segurança.
  - O sistema calcula e compensa a latência de rede (*ping offset*) para garantir precisão cirúrgica na chegada dos ataques.

### 5.6 Calculadora & Snipe Defensivo (com Cancel-Snipe)
- **Inserção Direta (Snipe):**
  - Insira a hora alvo com milissegundos (`HH:MM:SS.mmm`).
  - O bot lista as unidades disponíveis na aldeia ou nas suas aldeias vizinhas e indica a janela de envio exata até ao milissegundo.
- **Cancel-Snipe:**
  - Se não houver tropas noutras aldeias, clique em *"Agendar Cancel-Snipe"*.
  - O bot envia um comando de ataque ou apoio a uma aldeia bárbara próxima e exibe um temporizador regressivo no ecrã.
  - No segundo exato calculado, o comando é cancelado e as tropas regressam à sua aldeia no milissegundo exato entre o ataque de limpeza e o 1º nobre inimigo.

### 5.7 Painel Incomings & Auto-Dodge de Defesa
- **Alarme Vermelho (HUD de Perigo):**
  - Ao ser atacado, o banner superior pisca em vermelho e um alarme acústico de duplo pulso militar soa nas colunas do computador.
  - O painel lista a origem, aldeia alvo, hora de impacto e estima a unidade mais lenta (Espião, Cavalaria Leve, Bárbaro/Espada, Aríete/Catapulta ou Nobre).
- **Auto-Dodge (Desvio Automático):**
  - Ative o switch *"Auto-Dodge"*.
  - Selecione a aldeia bárbara de fuga e os segundos de antecedência (ex.: 30 segundos antes do impacto).
  - O bot retira todo o exército da aldeia antes do impacto e cancela a ordem logo a seguir, garantindo que as suas tropas regressam intactas após o ataque do inimigo.

### 5.8 Academia & Cunhagem de Moedas
- **Cunhagem Automática:**
  - Ative o módulo na aba `#tab-snob`.
  - Defina o limiar do armazém (ex.: cunhar moedas sempre que Madeira, Argila e Ferro excederem 85% da capacidade máxima).
  - Isto impede que o armazém transborde enquanto dorme ou trabalha.

### 5.9 Mercado & Balanço de Recursos
- **Aba `#tab-market`:**
  - Visualize as rotas ativas de mercadores e tempos de chegada.
  - Crie rapidamente ofertas de troca 1:1 no mercado para converter recursos em excesso (ex.: excesso de ferro) no recurso que necessita para cunhar ou recrutar.

### 5.10 Visualizador & Ativação de Inventário
- **Aba `#tab-inventory`:**
  - Visualize todos os itens da sua conta com respetivos ícones, percentual de bónus e duração.
  - Para sua segurança total, os itens **nunca são consumidos automaticamente**: cada ativação exige clique manual e confirmação explícita num modal visual.

---

## 6. Resiliência de Rede & Proxies

- **Reconexão Automática:** Se o seu Wi-Fi cair momentaneamente ou o router reiniciar, o bot efetua até 3 tentativas com backoff exponencial, restabelecendo a sessão e os cookies sem interromper a execução nem perder comandos em fila.
- **Configuração de Proxy:** Para contas adicionais, pode configurar um proxy HTTPS ou SOCKS5 residencial nos detalhes do perfil (formato: `http://utilizador:senha@ip:porta`). O tráfego de rede passará integralmente pelo túnel configurado.

---

## 7. Boas Práticas de Segurança Anti-Ban

1. **Ative Delays Naturais:** Deixe os atrasos gaussianos e micro-jitters ativos por padrão. O bot simula tempos de reação humanos que variam de clique para clique.
2. **Não Utilize Delays Abaixo de 250ms:** Para ações comuns de recolha ou construção, mantenha intervalos realistas.
3. **Pausas Regulares:** O agendador inclui pausas periódicas automáticas para simular períodos em que o jogador descansa ou está ausente.
4. **Responda aos Captchas Prontamente:** Ao ouvir o alarme sonoro, utilize o botão do navegador para resolver o desafio sem demora.

---

## 8. Perguntas Frequentes & Resolução de Problemas

### O que fazer se o bot disser "Sessão expirada"?
Abra o menu de login visual, autentique-se novamente e carregue em "Concluir Login". O cookie `sid` será atualizado automaticamente.

### Posso minimizar a janela da aplicação?
Sim! O motor continua a trabalhar normalmente em segundo plano quando a janela está minimizada.

### Onde ficam guardados os ficheiros da base de dados e logs?
Ficam todos na pasta `data/` junto ao executável (`data/accounts.db` e `data/world_data.db`). Pode fazer cópia de segurança dessa pasta para transferir as suas configurações para outro computador.

---

*Tribal Wars Bot v2.0.0 - Automação Avançada com Precisão e Segurança.*
