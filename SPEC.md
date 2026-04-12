# League of Legends Auto Attack Tool - Especificação

## 1. Visão Geral do Projeto

**Nome:** LoL Auto Attack CV  
**Tipo:** Ferramenta de automação para League of Legends  
**Funcionalidade:** Detectar automaticamente minions e campeões inimigos na tela usando visão computacional e executar auto-ataque quando há alvo em alcance.  
**Plataforma:** macOS (funcionando com trackpad/sem mouse físico)

## 2. Problema Identificado

- O League of Legends lançou um novo sistema de controle onde o movimento é feito com WASD
- O auto-ataque existente que usa movimento do mouse não funciona com o novo controle WASD
- Usuários de MacBook sem mouse físico têm dificuldade para fazer auto-ataques
- O trackpad do MacBook não oferece precisão adequada para jogabilidade competitiva

## 3. Solução

### Abordagem Técnica
- Usar **PyAutoGUI** para captura de tela e controle do mouse
- Usar **OpenCV** para visão computacional (detecção de objetos)
- Detectar minions e campeões inimigos através de reconhecimento de cores e formas
- Posicionar o cursor do mouse sobre o alvo detectado e clicar automaticamente

### Arquitetura
```
[Captura de Tela] -> [Processamento de Imagem (OpenCV)] -> [Detecção de Alvos] -> [Clique Automático]
```

### Componentes Principais
1. **Screen Capture**: Captura regionada da tela do jogo
2. **Object Detection**: Detecção de minions (cores azul/vermelho para aliados/inimigos)
3. **Target Selection**: Selecionar o alvo mais próximo ou de maior prioridade
4. **Auto Click**: Executar clique quando alvo está em alcance

## 4. Funcionalidades

### Core Features
- [ ] Captura de tela em tempo real do jogo
- [ ] Detecção de minions inimigos por cor (vermelho = inimigo)
- [ ] Detecção de campeões inimigos
- [ ] Clique automático no alvo detectado
- [ ] Toggle de ativação/desativação (tecla hotkey)
- [ ] Ajuste de sensibilidade e área de detecção

### Configurações
- Tecla de ativação: `F` (configurável)
- Área de captura: Definida pelo usuário
- Delay entre cliques: Ajustável (para evitar spam)
- Prioridade de alvo: Mais próximo / Mais saúde / Campeão primeiro

## 5. Requisitos Técnicos

### Bibliotecas Python
- `pyautogui` - Controle de mouse e captura
- `opencv-python` - Processamento de imagem
- `numpy` - Operações matemáticas
- `pygetwindow` - Gerenciamento de janelas
- `pynput` - Captura de teclas globais

### Considerações de Segurança
- Não violar Terms of Service do LoL (usar com responsabilidade)
- Implementar delays e naturalidade nos movimentos
- Não interferir com other processos do sistema