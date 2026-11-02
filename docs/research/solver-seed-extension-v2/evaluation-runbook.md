# Avaliação completa: implementação e passagem para a CLI

O adaptador de avaliação está isolado da preparação c623fe858f62 e de toda a PR89. A matriz conserva 144 chamadas novas, uma thread física por solve, TimeLimit=3.600 s e seeds 42/43/44. O corpus de aprendizado, o checkpoint CPU, os hiperparâmetros e a política de Starts não mudam. A instalação no HPC e a liberação de avaliações ainda não foram realizadas.

## Do retorno de guidance ao preflight das 16 instâncias

O último snapshot fornecido pelo autor registra guidance job 3784 RUNNING em 5min34s, com oito AllocCPUS. O job de raízes 3783 já foi recebido e conferido. A coleta terminal de guidance permanece necessária; não se presume que seis grafos e Starts existam apenas porque um job está em execução ou terminou tecnicamente.

Após a revisão do retorno de guidance, o autor executará um instalador com dois argumentos explícitos: commit da avaliação aprovado pelos checks e SHA256 do membro de metadados de guidance revisado. O instalador cria somente um novo estágio `pr94-evaluation-<commit12>` dentro do diretório de dados/evidências existente, sem alterar o estágio de preparação. Se o destino já existir, interrompe e preserva seu conteúdo. Não faz limpeza, reinstalação sobre a fonte anterior, treinamento, inferência ou submissão.

A inspeção utiliza os dez caminhos privados do binding histórico e os seis caminhos do estágio atual; não procura novos benchmarks ou substitui instâncias. Verifica os 16 modelos e, para cada pai, os bytes de raiz, grafo, predições e Starts contra os vínculos públicos. Confere o checkpoint sem desserializá-lo. Lê somente os JSONs de metadados e Starts; não carrega grafos Torch nem chama Gurobi. Identidades ausentes ou divergentes interrompem a inspeção. Não se produzem raízes ou predições substitutas para corrigir o inventário.

O retorno da instalação registra os 16 vínculos, ambiente, fonte, plano, configuração da partição/nó e zero chamadas científicas. Esse retorno precisa ser recebido e revisado antes da CLI de submissão. Um teste sintético não transforma esse preflight em concluído.

## Identidade do modelo e parâmetros

O núcleo de solução novo é uma derivação isolada do solver instalado na PR89. Uma referência textual conserva os bytes originais e um teste compara as árvores sintáticas. As únicas diferenças admitidas são o texto de apresentação, o agrupamento dos imports e o tratamento explícito de um Start vazio quando a política congelada abstém. O solver histórico e os registros de qualificação não são editados para aceitar novos pais.

O mapa completo de parâmetros vem do recibo histórico selado do job 3522, incluindo Method, Presolve, tolerâncias, limites absolutos e demais controles. A política nova altera somente os campos previstos: Seed por célula, uma thread e orçamento de uma hora. Não confia em defaults possivelmente alterados por um ambiente. O resultado reconcilia o mapa efetivamente observado com esse mapa e conserva MINIMIZE, o modelo fresco e a assinatura matemática original.

R e G têm a mesma **quantidade** de variáveis selecionadas e de positivos; seus rankings podem selecionar variáveis diferentes. Não se impõe artificialmente igualdade entre os conjuntos de nomes. O par de Starts é o mesmo nas três seeds. Uma abstenção válida gera dois Starts vazios, preservados como tal: executa-se o modelo original sem atribuições iniciais, mantendo o identificador M1/M2 e a abstenção registrada. Não há nova inferência, seleção de limiar ou troca de método para preencher a célula.

## Submissão e concorrência

A CLI de submissão exige o hash exato do plano instalado que foi revisado. Verifica novamente fonte, ambiente, modelos/artefatos, espaço disponível e configuração do scheduler. A configuração permite o pedido de até quatro jobs de 64 GiB; a disponibilidade atual não é garantida. O scheduler pode mantê-los PENDING. A disponibilidade concorrente de licenças também não é certificada pelo inventário; uma falha real de licença para o job e exige diagnóstico, sem retry.

O operador cria um claim global de campanha e um registro durável por pedido de submissão. Submete os 48 blocos com hold; registra cada ID antes de inspecionar o perfil. Confere dono, partição, parede, CPU, memória, ausência de GPU e dependência. Somente depois de conferir todos os blocos grava a submissão completa e libera da cauda para as cabeças das quatro cadeias. Cada sucessor usa afterok do bloco anterior da mesma cadeia e confere os artefatos fechados desse predecessor.

Uma resposta ambígua, recurso inesperado ou perda de observação conserva claims, IDs e arquivos. Não há caminho de repetição automática, liberação cega, cancelamento ou remoção de resultados. O comando de status mostra também um prefixo de submissões confirmadas e pedidos com resposta ainda não confirmada; não tenta resolver essa ambiguidade executando outro sbatch.

Cada bloco abre três modelos frescos, na ordem prospectiva da matriz. Cada filho precisa corresponder ao job, grupo e célula aprovados e cria um único intent imediatamente antes de otimizar. O watchdog qualificado continua supervisionando a RAM do job e o prazo de 3.780 s por filho. Falhas interrompem o restante do bloco. As outras cadeias já liberadas não são canceladas automaticamente.

## Instrumentação, arquivos e orçamento

São 48 jobs de até quatro horas: 192 job-h e 192 core-h físicos de reserva para avaliações, com 144 solver-h. Acrescentando as preparações já previstas, o teto permanece 50 jobs, 145 solver-h, 195 job-h somadas, 198 core-h físicos e uma V100 GPU-h. Os produtos de alocação não são utilização, energia ou cobrança. A concorrência e a sobreposição entre jobs serão registradas; não se assumirá o mesmo regime temporal da campanha serial anterior.

A preparação continua com sua própria contabilização. A avaliação não cobra a preparação compartilhada duas vezes nem supõe custo ausente igual a zero. O recibo separa Runtime, tempo da função, supervisão e accounting. Enquanto os custos completos de preparação não forem qualificados, os cenários cold/amortizados permanecem incompletos, mesmo quando a aritmética de três usos é possível.

Para reter logs, vetores e recibos das 144 chamadas, a proposta de trabalho passa de 64 para **256 GiB**, com **320 GiB livres na admissão**. São limites de planejamento/observação, não reserva de quota no filesystem. O processo impõe 256 MiB por arquivo; verifica até 1 GiB de saída por célula e o consumo do estágio entre filhos. O watchdog verifica o piso de 64 GiB livres com uma única consulta ao filesystem, sem percorrer toda a árvore durante a medição. A perda de espaço conserva a saída parcial e sua causa; não desencadeia limpeza ou retry. Temporários/caches são direcionados somente ao estágio RAID.

Os tempos de primeiro atingimento de 10%, 5%, 1% e 0,01% são observações de callbacks, não instantes contínuos exatos. O recorder qualificado também conserva os antigos campos de horizontes; somente o horizonte de uma hora é elegível nesta campanha. Os horizontes posteriores ficam explicitamente fora do orçamento e não recebem valores extrapolados.

## Coleta e disposição das células

O coletor faz uma consulta de accounting e lê arquivos somente quando o job e todos os seus steps observados, incluindo batch/extern, são terminais. Pode exportar um subconjunto terminal sem abrir JSONs de jobs em execução. Os demais registros permanecem esperados/não recebidos, e não viram zeros ou falhas presumidas. Uma coleta parcial recebe nome novo; o retorno final não é sobrescrito.

Se um solve terminou mas a qualificação de seu resultado falhou, o relato bruto já escrito é preservado com marcação não qualificada. Logs e vetores ficam privados, com seus selos. Intents são registrados separadamente dos resultados: um intent prova a intenção durável, não que uma chamada foi concluída. A coleta não promove nenhum flag científico.

Após cada retorno, a análise distinguirá qualidade, alvo observado, censura, falha, ausência e sensibilidade numérica. M7 permanece na amostra; M4/M12 mantêm suas restrições. Somente a análise qualificada dos resultados permitirá concluir S5/S6. Nenhuma dessas verificações autoriza merge, publicação em Pages ou depósito Zenodo.
