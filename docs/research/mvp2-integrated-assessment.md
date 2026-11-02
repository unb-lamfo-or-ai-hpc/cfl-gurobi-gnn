# R2-D8 — Síntese científica e auditoria de integração

Revisão de 2 de novembro de 2026. Este relatório atualiza a síntese com as 60 células da PR89. Ele reutiliza os exames já concluídos cujas fontes permanecem idênticas e registra o que ainda depende de integração ou decisão humana. Não equivale a uma certificação universal do software, dos ótimos ou da generalização. A [versão anterior](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/9453b82314a4ca5ffaf1850d26e5eac5dbc3d98f/docs/research/mvp2-integrated-assessment.md) conserva os diagnósticos intermediários. O [plano por Sprints e PRs](mvp2-closeout-plan.md) governa a continuidade.

## Conclusão sustentada pelas evidências

O projeto demonstra uma implementação rastreável de GNN→Start parcial e uma avaliação empírica de seus efeitos condicionais. Os valores sugeridos não fixam variáveis nem alteram a região viável. O benefício depende da instância, do cap de threads, do alvo de qualidade e da fronteira de custo. A evidência não demonstra superioridade geral, efeito causal da seleção class-aware, ótimo global comum nos casos numericamente sensíveis ou generalização independente.

A contribuição C2 é a caracterização desses regimes favoráveis/adversos e das diferenças entre qualidade primal, progresso dual, atingimento e censura. C3 é a análise de custo dentro de fronteiras explícitas, incluindo preparação histórica, execução, amortização e treinamento. C1 permanece uma obrigação metodológica de implementação/proveniência, não uma terceira novidade algorítmica. A revisão de literatura já realizada no chat 01.04 é reutilizada; não houve nova campanha bibliográfica nem experimento.

## Evidências reconciliadas

| Bloco | Escopo verificável | Interpretação e limite |
| --- | --- | --- |
| Dados e modelo |54 pais admitidos de 90 candidatos; split 34/10/10; checkpoint CPU original | Admissão por qualidade de labels e exposição histórica; sem nova aprendizagem ou prova de generalização |
| CPU principal |150 observações seed 42 em seis easy e quatro medium; 97 alvos reportados e 53 censuras; 30 linhas M4/M12 sensíveis incluídas na amostra | Fonte e números conferidos pelo mapa afirmação–evidência; linhas/caps não são novos pais |
| CPU 12 h |60/60 recibos,60 COMPLETED/0:0 e 180 linhas de accounting; 47 alvos reportados e 13 censuras M7 | Recepção fechada; cada métrica conserva seus limites. [Manifesto](../evidence/pr89/final-20261101/manifest.json), [disposições](../evidence/pr89/final-20261101/disposition.csv) |
| M12, exame primal |Dois laudos, dez pontos: G/4, G/8, G/16 exatos no escopo; sete controles com uma binária fracionária e padrão arredondado inviável | Aritmética racional de todas as linhas/bounds/domínios e objetivo; cinco outros pontos não examinados; nenhum certificado dual exato |
| CPU 12 h, custos |293,919 h somadas de Runtime e 295,072 h de elapsed; 1750,185 core-h físicos observados | Alocação×duração não é utilização, energia ou cobrança; preparação histórica e fila são outros escopos |
| GPU pareada |Uma comparação seed 42: speedup de loop 2,167 e de job 1,831; perda F1 absoluta 0,032468; mais GPU-h alocadas | O ganho de tempo não preserva a qualidade selecionada nem isola causalidade da GPU; esses pesos não substituem o predictor CPU |
| Materiais históricos |Coortes antigas de 39 instâncias e de seis medium, com seus próprios protocolos | Mantidas separadas dos 150 registros principais e das 60 novas observações de horizonte longo; PCA de descritores, não embeddings aprendidos |

A [reconciliação completa](pr89-complete-reconciliation-20261101.md) valida os controles e os seis novos retornos, reutilizando o exame selado das 54 células anteriores. Os arquivos dos snapshots 50/54, seus parâmetros e flags não foram alterados. O job 3734 está incluído com resultado, vetor, log, supervisão e custos; o SHA 256 do ZIP local é igual ao que o autor voltou a conferir no HPC.

## Qualificação por métrica e por instância

| Instância | Resultado terminal | Uso permitido no relato | O que não decorre dele |
| --- | --- | --- | --- |
| M0 |15 alvos reportados; G antes de B em quatro caps e depois de ambos controles com dois threads | Contrastes descritivos no mesmo critério tolerado; preservar pequena discrepância cruzada de 0,000524% | Um ótimo exato comum ou aceleração uniforme |
| M4 |15 alvos reportados; discrepância cruzada de 0,132417% | Qualidade/custo/tempo com restrição numérica explícita | Speedup certificado ou remoção da restrição por gap zero |
| M7 |Dois alvos reportados e 13 censuras; primal terminal reportado comum | Comparar progresso dual, gaps, alvos efetivamente observados e custos; reter massa censurada | Inviabilidade ou exclusão por dificuldade pós-resultado |
| M12 |15 alvos reportados; grande diferença de esforço e tempo | Separar aceitação sob tolerâncias, primal exato auditado e custos observados | Que o Start prendeu a árvore em ótimo local, que controles fracionários são melhores soluções inteiras ou que os quocientes de tempo provam speedup para um mesmo ótimo |

Nas comparações de M12 a 8/16 threads, o Gurobi reporta gap interno zero em todos seis runs. Os vetores G satisfazem os exames primais exatos; os controles contêm uma binária fracionária tolerada, cuja projeção inteira viola uma linha por 0,0000416587. Uma obstrução por intervalos exclui todo complemento contínuo desse padrão. O custo de busca, as iterações e o modelo presolvido diferem substancialmente. Isso dá suporte a uma interpretação de trajetórias distintas, não a um mecanismo causal isolado.

Censura depende do alvo. Todos 60 runs observaram 10% de gap,54 observaram 5%, e 47 observaram 1%/0,01%. Runtime de timeout não é tempo de sucesso; observações de callbacks são cruzamentos registrados, não tempos contínuos exatos. Não misturar esse horizonte de 12 h com as observações históricas de 1 h usadas na futura extensão.

## Auditoria em duas passagens: o que foi conferido e o que permanece aberto

| Área | Verificações já sustentadas | Limite ou gate restante |
| --- | --- | --- |
| A — software científico | Fluxo B/R/G, identidade de modelo/Start, implementação da relaxação, fonte instalada 9ab7823c, normalização/checkpoint e parâmetros documentados; exames anteriores reutilizados | Os pesos/grafos históricos não foram novamente carregados nem o treinamento reproduzido. A combinação real PR89+PR93 deve passar CI após integração autorizada |
| B — evidência experimental | Matriz 60 única, arquivos e controles, estados/códigos, métricas temporais, custos e escopo dos dez pontos M12; 210 registros históricos e GPU preservados | Limites M4/M12/M0 e uma seed principal permanecem científicos. Nenhum flag bruto foi promovido e nenhum retry foi realizado |
| C — artigo | Pergunta/contribuições C2/C3, métodos, populações separadas, resultados adversos, referências e limites compatíveis com as fontes; 101 testes do manuscrito passaram | Revisão científica final dos coautores e aceite da interpretação, sem circulação automática pelo agente |
| D — apêndices e pacote | Tabela completa 60, restauração histórica, parâmetros/hiperparâmetros, comparação documental de interfaces, links, números e fontes; dois PDFs inspecionados em 68 páginas, sem referências não resolvidas ou texto fora da página | Revisar o pacote resultante de qualquer nova evidência e a release efetiva; publicação/submissão dependem de aprovação |

A auditoria de integração ainda não é declarada integralmente encerrada. Existe uma falha de checkout Windows identificada: a conversão LF→CRLF do manifesto muda seu SHA 256 de 6fb17285… para b5150502…, exatamente como no CI. A correção preparada desabilita conversão de texto nos recibos selados; ela não normaliza, altera ou dispensa os hashes. Cinco testes rápidos cobrem os três snapshots, sua continuidade, as disposições, a divergência de finais de linha e a rejeição de adulteração. O novo CI deve confirmar a correção nos quatro ambientes antes de Ready.

Os PDFs da fonte 9453b823 foram entregues: artigo 24 p, referências na 20ª, apêndices 44 p. Numeração de acknowledgements/declaração de IA/referências, agradecimento à UJA/DaSCI e declaração dos modelos 6.1 Sol/6.0 Astra estão preservados. CI aprovado valida implementação e integridade editorial; não certifica validade científica por si só.

## Cobertura dos produtos R2-D1–D8

| Produto | Situação atual |
| --- | --- |
| D1 — contrato | R3 e decisões/supersessões documentados; mandato científico inalterado |
| D2 — métodos | B/R/G, relaxação, inferência, Starts, modelos e hiperparâmetros explicados e ligados às fontes |
| D3 — dados/modelos | Coortes e partições reconciliadas, histórico 39 separado, checkpoint CPU e limitações de proveniência explícitos |
| D4 — determinismo | Semente, paralelismo, Method=-1, TimeLimit/WorkLimit e interfaces distinguidos; evidência de raiz concorrente determinística apenas nos logs efetivamente examinados |
| D5 — eficácia | Resultados principal/GPU/histórico e CPU 12 h recebidos; efeitos condicionais, censura e numerics delimitados; revisão científica final pendente |
| D6 — desempenho/economia | Fronteiras de relógio, preparação, reutilização, amortização e alocação reconciliadas; sem energia/preço/utilização ou cold end-to-end completo inventados |
| D7 — planejamento | Plano único por Sprints/PRs atualizado com os gates de merge, CLI, publicação e submissão |
| D8 — síntese especializada | Este relatório incorpora o retorno completo e os laudos; aguarda CI de integração e revisão final, sem reivindicar certificação universal |

## Continuidade da PR94 e decisões humanas

A instalação zero-call está conferida em c623fe8, plano b41953a8. Raízes, grafos, predições e Starts novos ainda não foram recebidos. O job de raízes depende da CLI já entregue ao autor. O bloco histórico de uma hora contém 57 términos no critério reportado e 33 interrupções por tempo entre as 90 candidatas. Há 79 registros com cruzamento de 10% disponível e 57 com cruzamento de 5%/1%; ausência de cruzamento não é preenchida com Runtime. Todas as nove linhas históricas de M7 são time-limited e não têm cruzamento de 10% registrado nesse orçamento. Isso não contradiz os dois atingimentos posteriores na PR89 de 12 h. Esses totais descrevem disponibilidade e estados arquivados, não admissão irrestrita de reutilização. O retorno deve confirmar o job e todos steps terminais, identidades dos seis modelos, plano/fonte/ambiente, seis resultados e claims compatíveis, supervisão sem parada e selos fechados. Claims não provam chamadas concluídas; um retorno parcial deve ser preservado para diagnóstico.

Somente depois da revisão desse retorno e de sua aceitação por hash haverá CLI separada para guidance. O uso de uma V100 de 32 GB, o checkpoint original, a ausência de labels no forward e os Starts R/G pareados permanecem fixos. As 54 avaliações novas ainda não têm dispatcher liberado; as 90 identidades históricas conservam qualificação por métrica, com 18 linhas M4/M12 restritas.

M7 continua na coorte por decisão do autor. A discussão de nove medium não alterou o protocolo 144/90/54. Não há novos treinamentos ou ablações implícitos. As decisões humanas necessárias continuam sendo as execuções na CLI, eventuais falhas com disposição específica, os merges, a interpretação científica final e a publicação/submissão. Nenhuma comunicação foi enviada em nome dos autores. A meta permanece manuscrito completo até 15/12/2026 e submissão até 14/1/2027.
