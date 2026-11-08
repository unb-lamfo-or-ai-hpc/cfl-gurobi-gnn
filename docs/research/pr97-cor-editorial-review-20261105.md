# PR97 — revisão científica e conformidade editorial com COR

Revisão de 5 de novembro de 2026. Fontes de decisão: mandato do chat 01.02 de 5/11, contrato R3, [base do artigo e apêndices](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/tree/7d1aed7f1489bdb8d51f77dced00a97dac7c32e4/manuscript), [retorno reconciliado da PR94](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/tree/7d1aed7f1489bdb8d51f77dced00a97dac7c32e4/docs/evidence/pr94/final-20261105) e [Guide for Authors](https://www.sciencedirect.com/journal/computers-and-operations-research/publish/guide-for-authors), captura fornecida de 3/11/2026 (19 páginas). As observações dos relatórios de 3/11 usadas aqui são as reproduzidas no mandato. A captura fornece as regras abaixo; a página live não pôde ser consultada nesta revisão.

## Matriz de conformidade

Categorias: CONFORME, AJUSTAR, PENDENTE DE AUTOR, NÃO VERIFICADO e NÃO APLICÁVEL. As evidências se referem à revisão da PR97, não a uma decisão do periódico.

| Requisito e natureza | Situação | Evidência | Correção ou verificação final | Responsável |
|:--|:--|:--|:--|:--|
| Resumo factual e autônomo, até 250 palavras (obrigatório, p. 9) | CONFORME | Objetivo, B/R/G em palavras, C2/C3, campanhas separadas e acrônimos definidos | Conferir contagem no HEAD; manter o treinamento GPU como contexto secundário | Codex |
| 1–7 keywords em inglês (obrigatório, p. 10) | CONFORME | Cinco termos no front matter | Revisar termos com o texto final | Codex |
| Highlights editáveis, 3–5, até 85 caracteres (obrigatório, p. 10) | CONFORME | Cinco frases em `manuscript/highlights.txt` | Entregar como arquivo separado no sistema | Codex / autor correspondente |
| Graphical abstract (recomendado, p. 10) | NÃO VERIFICADO | A figura do pipeline pode orientar um resumo gráfico; direitos e legibilidade a 13 cm ainda precisam de avaliação | Só preparar se for escolhido; a guia indica largura mínima de 1328 px e formato preferido PDF, EPS, TIFF ou MS Office | Autores |
| Fonte editável e equações/tabelas editáveis (obrigatório, pp. 9–11) | CONFORME para a prévia | Quarto gera TeX do artigo e suplemento, bibliografia e pacote de dependências. Tabelas e equações são texto | Usar o pacote do mesmo commit dos PDFs aceitos; verificar novamente no pacote final | Codex |
| Título, autores e endereços completos, correspondente e email (obrigatório, p. 9) | PENDENTE DE AUTOR | Título aprovado, ordem, afiliações, ORCIDs e emails existentes | Confirmar endereços postais completos e designar um correspondente | Autores |
| Competing interests, financiamento, CRediT (declarações do guia, pp. 5–6 e 14) | PENDENTE DE AUTOR | [Checklist de submissão](../../manuscript/submission-checklist.md) | Fornecer fatos e papéis individuais, preencher formulário e confirmar o texto | Autores |
| Declaração de IA, quando aplicável (obrigatória, pp. 6–7) | PENDENTE DE AUTOR | Seção existente antes das referências; identifica ferramentas e declara revisão e responsabilidade | Confirmar uso e revisão humana na versão final | Autores |
| Dados e Option C (obrigatório, p. 13) | PENDENTE DE AUTOR | Proposta factual no artigo; inventário abaixo; plano de curadoria versionado | Verificar depósito e citação persistente, ou declarar justificativa específica e aprovada | Autores / Codex |
| Referências, correspondência e estilo autor–ano (pp. 3, 15–16) | CONFORME para citações e estilo; metadados externos finais NÃO VERIFICADOS | Build confere a cobertura de citações; Harvard/Elsevier autor–ano. PaScal reaproveita a bibliografia do Model Agrologistic | Conferir os metadados das entradas novas e revalidar links/DOIs no pacote de submissão | Codex |
| Figuras, tabelas, legendas e posição (pp. 10–12) | AJUSTAR no exame visual final | Figuras vetoriais com fonte estática e tabelas editáveis. Novas tabelas da PR94 têm legendas e são chamadas no texto | Conferir Figura 1, Tabela 1, Figura 4, cortes, leitura em escala e referências no PDF do HEAD | Codex / autores |
| Parágrafo antes e depois de elementos centrais (preferência editorial) | AJUSTAR no exame visual final | Contexto e interpretação no texto; B preserva tabelas históricas e adversas | Revisar transições no PDF; manter o limite interno de 20 páginas, que não é atribuído ao periódico | Codex / autores |
| Suplemento autônomo versus apêndices dentro do artigo (pp. 12 e 15) | PENDENTE DE AUTOR | O pacote atual usa suplemento autônomo A/B/C | Se forem anexados ao artigo, usar Fig. A.1, Table B.1 e Eq. (C.1), com teste de todas as referências. Selecionar os históricos de 39 instâncias sem apagar o arquivo | Autores / Codex |
| Vídeo e co-submissão MethodsX/Data in Brief (opcionais) | NÃO APLICÁVEL | Pacote científico atual em artigo e suplemento | Reavaliar apenas se selecionados pelos autores | Autores |

## Disponibilidade e limites de reprodução

R1 = reconstrução analítica. R2 = reprodução das predições e Starts. R3 = reprodução integral da preparação, treinamento e otimização. A sigla R3 neste quadro denota o nível de reprodução, distinto do contrato científico com a mesma sigla.

| Artefato | Situação verificada | Vínculo e limite |
|:--|:--|:--|
| Originais MILPBench | DISPONÍVEL NA ORIGEM | Fonte citada e hashes no [inventário de instâncias](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/7d1aed7f1489bdb8d51f77dced00a97dac7c32e4/docs/evidence/e0/pr85/parents.csv). Conferir direitos de redistribuição antes de espelhar. |
| Dataset de treino e etiquetas completas | RESTRITO | Metadados de admissão públicos. Bytes completos e direito de redistribuição ainda não validados para o depósito. |
| Partições | PUBLICAMENTE DISPONÍVEL | [Tabela de folds](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/7d1aed7f1489bdb8d51f77dced00a97dac7c32e4/configs/splits/cfl_90_seed42_folds.csv) com a regra de admissão que produz 34/10/10. |
| Grafos, features, vetores raiz e predições | RESTRITO | Configuração, encoder e selos públicos. Reprodução de bytes requer acesso às entradas e ao estado numérico. |
| Checkpoints e normalização | RESTRITO | [Ledger](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/7d1aed7f1489bdb8d51f77dced00a97dac7c32e4/docs/evidence/e0/pr85/checkpoints.csv) identifica o artefato CPU e as condições de seleção. A comparação GPU não fornece um substituto. |
| Configurações, executores, ambiente e dependências | PUBLICAMENTE DISPONÍVEL, com lacunas ambientais | Apêndice C, planos e recibos fixam versões e controles reportados. CPU exata, OS/Slurm e driver da máquina permanecem por confirmar. |
| Starts | RESTRITO | Métodos, contagens, regras e hashes nos retornos e planos. Vetores separados dos artefatos públicos. |
| Resultados B/R/G, CPU12h e GPU | PUBLICAMENTE DISPONÍVEL em forma derivada | Recibos e tabelas nas pastas de [evidência](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/tree/7d1aed7f1489bdb8d51f77dced00a97dac7c32e4/docs/evidence), com disposições e escopos. Logs/vetores privados e auditorias exatas delimitadas conservam sua própria custódia. |
| Scripts e dados compactos de tabelas e figuras | PUBLICAMENTE DISPONÍVEL | [Construtor estático](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/7d1aed7f1489bdb8d51f77dced00a97dac7c32e4/scripts/manuscript/build_results_assets.py), [células da PR94](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/7d1aed7f1489bdb8d51f77dced00a97dac7c32e4/docs/evidence/pr94/final-20261105/cells.csv) e reconciliador offline. |
| DOI e licenças do pacote de preservação final | NÃO VERIFICADO | Conferir inventário, redistribuição de entradas e derivados e identidade do depósito antes de anunciar um DOI. |

R1 tem dados públicos e geração estática verificada pela CI. Reproduzir a reconciliação de nível de ZIP da PR94 requer os dois ZIPs originais; o CSV e o sumário compactos já permitem reanálise dos resultados. Para R2 há código, configuração e identidades, com componentes de acesso restrito e sem repetição independente do encadeamento. Para R3 existem protocolos e recibos, mas reprodução integral exige os dados, pesos, dependências, solver licenciado e ambiente descritos. Os testes editoriais e de integração não contam como repetição científica.

## Suficiência da evidência sobre warm-start

C2 é sustentada em escopo condicional. No CPU12h, G antecede B em quatro de cinco caps de M0; no M7 nenhum G fecha o alvo, apesar do primal comum e das diferenças de bound. Na PR94, M20 mostra atingimento exclusivo de G nas três seeds fora dos casos numericamente restritos, e as fáceis mostram piora agregada de tempo ao alvo estrito. M12 exige a restrição por cruzamento de limites e não fornece um speedup certificado. As instâncias, e não as células ou seeds, delimitam as unidades independentes de comparação.

C3 é sustentada pelas medições e pelos cenários de custo delimitados. Nas seis fáceis a 16 threads, a razão G/B de 0,8435 no solver vira 1,0461 com preparação fria delimitada. Os custos frios e amortizados de R/G da PR94 permanecem sem qualificação. A comparação GPU mede um par de treinamentos e sua contrapartida de qualidade, sem medir aceleração do MILP.

Uma campanha hard não é necessária para essas duas alegações. Testar hard responderia a outra pergunta, a transferência fora da amostra admitida: nenhum dos 30 candidatos hard passou o filtro de qualidade das etiquetas. Uma futura extensão teria de fixar seleção de instâncias, congelar o preditor, verificar raiz/grafo/Start, dimensionar memória e licença, e registrar comparações B/R/G no mesmo orçamento com censura e custos explícitos. Uma primeira estimativa de capacidade é pré-requisito para definir concorrência de blocos. Ela não mudaria a composição das amostras atuais nem fundamentaria superioridade universal.

## Registro de mudanças e validação

- Resumo reequilibrado entre campanhas, discussão liga qualidade preditiva, busca e custos. Termos de desempenho e escalabilidade incorporam a distinção usada no [Model Agrologistic PR151](https://github.com/unb-lamfo-or-ai-hpc/model-agrologistic/pull/151) e citam [PaScal](https://doi.org/10.1109/ACCESS.2025.3639388) e [Cornell](https://cvw.cac.cornell.edu/parallel/efficiency/scaling).
- Contagem estática de 26.753 parâmetros e 256 entradas de buffers usando a configuração 7/5/1, largura 32, dois ciclos e o blob do modelo indicado pelo plano de treino. A contagem descreve a arquitetura. Reutiliza-se a identidade do checkpoint no ledger.
- A PR94 integra os quatro arquivos divergentes com ambas as proteções de bytes e testes. O commit executado é pai da integração, com os arquivos de execução preservados. O teste de preparação usa o blob histórico exato de pr86_solver.py como fixture, pois develop conserva no caminho ativo a versão posterior da PR89.
- Validar fontes, reivindicações numéricas, renderização e pacote TeX. A CI da árvore combinada valida código/proveniência e usa dados sintéticos nas verificações de tensores. Execução científica e ensaios adicionais ficam fora desta revisão.
