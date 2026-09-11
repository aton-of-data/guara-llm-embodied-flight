# ADR 0001 — Árbitro RTA como ModeExecutor vs. nó independente

- Estado: Proposto (P1, 2026-09-11)
- Relacionados: SPEC §2, §3.5, §4, §5; ADR 0005

## Contexto

O árbitro precisa (a) retirar a função complexa (CF) do controle e (b) acionar
Hold/RTL/Land com latência mensurável, e (c) ter falhas próprias com reação
conhecida do PX4. Fatos relevantes:

- `ModeExecutorBase::scheduleMode/rtl/land` acionam modos internos via
  `VEHICLE_CMD_SET_NAV_STATE` em tópico dedicado [G 1.1-1.4].
- O executor só fica in charge quando seu owned mode é selecionado; troca feita
  pelo usuário (RC/MAVLink) devolve o controle ao autopiloto; trocas feitas pelo
  executor o mantêm in charge [G 1.6, A.2, A.3].
- Um modo externo que para de responder ao arming check leva o PX4 a RTL em
  ~1,2 s; `can_arm_and_run=false` produz o mesmo efeito em ≤ ~300 ms [G 2.1-2.4, A.5, A.6].
- Com o veículo armado o PX4 não aceita novos registros [G 2.7].
- `sendCommandSync` aloca e pode bloquear ~3,9 s [G A.1].

## Opções

**A. ModeExecutor com owned mode "gateway" da CF (mesmo processo).**
A CF publica setpoints num tópico do Guará; o owned mode os repassa ao PX4.

**B. ModeExecutor cujo owned mode é a própria CF em outro processo.**
Exige que a CF registre o modo e que o executor seja o mesmo registro —
a interface-lib associa executor e owned mode no mesmo objeto [G 1.5]; não há
evidência de executor possuir modo de outro processo. [DESCONHECIDO] → descartada sem novo P0.

**C. Nó independente enviando `vehicle_command` como GCS.**
Comandos com fonte `User` retiram qualquer executor do comando [G A.3]; o
árbitro não teria owned mode, portanto nenhum sinal de vida monitorado pelo
PX4 (FM-1/FM-4 sem reação). Aceitação de `SET_NAV_STATE` vindo de
`/fmu/in/vehicle_command` não foi verificada: [DESCONHECIDO].

## Decisão

Opção **A**, com as regras:

1. Processo `guara_rta` contém `GuaraExecutor` (ModeExecutorBase) e
   `GuaraCfGateway` (ModeBase, owned mode). `Settings.activation =
   ActivateOnlyWhenArmed` (padrão) [G 1.5].
2. **Separação decisão/atuação:** `DecisionCore` é código puro (sem ROS, sem
   alocação após init, tempo limitado) executado por timer de período `T_s`.
   A atuação (`scheduleMode`, `rtl`, `land`) roda em callback group separado,
   alimentada por uma fila de capacidade fixa. O bloqueio de [G A.1] fica fora
   do caminho de decisão, conforme CLAUDE.md.
3. **Heartbeat do núcleo:** `GuaraCfGateway::checkArmingAndRunConditions`
   reporta falha se a idade do último tick do núcleo > `H_max` (FM-4) [G A.4-A.6].
4. **Gateway como Input Manager:** no tick que dispara T3, o gateway passa a
   publicar velocidade zero e descarta a CF até voltar ao estado `CF` (FM-7).
5. O Guará **nunca** chama `deferFailsafesSync(true)` (AC-20).
6. `COM_MODE_ARM_CHK` permanece `0`: aceitar registro em voo abriria a porta
   para componentes não inspecionados antes da decolagem. Consequência aceita: FM-3.

## Consequências

- (+) Morte ou travamento do árbitro com CF ativa cai na cadeia de fallback do
  PX4 (RTL), sem código extra no FMU.
- (+) A CF não comanda o PX4 diretamente pelo caminho previsto; o gateway pode
  bloqueá-la no mesmo tick da decisão.
- (−) A CF depende do processo do árbitro: crash do árbitro interrompe a CF.
- (−) Com RF interna ativa, morte do árbitro não é detectada (FM-2).
- (−) Piloto que troca de modo desliga o Guará até reentrar no owned mode (por projeto).
- (−) FM-12: o gateway não impede outros publicadores em `/fmu/in/trajectory_setpoint` [G A.13].
- Riscos a verificar em M3: AC-15, AC-15b, AC-16, AC-16b, AC-21.
