# Encerramento do MVP 2.0 por Sprints e PRs

Atualizado em 2 de novembro de 2026. Este é o planejamento operacional vigente. A [versão anterior](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/9453b82314a4ca5ffaf1850d26e5eac5dbc3d98f/docs/research/mvp2-closeout-plan.md) conserva a evolução das decisões; nenhum recibo, contrato científico ou parâmetro experimental foi substituído por esta atualização.

## Situação de partida

A campanha da PR89 terminou: 60 jobs COMPLETED/0:0 e 60 resultados reconciliados, sem ausências. O [retorno completo](../evidence/pr89/final-20261101/manifest.json) e a [reconciliação](pr89-complete-reconciliation-20261101.md) registram 47 atingimentos do alvo terminal reportado e 13 censuras, todas em M7. A consulta conjunta foi em 2/11 às 02:24:05 UTC, equivalente a 1/11 às 23:24:05 em Fortaleza. A recepção/reconciliação está fechada, independentemente de o resultado ser favorável. Ela não foi adiada até a qualificação científica.

A PR93 integra toda a campanha no artigo e nos apêndices separados. Os PDFs de revisão da fonte 9453b823 foram entregues em 2/11: artigo com 24 páginas, referências a partir da 20ª; apêndices com 44 páginas. Os 101 testes do manuscrito e os gates de fontes/renderização/texto passaram. A inspeção visual cobriu todas as 68 páginas. Não é necessário renderizar novamente para mudanças apenas de governança ou testes.

A PR94 contém o protocolo e o adaptador isolado de preparação. A instalação zero-call está conferida. Nenhum retorno de submissão das raízes foi recebido; não se presume que exista novo job.

## Sequência de entregas e decisões

| Etapa | Entrega concreta | Condição para avançar |
| --- | --- | --- |
| PR89 — encerramento da campanha existente | Preservar fonte 9ab7823c; manter o retorno 60 e as disposições por métrica | Recepção fechada; revisão de encerramento e aprovação específica de merge |
| PR93 — síntese do estudo atual | Finalizar a auditoria integrada, corrigir divergências documentais e apresentar artigo/apêndices consistentes | CI da integração aprovado, limites científicos visíveis e revisão humana do texto |
| PR94 — raízes | Um jobCPU de 2 h, um core físico,64 GiB e até seis chamadas de raiz de 600 s | CLI do autor; coletar somente após estado terminal e revisar o retorno |
| PR94 — grafos/predições/Starts | Um job de 1 h, quatro cores físicos,64 GiB e uma V100 de 32 GB; até seis forwards congelados | Aceitação por hash das seis raízes, seguida de CLI separada; nenhuma avaliação MILP nesta etapa |
| Próxima entrega experimental | Dispatcher isolado das 54 novas células, com manifesto e recursos aprovados e 90 reaproveitamentos dispostos por métrica | Artefatos reais conferidos, testes/CI do dispatcher e intervenção específica na CLI |
| Resultados da extensão | Reconciliar resultados existentes e novos; analisar pares dentro de instância/seed/configuração | Sem completar ausências com zero, sem retries automáticos e sem misturar horizontes diferentes |
| Revisão final e publicação | Atualizar o manuscrito somente com evidência qualificada; auditoria editorial e sincronização controlada | Aprovações específicas de merge, publicação e submissão |

A integração prevista continua PR89→develop, PR93→develop e depois uma release develop→main. Os commits da PR89 não são ancestrais da PR93; após a integração autorizada, o CI deve validar a combinação efetiva antes do merge seguinte. Não simular essa aprovação mudando a fonte instalada ou a história Git.

## Regras científicas de encerramento

Cada uma das 60 células tem uma disposição em [disposition.csv](../evidence/pr89/final-20261101/disposition.csv). Separar aceitação sob tolerâncias, primal exato auditado, bound/gap reportado, alvo observado, censura e custo. Os flags brutos permanecem falsos; a documentação não os promove silenciosamente.

Os dois laudos de M12 cobrem dez pontos. G/4, G/8, G/16 satisfazem os testes primais exatos no escopo declarado; sete controles contêm uma binária fracionária e um padrão arredondado inviável. Cinco pontos de M12 continuam fora desse exame independente. Nenhuma prova dual exata, ótimo global comum ou speedup certificado foi estabelecido. M4 mantém sua restrição própria, e M0 conserva a pequena discrepância cruzada de bounds. Não extrapolar o resultado de um vetor para outro por terem objetivos iguais.

M7 permanece entre as dez medium. Treze interrupções pelo limite e dois atingimentos do alvo não demonstram inviabilidade. Excluir a instância depois de observar a dificuldade introduziria seleção por resultado. A alternativa discutida de nove medium não foi adotada: mudaria 144→135 células e 90→81 candidatas históricas, sem reduzir as 54 novas avaliações.

O orçamento de 12 h da PR89 não é intercambiável com o de 1 h do bloco histórico da extensão. Um timeout não é tempo observado de sucesso. Conservar cruzamentos efetivamente registrados e a censura específica de cada alvo; não interpolar trajetórias ou substituir tempos ausentes por Runtime.

## Protocolo e recursos da PR94

A coorte aprovada continua com seis easy e dez medium, solver seeds 42/43/44 e 144 células no manifesto de comparação de um core físico: 90 candidatas históricas e 54 novas. Os dez pais históricos e os seis novos não ampliam nem recompõem o split de aprendizagem 54/34/10/10. O checkpoint CPU original, sua normalização e seu threshold permanecem congelados. A identidade documental das 90 células não equivale à admissão de todas as métricas; 18 células M4/M12 continuam restritas.

A fonte instalada é c623fe858f62d8fa2a70eebf6f3aeee5692e8f90 e o plano b41953a81f48a91d73c8112bb6794ccce78e72c41ce6ddef7a28ff7e4c098a77. Não atualizar/reinstalar essa cópia para acompanhar commits documentais. O adaptador não contém dispatcher das 54 avaliações.

A proposta condicional completa permanece 20 jobs: uma preparação de raízes, uma de guidance e 18 grupos de avaliação. Tetos: 6 chamadas de raiz+54 avaliações,55 h de solver,75 h sequenciais reservadas,78 core-h físicos, uma V100 GPU-h,64 GiB de RAM por job e 64 GiB de trabalho, com 80 GiB livres na admissão. Fila, revisão humana, energia e preço não estão incluídos. Não somar cenários alternativos como consumo adicional nem usar horas de alocação como utilização medida.

Não reexecutar automaticamente uma célula histórica cuja reutilização falhar. Registrar a célula e o impacto no manifesto/orçamento para decisão específica. Preservar a fonte da PR89, seus checkpoints, MINIMIZE, seed 42, parâmetros, recursos e ordem. Novos treinamentos, métodos de raiz, tolerâncias, arquiteturas e hiperparâmetros permanecem trabalhos futuros. A extensão aprovada varia as seeds do solver, não a seed de treinamento.

## Dificuldade e análise estatística

Caracterizar primeiro tamanho, composição dos domínios, sparsity e escalas dos coeficientes, preservando os identificadores. As seis novas instâncias têm inventários de leitura conferidos; isso não prova dificuldade nem viabilidade. Não acrescentar piloto, novo preditor ou clustering compulsório para classificá-las.

Depois dos resultados, descrever dificuldade computacional empírica pelo progresso e pelos alvos de B sob o protocolo fixado, distinguindo alvos atingidos, censurados e ausentes. Uma classificação baseada no resultado de B é exploratória e relacionada ao próprio quociente G/B; não constitui uma característica independente para provar interação.

Parear B/R/G dentro de pai/seed/configuração. As seeds são repetições dentro da instância, não novos pais: 30 combinações medium/seed continuam sendo dez instâncias. Priorizar qualidade primal/dual, gaps, cobertura, censura e variação por pai. Médias geométricas de razões positivas elegíveis podem ser secundárias, com massa censurada e exclusões explícitas; não usar testes automáticos por célula ou inferir superioridade populacional.

## Sprints e marcos

| Sprint | Próxima entrega | Estado atual |
| --- | --- | --- |
| S1 — governança | Manter este plano, decisões e recibos rastreáveis | Coorte/M7 e responsabilidade preservadas; aprovações de merge/publicação separadas |
| S2 — métodos e prontidão | Revisão de software/proveniência e preparação isolada root→graph→Start | Instalação conferida; raízes/guidance aguardam CLI e retornos |
| S3 — execução e qualificação | Disposição 60 da PR89; depois extensão separadamente liberada | Recepção 89 fechada; nenhuma nova avaliação da extensão recebida |
| S4 — síntese científica | Concluir R2-D8 e análise por métrica; incorporar extensão quando qualificada | Síntese do estudo atual atualizada, sem ótima exatidão ou causalidade indevidas |
| S5 — artigo e apêndices | Revisão humana dos dois PDFs e reconciliação de cada mudança | Versão completa entregue; sem circulação em nome dos autores |
| S6 — auditoria e release | Rever integração real, pacote editorial e aprovações finais | Gate final continua obrigatório, inclusive após nova evidência |

As Sprints podem se sobrepor; nenhuma exige repetir preparação já concluída. Metas preservadas: manifestação preliminar dos coautores até 15/11 por circulação autorizada; extensão qualificada pretendida até 30/11; manuscrito completo aos coautores até 15/12/2026; revisão científica/editorial em dezembro; aprovação final pretendida em 7/1/2027; submissão pretendida em 10/1, com prazo máximo 14/1/2027. São metas, não garantias de fila ou conclusão.

Se a extensão ou a auditoria ameaçar 15/12, apresentar o impacto e uma alternativa limitada ao estudo atual, preservando resultados adversos e censurados. O próximo passo operacional é receber o job_id e o código de saída da CLI de raízes já entregue ao autor; se ainda não executada, ela deve ser executada uma única vez. Não há mais coleta pendente da PR89.
