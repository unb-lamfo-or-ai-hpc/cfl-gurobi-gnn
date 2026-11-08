# Encerramento do MVP 2.0 por Sprints e PRs

Atualizado em 2 de novembro de 2026 após a orientação de acelerar S1–S4. A [versão anterior](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/b52cc5ef0952529feb231491d4a6ee2bd9d47f6b/docs/research/mvp2-closeout-plan.md) preserva o planejamento anterior. Esta revisão amplia prospectivamente a PR94; não modifica a campanha PR89, seus arquivos nem os dados históricos.

## Fechamento da avaliação e sequência atual — 5 de novembro de 2026

O [retorno reconciliado da PR94](../evidence/pr94/final-20261105/README.md) confirma 48 blocos terminais, 144/144 células e zero ausências ou registros inválidos. Os dois ZIPs e os manifestos conferem. A avaliação de 1 h fica separada da PR89 de 12 h. O registro abaixo da integração e publicação inicial é histórico: PR89 e PR93 entraram em develop, e PR95 e PR96 publicaram a versão intermediária em main.

1. **S5 — Revisão científica e editorial.** Revisar a PR editorial em develop com os contrastes B/R/G, os dados de 144 células, a sensibilidade sem M4/M12 e a atualização do artigo e dos apêndices. Conferir os vínculos numéricos, a CI e a paginação dos dois PDFs.
2. **S6 — Auditoria A–D e curadoria.** Fechar A (integridade dos dados e identidades), B (escopo das inferências e censuras), C (consistência do artigo e dos apêndices) e D (pacote de reprodutibilidade). Revisar em conjunto a PR94 de código/protocolo e a PR editorial. Merges exigem decisões específicas, com novo teste da árvore combinada se a base mudar.
3. **Release e depósito.** Preparar o release versionado e a promoção a main. Conferir a versão realmente servida no Pages e os downloads após aprovação. Para Zenodo, validar inventário, licenças e redistribuição, hashes, vínculo de versão e DOI antes de solicitar a decisão de depósito.
4. **Revisão e submissão.** Preparar o pacote completo para os coautores até 15/12/2026. As metas registradas permanecem aprovação final em 7/1/2027, submissão pretendida em 10/1 e limite em 14/1. A submissão fica com os autores.

## Evidências já disponíveis (histórico de 2 de novembro)

A PR89 está encerrada em execução e recepção: 60/60 jobs COMPLETED/0:0, 47 atingimentos do critério terminal reportado e 13 censuras de M7. A consulta conjunta foi em 2/11 às 02:24:05 UTC, ou 1/11 às 23:24:05 em Fortaleza. D0 permanece esse recebimento/reconciliação, independentemente do sinal dos resultados; não é uma nova data de qualificação. [Recibos e disposições](../evidence/pr89/final-20261101/manifest.json) conservam as versões parciais e os flags originais.

O artigo e o Apêndice B incluem os 60 registros e a auditoria delimitada de dez pontos M12. M7 conserva suas 15 observações, 13 censuras terminais, gaps e figuras. Nesta revisão, o artigo aprofunda a discussão de M7, separando melhora primal, progresso dual e fechamento do alvo; o Apêndice B reúne a tabela de cobertura por instância, a figura de tempos M0/gaps M7 e os 60 registros. Nenhum timeout é convertido em sucesso. M4/M12 continuam sem certificado de ótimo comum ou speedup certificado; M0 mantém a ressalva de bound.

A fonte 7acf74d462f98903931442caa668960a898cad24 da PR93 passou no CI Manuscript 41461449499 e na matriz completa Evidence 41461449424, incluindo os dois Windows. A proteção contra conversão de bytes selados resolveu a divergência de hash sem alterar evidências. Novas mudanças exigem seus próprios checks. Os PDFs anteriores, fonte 9453b823, continuam identificados como versões anteriores; não se afirma que contenham a revisão textual atual.

As preparações 3783 e 3784 foram recebidas e revisadas: seis raízes em 340 s e seis forwards em 387 s, sem treino novo. Fonte c623fe858f62 e plano b41953a8 continuam congelados. A instalação isolada da avaliação, fonte 10fd1af20ff4/plano 44b443a1, passou no preflight das 16 cadeias de modelo/raiz/grafo/predições/Starts e reportou zero chamadas científicas e submissões. Os metadados foram reconciliados; vetores privados não foram reproduzidos independentemente.

A tentativa inicial, jobs 3785–3832, foi encerrada e preservada: quatro FAILED antes do worker Python e 44 CANCELLED, sem resultado científico. O coletor e a transferência foram conferidos, incluindo SHA256 e membros do arquivo de encerramento. A falha de resolução do estágio no script copiado pelo Slurm foi corrigida e coberta por regressões reais de spool no Linux.

A recuperação específica foi autorizada pelo autor. A fonte corrigida 81c829b66f6d passou nos cinco jobs da CI 41496227917 antes da instalação isolada. O roteiro comparou integralmente o plano novo ao plano científico já aceito e registrou o aceite antes de sbatch. O retorno do autor informa plan SHA256 92ac169c5ccb69962628dc0b91aab6afff183538da87f14e3ebf080b8cfe53fb, CLI exit0 e 48 novos IDs 3833–3880, para as mesmas 144 avaliações. O snapshot sem horário de consulta registra 3835/3836 COMPLETED, 3839/3840 RUNNING e 44 PENDING. São seis avaliações esperadas nos dois blocos concluídos, ainda sem resultados coletados ou qualificados. O ZIP de instalação 70360903 foi informado, mas não recebido localmente. O [recibo delimitado](pr94-recovery-launch-20261102.json) distingue essas verificações. Não repetir instalação, preparação, submissão ou cancelamento.

## Sprints em paralelo e entregas

| Sprint | Trabalho agora | PR e gate de conclusão |
| --- | --- | --- |
| S1 — contratos e integração | Registrar a nova matriz e recursos; preparar a resolução dos quatro conflitos documentais da PR89; preservar a fonte instalada | PR89: integração revisada, CI e merge em develop já autorizado |
| S2 — software, métodos e preparação | Preparação e admissão recebidas; entrada batch corrigida/testada; recuperação autorizada e 48 blocos submetidos | PR94: acompanhar retornos pela CLI do autor, preservar ambas as tentativas e reconciliar somente resultados recebidos |
| S3 — resultados CPU existentes | Concluir a leitura das 60 células, tabelas/figuras, M7 e limites M4/M12; conferir artigo/apêndices contra os recibos | PR93: auditoria da campanha completa, sem exigir um resultado favorável |
| S4 — síntese e primeira publicação revisada | Preservar IDs/falhas da primeira tentativa; integrar somente o desenho prospectivo, sem desempenho novo; concluir curadoria GitHub/Zenodo | PR93 em develop; depois uma PR distinta develop→main, com aprovação de merge/publicação e verificação de Pages |
| S5 — resultados novos | Após a PR94, reconciliar as 144 células, censuras/falhas/ausências, elegibilidade por métrica e custos; atualizar análise pareada por instância/seed | PR de resultados, sem misturar a campanha de 1 h com a de 12 h |
| S6 — fechamento científico/editorial | Após a análise nova, auditoria final A–D, revisão integral de artigo/apêndices, depósito e declarações, versão final e submissão | Aprovações humanas específicas; não condicionar aceitação a obter ganho da GNN |

## Integração de PR89 e PR93

O autor autorizou especificamente o merge de PR89 e PR93 em develop após checks. Os quatro conflitos documentais foram resolvidos preservando o conteúdo atual e as adições históricas datadas. A árvore candidata contém os 17 caminhos da PR89; os 13 blobs sem sobreposição são idênticos aos originais. O commit de integração 94d909de incorpora develop como segundo pai sem rebase ou force-push, mantendo 9ab7823c na história e intacto no HPC. O inventário está em [pr89-integration-resolution.json](pr89-integration-resolution.json).

A CI da integração deve concluir antes do merge de PR89. Em seguida, PR93 recebe a base integrada, conserva fontes/recibos e passa nos checks de evidências e na renderização/verificação dos dois PDFs. A autorização de develop não equivale à aprovação da promoção posterior a main. A PR95 já existente será reutilizada para essa promoção, sem PR duplicada.

## PR94: matriz nova e lançamento limitado

A [matriz v2 na PR94](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/tree/docs/mvp2-solver-seed-protocol/docs/research/solver-seed-extension-v2) define 144 avaliações novas: 6 easy + 10 medium, B/R/G e seeds 42/43/44, uma thread física e TimeLimit=3.600 s. Os 90 registros antigos permanecem como evidência histórica e não substituem células novas. M7 permanece; treino 54/34–10–10 e checkpoint original não mudam. A ordem B/R/G é balanceada por instância sem usar resultados.

São 48 blocos de três solves sequenciais, distribuídos em quatro cadeias. A concorrência proposta é de no máximo quatro jobs de avaliação; os limites devem ser confirmados com a capacidade/licença reais. O teto do conjunto, incluindo preparação, é 50 jobs, 150 chamadas de otimização, 145 solver-h, 195 job-h somadas, 198 core-h físicos e 1 V100 GPU-h. O pico das avaliações é 4 núcleos físicos e 256 GiB. O mínimo idealizado de 48 h para avaliações não inclui fila, preparação, revisão ou falhas. O armazenamento foi dimensionado em 256 GiB de trabalho, admissão com 320 GiB livres, piso observado de 64 GiB e limites por arquivo/célula. O preflight passou nessa política; não é reserva de quota nem garantia de disponibilidade futura.

O compilador e o dispatcher isolado estão implementados. A instalação original 10fd1af e o plano44b443a1 são preservados com seus claims. A recuperação81c829b6 usa outro estágio e claim específico, com equivalência integral dos campos científicos, entradas, ambiente, ordem e recursos. Todos os outros arquivos científicos permanecem iguais; os Starts são reutilizados. O novo plano92ac169c foi revisto automaticamente antes de qualquer sbatch, conforme o roteiro explicitamente autorizado.

A tentativa original conta48 IDs, a preparação2 e a substituta48:98 IDs históricos, não288 solves científicos. A matriz de avaliação continua limitada a144 novas chamadas, além das seis raízes já concluídas; os pedidos de reserva da tentativa abortada são contabilizados à parte do uso efetivo e do orçamento científico. Quatro falhas de entrada e44 cancelamentos não são tempos zero de otimização nem censura por TimeLimit. Os novos48 blocos foram submetidos; não há retry automático ou autorização para uma terceira tentativa.

A concorrência afeta a interpretação do tempo. Registrar sobreposição entre jobs e recursos reais, conservar B/R/G pareados por instância–seed e não apresentar as três seeds como três redes treinadas. Os resultados da PR89 não serão reclassificados segundo o protocolo novo.

## Curadoria antes de concluir a PR93

O [plano GitHub/Zenodo](mvp2-data-release-plan.md) define: código, contratos, inventários, recibos pequenos, CSVs e fontes de figuras no GitHub; snapshot fixo de software, artefatos redistribuíveis de modelos/preparação, evidências volumosas revisadas e produtos editoriais no depósito científico. Credenciais, temporários e ZIPs privados não se tornam públicos. Direito de redistribuição, inventário de membros, hashes, relação de versões e DOI devem ser conferidos; nenhum DOI novo ou upload é presumido.

A primeira publicação revisada conterá PR89 completa e, após o lançamento real, o desenho prospectivo da PR94 sem antecipar resultados. S5/S6 produzirão a versão científica final após a campanha nova. O release de Pages intermediário será identificado pela versão, sem simular conclusão final do MVP2.

## Sequência de merge e datas

1. Concluir os checks da integração e realizar o merge da PR89 em develop, já especificamente autorizado.
2. Incorporar a base integrada na PR93, preservar bytes e história, executar os checks da combinação e concluir a auditoria científica/editorial.
3. Preservar os recibos da tentativa inicial e da recuperação efetivamente submetida da PR94; incluir o desenho e seus limites no artigo/apêndices, sem antecipar resultados ou inserir instruções de fila. Fechar o plano de dados antes do pedido de merge da PR93.
4. Concluir os checks e realizar o merge da PR93→develop, já especificamente autorizado. Atualizar a PR95 develop→main e solicitar sua aprovação de merge/publicação; verificar depois a versão realmente servida pelo Pages.
5. Após os resultados da PR94, concluir S5/S6 por PRs coerentes de resultados e release final. Não reservar números nem gerar uma PR por correção trivial.

Metas: manuscrito completo aos coautores até 15/12/2026; revisão em dezembro; aprovação final pretendida em 7/1/2027; submissão pretendida em 10/1; limite de 14/1. Nenhuma comunicação é enviada em nome dos autores. Se filas, armazenamento, licença, preparação ou qualificação ameaçarem essas metas, registrar o impacto e submeter uma alternativa científica explícita, sem mudar silenciosamente o desenho ou o prazo. Não há novas sementes de treino, arquiteturas, métodos de raiz ou tolerâncias no MVP2.
