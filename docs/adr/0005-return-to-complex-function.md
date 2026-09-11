# ADR 0005 — Política de retorno à função complexa

- Estado: Proposto (P1, 2026-09-11)
- Relacionados: SPEC §3.4-§3.5 (T3-T7, P-3, P-4); AC-12, AC-13

## Contexto

Retornar à CF depois de uma recuperação aumenta disponibilidade, mas arrisca
chattering (CF→RF→CF repetido) e reentrada numa situação ainda perigosa.
Condicionantes:

- Voltar à CF significa o executor agendar o próprio owned mode, o que mantém
  o executor in charge [G 1.7, A.3].
- Qualquer troca de modo pelo piloto/GCS retira o executor do comando [G 1.6].
- O callback de `scheduleMode` é chamado quando o modo publica `ModeCompleted`
  ou quando o executor é desativado [G 1.3]. Quais modos internos publicam
  `ModeCompleted` (em particular Hold) não foi verificado: [DESCONHECIDO];
  a política não depende disso.

## Opções

A. Nunca retornar (RF é terminal).
B. Retornar assim que `¬U`.
C. Retornar com histerese `h`, dwell `T_d` e limite de chaveamentos (`N_max` em `W`).
D. Retornar só com confirmação do operador.

## Decisão

**C** para RF = HOLD; **A** para RTL e LAND.

1. Retorno (T5) só a partir de `RF(HOLD)`, quando `C(k)` for verdadeiro
   continuamente por `T_d` e `t_k − t_sw ≥ T_d`.
2. De `RF(RTL)` ou `RF(LAND)` não há retorno automático: essas ações indicam
   causa grave (monitor configurado ou escalonamento).
3. `N_max` chaveamentos CF→RF em `W` ⇒ `LATCHED` (sem retorno até `¬IC`).
4. Escalonamento (T6/T7) só aumenta o `rank` (`HOLD < RTL < LAND`), nunca reduz.
5. Escalonamento por persistência: `RF(HOLD)` com `U` verdadeiro por mais de
   `T_esc` = 30 s [HIPÓTESE] ⇒ `select` passa a retornar LAND. **Desabilitado
   por padrão** em v1 (`escalation_enabled=false`) até M6 medir seu efeito.
6. `return_enabled` é parâmetro de cenário; P4 compara políticas A e C com as mesmas seeds.
7. Ao retornar, a CF recebe um evento de retomada; o gateway só libera setpoints
   com timestamp posterior a `t_return` (evita setpoint velho acumulado).

## Consequências

- (+) Chattering limitado por construção (P-4), verificável em unidade (AC-13).
- (+) Distingue interrupções transitórias (tráfego que passa) de causas graves.
- (−) `T_d` e `h` aumentam o tempo fora da CF; efeito medido como taxa de conclusão de missão (P4).
- (−) Reentrada após `T_d` ainda pode encontrar risco que o preditor não modela (SPEC §7).
- Parâmetros `h`, `T_d`, `N_max`, `W`, `T_esc`: todos [HIPÓTESE], ajustados só com dados de `results/`.
