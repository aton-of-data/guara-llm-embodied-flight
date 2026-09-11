# third_party — versões pinadas

Fonte única de API do projeto (ver CLAUDE.md). Os repositórios são clones rasos
(`--depth 1`, sem submódulos) recriados por `scripts/fetch_third_party.sh`.
O conteúdo dos clones não é versionado; apenas este arquivo e o script.

Clonado em 2026-09-11.

| Repositório | Remoto | Ref | Commit | Data do commit | Licença |
|---|---|---|---|---|---|
| PX4-Autopilot | https://github.com/PX4/PX4-Autopilot.git | tag `v1.17.0` | `d6f12ad1c4f70ad3230afd7d86e971421e02fef4` | 2026-04-24 | BSD-3-Clause |
| px4_msgs | https://github.com/PX4/px4_msgs.git | branch `release/1.17` | `86d8239e962f6939e05c3737784f60c02fa884db` | 2026-03-22 | BSD-3-Clause |
| px4-ros2-interface-lib | https://github.com/Auterion/px4-ros2-interface-lib.git | branch `release/1.17` | `4a3370f084ac6f1ef001a4afa2b007845ffd0837` | 2026-06-09 | BSD-3-Clause |
| ogma | https://github.com/nasa/ogma.git | tag `v1.15.0` | `69485b3442d76c48faaee30b37f9cbee212ceca6` | 2026-07-22 | Apache-2.0 |
| daidalus | https://github.com/nasa/daidalus.git | tag `DAIDALUSv2.0.3a` | `0647596edb218f8e8c7731ff800396297bbace99` | 2023-09-08 | NASA Open Source Agreement (NOSA) |
| fret | https://github.com/NASA-SW-VnV/fret.git | tag `v3.1.0` | `58db455be35182a015e607232d9f4e3c86731932` | 2026-03-13 | NOSA (ver `LICENSE.pdf`) |
| copilot | https://github.com/Copilot-Language/copilot.git | tag `v4.8.1` | `365fb21429aa0b880f81d72dcaa9f207f5ea2d0a` | 2026-09-08 | BSD-3-Clause |

## Compatibilidade PX4 ↔ px4_msgs ↔ px4-ros2-interface-lib

Verificado byte a byte: todos os `.msg` de `px4_msgs@86d8239` são idênticos aos
de `PX4-Autopilot@d6f12ad` (`msg/` e `msg/versioned/`), 0 diferenças.

```bash
cd third_party
for f in px4_msgs/msg/*.msg; do b=$(basename $f); \
  src=$(ls PX4-Autopilot/msg/$b PX4-Autopilot/msg/versioned/$b 2>/dev/null | head -1); \
  [ -z "$src" ] && echo "missing $b" || cmp -s $f $src || echo "diff $b"; done
```

`px4-ros2-interface-lib` `release/1.17` é o branch de release correspondente ao
PX4 1.17. Seu `dependencies.repos` aponta para `px4_msgs` `main`; o Guará sobrepõe
isso com o commit pinado acima.

## Escolhas de versão (propostas, pendentes de confirmação no CLAUDE.md)

- PX4: `v1.17.0` — última tag estável (existem `v1.18.0-rc1` e betas, não estáveis).
- ROS 2: Humble — única distro "suportada e recomendada" pela documentação do PX4 v1.17.0
  (ver GROUNDING.md, linha R0). O template ROS do Ogma usa Jazzy (Space ROS); ver risco em GROUNDING.md.
- Ogma: `v1.15.0` — última tag.
