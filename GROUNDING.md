# GROUNDING.md — P0

Fatos verificados no código-fonte clonado em `third_party/` (commits em
`third_party/VERSIONS.md`). Nenhuma resposta vem de memória.

Abreviações de evidência (`repo@commit:arquivo:linha`):

| Alias | Repositório@commit |
|---|---|
| `PX4@d6f12ad` | PX4-Autopilot v1.17.0 |
| `msgs@86d8239` | px4_msgs release/1.17 |
| `lib@4a3370f` | px4-ros2-interface-lib release/1.17 |
| `ogma@69485b3` | ogma v1.15.0 |
| `daa@0647596` | daidalus DAIDALUSv2.0.3a |
| `cop@365fb21` | copilot v4.8.1 |

Caminhos curtos: `lib/…` = `px4_ros2_cpp/…`; `cmd/…` = `src/modules/commander/…`;
`dds/…` = `src/modules/uxrce_dds_client/…`.

Confiança: **ALTA** = lido diretamente no código; **MÉDIA** = inferido
combinando trechos lidos, sem execução; **DESCONHECIDO** = sem evidência.

---

## R0 — Pré-condições de versão

| # | resposta | evidência | confiança |
|---|---|---|---|
| R0.1 | Mensagens de `px4_msgs@86d8239` são idênticas às de PX4 v1.17.0 (0 arquivos diferentes). | comando em `third_party/VERSIONS.md`; `PX4@d6f12ad:msg/versioned/` | ALTA |
| R0.2 | A documentação do PX4 v1.17.0 declara ROS 2 **Humble** (Ubuntu 22.04) como plataforma suportada e recomendada. | `PX4@d6f12ad:docs/en/ros2/user_guide.md:53` | ALTA |
| R0.3 | CI da interface-lib compila contra Humble; pacotes Debian são gerados para Humble e Jazzy. | `lib@4a3370f:.github/workflows/build_and_test.yml:22,33`; `lib@4a3370f:.github/workflows/build-publish-debian-packages.yml:23,25` | ALTA |
| R0.4 | O Dockerfile do template ROS do Ogma usa `osrf/space-ros:jazzy-2026.04.0` (Jazzy), divergente de R0.2. | `ogma@69485b3:ogma-core/templates/ros/Dockerfile:1,21` | ALTA |

---

## Q1 — ModeExecutor ativando modos internos (Hold, RTL, Land)

| # | resposta | evidência | confiança |
|---|---|---|---|
| 1.1 | API genérica: `void scheduleMode(ModeBase::ModeID mode_id, const CompletedCallback& on_completed, bool forced=false)`. Atalhos: `takeoff(cb, alt, heading)`, `land(cb)`, `rtl(cb)`. `CompletedCallback = std::function<void(Result)>`. | `lib@4a3370f:lib/include/px4_ros2/components/mode_executor.hpp:34,102-108` | ALTA |
| 1.2 | IDs de modo internos expostos: `kModeIDLand` (`NAVIGATION_STATE_AUTO_LAND`=18), `kModeIDRtl` (`AUTO_RTL`=5), `kModeIDLoiter` (`AUTO_LOITER`=4), `kModeIDDescend`, `kModeIDPosctl`, `kModeIDTakeoff`, `kModeIDPrecisionLand`. **Não existe `kModeIDHold`**; "Hold" corresponde a `AUTO_LOITER` (o próprio PX4 usa `AUTO_LOITER` ao "switch to Hold"). | `lib@4a3370f:lib/include/px4_ros2/components/mode.hpp:73-89`; `msgs@86d8239:msg/VehicleStatus.msg:40,41,54`; `PX4@d6f12ad:cmd/ModeManagement.cpp:358-361` | ALTA |
| 1.3 | Implementação: `scheduleMode` envia `VEHICLE_CMD_SET_NAV_STATE` com `param1=mode_id` via `sendCommandSync` (bloqueia até ACK); cancela agendamento anterior; se desarmado e `forced=false`, retorna `Result::Rejected` sem enviar. O callback é chamado quando o modo publica `ModeCompleted` ou quando o executor é desativado. | `lib@4a3370f:lib/src/components/mode_executor.cpp:225-261` | ALTA |
| 1.4 | Comandos do executor saem no tópico `fmu/in/vehicle_command_mode_executor`, distinto de `fmu/in/vehicle_command`. | `lib@4a3370f:lib/src/components/mode_executor.cpp:48`; `PX4@d6f12ad:dds/dds_topics.yaml:176-177` | ALTA |
| 1.5 | Sequência de chamadas: (a) subclasse de `ModeExecutorBase` com um `ModeBase` próprio ("owned mode"); (b) `doRegister()` do executor e do modo no startup (bloqueante) — `NodeWithModeExecutor` faz isso; (c) PX4 chama `onActivate()` quando o executor fica "in charge"; (d) dentro da máquina de estados, `rtl(cb)` / `land(cb)` / `scheduleMode(kModeIDLoiter, cb)`; (e) `onDeactivate(reason)` quando perde o controle. Exemplo real: takeoff → `scheduleMode(ownedMode().id())` → `rtl` → `waitUntilDisarmed`. | `lib@4a3370f:lib/include/px4_ros2/components/mode_executor.hpp:59-78`; `lib@4a3370f:lib/include/px4_ros2/components/node_with_mode.hpp:117-120`; `lib@4a3370f:examples/cpp/modes/mode_with_executor/include/mode.hpp:75-120` | ALTA |
| 1.6 | **Condição de "in charge"**: `VehicleStatus.executor_in_charge == id()` e (armado ou `ActivateAlways` ou `ActivateImmediately` na 1ª vez). O PX4 só coloca o executor no comando quando o usuário entra no **owned mode**; se o usuário (RC/GCS) troca para um modo não pertencente ao executor, o controle volta ao autopiloto (`AUTOPILOT_EXECUTOR_ID`) e o executor recebe `onDeactivate(Other)`; em failsafe recebe `onDeactivate(FailsafeActivated)`. | `lib@4a3370f:lib/src/components/mode_executor.cpp:369-385`; `PX4@d6f12ad:cmd/ModeManagement.cpp:415-434`; `msgs@86d8239:msg/VehicleStatus.msg:69` | ALTA |
| 1.7 | Consequência para o árbitro: modos agendados pelo executor (Hold/RTL/Land) **mantêm** o executor in charge; o árbitro só arbitra enquanto o owned mode (função complexa) ou um modo que ele agendou estiver ativo. | `lib@4a3370f:lib/src/components/mode_executor.cpp:256-260,387-396` | MÉDIA |
| 1.8 | `deferFailsafesSync(enabled, timeout_s)` adia a maioria dos failsafes enquanto o executor está in charge (0 = padrão do sistema, −1 = sem timeout); padrão do FMU = 30 s. Não adia limites de atitude nem "modo não pode rodar". `onFailsafeDeferred()` é chamado quando o FMU queria entrar em failsafe. | `lib@4a3370f:lib/include/px4_ros2/components/mode_executor.hpp:80-84,127-139`; `PX4@d6f12ad:cmd/failsafe/framework.h:50` | ALTA |

---

## Q2 — Executor / modo externo que para de responder

| # | resposta | evidência | confiança |
|---|---|---|---|
| 2.1 | Mecanismo de vida: o commander publica `ArmingCheckRequest` a cada `UPDATE_INTERVAL = 300 ms`; resposta esperada em `REQUEST_TIMEOUT = 50 ms`. Constantes **compiladas** (`static constexpr`), não parâmetros. | `PX4@d6f12ad:cmd/HealthAndArmingChecks/checks/externalChecks.hpp:69-71`; `PX4@d6f12ad:cmd/HealthAndArmingChecks/checks/externalChecks.cpp:286-305` | ALTA |
| 2.2 | Registro é marcado **unresponsive** quando `++num_no_response > NUM_NO_REPLY_UNTIL_UNRESPONSIVE (3)`; logo após registrar, o limite é `NUM_NO_REPLY_UNTIL_UNRESPONSIVE_INIT (10)`. Uma resposta zera o contador. | `PX4@d6f12ad:cmd/HealthAndArmingChecks/checks/externalChecks.hpp:72-75`; `…/externalChecks.cpp:237-238,256-278` | ALTA |
| 2.3 | Tempo de detecção derivado: ~4 ciclos × 300 ms ≈ 1,2 s (+ até 50 ms) após a última resposta. **HIPÓTESE a medir** — não medido. | derivado de 2.1 + 2.2 | MÉDIA |
| 2.4 | Efeito com o veículo armado no modo externo: o bit `mode_req_other` do modo é setado → `modeCanRun()` falso → `checkModeFallback` retorna `Action::RTL`, marcado `cannotBeDeferred()` e `allowUserTakeover(Always)` (por isso **sem** o atraso `COM_FAIL_ACT_T`). Se RTL também não puder rodar, o framework cai para os fallbacks seguintes (Land/Descend…). Evento: "Mode is unresponsive". | `…/externalChecks.cpp:130-135,207-214`; `PX4@d6f12ad:cmd/HealthAndArmingChecks/checks/modeCheck.cpp:184-186`; `PX4@d6f12ad:cmd/failsafe/framework.cpp:699-716`; `PX4@d6f12ad:cmd/failsafe/failsafe.cpp:638-641,698-702`; `PX4@d6f12ad:cmd/failsafe/framework.cpp:350-360` | MÉDIA (cadeia lida; não exercitada em SITL) |
| 2.5 | Se o modo substitui um modo interno (`replaces_nav_state`) e está unresponsive, o PX4 usa o modo interno ("External mode is unresponsive, falling back to internal"). | `PX4@d6f12ad:cmd/ModeManagement.cpp:437-461` | ALTA |
| 2.6 | O timeout rastreia o **registro do arming check do modo**, não o executor em si. Se o árbitro morrer enquanto um modo **interno** agendado por ele (ex.: Hold) está ativo, nenhum código lido força saída desse modo interno. | `…/externalChecks.cpp:130-135` (só age com `nav_mode_id != -1`) | MÉDIA |
| 2.7 | **Com o veículo armado** (padrão `COM_MODE_ARM_CHK=0`): novos registros são rejeitados ("Not accepting registration requests while armed") e remoções/unregistrations só são processadas desarmado. ⇒ um árbitro que reinicia em voo **não consegue se re-registrar**. | `PX4@d6f12ad:cmd/ModeManagement.cpp:372-388,389-408`; `PX4@d6f12ad:cmd/commander_params.c:1039-1048` | ALTA |
| 2.8 | Unregister explícito do modo ativo (desarmado) → troca para Hold (`AUTO_LOITER`). No `onDisarm`, modo unresponsive → Hold. | `PX4@d6f12ad:cmd/ModeManagement.cpp:358-361,485-489` | ALTA |
| 2.9 | Parâmetros relacionados: `COM_FAIL_ACT_T` (padrão 5 s, atraso em Hold antes do failsafe para ações com takeover `Auto`); `COM_OF_LOSS_T` (padrão 1 s, só para o nav_state `OFFBOARD`, não para modos externos); `COM_MODE_ARM_CHK` (padrão 0). | `PX4@d6f12ad:cmd/commander_params.c:298-311,340`; `PX4@d6f12ad:cmd/HealthAndArmingChecks/checks/offboardCheck.cpp:38-66`; `PX4@d6f12ad:cmd/failsafe/failsafe.cpp:665` | ALTA |
| 2.10 | Não há watchdog de setpoint para modos externos equivalente a `COM_OF_LOSS_T`: um processo com a thread de setpoints travada mas callbacks de arming check ativos (multi-thread) não seria detectado por 2.1–2.4. | ausência verificada em `offboardCheck.cpp` (só `OFFBOARD`) e `externalChecks.cpp` | MÉDIA |

---

## Q3 — Tópicos `/fmu/out/*` padrão e tráfego

| # | resposta | evidência | confiança |
|---|---|---|---|
| 3.1 | Publicações padrão (27): `register_ext_component_reply`, `arming_check_request` (5 Hz), `mode_completed` (50), `battery_status` (1), `collision_constraints` (50), `estimator_status_flags` (5), `failsafe_flags` (5), `manual_control_setpoint` (25), `message_format_response`, `position_setpoint_triplet` (5), `sensor_combined`, `timesync_status` (10), `transponder_report`, `vehicle_land_detected` (5), `vehicle_attitude`, `vehicle_control_mode` (50), `vehicle_command_ack`, `vehicle_global_position` (50), `vehicle_gps_position` (50), `vehicle_local_position` (50), `vehicle_odometry`, `vehicle_status` (5), `airspeed_validated` (50), `vtol_vehicle_status`, `home_position` (5), `wind` (1), `gimbal_device_attitude_status` (20). Sem `rate_limit` = taxa de publicação uORB. | `PX4@d6f12ad:dds/dds_topics.yaml:6-109` | ALTA |
| 3.2 | **`/fmu/out/transponder_report` é exposto por padrão** (`px4_msgs::msg::TransponderReport`: lat/lon em graus, altitude AMSL m, heading rad, hor/ver velocity m/s, `tslc`, `flags` de validade). | `PX4@d6f12ad:dds/dds_topics.yaml:53-54`; `msgs@86d8239:msg/TransponderReport.msg:1-25` | ALTA |
| 3.3 | Fontes de `transponder_report` no PX4: MAVLink `ADSB_VEHICLE` (mavlink_receiver), driver Sagetech MXS e `navigator fake_traffic` (publica 24 relatórios falsos em torno da posição atual). **Não há** `/fmu/in/transponder_report`; injetar intrusos pelo ROS 2 exige MAVLink `ADSB_VEHICLE`, `fake_traffic`, ou adicionar a assinatura em `dds_topics.yaml` (build custom). | `PX4@d6f12ad:src/modules/mavlink/mavlink_receiver.cpp:224`; `PX4@d6f12ad:src/modules/navigator/navigator_main.cpp:1258-1260,1331-1333,1688`; `PX4@d6f12ad:dds/dds_topics.yaml:112-225` | ALTA |
| 3.4 | Nenhum tópico de geofence (`geofence_result`, `geofence_status`) é exposto por padrão, embora as mensagens existam. Preditor de geofence precisa manter o polígono no companion ou customizar `dds_topics.yaml`. | `grep -c geofence dds_topics.yaml` = 0; `PX4@d6f12ad:msg/GeofenceResult.msg`, `msg/GeofenceStatus.msg` | ALTA |
| 3.5 | Nomes de tópico recebem sufixo `_v<N>` quando `MESSAGE_VERSION != 0`: `vehicle_status` → `/fmu/out/vehicle_status_v1`, `vehicle_local_position` → `/fmu/out/vehicle_local_position_v1`; `vehicle_global_position`, `vehicle_attitude`, `vehicle_odometry` sem sufixo (versão 0). Interface-lib aplica o mesmo sufixo (exceto com rmw_zenoh). | `PX4@d6f12ad:dds/utilities.hpp:26-41`; `msgs@86d8239:msg/VehicleStatus.msg:3`; `msgs@86d8239:msg/VehicleLocalPosition.msg:4`; `msgs@86d8239:msg/VehicleGlobalPosition.msg:8`; `lib@4a3370f:lib/include/px4_ros2/utils/message_version.hpp:54-62` | ALTA |
| 3.6 | QoS dos publishers do PX4: `BEST_EFFORT`, `TRANSIENT_LOCAL`, `KEEP_LAST`. Assinantes ROS 2 **devem** usar QoS compatível (docs: `rmw_qos_profile_sensor_data`). | `PX4@d6f12ad:dds/utilities.hpp:78-83`; `PX4@d6f12ad:docs/en/ros2/user_guide.md:403-413` | ALTA |
| 3.7 | `vehicle_status` é limitado a 5 Hz no bridge: a confirmação de troca de modo observada via `vehicle_status` tem granularidade ≥ 200 ms; `vehicle_command_ack` não tem rate limit. Relevante para o orçamento de latência. | `PX4@d6f12ad:dds/dds_topics.yaml:70-71,88-90` | ALTA |

---

## Q4 — Variable DB do Ogma para o backend `ros`

| # | resposta | evidência | confiança |
|---|---|---|---|
| 4.1 | Formato JSON com três chaves: `inputs` (nome, tipo C, `active`, `connections[{scope:"ros/message", topic, field}]`), `topics` (`scope`, `topic`, `type` da mensagem ROS 2) e `types` (mapeamento `fromScope/fromType/fromField` → `toScope:"C"/toType`). `field` permite extrair um campo de mensagem composta. | `ogma@69485b3:ogma-cli/README.md:444-485`; `ogma@69485b3:ogma-core/CHANGELOG.md:29` (#499) | ALTA |
| 4.2 | **Exemplo mínimo real** (turtlesim, campo `x` de `turtlesim::msg::Pose`): ver bloco abaixo. | `ogma@69485b3:ogma-cli/examples/ros2-turtlesim/vars-db-turtlesim.json:1-27` | ALTA |
| 4.3 | Invocação real: `ogma ros --project ogma-cli/examples/ros2-turtlesim/project.ogma`, ou flags `--input-file`, `--input-format`, `--variable-file`, `--variable-db`, `--handlers-file`, `--template-dir`, `--template-vars`, `--target-dir`, `--testing-app`. **O README cita `--handlers`, mas o código define `--handlers-file`**. | `ogma@69485b3:ogma-cli/examples/ros2-turtlesim/README.md:59`; `ogma@69485b3:ogma-cli/src/CLI/CommandROSApp.hs:179-270`; `ogma@69485b3:ogma-cli/README.md:414,422` | ALTA |
| 4.4 | Template gerado: `msg->{{varDeclMsgField}}` se houver `field`, senão `msg->data`. | `ogma@69485b3:ogma-core/templates/ros/copilot/src/copilot_monitor.cpp:88-93` | ALTA |
| 4.5 | **Incompatibilidade de QoS**: o template assina com `create_subscription<T>(topic, 10, …)` (QoS padrão = RELIABLE). Com publishers BEST_EFFORT do PX4 (3.6), a assinatura não recebe dados. ⇒ M2 precisa de `--template-dir` próprio com QoS best-effort. | `ogma@69485b3:ogma-core/templates/ros/copilot/src/copilot_monitor.cpp:38-40`; `PX4@d6f12ad:dds/utilities.hpp:78-83` | ALTA (código); efeito em execução MÉDIA |
| 4.6 | Limitação documentada: o código C dos monitores Copilot não é gerado pelo comando `ros`; deve ser colocado em `monitor.h` / `monitor.c`. | `ogma@69485b3:ogma-cli/README.md:556-560` | ALTA |
| 4.7 | Ogma aceita especificações de componente do FRET (formatos `fcs_smv`, `fcs_lustre`). | `ogma@69485b3:ogma-core/data/formats/` | MÉDIA (formatos listados; fluxo FRET→Ogma não executado) |

Exemplo real (`vars-db-turtlesim.json`, íntegra):

```json
{ "inputs":
     [ { "name": "input_signal"
       , "type": "float"
       , "active": true
       , "connections":
           [ { "scope": "ros/message"
             , "topic": "/turtle1/pose"
             , "field": "x"
             }
           ]
       }
     ]
, "topics":
     [ { "scope": "ros/message"
       , "topic": "/turtle1/pose"
       , "type":  "turtlesim::msg::Pose"
       }
     ]
, "types": [
       { "fromScope": "ros/message"
       , "fromType":  "turtlesim::msg::Pose"
       , "fromField": "x"
       , "toScope":   "C"
       , "toType":    "float"
       }
     ]
}
```

---

## Q5 — API C++ do DAIDALUS v2

| # | resposta | evidência | confiança |
|---|---|---|---|
| 5.1 | Ownship: `void setOwnshipState(const std::string& id, const Position& pos, const Velocity& vel, double time)` (e sobrecarga sem `time`). Deve ser chamado antes dos intrusos. | `daa@0647596:C++/include/Daidalus.h:201,209` | ALTA |
| 5.2 | Intrusos: `int addTrafficState(const std::string& id, const Position& pos, const Velocity& vel[, double time])` → índice (1..`lastTrafficIndex()`; 0 = ownship). | `daa@0647596:C++/include/Daidalus.h:222,232,275-279` | ALTA |
| 5.3 | Construtores: `Position::makeLatLonAlt(lat,"deg", lon,"deg", alt,"ft")` e `Velocity::makeTrkGsVs(trk,"deg", gs,"knot", vs,"fpm")` (unidades como string). Vento: `setWindVelocityFrom(Velocity)`. | `daa@0647596:C++/include/Position.h:75,88`; `daa@0647596:C++/include/Velocity.h:244,260`; `daa@0647596:C++/include/Daidalus.h:317`; `daa@0647596:C++/examples/DaidalusExample.cpp:350-368` | ALTA |
| 5.4 | Tempo até violação: `double timeToCorrectiveVolume(int ac_idx)` (s relativo; `+inf` = sem conflito no lookahead; `NaN` = índice inválido). Por nível: `ConflictData violationOfAlertThresholds(int ac_idx, int alert_level)` → `conflict()`, `getTimeIn()`, `getTimeOut()`. Nível: `alertLevel(ac_idx)`, `alertLevelAllTraffic()`. | `daa@0647596:C++/include/Daidalus.h:2502-2515,2526-2551`; `daa@0647596:C++/include/ConflictData.h:27`; `daa@0647596:C++/include/LossData.h:66`; `daa@0647596:C++/examples/DaidalusExample.cpp:55-66` | ALTA |
| 5.5 | Qual função corresponde a "perda de well-clear" depende do alerter/região configurados (`corrective_region = MID` no DO-365B). Mapear "tempo até perda de DWC" para `timeToCorrectiveVolume` vs `violationOfAlertThresholds(idx, nível)` é decisão de SPEC. | `daa@0647596:Configurations/DO_365B_no_SUM.conf:72-80` | MÉDIA |
| 5.6 | Bandas: `horizontalDirectionBandsLength()`, `horizontalDirectionIntervalAt(i[, unit])`, `horizontalDirectionRegionAt(i)`; também resoluções e `horizontalDirectionRecoveryInformation()`. Existem famílias análogas para velocidade horizontal, vertical e altitude. | `daa@0647596:C++/include/Daidalus.h:1898-1923`; `daa@0647596:C++/examples/DaidalusExample.cpp:107-131` | ALTA |
| 5.7 | Configuração DO-365B: programática `set_DO_365B(bool type=true, bool sum=true)` (alerters Phase I, Phase II, Non-Cooperative) ou arquivo `loadFromFile("Configurations/DO_365B_SUM.conf")` / `DO_365B_no_SUM.conf`. | `daa@0647596:C++/include/Daidalus.h:142-153,1810`; `daa@0647596:Configurations/DO_365B_SUM.conf`; `daa@0647596:C++/examples/DaidalusExample.cpp:305-309,343` | ALTA |
| 5.8 | Valores do arquivo DO-365B (configuração do repositório, não afirmação regulatória): `lookahead_time = 180 s`, DWC Phase I `DTHR = 0.66 nmi`, `ZTHR = 700/450 ft`. Dimensionados para aeronaves maiores; uso com drones pequenos exige configuração própria — **HIPÓTESE a validar**. | `daa@0647596:Configurations/DO_365B_no_SUM.conf:4`; `daa@0647596:Configurations/DO_365B_SUM.conf:85-99` | ALTA (valores); MÉDIA (adequação) |
| 5.9 | Build C++: `Makefile` (sem CMake no repositório) ⇒ o pacote ROS 2 do DAIDALUS precisará de CMake próprio. | `daa@0647596:C++/Makefile`; `find C++ -name CMakeLists.txt` vazio | ALTA |
| 5.10 | Licença: NASA Open Source Agreement (`DAIDALUS2-NOSA.pdf`). Termos específicos do PDF não foram lidos nesta sessão. | `daa@0647596:README.md:66-69`; `daa@0647596:LICENSES/DAIDALUS2-NOSA.pdf` | ALTA (tipo); DESCONHECIDO (termos) |

---

## Q6 — CopilotVerifier

| # | resposta | evidência | confiança |
|---|---|---|---|
| 6.1 | Sim: `copilot-verifier` versão 4.8.1 está no monorepo do Copilot v4.8.1 e depende de `copilot-c99 >= 4.8.1 && < 4.9`. | `cop@365fb21:copilot-verifier/copilot-verifier.cabal:2-3,48` | ALTA |
| 6.2 | Invocação (Haskell): `Copilot.Verifier.verify :: CSettings -> [String] -> String -> Spec -> IO ()` (`verify csettings props prefix spec`) ou `verifyWithOptions :: VerifierOptions -> …` (ex.: `sideCondVerifierOptions`). Gera C99, compila para bitcode LLVM com `clang`, interpreta com Crucible e envia VCs a SMT. | `cop@365fb21:copilot-verifier/src/Copilot/Verifier.hs:168-172,264-267`; `cop@365fb21:copilot-verifier/README.md:72-80,294` | ALTA |
| 6.3 | Pré-requisitos: GHC 9.4/9.6/9.8 (`base < 4.20`), Cabal ≥ 3.10, `clang` + `llvm-link` **LLVM ≤ 16**, `z3` (ou cvc4/cvc5/yices). Deps: crucible 0.7, crucible-llvm 0.7, crux-llvm 0.9, what4 ≥1.6.1 <1.8. | `cop@365fb21:copilot-verifier/README.md:28-45`; `cop@365fb21:copilot-verifier/copilot-verifier.cabal:44-65` | ALTA |
| 6.4 | Escopo: verifica o C gerado pelo `copilot-c99` contra a semântica do `Spec`; não cobre o glue C++/ROS gerado pelo Ogma. | `cop@365fb21:copilot-verifier/copilot-verifier.cabal:13-18` | ALTA |
| 6.5 | Nenhuma ferramenta Haskell (ghc/cabal/stack), LLVM ou z3 está instalada nesta máquina; verifier não executado. | `which ghc cabal stack` → not found | ALTA |

---

## Adendo A — fatos adicionais verificados durante o P1 (2026-09-11)

Mesma regra do P0: somente código clonado. Estes itens sustentam decisões da SPEC e dos ADRs.

| # | resposta | evidência | confiança |
|---|---|---|---|
| A.1 | `sendCommandSync` (usado por `scheduleMode`/`rtl`/`land`) **cria uma subscription a cada chamada** (alocação dinâmica), faz espera ativa de até 3000 ms pela descoberta do publisher de `vehicle_command_ack`, depois publica o comando até 3 vezes esperando 300 ms por ACK. Pior caso de bloqueio da thread chamadora ≈ 3,9 s. O comando é publicado **antes** da espera pelo ACK. | `lib@4a3370f:lib/src/components/mode_executor.cpp:141-222` | ALTA |
| A.2 | `source_component = COMPONENT_MODE_EXECUTOR_START + id()`; o commander classifica comandos com `source_component >= COMPONENT_MODE_EXECUTOR_START` como `ModeChangeSource::ModeExecutor`. | `lib@4a3370f:lib/src/components/mode_executor.cpp:141`; `PX4@d6f12ad:cmd/Commander.cpp:1561,1567-1574` | ALTA |
| A.3 | Ao trocar para um nav_state sem executor associado, o executor in charge **só muda** se a fonte for `User` (RC/MAVLink); com fonte `ModeExecutor` permanece. | `PX4@d6f12ad:cmd/ModeManagement.cpp:415-434`; `PX4@d6f12ad:cmd/UserModeIntention.hpp:39-42` | ALTA |
| A.4 | `ModeBase` expõe `checkArmingAndRunConditions(reporter)` (chamado periodicamente, inclusive com o modo ativo), `onActivate/onDeactivate`, `setSetpointUpdateRate(hz)` e `updateSetpoint(dt_s)`. | `lib@4a3370f:lib/include/px4_ros2/components/mode.hpp:132-161` | ALTA |
| A.5 | A resposta ao `ArmingCheckRequest` é produzida no callback da subscription do próprio nó (QoS best-effort, depth 1), chamando o callback de checagem do modo; `reporter.armingCheckFailureExt(...)` põe `can_arm_and_run=false`. | `lib@4a3370f:lib/src/components/health_and_arming_checks.cpp:29-56`; `lib@4a3370f:lib/include/px4_ros2/components/health_and_arming_checks.hpp:30-37` | ALTA |
| A.6 | No PX4, `can_arm_and_run=false` de um modo externo seta `mode_req_other` para esse modo → mesma cadeia de fallback de 2.4 (modo não pode rodar → RTL). Latência de detecção ≤ 1 período de requisição (300 ms) + processamento. | `PX4@d6f12ad:cmd/HealthAndArmingChecks/checks/externalChecks.cpp:157-159`; itens 2.1 e 2.4 | MÉDIA (tempo não medido) |
| A.7 | Setpoints de trajetória: `px4_ros2::TrajectorySetpointType::update(velocity_ned, accel?, yaw?, yaw_rate?)`, `update(TrajectorySetpoint)`, `updatePosition(position_ned)`; `MulticopterGotoSetpointType` existe. | `lib@4a3370f:lib/include/px4_ros2/control/setpoint_types/experimental/trajectory.hpp:26-66`; `lib@4a3370f:lib/include/px4_ros2/control/setpoint_types/multicopter/goto.hpp:24,44` | ALTA |
| A.8 | `VehicleLocalPosition` (tópico `_v1`): `timestamp`, `timestamp_sample` (µs), `x,y,z` NED (m), `vx,vy,vz` (m/s), `ax,ay,az`, flags `xy_valid`, `v_xy_valid`, `z_valid`, `v_z_valid`, contadores de reset, `ref_lat/ref_lon/ref_alt`, `eph/epv/evh/evv`, `dead_reckoning`. | `msgs@86d8239:msg/VehicleLocalPosition.msg:6-77` | ALTA |
| A.9 | Na serialização DDS, os campos `timestamp` e `timestamp_sample` recebem `+ time_offset` da sessão uXRCE (sincronização com o agente); os demais campos de tempo não. | `PX4@d6f12ad:Tools/msg/templates/ucdr/msg.h.em:127-144`; `PX4@d6f12ad:dds/dds_topics.h.em:126,176` | ALTA (código); relógio de referência resultante no ROS 2: MÉDIA |
| A.10 | ULog registra por padrão `vehicle_status`, `vehicle_command`, `vehicle_local_position` e `transponder_report`. | `PX4@d6f12ad:src/modules/logger/logged_topics.cpp:132,138,145,150` | ALTA |
| A.11 | Geofence interno do PX4: `GF_ACTION` (padrão 2 = Hold; 3 RTL; 4 Terminate; 5 Land), `GF_SOURCE`, `GF_MAX_HOR_DIST`/`GF_MAX_VER_DIST` (0 = desabilitado), `GF_PREDICT` (padrão 0, marcado **[EXPERIMENTAL]** "may cause flyaways"). | `PX4@d6f12ad:src/modules/navigator/geofence_params.c:46-119` | ALTA |
| A.12 | Licença do DAIDALUS = **NASA Open Source Agreement v1.3**. Obrigações lidas: distribuição sob o próprio acordo com cópia do texto (3.A.1); distribuição não-fonte exige disponibilizar o fonte (3.A.2); aviso de copyright NASA proeminente (3.B); modificações descritas em arquivo de changelog identificando o autor (3.C); vedação de sugerir endosso da NASA (3.E); "Larger Work" combinando com software sob outra licença é permitido, mantendo a parte NOSA sob a NOSA (3.I); incluir o software em Larger Work não é, por si, Modification (1.F); aviso de controle de exportação dos EUA (3.J). Interpretação jurídica de compatibilidade com Apache-2.0/BSD **não** consta do texto. | `daa@0647596:LICENSES/DAIDALUS2-NOSA.pdf` (p. 1-5, cláusulas 1.E, 1.F, 3.A-3.J) | ALTA (texto); DESCONHECIDO (interpretação jurídica) |
| A.13 | `TrajectorySetpoint` não tem campo de identidade do emissor (só `timestamp`, `position`, `velocity`, `acceleration`, `jerk`, `yaw`, `yawspeed`); `/fmu/in/trajectory_setpoint` é assinado sem autenticação de origem. Qualquer nó ROS 2 no mesmo domínio pode publicar nele. | `msgs@86d8239:msg/TrajectorySetpoint.msg`; `PX4@d6f12ad:dds/dds_topics.yaml:158-159` | ALTA (formato); MÉDIA (efeito com modo externo ativo não exercitado) |

---

## Perguntas DESCONHECIDO / MÉDIA que bloqueiam o P1

Nenhuma das 6 perguntas ficou DESCONHECIDO. Os itens abaixo são MÉDIA ou
lacunas que o P1 deve tratar como **hipóteses** ou que exigem novo P0/SITL:

1. **Tempo real de detecção de executor morto** (2.3, 2.4): cadeia lida mas não
   exercitada. Precisa de teste SITL (M3) matando o processo em voo.
2. **Árbitro morto durante modo interno agendado** (2.6): comportamento
   inferido por ausência de código. Precisa de teste SITL.
3. **Árbitro não pode se re-registrar armado** (2.7, ALTA): o P1 precisa decidir
   entre aceitar essa limitação ou exigir `COM_MODE_ARM_CHK=1` (e avaliar risco).
4. **Semântica de "perda de well-clear" no DAIDALUS** (5.5): escolher a função
   e o alerter na SPEC; parâmetros DO-365B para drones pequenos são hipótese (5.8).
5. **Termos da NOSA** (5.10): RESOLVIDO no texto (A.12); interpretação jurídica segue [REVISAR].
6. **Fluxo FRET → Ogma** (4.7): não verificado; necessário para P3/M2.
7. **Divergência de distro** (R0.2 vs R0.4): RESOLVIDO em 2026-09-11 — usuário confirmou Humble; template Ogma
   (Jazzy) será substituído por template próprio em M2.
