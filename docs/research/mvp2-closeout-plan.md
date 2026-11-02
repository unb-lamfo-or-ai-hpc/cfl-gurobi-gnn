# Encerramento do MVP 2.0 por Sprints e PRs

Atualizado em 2 de novembro de 2026 após a orientação de acelerar S1–S4. A [versão anterior](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/b52cc5ef0952529feb231491d4a6ee2bd9d47f6b/docs/research/mvp2-closeout-plan.md) preserva o planejamento anterior. Esta revisão amplia prospectivamente a PR94; não modifica a campanha PR89, seus arquivos nem os dados históricos.

## Evidências já disponíveis

A PR89 está encerrada em execução e recepção: 60/60 jobs COMPLETED/0:0, 47 atingimentos do critério terminal reportado e 13 censuras de M7. A consulta conjunta foi em 2/11 às 02:24:05 UTC, ou 1/11 às 23:24:05 em Fortaleza. D0 permanece esse recebimento/reconciliação, independentemente do sinal dos resultados; não é uma nova data de qualificação. [Recibos e disposições](../evidence/pr89/final-20261101/manifest.json) conservam as versões parciais e os flags originais.

O artigo e o Apêndice B incluem os 60 registros e a auditoria delimitada de dez pontos M12. M7 conserva suas 15 observações, 13 censuras terminais, gaps e figuras. Nesta revisão, o artigo aprofunda a discussão de M7, separando melhora primal, progresso dual e fechamento do alvo; o Apêndice B reúne a tabela de cobertura por instância, a figura de tempos M0/gaps M7 e os 60 registros. Nenhum timeout é convertido em sucesso. M4/M12 continuam sem certificado de ótimo comum ou speedup certificado; M0 mantém a ressalva de bound.

A fonte 7acf74d462f98903931442caa668960a898cad24 da PR93 passou no CI Manuscript 41461449499 e na matriz completa Evidence 41461449424, incluindo os dois Windows. A proteção contra conversão de bytes selados resolveu a divergência de hash sem alterar evidências. Novas mudanças exigem seus próprios checks. Os PDFs anteriores, fonte 9453b823, continuam identificados como versões anteriores; não se afirma que contenham a revisão textual atual.

As preparações 3783 e 3784 foram recebidas e revisadas: seis raízes em 340 s e seis forwards em 387 s, sem treino novo. Fonte c623fe858f62 e plano b41953a8 continuam congelados. A instalação isolada da avaliação, fonte 10fd1af20ff4/plano 44b443a1, passou no preflight das 16 cadeias de modelo/raiz/grafo/predições/Starts e reportou zero chamadas científicas e submissões. Os metadados foram reconciliados; vetores privados não foram reproduzidos independentemente.

Depois dessa admissão, o autor submeteu os 48 jobs 3785–3832. No último snapshot, as quatro cabeças falharam no shell com `PR94_EVALUATION_INVALID_STAGE`, antes do worker Python, e 44 sucessores permanecem PENDING por dependências afterok. Não há resultados científicos de avaliação recebidos. A [análise do incidente na PR94](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/41beb21c702dfe6c1dabe78020ea6e0f3dd87fb3/docs/research/pr94-entry-failure-20261102.md) preserva os recibos e a correção candidata da entrada via spool. Nenhum job, claim ou fonte instalada foi alterado; recuperação exige decisão específica do autor.

## Sprints em paralelo e entregas

| Sprint | Trabalho agora | PR e gate de conclusão |
| --- | --- | --- |
| S1 — contratos e integração | Registrar a nova matriz e recursos; preparar a resolução dos quatro conflitos documentais da PR89; preservar a fonte instalada | PR89 pode ser concluída após a revisão da integração e aprovação específica do merge |
| S2 — software, métodos e preparação | Preparação e admissão das 16 instâncias recebidas; corrigir/testar a entrada batch copiada; preparar a recuperação apenas após decisão específica | PR94: preservar a tentativa falha, validar a correção e, se autorizada a recuperação, receber nova admissão/aceite de plano antes da submissão substituta |
| S3 — resultados CPU existentes | Concluir a leitura das 60 células, tabelas/figuras, M7 e limites M4/M12; conferir artigo/apêndices contra os recibos | PR93: auditoria da campanha completa, sem exigir um resultado favorável |
| S4 — síntese e primeira publicação revisada | Preservar IDs/falhas da primeira tentativa; integrar somente o desenho prospectivo, sem desempenho novo; concluir curadoria GitHub/Zenodo | PR93 em develop; depois uma PR distinta develop→main, com aprovação de merge/publicação e verificação de Pages |
| S5 — resultados novos | Após a PR94, reconciliar as 144 células, censuras/falhas/ausências, elegibilidade por métrica e custos; atualizar análise pareada por instância/seed | PR de resultados, sem misturar a campanha de 1 h com a de 12 h |
| S6 — fechamento científico/editorial | Após a análise nova, auditoria final A–D, revisão integral de artigo/apêndices, depósito e declarações, versão final e submissão | Aprovações humanas específicas; não condicionar aceitação a obter ganho da GNN |

## PR89: resolução preparada, merge ainda não realizado

A PR89 está divergente de develop: dois commits próprios e quinze commits posteriores em develop. A comparação em três vias identifica quatro sobreposições textuais: docs/article_plan.md, docs/current_status.md, docs/experiment_protocol.md e docs/research_context.md. Os demais acréscimos de código/testes da PR89 não têm sobreposição de blobs com develop nessa comparação. Um status dirty não é falha de experimento.

A resolução deverá conservar a documentação atual de develop e a adição histórica de 20/10 da PR89, explicitamente datada, sem restaurar antigos estados de preparação como atuais. O conjunto de código da PR89 precisa entrar integralmente: executor temporal, contrato, workflow, operador, coletor e testes, além das alterações do solver e recursos. Nenhuma resolução poderá editar a instalação 9ab7823c, seu plano, os Starts ou os recibos. O inventário e as resoluções propostas estão em [pr89-integration-resolution.json](pr89-integration-resolution.json).

Preparar e testar a árvore resolvida antes de solicitar a aprovação específica do merge. Não criar automaticamente um merge commit, rebase ou force-push para contornar o conflito. A combinação efetiva PR89+PR93 precisará manter tanto o bash -n do operador PR89 como o T1 de selos da PR93. A aprovação de uma dessas branches não equivale à aprovação da outra.

## PR94: matriz nova e lançamento limitado

A [matriz v2 na PR94](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/tree/docs/mvp2-solver-seed-protocol/docs/research/solver-seed-extension-v2) define 144 avaliações novas: 6 easy + 10 medium, B/R/G e seeds 42/43/44, uma thread física e TimeLimit=3.600 s. Os 90 registros antigos permanecem como evidência histórica e não substituem células novas. M7 permanece; treino 54/34–10–10 e checkpoint original não mudam. A ordem B/R/G é balanceada por instância sem usar resultados.

São 48 blocos de três solves sequenciais, distribuídos em quatro cadeias. A concorrência proposta é de no máximo quatro jobs de avaliação; os limites devem ser confirmados com a capacidade/licença reais. O teto do conjunto, incluindo preparação, é 50 jobs, 150 chamadas de otimização, 145 solver-h, 195 job-h somadas, 198 core-h físicos e 1 V100 GPU-h. O pico das avaliações é 4 núcleos físicos e 256 GiB. O mínimo idealizado de 48 h para avaliações não inclui fila, preparação, revisão ou falhas. O armazenamento foi dimensionado em 256 GiB de trabalho, admissão com 320 GiB livres, piso observado de 64 GiB e limites por arquivo/célula. O preflight passou nessa política; não é reserva de quota nem garantia de disponibilidade futura.

O compilador e o dispatcher isolado estão implementados. A fonte instalada 10fd1af passou no CI completo 41478889138 e no preflight real das 16 instâncias; a execução da cópia de batch não estava coberta pelos testes anteriores. Os logs confirmaram erro na resolução do estágio via BASH_SOURCE. A correção candidata 41beb21c usa o estágio exportado na submissão, mantendo o corpo do operador; suas novas regressões de spool passaram no T1 Linux. A regressão completa 41489069293 está em andamento, e a correção não foi instalada.

A primeira tentativa compreende 48 IDs: quatro FAILED antes do worker e 44 PENDING, sem resultado de solve recebido. Não há permissão para remover dependências, requeue, apagar claims, repetir preparação ou reenviar. A recuperação proposta, ainda não autorizada, preserva tudo, cancela apenas 44 pendentes novamente confirmados próprios, prepara um estágio separado com CI e admissão de zero chamadas e substitui os 48 blocos para as mesmas 144 células após novo aceite de plano. Isso elevaria o registro histórico a 98 IDs incluindo preparação; pedidos de reserva e uso efetivo deverão ser contabilizados separadamente. Sem ampliação das células científicas, sementes, limite de tempo, arquitetura, checkpoint ou treino.

A concorrência afeta a interpretação do tempo. Registrar sobreposição entre jobs e recursos reais, conservar B/R/G pareados por instância–seed e não apresentar as três seeds como três redes treinadas. Os resultados da PR89 não serão reclassificados segundo o protocolo novo.

## Curadoria antes de concluir a PR93

O [plano GitHub/Zenodo](mvp2-data-release-plan.md) define: código, contratos, inventários, recibos pequenos, CSVs e fontes de figuras no GitHub; snapshot fixo de software, artefatos redistribuíveis de modelos/preparação, evidências volumosas revisadas e produtos editoriais no depósito científico. Credenciais, temporários e ZIPs privados não se tornam públicos. Direito de redistribuição, inventário de membros, hashes, relação de versões e DOI devem ser conferidos; nenhum DOI novo ou upload é presumido.

A primeira publicação revisada conterá PR89 completa e, após o lançamento real, o desenho prospectivo da PR94 sem antecipar resultados. S5/S6 produzirão a versão científica final após a campanha nova. O release de Pages intermediário será identificado pela versão, sem simular conclusão final do MVP2.

## Sequência de merge e datas

1. Concluir a resolução/revisão da PR89 e obter aprovação do merge em develop.
2. Incorporar a base integrada na PR93, preservar bytes e história, executar os checks da combinação e concluir a auditoria científica/editorial.
3. Preservar os recibos da tentativa inicial da PR94 e registrar separadamente uma eventual recuperação autorizada; incluir o desenho e seus limites no artigo/apêndices, sem antecipar resultados ou inserir instruções de fila. Fechar o plano de dados antes do pedido de merge da PR93.
4. Solicitar aprovação específica da PR93→develop. Preparar outra PR develop→main e solicitar sua aprovação de merge/publicação; verificar a versão realmente servida pelo Pages.
5. Após os resultados da PR94, concluir S5/S6 por PRs coerentes de resultados e release final. Não reservar números nem gerar uma PR por correção trivial.

Metas: manuscrito completo aos coautores até 15/12/2026; revisão em dezembro; aprovação final pretendida em 7/1/2027; submissão pretendida em 10/1; limite de 14/1. Nenhuma comunicação é enviada em nome dos autores. Se filas, armazenamento, licença, preparação ou qualificação ameaçarem essas metas, registrar o impacto e submeter uma alternativa científica explícita, sem mudar silenciosamente o desenho ou o prazo. Não há novas sementes de treino, arquiteturas, métodos de raiz ou tolerâncias no MVP2.
