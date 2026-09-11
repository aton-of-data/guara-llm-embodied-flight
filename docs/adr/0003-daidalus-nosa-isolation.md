# ADR 0003 — Isolamento da licença NOSA do DAIDALUS

- Estado: Proposto (P1, 2026-09-11) · Interpretação jurídica: [REVISAR]
- Relacionados: SPEC §2, §3.1 (`T_daa`); AC-10, AC-11

## Contexto

O DAIDALUS v2.0.3a é distribuído sob a NASA Open Source Agreement v1.3 [G 5.10, A.12].
Obrigações lidas no texto:

- redistribuição sob a própria NOSA, com cópia do acordo (3.A.1);
- distribuição de binário exige disponibilizar o fonte (3.A.2);
- aviso de copyright NASA proeminente (3.B);
- modificações identificadas em arquivo de changelog com autor e data (3.C);
- não sugerir endosso da NASA (3.E);
- "Larger Work" com software sob outra licença é permitido, mantendo a parte
  NOSA sob a NOSA (3.I); inclusão num Larger Work não é, por si, Modification (1.F);
- aviso de controle de exportação dos EUA (3.J).

O texto **não** trata de compatibilidade com Apache-2.0 (Ogma) ou BSD-3-Clause
(PX4, interface-lib, Copilot). A contribuição upstream ao Ogma (P7) exige que
nada NOSA entre nela. O DAIDALUS C++ não tem CMake [G 5.9].

## Opções

A. Linkar DAIDALUS dentro de `guara_rta`.
B. Pacote ROS 2 separado, processo separado, comunicação só por mensagem.
C. Repositório separado.

## Decisão

**B**, preparada para virar C sem mudança de interface:

1. Diretório `nosa/guara_daidalus/` com `LICENSE` = NOSA 1.3 (cópia do PDF/texto),
   aviso de copyright NASA e `CHANGES.md` (cláusula 3.C) para qualquer alteração
   em fontes do DAIDALUS.
2. Fontes do DAIDALUS **não** são copiadas para o repositório: o CMake de
   `guara_daidalus` compila a partir de `third_party/daidalus` no commit pinado.
   Se isso mudar, aplica-se o item 1 integralmente.
3. Interface pública = `guara_msgs/DaaStatus` (licença do Guará). Nenhum pacote
   fora de `nosa/` depende de `guara_daidalus` ou inclui cabeçalhos DAIDALUS
   (AC-11, `scripts/check_license_isolation.py`).
4. O restante do Guará compila, testa e roda com `guara_daidalus` ausente;
   nesse caso `DaaStatus` não é publicado e a entrada DAA é marcada ausente.
   Se o cenário exige DAA, `V(k)=1` (SPEC §3.1); se não exige, o canal DAA é desativado na configuração.
5. Imagens de container com DAIDALUS são marcadas como contendo software NOSA
   e trazem o texto do acordo e o link para o fonte (3.A.2).
6. Nenhum material do projeto sugere endosso da NASA (3.E).
7. Licença do código próprio do Guará: **[PARÂMETRO A DEFINIR]** pelo autor
   (Apache-2.0 facilitaria P7).

## Consequências

- (+) Contribuição ao Ogma (P7) e demais pacotes ficam livres de NOSA.
- (+) Crash do DAIDALUS não derruba o árbitro; vira dado velho (FM-6).
- (−) Latência extra `L3` no caminho DAA.
- (−) Mensagens duplicam unidades/convenções; exige teste de equivalência (AC-10).
- Pendência: revisão jurídica humana antes de publicar binários ou containers.
