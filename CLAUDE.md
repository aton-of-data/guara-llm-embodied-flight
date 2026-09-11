# Projeto Guará — memória do agente

## Missão
Runtime Assurance alinhado à ASTM F3269 para PX4 via ROS 2:
- monitores Copilot gerados pelo Ogma a partir de requisitos FRETish
- DAA com DAIDALUS v2 (pacote separado, licença NOSA)
- previsão de violação de geofence
- árbitro RTA implementado como ModeExecutor (px4-ros2-interface-lib)
- função de recuperação = modos internos do PX4 (Hold / RTL / Land)

## Verdades fixas
- Fonte de API: somente código clonado em third_party/ com commit pinado
  em third_party/VERSIONS.md. Nunca inferir API de memória.
- PX4, px4_msgs e px4-ros2-interface-lib em commits compatíveis entre si.
- Distro ROS 2: Humble. Versão PX4: v1.17.0. Ogma: v1.15.0.

## Engenharia
- C++17, colcon/ament, gtest + launch_testing.
- Toda função de segurança tem teste que falha antes da implementação.
- Caminho de decisão do árbitro sem alocação dinâmica e com tempo limitado.
- SITL sempre headless e reprodutível (seed + commit registrados).

## Git
- Commits granulares: uma mudança lógica por commit.
- Autor dos commits: aton-of-data.
- Nunca adicionar trailer Co-authored-by nem menção a assistente/IA.
- Mensagem: tipo(escopo): resumo no imperativo (ex.: feat(rta): add dwell-time hysteresis).

## Tooling JavaScript
- Qualquer ferramenta Node (ex.: dashboard de resultados): usar pnpm, nunca npm ou yarn.

## Proibições
- Não inventar números de desempenho; resultados só de results/ via script.
- Não declarar milestone concluído sem comando executado + trecho da saída.
- Escopo: segurança de voo civil. Nenhuma função de seleção de alvo ou armamento.
