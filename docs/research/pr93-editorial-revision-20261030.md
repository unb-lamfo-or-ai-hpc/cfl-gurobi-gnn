# PR93 — approved scientific/editorial revision, 30 October 2026

## Author decision and implementation scope

The author approved the diagnostic and proposed organization and explicitly authorized implementation in PR93. Merge and CLI intervention remain separate human gates. PR89 stays frozen at 9ab7823c6886d19e9ec865141a1cd35b3c3c16e5; no new scientific execution is performed.

The implemented title is **Evaluating Graph Neural Network-Based Partial Warm Starts for Capacitated Facility Location Problems**. C2/C3 are the two scientific contributions; C1 is the methodology. The manuscript is reorganized around the research question, optimization outcomes and bounded computational economics. The historical six-medium results are retained as distinct supporting evidence, with full tables/figures in Supplementary B. Supplementary A explains methods; C records configurations and provenance. Author instructions, future budgets and Human–AI decisions remain internal.

## Implementation and verification log

- Baseline: PR93 HEAD 3f5789fe34fe1dc9f80f84e3e2c46d3bdea3f30f, develop base. Both baseline workflows completed successfully, including Windows.
- New result displays read the same 150 seed42 rows and existing six-easy paired summaries. No dataset, raw flags, model, checkpoint, solver parameter or executor is changed.
- Numerical provenance expands from 17 to 27 registered claim groups and from four to seven immutable input sources; generated CPU tables/figures additionally preserve input/output hashes.
- The provisional abstract's approved 0.844 was a double rounding of 0.8434975331773139 through 0.8435. Direct three-decimal formatting is 0.843, now source-bound. The original observation and interpretation are unchanged.
- The reader-audience guard now includes highlights and the combined scientific supplement; it rejects internal status and unregistered supplement text.
- T1 source controls, 264 relative-link resolutions and 76 affected manuscript tests passed before rendering. Final-head CI and visual QA are recorded in the PR checkpoint after completion; this entry alone does not claim them.
- The article and separate A/B/C supplement render locally to HTML/PDF with no unresolved references. The main article is 23 pages, with numbered References beginning on page 20, within the internal body budget. Local Quarto is 1.9.38; the workflow remains pinned to 1.10.18. The current local publication-output gate passes and the editable LaTeX package includes both documents and all seven vector figures. Final CI checks the committed head independently.
- Visual QA reviewed all article and supplement pages; it corrected pipeline-label overflow, clipped zero-gap markers, a split five-row table and the formatting of full checkpoint identifiers. The last identifier line-break check is completed before the PR validation checkpoint. At the author’s subsequent request, a combined local PDF is prepared for the Codex tab; this is not an editorial submission.
- Local plotting dependencies are isolated in the Codex temporary directory, not installed into the HPC or the research environment. A temporary user-mode TeX tree is used for missing publication packages. No session temporary is uploaded to a blob service or external desktop app.
- Article/supplement final conclusions remain open to qualified CPU12h integration and the integral final audit. The current abstract is provisional in this internal record; no operational placeholder is inserted in reader prose.

## Remaining gates

Receive/reconcile and qualify all 60 cells; disposition by metric including missing/failed/censored/restricted records; integrate eligible results and costs; complete full scientific/editorial/appendix audit; resolve availability/rights and author declarations; obtain specific merge/publication/submission approval. No retry, new model/seed/method or experiment is implied.

## Approved diagnostic preserved below

The dated diagnostic below records the baseline reviewed before implementation. Its statements that implementation was awaiting approval describe that earlier stage; the approval and implementation log above supersede that operational status.

### Diagnostic of the pre-revision source
30/10/2026 · Primeira entrega do mandato de 30/10/2026 · documento interno para decisão científica.

Este diagnóstico não integra o artigo nem os suplementos de publicação. Não modifica a PR #93, não constitui aceite científico dos resultados pendentes e não autoriza execução experimental, merge ou publicação.

### 1. Referências conferidas e estado remoto

O PDF anotado tem 50 páginas, 840.694 bytes e SHA256 6f649661e213b0cf7fab98b7bd0eea25b4e515d61bfeca3b9c7b831863c151f1. Seu campo Subject informa “Review copy, 28 October 2026, source 346ddea49b33dc9b01095a0dc9e908ed453e7e17”. A modificação das anotações está datada de 30/10/2026. Há 21 comentários únicos: 13 na página 1 e oito na página 2. Os 21 objetos Popup repetem os comentários e não são 21 observações adicionais.

A referência revisada é anterior ao HEAD atual da PR #93, 3f5789fe34fe1dc9f80f84e3e2c46d3bdea3f30f. A PR permanece aberta, draft, com base develop. Portanto, este diagnóstico distingue comentários já atendidos no código atual de problemas ainda presentes. Foi extraído o texto de todas as 50 páginas; o confronto com as fontes atuais foi complementado pela inspeção visual das páginas anotadas e das páginas relevantes de métodos, figuras, tabelas, bibliografia e suplementos. Isso não é uma inspeção visual integral de um PDF do HEAD atual.

Os workflows Manuscript (40874722918) e Public evidence integrity (40874723085) concluíram com sucesso no HEAD atual. Os quatro ambientes Linux/Windows, Python 3.10/3.12, e matched-step estão aprovados. A indicação antiga de Windows em execução no corpo da PR ficou desatualizada; sua atualização é documental, a ser registrada na implementação aprovada. Não foi disparado novo CI, render, treinamento ou teste computacional nesta entrega.

A PR #89 continua aberta/draft com HEAD 9ab7823c6886d19e9ec865141a1cd35b3c3c16e5. A campanha é mantida em execução conforme informação do pesquisador. Não houve consulta ao HPC nem novo snapshot do scheduler em 30/10. O snapshot humano anterior cobre apenas 3713–3734, não estabelece estado atual dos 60 jobs nem qualificação das suas soluções. Nenhuma fonte, parâmetro, recurso, checkpoint ou sequência foi alterada.

### 2. Parecer científico

A revisão deve deslocar o centro da narrativa da construção do pipeline para duas avaliações: em que condições os inícios parciais ajudam a otimização e quanto da vantagem permanece dentro dos custos observados. Concordo com o título aprovado e com a retirada de C1 como contribuição científica independente. A representação bipartida, o treinamento e a integração via Start constituem a metodologia que permite avaliar C2 e C3.

O texto atual já contém explicações metodológicas importantes. Sua principal fragilidade é a distribuição da evidência: o estudo histórico de seis médias recebe tabelas e interpretação extensas, enquanto a comparação principal de dez instâncias apresenta sobretudo contagens e restrições. Isso deixa subutilizadas evidências existentes sobre efeitos condicionados aos recursos e sobre custos.

A revisão deve ser mais interpretativa, mas não mais otimista do que os dados. Não há base para afirmar causalidade do seletor class-aware, superioridade arquitetural, robustez multissemente, generalização independente ou economia operacional completa. Também não se pode garantir adequação científica à Computers & Operations Research apenas com nova redação: a suficiência das contribuições empíricas permanece uma decisão científica após a qualificação da #89 e a auditoria final.

A página oficial da revista pede comunicação compreensível a leitores de áreas distintas, resumo centrado no problema, contribuição e achados, resultados reproduzíveis e experimentação com valor científico próprio. Adota estilo Harvard. Isso apoia a reorganização proposta, sem impor APA ou transferir exigências de outros periódicos.
Fonte: https://shop.elsevier.com/journals/computers-and-operations-research/0305-0548.
O Guide for Authors específico retornou HTTP 403 nesta consulta. Não foi possível reconfirmar integralmente suas regras atuais; limites de 250 palavras, cinco highlights/85 caracteres e orçamento interno de páginas são tratados conforme o checklist vigente do repositório, sujeitos à conferência final da revista.

### 3. Disposição dos comentários das páginas 1–2

| ID | Página e tema | Disposição proposta e confronto com o HEAD |
| --- | --- | --- |
| A01 | 1: desenvolver Graph Neural Network (GNN) | Atender no resumo e na primeira ocorrência no corpo. |
| A02 | 1: usar Mixed-Integer Linear Programming (MILP) | Atender; a formulação abreviada atual não introduz o termo com a precisão desejada no abstract. |
| A03 | 1: retirar custos/censura da frase inicial | Reescrever a abertura pelo CFL e a motivação. Não substituir por “total computational cost” sem cobertura completa: os custos disponíveis incluem cenários delimitados. |
| A04 | 1: desenvolver Capacitated Facility Location (CFL) | Atender no abstract e reiniciar a definição na introdução. |
| A05 | 1: omitir a marca Gurobi no abstract | Atender com “solver”; identificar produto e versão nos métodos. Dizer que o solver tenta completar o candidato. |
| A06 | 1: retirar “54 quality-screened parents” do abstract | Atender; explicar a seleção 54/90 e as partições no desenho experimental. Não chamar a divisão de adequada sem descrever seu alcance. |
| A07 | 1: simplificar 210/150 registros, outras sementes e censura | Atender à simplificação. Corrigir a população na sugestão marginal: 150 = (6 fáceis + 4 médias) × 3 métodos × 5 caps; não seis médias. Manter história auxiliar no GitHub e definições científicas de censura nos métodos/resultados. |
| A08 | 1: excesso de certificação/restrições no resumo | Retirar a contabilidade detalhada da abertura; manter limitações numéricas relevantes nos resultados, notas e conclusão. Não confiná-las aos registros internos. |
| A09 | 1: detalhar LP → inferência nos métodos, não no abstract | Atender; R continua identificado de forma simples como comparador baseado na relaxação. |
| A10 | 1: preferir GNN a “neural” | Atender quando melhora a identificação do componente; evitar alternância de termos sem necessidade. |
| A11 | 1: retirar seed/epochs/3400 updates do abstract | Atender; explicar atualização de pesos e trabalho global no desenho da comparação GPU e no suplemento técnico. |
| A12 | 1: resumir o resultado GPU no contexto global | Atender. GPU é resultado complementar; C2/C3 sobre otimização e custos orientam a conclusão. |
| A13 | 1: título com “graph neural network” | Aplicar exatamente o título aprovado pelo mandato; a sugestão parcial foi superada por essa decisão. |
| A14 | 2: conclusão negativa pouco útil e relação com literatura | Substituir a frase genérica por interpretação concreta. Não ocultar resultados desfavoráveis: o mandato determina sua preservação. Não usar citações para transformar uma deterioração observada em resultado favorável ou “esperado” sem evidência. |
| A15 | 2: retirar frase de campanha em execução | Já atendido no artigo atual. O PDF antigo ainda a contém. Impedir sua reaparição na nova montagem. |
| A16 | 2: completar MILP nas keywords | Atualizar keywords para Mixed-Integer Linear Programming e verificar consistência. Não é necessário repetir a expansão em toda ocorrência posterior de MILP. |
| A17 | 2: definir CFL no início da introdução | Atender. Abstract e corpo devem ser legíveis separadamente. |
| A18 | 2: preferir “warm-start candidates” a “assignment patterns” | Atender na progressão introdutória, definindo valor parcial candidato antes de discutir o mecanismo. |
| A19 | 2: explicitar custo e separar F1 de utilidade | Atender; este será o elo entre motivação, C2 e C3. Bom F1 não é necessário nem suficiente para ganho do solver. |
| A20 | 2: referência MILPBench sem ano e padronização | Corrigir pela fonte verificável; manter Harvard/elsarticle-harv. Não inventar ano: verificar metadado ou convenção editorial para ausência de data, distinguindo acesso e publicação. |
| A21 | 2: explicar a conclusão do Start e viabilidade | Explicar tentativa de completar/reparar; o candidato parcial da GNN não é uma solução viável garantida. Aceitação pelo solver depende das suas convenções/tolerâncias. |

Três qualificações são essenciais: a população correta das 150 resoluções; a ausência de garantia de viabilidade pelo Start; e a manutenção dos resultados desfavoráveis onde sustentam a interpretação. O mandato de 30/10 resolve essas ambiguidades das anotações.

### 4. Matriz detalhada de revisão

As páginas referem-se ao PDF anotado, não a uma paginação futura. “Agora” indica independência do retorno CPU12h. “Mista” permite preparar estrutura/fontes agora, com conclusão dependente da #89.

| Local | Problema | Prioridade | Alteração proposta | Fundamentação | Dependência | Aceite |
| --- | --- | --- | --- | --- | --- | --- |
| Título; index.qmd; metadados e documentos correntes | Título atual centra class-aware e diverge da nova decisão | P0 | Aplicar exatamente o título aprovado; registrar supersessão nas orientações correntes, sem retroeditar recibos históricos | Mandato §§2,30 | Agora | Busca de consistência nos arquivos editáveis; metadados e capa concordam; versões arquivadas preservadas |
| Introdução, p.2; contrato/documentos correntes | Contribuição aparece como integração; registros ainda apresentam C1–C3 | P0 | C1 torna-se metodologia; reivindicar apenas C2/C3, com mapeamento interno para os IDs históricos | Mandato §§3–5,8 | Agora | Uma pergunta, um objetivo e duas contribuições; sem renomear IDs científicos/experimentais antigos |
| Abstract, pp.1–2 | Inventário de auditoria ocupa o espaço dos achados | P1 | Substituir integralmente pelo resumo proposto; resultados existentes identificados e versão provisória registrada apenas no controle interno | A01–A12; mandato §7 | Mista | Contexto→objetivo→desenho→achados→interpretação; limite vigente; nenhuma previsão de resultado CPU12h |
| Introdução, p.2 | Motivação não explicita o possível desaparecimento do ganho após preparação | P1 | Explicar CFL, MILP, candidato parcial, utilidade e custo em sequência; anunciar C2/C3 | A17–A19; custos PR86 | Agora | Leitor compreende o problema científico antes dos detalhes da política |
| Artigo/suplementos; highlights.txt | Fronteira leitor/documentação não cobre todos os materiais; último highlight diz “Separate CPU and GPU proposals preserve pending results as pending” | P0 | Remover gestão de campanha dos highlights e incluir esse arquivo e capas/metadados editoriais na revisão de público | Mandato §§7,27; política de 29/10 | Agora | Nenhum status operacional, instrução ao revisor ou orçamento prospectivo nos materiais de publicação |
| Related Work, pp.3–4 | Contraste entre interfaces é breve; custos não sustentam suficientemente C3 | P1 | Sintetizar informação predita, intervenção no solver e escopo de avaliação; preparar matriz comparativa com fontes primárias já selecionadas | Revisão 01.04; D4; mandato §11 | Agora | Não confunde branching, sub-MIPs, regiões restritas e Start nativo; itens não verificados sobre custos são “não verificado” |
| Formulação, pp.4–5 | Formulação matricial correta para a representação, mas pouco ancorada no problema econômico | P1 | Introduzir instalações, clientes, capacidade/demanda e minimização em linguagem natural; acrescentar notação econômica apenas se a correspondência já documentada permitir | R3; mandato §12 | Agora | Nenhuma formulação alternativa apresentada como se fosse o modelo efetivamente executado; nenhum novo gate de gerador |
| Grafo e arquitetura, pp.5–6 | Definições e equações chegam com elevada densidade | P1 | Introduzir nós/arestas e troca de mensagens; distinguir dois ciclos de duas simples passagens; levar derivação detalhada ao suplemento A | Mandato §§13–14; implementação citada | Agora | Variável→restrição→variável e saída binária inequívocas; 2 ciclos/32 fixos, sem alegar busca otimizada |
| Hiperparâmetros, pp.6,32–34 | Racional é útil, mas repetitivo e por vezes retrospectivo | P1 | Tabela compacta “valor/origem fixo-fitado-selecionado/justificativa/limite”, com referências pertinentes | Adam, clipping, Gasse; mandato §§14–15 | Agora | Evidência histórica separada de motivação; nenhuma referência usada como validação CFL de um valor não comparado |
| Relaxação→inferência→Start, pp.7,9,34–35 | Explicação está espalhada por seções | P0 | Sequência única: modelo→primeiro MIPNODE ótimo da raiz→cbGetNodeRel→features/grafo→modelo congelado→escores→seleção→Start→tentativa do solver | R3 methods; mandato §§9,16–17 | Agora | Não usa model.relax() para descrever a captura; sem promessa de viabilidade; região original preservada |
| B/R/G; suporte, p.7 | R pode parecer controle LP independente; cap médio pode ser confundido com 10% efetivos | P0 | Definir suporte k e quantidade q de uns; R usa ranking próprio e (k,q) de G; explicar cap de 20.000 | R3; bindings e regra de seleção | Agora | Controle dependente e custos compartilhados explícitos; IDs M0/M1/M2 preservados; cobertura média não chamada automaticamente de 10% |
| Proveniência de modelos | Diferentes cronologias podem ser comprimidas em “o modelo” | P0 | Tabela liga cada evidência a população, checkpoint, seleção e schedule; preservar a cadeia original CPU e separar pesos GPU | PR85/86 e arquivo PR60 | Agora | Cada figura/métrica usa a cadeia correta; nenhuma substituição pelos pesos GPU; sem reabrir pesos ou refazer inferência |
| Populações, pp.7–12 | Estudo histórico abre Experimental Design; comparação principal aparece depois | P0 | Tabela única: 90→54;34/10/10; histórico6M; principal6F+4M; ampliado4M; GPU | Mandato §§18–20; summary.json | Agora | 150/60 são resoluções repetidas; #89 não acrescenta instâncias independentes às quatro médias |
| Determinismo, pp.9,35–36 | Pergunta aprovada pode soar como garantia incondicional | P0 | Manter pergunta exata e qualificar modelo/parâmetros/máquina/versão, Method automático, valores não exportados e término por tempo | R3; documentação oficial Gurobi | Agora | Nem seed42 garante tudo nem Method=-1 prova por si só não determinismo; nenhuma mudança de parâmetro |
| Métricas, pp.9–10; desenho | Gap domina antes da separação primal/dual | P0 | Definir endpoints e comparabilidade antes dos resultados; distinguir primal, dual, gap, tempo observado, censura, ausência e restrição numérica | Mandato §§19–21; R3 metrics | Agora | MIPGap=0,0001 significa 0,01%; nenhum timeout vira evento completo; reordenação não chamada de pré-registro |
| Principal CPU, pp.11–12 | Contagens sem resultados condicionais suficientes | P1 | Trazer razões pareadas/efeitos individuais e escalabilidade já existentes; estratos fácil/médio e denominadores elegíveis | PR86 final e arquivos seed42 | Mista | Figuras/tabelas respondem C2; preservam resultados desfavoráveis; nenhuma promoção global dos flags |
| M4/M12 e retorno ampliado | Sensibilidade pode ser diluída pela narrativa de maior orçamento | P0 | Disposição por célula e por métrica, com notas próximas dos resultados e seção de limitações | R3; mandato §23 | #89 para novos resultados | 60 células reconciliadas; original flags preservados; ausência/falha/censura não fundidas; mais tempo não declarado reparo numérico |
| Economia computacional | C3 aparece como ressalva, sem comparação substantiva no corpo | P1 | Mostrar contraste solver/tentativa/preparação fria delimitada/reuso/amortização; custos ausentes e treinamento separados | PR86 final, cost_scenarios; mandato C3 | Mista | Escopos e denominadores explícitos; cenários de 5 e 7 usos distintos; sem economia total/energia/moeda inventada |
| Histórico6M, pp.14–18 | Domina a apresentação em relação ao estudo principal | P1 | Síntese curta no corpo e tabelas/diagnósticos estendidos no suplemento B | Mandato §§6,22 | Agora | Seis médias continuam visíveis e distintas, sem substituir resultados principais ou somar amostras |
| GPU, pp.12–14 | Ênfase em contagem de updates e speedup desloca o foco | P1 | Relatar tempo, qualidade selecionada e GPU-h conjuntamente; detalhes de schedule no suplemento; causalidade CPU/GPU qualificada | PR87; mandato R5 | Agora | Preserva 2,167/1,831, queda F1 0,032468 e maior GPU-h; não atribui benefício downstream |
| Discussão e conclusão, pp.18–20 | Limitações predominam; faltam mecanismos observáveis e resposta C2/C3 | P1 | Interpretar regimes, primal/dual e custo; confrontar interfaces da literatura; concluir de forma condicional | Mandato §§24–25 | Mista | Afirmações amarradas aos achados; nenhuma causalidade do seletor; conclusão final aguarda qualificação |
| Suplementos, pp.26–50 | Pacote antigo contém orçamento, revisão de autores e HAI; current já removeu parte | P1 | A métodos; B resultados estendidos; C reprodutibilidade; futuro compacto na conclusão; HAI interno | Mandato §§26–28; diff atual | Mista | Inclusão por função científica; material interno não retorna ao pacote; declaração de IA preservada |
| Pipeline, p.3, e demais figuras | Pipeline atual foi desenhado para “new medium model”; pouco explícitos R, preparação e custo | P1 | Figura de inferência com ramificação R dependente de G e separação treino/uso; custos fora/na resolução identificados | Fonte da figura e R3 | Agora | Adequada às 6F+4M; legenda independente; região viável preservada; nenhuma figura histórica sobrescrita sem trilha |
| Referências, pp.20–25 | MILPBench sem ano; URLs/DOIs repetidos; oito avisos de pages | P2 | Conferir metadados e tipo de publicação; eliminar redundância de apresentação; manter autor–ano Harvard | A20; BibTeX atual; elsarticle-harv | Agora | Citações resolvidas; nenhum dado inventado; ausência de pages tratada segundo tipo, não como erro automático |
| Tipografia e tabelas | Números colados a palavras; tabelas/fórmulas densas; texto próximo às bordas na figura do pipeline | P2 | Inglês científico contínuo, padronização de espaços/unidades e legendas; arredondar apresentação sem mudar fonte | Inspeção visual e texto atual | Agora | Inspeção visual final; nenhuma fórmula/tabela cortada; leitores compreendem unidades/escopo |
| Índice afirmação–evidência e testes | Mapa de 17 grupos/4 fontes não cobre todos os novos enunciados; literais atuais prendem a organização antiga | P0 | Atualizar vínculos e localização dos claims ao reorganizar; ampliar às tabelas C2/C3 e à história usada | claim-evidence.json e gates atuais | Mista | Valores, fontes e populações verificáveis; novas redações não afrouxam limites; contagem histórica pode ficar fora do artigo sem perder proveniência |
| Reprodutibilidade e pacote editorial | Acesso a dados/pesos/direitos e declarações ainda não concluídos | P1 | Preparar inventário e declaração fiel de disponibilidade; decisões autorais e depósito/publicação separados | Checklist vigente; política oficial da revista | Mista | Nenhuma promessa falsa de acesso/DOI; CRediT/funding/COI/autoria aprovados; pacote final auditado |

### 5. Arquitetura proposta para o artigo

Título aprovado, a aplicar na segunda entrega:
**Evaluating Graph Neural Network-Based Partial Warm Starts for Capacitated Facility Location Problems**

1. **Introduction.** CFL, desafio de otimização, informação aprendida, pergunta única, objetivo e duas contribuições.
2. **Related Work.** Representação/branching como base; maior atenção à orientação primal e aos inícios; avaliação comparável e custos.
3. **Methodology.** Modelo efetivamente usado; grafo; GNN/treinamento; inferência; Start; B/R/G.
4. **Experimental Design.** Populações e exposições; protocolos separados; parâmetros; endpoints; custos; comparação/estatística; plataforma.
5. **Computational Results.** Qualidade preditiva necessária; efeitos B/R/G; tempos/escalabilidade; custos; GPU complementar. Histórico em síntese com remissão ao suplemento B.
6. **Discussion.** Regimes observados, papel primal/dual, custo versus benefício, diálogo com literatura e limites.
7. **Conclusions and Future Research.** Resposta C2/C3 e limites essenciais; sensibilidades somente futuras.
8. **Acknowledgements.** Agradecimento à UJA e DaSCI por dgx-dasci.
9. **Declaration of generative AI and AI-assisted technologies in the manuscript preparation process.** Texto aprovado preservado.
10. **References.** Numerada conforme decisão do autor, com bibliografia Harvard.

Não são dez seções científicas concorrentes: as últimas três são o backmatter já aprovado. A numeração final segue a classe e o render.

Pergunta principal, preservada exatamente:
*Can partial initial values predicted by a graph neural network (GNN) be used as warm starts for a deterministic MILP solver and improve its performance when solving Capacitated Facility Location (CFL) problems?*

Sua operacionalização identifica condições de benefício e o efeito dos custos. As dimensões de avaliação não se tornam perguntas principais adicionais. O termo “deterministic” será qualificado pelo protocolo; não atesta repetibilidade temporal de cada execução.

Objetivo geral: modelar, desenvolver e avaliar uma GNN em HPC para investigar os efeitos de valores iniciais parciais em um solucionador MILP aplicado ao CFL. SO1–SO8 continuam rastreados no relatório interno; sua lista de gestão não precisa dominar a introdução.

### 6. Proposta de abstract — 212 palavras

Esta é uma proposta provisória baseada apenas em evidências existentes. A marca “provisória” e as dependências abaixo são deste diagnóstico interno; não fazem parte da prosa de publicação.

Capacitated Facility Location (CFL) problems are commonly formulated using Mixed-Integer Linear Programming (MILP), whose solution requires both finding feasible decisions and assessing their quality. A Graph Neural Network (GNN) can propose partial warm starts, but their usefulness depends on the solver response and the cost of preparing them. We evaluate these two aspects by comparing optimization without an external start, a root-relaxation-based start, and a GNN-generated start. The principal retrospective comparison comprises six easy and four medium benchmark instances, one fixed solver seed, and five thread configurations. For the six easy instances, geometric-mean GNN-to-baseline solver-time ratios indicate longer runtimes at one and two threads and shorter runtimes at four, eight, and sixteen threads. At sixteen threads, the GNN-to-baseline ratio is 0.844 for solver runtime and 1.046 for supervised execution with delimited cold preparation, illustrating how overhead can reverse a solver-level advantage. Medium-instance outcomes are interpreted with endpoint-specific censoring and numerical qualifications. A complementary one-versus-four-GPU training comparison yields a 1.831-fold whole-job speedup, accompanied by lower selected predictive quality and higher allocated GPU-hours. These observations show that the practical value of GNN-generated partial starts depends on instance characteristics, resource settings, and the scope and reuse of preparation work. Predictive accuracy and training speed therefore need to be evaluated alongside optimization outcomes and computational costs.

As razões CPU acima são T_G/T_B, portanto menores que 1 favorecem G. Não são o speedup T_B/T_G. Os valores apresentados não dependem da #89: 0,844 arredonda 0,8435 e 1,046 arredonda 1,0461 na revisão final da PR86. São agregados geométricos de seis fáceis, seed42,16 threads; o segundo refere-se à tentativa com preparação fria delimitada, não a uma medição end-to-end completa nem a uma execução isolada nova.

Após a qualificação da #89, revisar externamente os seguintes trechos: desenho da população ampliada; síntese dos efeitos nas médias; qualificação temporal/numérica; alcance de custos; resposta final. Não basta acrescentar um resultado favorável ao fim do resumo. A versão definitiva deve refletir todos os resultados elegíveis e a primazia científica de C2/C3.

### 7. Parágrafos propostos das contribuições

**Conditional optimization effects (C2).** We assess how GNN-generated partial starts affect CFL optimization under matched model, resource, and stopping conditions. Comparisons with an unguided solver and a support-matched root-relaxation start characterize instance- and thread-dependent changes in primal quality, dual bounds, optimality gaps, and observed time to quality targets. The assessment retains adverse outcomes, censoring, and numerical qualifications, and concerns the evaluated instances rather than universal or seed-averaged superiority.

**Computational cost–benefit assessment (C3).** We examine whether solver-level benefits persist within the computational costs required to generate and apply partial starts. Measured preparation and execution components are distinguished from delimited cold-use, reuse, and amortization scenarios, while offline training and allocated CPU/GPU resources are reported separately. This accounting identifies the scope within which a solver-level gain can remain useful, without equating incomplete cost coverage with complete operational savings.

No artigo, estas duas contribuições podem ser apresentadas como primeira e segunda sem exibir os códigos de gestão. O mapeamento interno continua C2/C3; C1 permanece identificado historicamente como mecanismo metodológico. A redação definitiva será ajustada à evidência qualificada, sem prometer achados ainda ausentes.

### 8. Plano dos resultados: o que entra e por quê

### R1 — Qualidade preditiva
Um quadro compacto caracteriza o modelo efetivamente empregado: seleção por validação, raridade dos positivos, F1 e AP/PR-AUC com sua agregação. Curvas completas e diagnósticos de calibração no suplemento B quando necessários. Não misturar o checkpoint CPU com os modelos GPU nem transformar classificação no resultado principal.

### R2 — Eficácia B/R/G
Apresentar efeito individual por instância e cap, distinguindo primal, dual, gap e limiar observado. Tabelas devem identificar elegibilidade e resultado censurado/ausente/restrito, e não apenas vencedores. As seis fáceis e quatro médias ficam em estratos separados. A camada CPU12h será acrescentada somente após qualificação, com orçamento e observação próprios.

### R3 — Eficiência e escalabilidade
Os dados existentes já permitem mostrar que a razão geométrica T_G/T_B das seis fáceis é 1,1806/1,1643/0,7077/0,7056/0,8435 para 1/2/4/8/16 threads, respectivamente. Isso expressa heterogeneidade no agregado de seis instâncias, não que todas melhoram nem que 4/8/16 sejam configurações ótimas. O controle R precisa permanecer visível. As razões entre métodos não se confundem com T_m(1)/T_m(r) dentro de um método. Censuras e M4/M12 não entram como tempos de solução certificados.

Esses contrastes são descritivos. Os intervalos exploratórios não constituem teste confirmatório de superioridade nem de interação entre método e threads. Em 16 threads, tanto o intervalo da razão de Runtime quanto o do cenário frio delimitado incluem 1. A mudança de direção do estimador pontual é uma observação do conjunto avaliado, não uma fronteira econômica ou configuração ótima estimada para novas instâncias.

### R4 — Custos e C3
A evidência já existente das seis fáceis, seed42,16 threads fornece um contraste útil:

| Escopo | Razão T_G/T_B | Leitura |
| --- | ---: | --- |
| Runtime do solver | 0,8435 | Vantagem no intervalo do solver |
| Tentativa + preparação fria delimitada | 1,0461 | Vantagem não permanece nesse cenário |
| Tentativa + preparação fria com rateio ampliado | 1,0692 | Rateio mais amplo mantém essa reversão |
| Tentativa + preparação delimitada amortizada em sete usos | 0,8935 | Reuso altera a comparação sob essa hipótese |
| Tentativa + preparação ampliada amortizada em sete usos | 0,8969 | Resultado condicionado ao rateio e reuso declarados |

Fonte já publicada: docs/research/pr86-final-analysis.md e arquivos de custos correspondentes. O reuso em sete usos é deste cenário histórico; a alocação em cinco usos de outros produtos não é intercambiável. Não extrapolar para as médias, a #89, custo monetário, energia ou implantação completa. Componentes ausentes continuam ausentes; intervalos inclusivos não são somados duas vezes.

### R5 — GPU complementar
Mostrar conjuntamente 2,167 de speedup do loop e 1,831 do job, F1 selecionado 0,723065→0,690597 e GPU-h alocadas 0,5614→1,2267. A precisão final dependerá da tabela/legenda. Explicar CPU4→16 acompanhando GPU1→4, uma seed e ordem fixa. Não inferir causalidade GPU isolada ou benefício das novas redes para os Starts CPU.

### Evidência preliminar histórica
Retém uma síntese curta no corpo: melhora de gap em cinco de seis médias, efeito influenciado por algumas instâncias e endpoints distintos. Tabelas completas, influência e curvas vão ao suplemento B com seu próprio protocolo e limites. Não fornece a resposta substituta da comparação CPU principal/ampliada.

### 9. Populações a apresentar sem ambiguidade

| Conjunto | Composição | Papel e unidade |
| --- | --- | --- |
| Candidatas/admitidas | 90 candidatas; 54 admitidas:30 fáceis+24 médias | Seleção por qualidade de etiqueta; nenhuma hard admitida |
| Partições preditivas | 34 treino;10 validação;10 teste | Instância original como unidade; teste6F+4M historicamente exposto |
| Histórico preliminar | Seis médias de teste; seis médias de validação do seu protocolo | Coorte de otimização distinta; não adicionar à amostra principal |
| CPU principal existente | 10 instâncias ×3 métodos ×5 caps =150 resoluções seed42 | 6F+4M; condições repetidas dentro de instância |
| CPU ampliada | 4 médias ×3 métodos ×5 caps =60 resoluções seed42 | Mesmas quatro médias expostas;12h; nenhum resultado ainda recebido nesta revisão |
| GPU | Um par serial1/DDP4; treino34/val10/teste10 | Comparação de configurações de treinamento, não 10 replicações do efeito de GPU |

Os 97 alvos terminais reportados e 53 censuras referem-se às 150 resoluções; os 30 registros sensíveis M4/M12 são um subconjunto. Essas contagens servem à disposição científica da amostra e não precisam abrir o abstract. Preservar os 210 registros históricos no repositório não obriga a narrar sua contabilidade na abertura do artigo.

### 10. Suplementos propostos e sua seleção

| Destino | Conteúdo | Ação sobre o material atual |
| --- | --- | --- |
| Supplementary A — Model and Method Details | Representação/equações, arquitetura, justificativas proporcionais, hiperparâmetros, inferência, pseudocódigo B/R/G | Reorganizar gnn-methods-audit e a parte de aprendizagem/seleção da configuration-reference; eliminar duplicações |
| Supplementary B — Extended Experimental Results | Resultados por instância, tabelas históricas, CPU elegível, curvas, censura, restrições numéricas e custos | Consolidar fontes existentes agora e acrescentar CPU12h somente após qualificação; não publicar tabelas vazias como resultados |
| Supplementary C — Reproducibility and Computational Settings | Dados/partições, checkpoints, versões, hardware/alocação, parâmetros, hashes, proveniência e limites de acesso | Reter valores exatos e links imutáveis; distinguir especificação de observação; não incluir orçamento de gestão |
| Conclusions and Future Research | Questões de sensibilidade realmente motivadas pelos limites observados | Resumir seeds, root method, capacidade e ablação; não manter um plano de execução inteiro como suplemento autônomo |
| docs/research e PR | Histórico, orçamentos, planos B–E, decisões HAI, coauthor brief, estados de jobs, autorização | Permanecem internos. Os dois últimos grupos já foram separados em 29/10 e não devem retornar ao pacote |

Supplementary B é um suplemento de resultados, não o antigo Appendix B sobre IIEA-S. A terminologia final evitará essa colisão. A declaração editorial de IA permanece no artigo com texto e autoria aprovados. Nenhum estudo Human–AI será promovido a contribuição.

A numeração A/B/C é uma proposta editorial, não uma exigência do Guide for Authors reconfirmada nesta consulta. Cada arquivo deve ser autossuficiente, com título, legenda e referências necessárias, sem capa “for coauthor review”, data da campanha, número de PR ou instrução temporária. Hashes e links de proveniência têm função científica e podem permanecer.

### 11. Discussão e interpretação a desenvolver

A primeira discussão deve explicar o efeito observado, depois seu alcance: quais instâncias/configurações ajudam ou prejudicam; se o gap melhora por primal, dual ou ambos; se a antecipação de um alvo permanece quando se considera a preparação; em quais condições de reuso o cenário muda. Esses são temas de C2/C3, não novas perguntas principais.

A relação com MIP-GNN, Neural Diving e Predict-and-Search deve partir da interface e do critério de comparação. Não alegar que esses trabalhos omitem custos sem consultar a seção correspondente da fonte primária. Na matriz de posicionamento, usar “não verificado” quando só a revisão anterior não sustentar uma conclusão sobre o custo. Tampouco transferir os percentuais de outros problemas para CFL ou apresentar uma comparação experimental com algoritmos não executados.

A arquitetura Gasse-inspired é justificável como escolha para a estrutura variável–restrição, não como novidade ou melhor variante. GCN, GraphSAGE, GAT e GATv2 podem contextualizar, mas não exigem uma nova grade experimental.

Manter a distinção entre configuração reproduzível, trajetória algorítmica e término por tempo. O manual de Start descreve uma tentativa de completar valores parciais. A orientação oficial de determinismo condiciona repetibilidade aos inputs/máquina/versão e alerta para parâmetros temporais e seleções concorrentes. A seed42 sozinha não é uma prova. Não concluir pelo valor Method=-1 que toda execução foi não determinística; não imputar ConcurrentMIP ou algoritmo efetivo ausentes. Isso permite descrição das comparações observadas, não variância multissemente nem speedups esperados estáveis.
Fontes: https://support.gurobi.com/hc/en-us/articles/360031636051-Is-Gurobi-deterministic e https://docs.gurobi.com/projects/optimizer/en/current/reference/attributes/variable.html#attr:Start.

### 12. Execução da revisão após aprovação

| Frente | Trabalho antecipável | Dependência mantida |
| --- | --- | --- |
| S1 | Registrar título/C1 como supersessões de comunicação científica; atualizar documentos correntes | Sem alterar contratos de execução instalados |
| S2 | Métodos/pipeline, populações, parâmetros, proveniência, bibliografia direcionada | Sem novas raízes, inferências, treinamentos ou testes de solver |
| S4 | Interpretar PR86/87, construir C2/C3 com limites, preparar tabelas existentes | Síntese das quatro médias em12h aguarda #89 |
| S5 | Reescrever estrutura, abstract provisório, contribuições, discussão, suplementos A/B/C e highlights | Abstract/conclusões finais e pacote fechado aguardam qualificação |
| S3 | Nenhuma alteração da campanha; preparar esquema de análise já aprovado | Recepção/reconciliação60células, integridade, disposição/eligibilidade por métrica, resultados e custos |
| S6 | Preparação editorial dos materiais e pendências autorais | Revisão/aprovação final, merge, publicação e submissão específicos |

Recomendo continuar na mesma PR #93. Não há razão metodológica para encerrar ou fragmentar esta revisão em PRs menores. Após aprovação do diagnóstico, implementar em commits coerentes: (1) eixo científico/título/estrutura; (2) métodos/populações/suplementos; (3) resultados existentes/C2/C3/figuras/claim map; (4) revisão editorial e validação. Esses commits não constituem novas Sprints ou autorizações experimentais.

Não promover a revisão de develop para main/Pages sem autorização específica. Atualizar título no branch de trabalho não autoriza publicação.

T1: conferir fontes, números/citações, público-alvo, duplicações e links. T2: testes dos controles de manuscrito/proveniência efetivamente afetados; atualizar expectativas editoriais sem enfraquecer proteções científicas. T3: CI do HEAD final e render com inspeção visual de todas as páginas do pacote final. Não repetir solver, treinamento, inferência, replay histórico ou coleta apenas para validar prosa. Checks verdes anteriores são o baseline, não prova de aprovação da futura revisão.

### 13. Dependências da #89 e decisão humana

Depois do retorno, reconciliar as 60 células sem redefinir silenciosamente o marco de recepção/reconciliação. Dispor cada ausência, falha, censura e restrição numérica por métrica; conservar fonte/ambiente/start/checkpoint e flags originais. Só então preencher eficácia nas médias, cruzamentos/horizontes, efeitos de caps, contabilidade de recursos e interpretação C2/C3. Não interpolar ou prolongar trajetórias; limites maiores não tornam12h um prefixo de um solve configurado com outro orçamento.

Se houver célula sem retorno, dependência bloqueada ou evidência insuficiente, apresentar o impedimento e solicitar decisão específica. Não executar retry. A autorização de consulta/coleta/análise já existente não deve ser submetida novamente como orçamento novo; a intervenção humana continua necessária para cada acesso CLI ao HPC.

A auditoria integral final do repositório, resultados, artigo e suplementos é obrigatória após a qualificação. A passagem independente/documental desta entrega não a substitui.

O prazo de 15/12/2026 para manuscrito completo aos coautores permanece meta; dezembro é reservado a revisão e janeiro ao fechamento editorial, com aprovação pretendida07/01, submissão10/01 e máximo14/01/2027. Uma demora de qualificação ou insuficiência científica exigirá impacto e alternativa editorial explícitos, não conclusão favorável fabricada nem experimento automático.

Decisões:
- Já tomadas pelo autor: título exato; apenas C2/C3 como contribuições; C1 metodológico; novos experimentos como futuro; campanha imutável; merges/publicação específicos.
- Decisão imediata prevista no mandato: aprovação científica deste diagnóstico, estrutura, proposta de abstract/contribuições e organização dos suplementos antes da implementação. Não é nova autorização genérica para editar o GitHub.
- Após #89: aceitar a síntese qualificada e a suficiência científica para o periódico, ou decidir a alternativa editorial se persistir lacuna material. Não há proposta de novo experimento como condição automática.
- No fechamento: autoria/CRediT, funding/COI, declaração de disponibilidade/direitos, texto editorial final, merge, publicação e submissão. Não foram inferidos de commits nem modificados.

A instrução final do mandato determina: “A tarefa imediata é produzir o diagnóstico detalhado, a matriz de revisão e a proposta de novo abstract, sem alterar ainda a PR #93.” Também estabelece: “Após aprovação humana, implementar a revisão na PR #93”. Por isso esta entrega é somente diagnóstica. Nenhum bloqueio do sandbox ou exigência de skill criou esse gate.

### 14. Fontes específicas do diagnóstico

Todos os caminhos abaixo foram consultados no HEAD 3f5789fe, salvo as fontes históricas explicitadas pelos próprios manifestos. Datas, estados e decisões históricas não foram promovidos a autoridade atual.

- [Artigo atual](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/3f5789fe34fe1dc9f80f84e3e2c46d3bdea3f30f/manuscript/index.qmd), [guia de suplementos](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/3f5789fe34fe1dc9f80f84e3e2c46d3bdea3f30f/manuscript/supplement/README.md), [métodos](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/3f5789fe34fe1dc9f80f84e3e2c46d3bdea3f30f/manuscript/supplement/gnn-methods-audit.md), [configurações](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/3f5789fe34fe1dc9f80f84e3e2c46d3bdea3f30f/manuscript/supplement/configuration-reference.md), [futuro](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/3f5789fe34fe1dc9f80f84e3e2c46d3bdea3f30f/manuscript/supplement/sensitivity-review-plan.md).
- [R3](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/3f5789fe34fe1dc9f80f84e3e2c46d3bdea3f30f/docs/research/mvp2-r3-contract.md), [métodos/modelos](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/3f5789fe34fe1dc9f80f84e3e2c46d3bdea3f30f/docs/research/mvp2-r3-methods-and-models.md), [métricas/reprodutibilidade](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/3f5789fe34fe1dc9f80f84e3e2c46d3bdea3f30f/docs/research/mvp2-r3-metrics-and-reproducibility.md).
- [PR86 análise final](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/3f5789fe34fe1dc9f80f84e3e2c46d3bdea3f30f/docs/research/pr86-final-analysis.md), [summary seed42](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/3f5789fe34fe1dc9f80f84e3e2c46d3bdea3f30f/docs/evidence/methodology-20261019/summary.json), [razões seed42](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/3f5789fe34fe1dc9f80f84e3e2c46d3bdea3f30f/docs/evidence/methodology-20261019/seed42_paired_speedups.csv), [custos seed42](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/3f5789fe34fe1dc9f80f84e3e2c46d3bdea3f30f/docs/evidence/methodology-20261019/seed42_cost_scenarios.csv).
- [D4 literatura](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/3f5789fe34fe1dc9f80f84e3e2c46d3bdea3f30f/docs/research/methodology-20261019/D4-related-work.md), [síntese R2-D8](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/3f5789fe34fe1dc9f80f84e3e2c46d3bdea3f30f/docs/research/mvp2-integrated-assessment.md), [checkpoint bindings](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/3f5789fe34fe1dc9f80f84e3e2c46d3bdea3f30f/docs/evidence/e0/pr85/checkpoints.csv).
- [Mapa de17grupos](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/3f5789fe34fe1dc9f80f84e3e2c46d3bdea3f30f/manuscript/supplement/claim-evidence.json), [manifesto histórico](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/3f5789fe34fe1dc9f80f84e3e2c46d3bdea3f30f/manuscript/results/current/pr60_scientific_evidence_manifest.json), [BibTeX](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/3f5789fe34fe1dc9f80f84e3e2c46d3bdea3f30f/manuscript/references.bib), [highlights](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/3f5789fe34fe1dc9f80f84e3e2c46d3bdea3f30f/manuscript/highlights.txt), [checklist](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/3f5789fe34fe1dc9f80f84e3e2c46d3bdea3f30f/manuscript/submission-checklist.md).
- [Razões agregadas e intervalos existentes](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/3f5789fe34fe1dc9f80f84e3e2c46d3bdea3f30f/docs/evidence/pr86/final-210/paired_uncertainty.csv) e [componentes dos cenários de custo](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/3f5789fe34fe1dc9f80f84e3e2c46d3bdea3f30f/docs/evidence/pr86/final-210/cost_scenarios.csv). Foram conferidas as seleções seed42/M2/M0, seis instâncias fáceis, e as linhas de 16 threads; não foram reestimados intervalos nem executados experimentos.
- [Manuscript CI](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/actions/runs/40874722918) e [evidence CI](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/actions/runs/40874723085).

