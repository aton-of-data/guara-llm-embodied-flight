# ADR 0002 — Monitores no companion (fase 1) vs. no FMU (fase 2)

- Estado: Proposto (P1, 2026-09-11)
- Relacionados: SPEC §2, §4, §7 item 7; ADR 0001

## Contexto

Os monitores Copilot podem rodar (a) como nó ROS 2 gerado pelo Ogma no
companion/SITL ou (b) como código C99 dentro de um módulo do PX4.

- O Ogma v1.15.0 gera aplicação ROS 2 com template customizável; o C dos
  monitores é inserido manualmente (`monitor.h/.c`) [G 4.3-4.6].
- O template padrão tem QoS incompatível com o PX4 [G 4.5].
- Ogma v1.15.0 tem backends cFS, ROS e F Prime [G 4.3]; **não há backend PX4**
  verificado. Integração do C gerado pelo Copilot num módulo PX4: [DESCONHECIDO].
- No companion, cada entrada chega com rate limit do bridge e latência DDS [G 3.1, 3.7].

## Opções

A. Companion: nó ROS 2 por Ogma com template próprio.
B. FMU: módulo PX4 com C99 do Copilot, assinando uORB.
C. Híbrido desde o início.

## Decisão

**A na fase 1**; B é trabalho futuro (fase 2), condicionado a um novo P0
sobre a estrutura de módulos do PX4 v1.17 e ao orçamento de CPU/memória do FMU.

Regras da fase 1:
1. Template Ogma próprio em `ros2_ws/src/guara_monitors/template/` com
   `rclcpp::SensorDataQoS()`-compatível (best-effort) e nomes `_v1` [G 3.5, 3.6].
2. Cada veredito publica `stamp` da amostra de entrada mais recente usada, para
   medir `L2` (SPEC §4).
3. Monitores são classificados `switch` (entram em `M(k)`) ou `log` (só registro).
4. O C gerado pelo Copilot não deve depender de alocação dinâmica, preservando
   a opção B.

## Consequências

- (+) Iteração rápida; reutiliza o fluxo Ogma documentado.
- (+) Isola a fase 1 de modificações no firmware.
- (−) Latência adicional `L1+L3` e dependência do bridge; monitores não veem
  dados em taxa uORB.
- (−) Não herda o isolamento do FMU (SPEC §7 item 7).
- Critério para abrir a fase 2: p99 de `L1+L2+L3` (M7) impedindo O-1 com
  parâmetros operacionalmente aceitáveis.
