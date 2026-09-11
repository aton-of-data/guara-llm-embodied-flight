# ADR 0004 — Estratégia de previsão de geofence

- Estado: Proposto (P1, 2026-09-11)
- Relacionados: SPEC §3.1 (`T_gf`), §3.3 (O-1); AC-8, AC-9, AC-22

## Contexto

- Nenhum tópico de geofence é exposto pelo bridge padrão [G 3.4].
- O PX4 tem geofence interno com `GF_ACTION` (padrão Hold) e `GF_PREDICT`
  marcado experimental com aviso de "flyaways" [G A.11].
- `vehicle_local_position_v1` fornece posição/velocidade/aceleração NED,
  flags de validade, contadores de reset e `eph/evh` [G A.8], a até 50 Hz [G 3.1].
- Requisitos de engenharia: cálculo sem alocação e com tempo limitado (CLAUDE.md).

## Opções

A. Usar `GF_PREDICT` do PX4 como Safety Monitor.
B. Expor `geofence_result` via `dds_topics.yaml` customizado e reagir à violação.
C. Preditor próprio no companion: tempo até cruzar a fronteira, com modelo de frenagem.
D. Conjunto alcançável (reachability) completo.

## Decisão

**C**, com o geofence interno do PX4 mantido ativo como camada independente
(`GF_ACTION` ≠ 0, sem `GF_PREDICT`).

Definição (v1):

1. Geofence de inclusão = polígono simples (convexo ou côncavo) em NED local,
   até `N_max_vert` = 64 vértices [HIPÓTESE], mais teto e piso de altitude.
   Armazenado em array de tamanho fixo; carregado na inicialização.
   Conversão lat/lon → NED usa `ref_lat/ref_lon`; um incremento em
   `xy_reset_counter` ou mudança de referência invalida a entrada (`V(k)=1`) até reprojeção.
2. Distância de parada (horizontal): `d_stop(v) = |v|²/(2·a_brake) + e_pos`,
   com `a_brake` [HIPÓTESE, medida em M4] e `e_pos = k_σ·eph` [HIPÓTESE `k_σ`=2].
   A latência **não** entra aqui; ela é coberta pelo limiar (SPEC O-1: `τ_gf ≥ δ_lat`).
3. `D` = distância ao longo de `v̂` até o primeiro cruzamento de aresta a partir
   de `p` (interseção raio-segmento em todas as arestas, O(N), sem alocação).
   `T_gf = max(0, (D − d_stop)/|v|)`: tempo restante até o último instante em que
   iniciar a frenagem ainda evita a violação. Análogo vertical com `vz`, teto/piso
   e `a_brake,z`; `T_gf` = mínimo dos dois.
   Se já fora da geofence: `T_gf = 0`. Se `|v| < v_min` e dentro: `T_gf = +∞`.
4. Vento: não modelado em v1 além do que já está em `v` estimada; cenários
   com rajada (P4) medem o efeito. `τ_rec,gf` e `a_brake` são medidos em SITL.
5. Horizonte máximo `T_hor` = 30 s [HIPÓTESE]; além disso `+∞`.

## Motivos

- A (`GF_PREDICT`) é explicitamente experimental no código [G A.11] e fica
  dentro do FMU, fora do alcance da Switching Logic do Guará.
- B só informa violação já ocorrida (ou a do preditor experimental), sem margem temporal.
- D é mais forte, mas cara e difícil de limitar em tempo; fica para trabalho futuro.

## Consequências

- (+) `T_gf` contínuo, comparável ao limiar `τ_gf`, testável analiticamente (AC-8).
- (+) Duas camadas independentes (Guará + geofence do PX4).
- (−) Modelo de velocidade constante subestima risco em curva ou sob rajada.
- (−) Polígono duplicado (Guará e PX4) pode divergir; o cenário deve carregar ambos
  do mesmo arquivo e `config.yaml` registra o hash.
