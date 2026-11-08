# Avaliação completa: implementação e passagem para a CLI

O adaptador de avaliação está isolado da preparação c623fe858f62 e de toda a PR89. A matriz conserva 144 chamadas novas, uma thread física por solve, TimeLimit=3.600 s e seeds 42/43/44. O corpus de aprendizado, o checkpoint CPU, os hiperparâmetros e a política de Starts não mudam. A instalação e sua inspeção de zero chamadas já foram recebidas e revisadas. A submissão dos 48 jobs foi realizada, mas as quatro cabeças falharam antes do worker e os 44 sucessores foram depois cancelados pelo autor. O pacote de encerramento confirmou os 48 terminais (4 FAILED/44 CANCELLED) e a recuperação recebeu autorização específica. Nenhum resultado de avaliação foi recebido. Ver o [incidente confirmado](../pr94-entry-failure-20261102.md); os passos genéricos abaixo não autorizam repetição ou recuperação automática.

## Do retorno de guidance ao preflight das 16 instâncias

O retorno terminal de guidance **3784** foi recebido e conferido: COMPLETED/0:0 em 387 s, oito AllocCPUS, seis inferências e nenhuma otimização ou treinamento adicional reportados. Os seis suportes são não vazios, com 20.000 variáveis cada; hashes de modelos, raízes, checkpoint e selos de artefatos correspondem aos vínculos esperados. A [revisão](../pr94-guidance-review-20261102.json) descreve o escopo: os vetores privados não foram transferidos nem reproduzidos aqui. A inspeção seguinte verificará seus bytes e os Starts das 16 instâncias.

A fonte fixada para avaliação é `10fd1af20ff40c43147331e7321adf10c151a6f5`, com CI completa `41478889138` aprovada nos quatro ambientes e em tensores. O instalador usa esse commit e o hash **do membro** `guidance-public-return.json` revisado, `7722bacdbb308f7fe8a17c26504cde1f00989eac8d66c2ff68a321a17a73f5a4`. O hash do ZIP, `73599b8eba57c8d9b9fa65bcff9e26151e241cf154cab6f1782a71deba134831`, identifica a transferência e não substitui o hash do membro nesse argumento. A atualização dos recibos e da documentação não muda a fonte de execução fixada.

Após a revisão do retorno de guidance, o autor executará um instalador com dois argumentos explícitos: commit da avaliação aprovado pelos checks e SHA256 do membro de metadados de guidance revisado. O instalador cria somente um novo estágio `pr94-evaluation-<commit12>` dentro do diretório de dados/evidências existente, sem alterar o estágio de preparação. Se o destino já existir, interrompe e preserva seu conteúdo. Não faz limpeza, reinstalação sobre a fonte anterior, treinamento, inferência ou submissão.

A inspeção utiliza os dez caminhos privados do binding histórico e os seis caminhos do estágio atual; não procura novos benchmarks ou substitui instâncias. Verifica os 16 modelos e, para cada pai, os bytes de raiz, grafo, predições e Starts contra os vínculos públicos. Confere o checkpoint sem desserializá-lo. Lê somente os JSONs de metadados e Starts; não carrega grafos Torch nem chama Gurobi. Identidades ausentes ou divergentes interrompem a inspeção. Não se produzem raízes ou predições substitutas para corrigir o inventário.

O retorno da instalação registra os 16 vínculos, ambiente, fonte, plano, configuração da partição/nó e zero chamadas científicas. Esse retorno precisa ser recebido e revisado antes da CLI de submissão. Um teste sintético não transforma esse preflight em concluído.

## Identidade do modelo e parâmetros

O núcleo de solução novo é uma derivação isolada do solver instalado na PR89. Uma referência textual conserva os bytes originais e um teste compara as árvores sintáticas. As únicas diferenças admitidas são o texto de apresentação, o agrupamento dos imports e o tratamento explícito de um Start vazio quando a política congelada abstém. O solver histórico e os registros de qualificação não são editados para aceitar novos pais.

O mapa completo de parâmetros vem do recibo histórico selado do job 3522, incluindo Method, Presolve, tolerâncias, limites absolutos e demais controles. A política nova altera somente os campos previstos: Seed por célula, uma thread e orçamento de uma hora. Não confia em defaults possivelmente alterados por um ambiente. O resultado reconcilia o mapa efetivamente observado com esse mapa e conserva MINIMIZE, o modelo fresco e a assinatura matemática original.

R e G têm a mesma **quantidade** de variáveis selecionadas e de positivos; seus rankings podem selecionar variáveis diferentes. Não se impõe artificialmente igualdade entre os conjuntos de nomes. O par de Starts é o mesmo nas três seeds. Uma abstenção válida gera dois Starts vazios, preservados como tal: executa-se o modelo original sem atribuições iniciais, mantendo o identificador M1/M2 e a abstenção registrada. Não há nova inferência, seleção de limiar ou troca de método para preencher a célula.

## Instalação recebida e plano aceito

A inspeção da fonte `10fd1af20ff40c43147331e7321adf10c151a6f5` terminou em 11,124 s e reportou 16 cadeias conferidas, zero otimizações, inferências, treinamentos e submissões. As projeções de todos os vínculos correspondem aos recibos históricos/novos e ao checkpoint congelado; o ambiente coincide com a preparação. O [recibo](../../evidence/pr94/evaluation-installation-10fd1af20ff4/installation-review.json) e a [revisão](../pr94-evaluation-installation-review-20261102.json) preservam o escopo e os hashes. Os vetores privados e o plano privado completo não foram transferidos nem reproduzidos a partir do ZIP; os checks de bytes/Starts foram feitos pelo preflight instalado.

O hash do plano instalado, conferido no recibo e na saída da CLI, é **`44b443a127af5ec4795e454b534aca8274c8e9a3d3d0ddb91fd67bb4cd4a9600`**. O comando `submit` foi executado com esse hash e registrou os jobs 3785–3832. Os quatro primeiros falharam no guarda de estágio; as quatro cadeias não avançam por `afterok`. Não repetir o comando nem alterar dependências. A fonte instalada e os claims originais permanecem preservados durante a recuperação autorizada. A configuração de batch/dgx-dasci admite o teto proposto, mas não reserva CPUs, RAM, armazenamento ou licenças. O operador verifica novamente a admissão e os perfis reais antes de liberar os holds.

## Recuperação autorizada, antes de qualquer substituição

O [roteiro da recuperação](../pr94-entry-recovery-20261102.md) usa uma única etapa de CLI operada pelo autor, com espera limitada pela CI do commit fixado. Depois da inspeção sem chamadas científicas, revisa o novo plano por equivalência integral ao plano completo `44b443a1` já recebido e aprovado. Dados, Starts, ambiente, parâmetros, grupos e recursos devem conservar seus valores JSON canônicos; apenas a fonte técnica revisada, a proveniência da recuperação e metadados de consulta/ocupação têm exceções fechadas. Um relatório exclusivo é ligado ao novo hash antes do primeiro sbatch. Qualquer divergência interrompe. Não há assinatura humana fictícia, expansão científica ou repetição automática.

O fechamento original e seus bytes são conferidos novamente; o claim antigo não é apagado, movido ou sobrescrito. A substituição usa o claim fixo `pr94-full-v2-entry-recovery-1.claim.json`. As regras de holds, perfis, quatro cadeias e coleta abaixo continuam válidas. O template público precisa ser preenchido com o commit e a execução de CI revisados; somente o autor executará a versão fixada preparada no scratch do Codex.

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
