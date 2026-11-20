# Plano de retomada: migração, preservação e protocolo do MVP 3.0

**Data:** 20/11/2026. **Situação:** análise encerrada para a pausa solicitada.

Este plano organiza a continuidade da PR 102 e a revisão documental da PR 99.
Ele não altera o mandato científico, não reabre a campanha encerrada da PR 98
e não autoriza desenvolvimento experimental ou execução da campanha MVP3.
As PR 99/101 permanecem em rascunho e não foram modificadas nesta etapa.

## Estado confirmado

O ambiente NPAD com Python 3.13.15, Gurobi 14.0.0, Torch 2.7.1+cu118 e PyG 2.7.0
passou pela qualificação de bibliotecas na V100 (job 2278626) e pelo teste da
arquitetura Gasse com três atualizações sintéticas de Adam e licença nativa
Gurobi (job 2278658). O segundo job terminou COMPLETED/0:0 em 37 s, com primal e
dual 1, gap 0 e Threads=0 no MILP técnico. O inventário de versões do venv313
original permaneceu idêntico. Os dois resultados reconstruídos reproduzem os
SHA256 informados pelo pesquisador. A fonte executada 53dc41f passou nos cinco
jobs de CI 44816872315.

Esse GO é de compatibilidade técnica. Ele não demonstra desempenho em CFL,
treinamento completo, leitura do checkpoint histórico, DDP ou capacidade de
memória para as instâncias reais. O próprio pyproject do CFL declara
Python>=3.10, gurobipy>=10 e torch>=2.0, sem um teto declarado que impeça essas
versões. A instalação/importação do pacote completo e seus CLIs ainda precisam
ser conferidos após o clone, sem atualizações automáticas de dependências.

O inventário DGX foi recebido e conferido por SHA256 e CRC do ZIP. A indicação
de incompletude decorre do limite de 32 consultas Git entre 43 localizações em
cfl-mvp2-evidence. Onze consultas ficaram pendentes. A seleção inicial também
usou pr57_54; o registro de worktrees aponta pr57-54. Esta última pasta precisa
ser inventariada; a fonte e o recibo da primeira coleta serão preservados como
executados. Não houve exclusões ou movimentações.

Os volumes abaixo são GB decimais de arquivos regulares. Excluem objetos Git,
credenciais e alvos de links não seguidos, podem contar hardlinks mais de uma
vez e não constituem uma estimativa final de espaço ou volume a transferir.

| Conteúdo observado | Volume aproximado | Implicação |
| --- | ---: | --- |
| Repositório principal e dados locais | 195,56 GB | Há uma entrada rastreada modificada e 40 entradas não rastreadas; preservar antes de qualquer limpeza |
| pyg_dataset, dentro do total anterior | 168,07 GB; 6.886 arquivos | Principal componente de dados; localizar vínculos com os conjuntos e modelos usados |
| Três ZIPs originais em CFL | 5,58 GB | Originais das famílias easy/medium/hard a conservar e identificar por hash |
| cfl-mvp2-evidence | 14,64 GB | Resultados, fontes, preparação, modelos e também componentes de ambiente/cache |
| cfl-zenodo-staging | 52,65 GB | Pacotes de épocas distintas; o staging não comprova depósito nem duplicação byte a byte |
| Worktrees já inventariados | 0,115 GB | Nove estados Git limpos entre os consultados; isso não prova ausência de dados ignorados |

Os caminhos bipartite_graphs, intermediate_lps e raw/MILPBench/CFL existem no
repositório principal. real_train_output e metadata não existem nos caminhos
esperados. Há outros diretórios de modelos e manifestos operacionais; seus
vínculos precisam ser reconciliados antes de concluir que um dado está ausente.

## 1. Concluir a análise de migração para o NPAD

A próxima rodada de leitura terá três entregas: completar a cobertura DGX,
localizar os artefatos canônicos pelos manifestos e conferir o armazenamento
de destino. As onze consultas Git e o worktree pr57-54 serão inspecionados de
forma dirigida, sem repetir a varredura completa. Serão identificados os nomes
do trabalho local ainda não commitado e os vínculos de ambiente que dependem
de arquivos dentro da área de evidências.

Oito manifestos pequenos já foram localizados por metadados nas preparações de
PR87, PR94 e PR 98. Na retomada, sua leitura deverá mapear originais, grafos,
rótulos, partições, Starts e checkpoints sem carregar tensores ou executar
solvers. Os seletores e metadados esperados estão salvos no checkpoint privado.
Credenciais e históricos de shell não pertencem a essa coleta científica.

No NPAD, falta conferir capacidade e quota efetiva de scratch, retenção,
diretórios de trabalho/preservação e condições de acesso. Espaço livre do
filesystem não equivale a quota individual. A topologia e a preempção CANCEL
devem entrar no orçamento; o sucesso com uma V100 não qualifica DDP ou uma
reserva maior. Quantificar CPU-horas, GPU-horas, memória, I/O e espaço temporário
separadamente do tempo de calendário.

**Entrega:** manifesto de migração com origem, destino, papel científico,
tamanho, SHA256, referência de proveniência, tratamento de links e prioridade
de transferência. A lista operacional inicial pode ser menor que o arquivo
histórico completo, sem alterar a coorte científica prevista no mandato.

## 2. Concluir a classificação e organizar o DGX

| Destinação | Conteúdo a avaliar | Critério para concluir |
| --- | --- | --- |
| Copiar para NPAD | Originais CFL; modelos/LPs usados; grafos e rótulos necessários; metadados/partições; checkpoint canônico; evidências necessárias à reprodução | Vínculos documentados e verificação de hashes na origem e destino |
| Preservar em tar.gz no DGX | Campanhas encerradas, falhas, claims, recibos, fontes congeladas, logs/vetores, trabalho local não publicado e pacotes históricos | Arquivo privado por unidade coerente, índice, revisão/versões, SHA256, teste de leitura e restauração isolada |
| Candidatos à exclusão | Cópias locais de arquivos reproduzíveis do GitHub e caches/builds comprovadamente dispensáveis; cópias adicionais já preservadas | Identidade/versão verificadas, cópia retida válida e nenhuma referência operacional necessária |
| Manter sem decisão imediata | Dados únicos, alterações não commitadas, pr57-54 ainda não inventariado, alvos de links e componentes usados por ambientes | Completar inventário e análise de dependências antes de escolher uma ação |

A presença de um arquivo no GitHub ou no Codex não basta para liberá-lo para
exclusão. Conferir versão, identidade e completude; uma cópia temporária do
Codex não será a única preservação de evidência científica. Os dados ignorados
pelo Git não são automaticamente recuperáveis por um clone. O status Git limpo
também não inventaria esses dados.

Archive/quarantine serão examinados pelo conteúdo e pela proveniência. Há
históricos de shell na quarentena, que exigem tratamento privado separado e
ficam fora do conjunto científico a migrar. Os pacotes Zenodo têm tamanhos
distintos entre preparações: não tratá-los como duplicatas sem comparação.

A organização usará um registro de localização e arquivos por campanha, sem
renomear arbitrariamente diretórios citados por planos e recibos congelados.
Antes de comprimir/remover qualquer componente de ambiente ou cache, verificar
se algum interpretador ou biblioteca ainda depende dele. Para cada tar.gz,
registrar origem, revisão, inventário de membros, hashes e procedimento de
restauração; preservar links sem seguir alvos externos indiscriminadamente.
Primeiro verificar o arquivo e a preservação; depois preparar a lista exata de
exclusões. Os comandos concretos serão executados pelo pesquisador na CLI.

**Entrega:** registro de destinação por arquivo/conjunto e roteiro de limpeza
com alvos exatos. Nesta análise nenhum arquivo recebeu autorização definitiva
de exclusão apenas com base em nome, tamanho, data ou suposta redundância.

## 3. Clonar o CFL e preparar o trabalho do MVP 3.0

Após a qualificação técnica e a organização DGX revisada, conferir a revisão
aprovada de develop e criar um clone dedicado no NPAD. Preservar os ambientes
existentes e o projeto Agrologistic; os rascunhos PR 99/101 não serão incorporados
automaticamente. O merge da PR 102 continua dependente de autorização específica.

Conferir as dependências do pacote completo antes de qualquer instalação; se
for necessária, preparar uma CLI que mantenha as versões já qualificadas.
Após o clone, configurar a licença na pasta secrets própria do CFL por um passo
específico. O caminho Agrologistic foi autorizado apenas para o teste já concluído;
nenhuma credencial será incluída nos pacotes de dados ou no GitHub.

Transferir os dados pelo manifesto, mantendo os originais DGX até a verificação
do destino. Comparar hashes e contagens, conferir os alvos de links e registrar
um novo mapa de caminhos NPAD sem reescrever os manifestos históricos. Separar
o conjunto de trabalho dos arquivos de preservação. Testes com dados reais
necessitam de uma CLI concreta e delimitada; não repetir o treino completo nem
lançar a campanha como consequência automática da migração.

O início do desenvolvimento experimental do MVP3 fica condicionado à aprovação
do protocolo pelos coautores. Depois desse gate, abrir PRs de implementação
pequenas, com critérios de aceitação vinculados ao protocolo aprovado. A
infraestrutura migrada não transfere para o MVP3 os antigos orçamentos ou
autorizações de execução.

## 4. Terminar a revisão metodológica antes do desenvolvimento

Retomar a PR 99 a partir do rascunho existente e do plano editorial solicitado,
sem reescrever o mandato. Incorporar primeiro os dois adendos adicionais quando
forem fornecidos e resolver suas consequências antes de congelar o protocolo.
A redação seguirá a organização abaixo, com definições apresentadas antes do
uso e distinção explícita entre decisões aprovadas e propostas não executadas.

1. **Introdução e contexto:** encerrar o alcance do MVP2, expor resultados
   condicionais e limitações e formular a pergunta/contribuições do MVP3.
2. **Métodos e modelos:** apresentar a formulação matemática, identidade
   MINIMIZE, modelos e braços do mandato, mecanismo GNN/Start/solver e recursos
   nativos Gurobi. Tratar Benders como investigação separada, com equivalência
   matemática, validade de cortes, orçamento e autorização próprios.
3. **Planejamento experimental:** tornar explícitos fatores, pares comparáveis,
   versões, recursos e critérios de parada. Discutir organização/particionamento
   para controlar tempo e memória sem mudar silenciosamente o problema ou
   excluir instâncias difíceis após observar os resultados. Qualificar o uso
   de Threads=0 em relação à afinidade e aos recursos realmente reservados.
4. **Coleta e dados:** conferir as 90 instâncias previstas, papéis dos conjuntos,
   exposição histórica, qualidade dos rótulos, partições, checkpoints, métricas,
   estados de execução e proveniência. Preservar os originais e a trilha MVP2.
5. **Análise:** separar avanço primal, fechamento dual, qualidade preditiva e
   utilidade para o solver. Predefinir censura/elegibilidade, comparações
   pareadas, razão T_G/T_B (abaixo de1 favorece G) e tratamento dos custos de preparação/amortização.
   Manter explícitas as hipóteses dos cenários de amortização, sem tratar sete reutilizações como um ponto de equilíbrio empiricamente demonstrado. Distinguir performance, speedup, eficiência, escalabilidade e throughput;
   não misturar tempos DGX/Gurobi13 com NPAD/Gurobi14 como um mesmo experimento.
6. **Apêndices e nota técnica:** reunir definições, fórmulas, parâmetros,
   contratos de evidência e orçamento, mantendo o corpo didático. Conferir
   sinais, índices, unidades e notação de todas as fórmulas; revisar tabelas e
   figuras na versão renderizada e no texto extraído.

O protocolo e a Nota Técnica Gurobi serão disponibilizados em PDF no Codex para
revisão do pesquisador antes da circulação aos coautores. Não enviar mensagens
ou materiais em nome dos autores. A aprovação deve resolver as decisões
científicas pendentes e o orçamento factível, além da apresentação editorial.
O marco documental vigente é 03/12/2026; avaliar seu risco na retomada conforme
a duração da pausa e a chegada dos adendos. A submissão pretendida permanece
18/03/2027, sem promessa de conclusão ou execução automática.

## Primeira sequência na retomada

1. Conferir o checkpoint e o estado das PR 102/99, preservando 53dc41f como fonte
   executada da qualificação já concluída.
2. Preparar a CLI dirigida das onze consultas Git, do worktree pr57-54 e dos
   oito manifestos de vínculos, além da leitura de quota/armazenamento NPAD.
3. Produzir o manifesto de migração e a lista concreta de preservação/limpeza;
   só então preparar empacotamento, clone e transferência para a CLI.
4. Avançar em paralelo na revisão editorial/metodológica da PR 99. Aprovar o
   protocolo com os coautores antes de abrir o desenvolvimento experimental.

Não há novo job HPC, coleta, limpeza, clone, transferência de dados científicos
ou implementação autorizado ou agendado por este checkpoint de pausa.
