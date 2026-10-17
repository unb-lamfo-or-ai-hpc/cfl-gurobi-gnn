# PR86 — instrumentação prospectiva, sem autorização de execução

## O que foi implementado

O head anterior `190f5b84678051b191f4c3e131d622ae33dfa333` passou nos quatro
checks de evidências (Ubuntu/Windows, Python 3.10/3.12). Esta continuação
implementa o núcleo parametrizado da resolução e o registro temporal de uma
tentativa futura. Não representa execução da matriz nem conclusão da PR86.

O solver histórico fixa um thread e seed 42 no adaptador `NativeModel`.
Reutilizá-lo sem configuração explícita não realizaria a matriz aprovada como
proposta. `scripts/evidence/pr86_solver.py` é uma versão prospectiva da função
E0: reaproveita o adaptador nativo, a assinatura matemática, a auditoria de
soluções e a interpretação das mensagens de início. Define e verifica, antes
de `optimize`, Threads, Seed, TimeLimit=3600, MIPGap=1e-4 e SoftMemLimit=48 GB
decimais. Rejeita versão de Gurobi diferente de 13.0.1 e sentido efetivo
diferente de MINIMIZE. A declaração original MAXIMIZE continua registrada.

São aceitos os cinco caps 1/2/4/8/16 com seed 42 e seeds 43/44 somente com um
thread. M0 não recebe início; M1/M2 recebem atribuições previamente vinculadas,
sem nova seleção baseada nos resultados. O núcleo exige um callback para criar
uma intenção durável imediatamente antes de sua única chamada de otimização.
Este callback não substitui aprovação de orçamento ou verificação de preparação.

O arquivo histórico `src/cfl_gnn/solvers/paired_partial_start.py`, o executor
E0 e os recibos anteriores permanecem intactos. A versão separada evita mudar
o código vinculado aos resultados históricos. Não há alteração de arquitetura,
dataset, hiperparâmetros de treinamento ou ambiente `tfm_env`.

## Como os custos são separados

`scripts/evidence/pr86_attempt_instrumentation.py` envolve um dispatcher futuro
e registra a tentativa antes da chamada. Um diretório já existente não pode ser
reutilizado; a intenção de otimização e os recibos usam criação exclusiva com
flush/fsync. Uma exceção ou interrupção gera estado de pausa, não retry.

| Intervalo | O que contém | O que não permite afirmar |
| --- | --- | --- |
| Função solver | leitura/hash, construção, otimização, auditoria, exportação de solução e restante disjunto | não inclui todo o processo ou job |
| Supervisor existente | processo filho e fechamento de seu log, conforme interface histórica | não cobre sua primeira amostra de memória ou preparação em outro processo |
| Dispatcher | intervalo externo medido pela nova instrumentação | sua decomposição depende da futura integração concreta |
| Tentativa até exportação do recibo | dispatcher, controle local e escrita do recibo | não é tempo de todo o job, fila ou campanha |

O recibo principal não pode medir o tempo necessário para escrever a si mesmo.
Por isso, `timing_tail.json` registra separadamente a duração dessa escrita e
o SHA256 dos bytes de `attempt.json`. A escrita do próprio `timing_tail.json`
fica explicitamente fora do intervalo; não é declarada custo zero. A validação
reconcilia os intervalos e rejeita alteração dos bytes do recibo principal.

O adaptador desconta a exportação de `other` antes de somar as regiões da função
solver. Custos de preparação histórica desconhecidos permanecem ausentes.
M1 não passa a ser um baseline LP independente: mantém sua dependência da GNN.
Não se agrega uma preparação hipotética aos tempos medidos da tentativa.

## Falhas e limites

Uma parada do supervisor, perda de observação de memória ou retorno do solver
com status 17 (SoftMemLimit) pausa a continuação. Status 17 não recebe o rótulo
de tentativa concluída, mesmo quando o solver produziu um relatório válido.
O tempo supervisionado conhecido é preservado. Uma intenção sem relatório final
não prova a quantidade exata de chamadas realizadas: o contador fica desconhecido.
Os textos das exceções, caminhos privados e logs não são copiados ao recibo público.

O núcleo não concede autorização ou cria aprovações. A integração de 12/10,
descrita abaixo, liga o supervisor existente ao filho isolado; ainda não é
um operador de campanha admitido. Os testes usam substitutos sintéticos para
alocação/solver, não uma execução instalada no HPC.

## Validação offline e próximo passo

As regressões usam objetos sintéticos no lugar de Gurobi: verificam as 210
células planejadas, os 21 pares método/cap/seed permitidos para um pai,
parâmetros antes da única chamada simulada, MINIMIZE, falhas, interrupções,
intenção duplicada, custos ausentes e integridade do recibo/exportação.
Não houve solver real, inferência, treinamento, GPU, Slurm ou alteração de pacotes.

Validação focada: 47 testes PR86 em Python 3.13 e 17 regressões novas em
Python 3.10 passaram; Ruff 0.16.8 lint/format passou em 127 arquivos. A primeira
suíte completa encontrou restrições de escrita/rename e criação de repositórios
Git no TEMP do sandbox Windows (818 testes, uma falha, dez erros, sete skips).
Esses resultados não são aprovação da suíte. A repetição completa passou:
819 testes, sete skips previstos, Python 3.10, em 553,759 s. Usou TEMP/TMP em
um diretório gravável do workspace, sem relaxar os testes ou modificar fontes
históricas. O CI do head publicado é verificado separadamente na PR.

Comandos de regressão, na raiz do repositório, usando um diretório temporário
gravável quando necessário:

```text
python -B -m unittest discover -s tests/evidence
python -B -m unittest discover -s tests/evidence -p "test_pr86*.py"
python -m ruff check --config configs/quality/pr64-ruff.toml scripts/evidence tests/evidence
python -m ruff format --check --config configs/quality/pr64-ruff.toml scripts/evidence tests/evidence
```

## Integração de 12/10/2026: o que, como e por quê

`pr86_isolated_executor.py` conecta a instrumentação ao supervisor já qualificado
`paired_memory_runtime_v2`, em vez de duplicar sua implementação. Confere
commit e bytes do código, célula do plano, modelo, inícios, checkpoint,
preparação, ambiente e referências de revisão. As revisões são reutilizáveis
por campanha, com vínculos por pai; não se pede nova decisão humana por célula.
As mesmas funções validam as fronteiras de lançamento e de otimização.

O filho usa afinidade com um processador lógico por núcleo físico, cgroup
hierárquico, limites 48 GB / 56 GiB / 64 GiB e prazo de 3780 s. Os logs privados
fechados são selados por hash. O grupo respeita a ordem congelada dos três
métodos, compara assinatura matemática/parâmetros e interrompe no primeiro
retorno incompleto. Diretórios/intenção exclusivos impedem sobrescrever ou
reexecutar uma tentativa no mesmo destino. Não há retry automático.

Uma especialização pequena, `pr86_native_model.py`, garante liberação de
modelo/ambiente quando a construção falha e quando o descarte do modelo falha.
Ela herda a construção matemática histórica. Uma primeira correção no adaptador
antigo foi rejeitada pela regressão dos hashes E0 e retirada antes da entrega:
os arquivos históricos e recibos não foram recalculados para acomodar mudanças.

Limites explícitos: este adaptador não implementa ainda a posse global das
210 células, submissão Slurm, coleta de toda a campanha ou contabilização de
fila/job. A preparação prospectiva e sua revisão científica não são geradas
por ele. Sem os três vínculos aceitos (preparação, ambiente e
orçamento), a execução falha antes da alocação/solver. Um hash prova identidade,
não prova a verdade científica de uma aprovação.

## Engenharia proporcional ao MVP

Fluxo adotado na mesma PR: **implementação/T1 → regressão relacionada/T2 →
estabilização → T3/CI no HEAD final → Ready**. T1 e T2 não são novas aprovações
humanas nem workflows adicionais; são seleções locais da suíte existente.
O CI mantém os quatro braços e uma única descoberta da suíte de evidências.

Nesta base, os workflows de evidências e manuscrito descobrem diretórios
diferentes. Não foi demonstrada a duplicação de suítes do outro projeto; não
se transplantou essa conclusão. Preservamos o teste em `push` de `develop`,
que verifica o commit pós-merge. Acrescentamos cache pip, nomes das etapas e
log de testes como artefato por 14 dias, além do gatilho para código `src/cfl_gnn`
consumido pelos testes. Não removemos verificações de identidade em fronteiras
diferentes e não criamos um framework novo de CI.

Medição inicial do [run 38175411352](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/actions/runs/38175411352),
head `a0ce4f7`, quatro conclusões `success`, durações obtidas das etapas na API:

| Ambiente | Instalação de dependências (s) | Suíte (s) |
| --- | ---: | ---: |
| Ubuntu / Python 3.10 | 6 | 60 |
| Ubuntu / Python 3.12 | 6 | 60 |
| Windows / Python 3.10 | 10 | 168 |
| Windows / Python 3.12 | 16 | 159 |

Os timestamps têm resolução de segundos. Esta é uma observação, não uma linha
de base completa de ciclos por PR, falhas ou filas. Registrar próximos runs e
classificar falhas como código, fixture, ambiente, infraestrutura ou contrato
científico antes de modificar amplamente a matriz. Não prometemos redução
percentual. Nesta entrega, T1 teve 10 testes novos aprovados; T2 teve 57 testes
aprovados em 29,398 s após preservar a fonte histórica. A falha inicial de T2
era uma alteração de contrato de bytes, não um motivo para relaxar o teste.

T3 local de 12/10: **829 testes aprovados, sete skips previstos, 414,062 s**,
Python 3.10.9 com TEMP/TMP gravável no workspace. Ruff 0.16.8 lint/format passou
nos 131 arquivos do escopo. Estes tempos locais não são comparáveis diretamente
ao runner GitHub. O CI remoto precisa validar o novo HEAD separadamente.

## Próxima fronteira

Concluir o operador de campanha/coleta e a preparação medida sem combinar
predições antigas com raiz nova de proveniência distinta. A decisão explícita
do autor em 12/10 congela a formulação CFL como correta, exceto por MAXIMIZE;
MINIMIZE é obrigatório até a última Sprint. O executor registra esse contrato
fixo e não exige uma nova aprovação de formulação por campanha.

A busca delimitada no upstream MILPBench, commit
`9379501f1edee74ee323489e2846b9e172823ff9`, não encontrou um gerador CFL que
associe os índices achatados às entidades econômicas. O arquivo
`Baseline Library/GNN_MILP/Code/my1_generate_data_new.py` lê modelos LP já
existentes para gerar representações; não certifica sua geração econômica.
Isso não prova ausência global de documentação. O autor esclareceu que essa
busca não deve bloquear o desenvolvimento nem gerar exigência de gerador:
a formulação correta com correção exclusiva de sentido é premissa congelada.
A solicitação anterior de recertificação foi retirada. Permanecem as verificações
técnicas de identidade do modelo, variáveis, parâmetros, partições e recursos.

Somente após esses vínculos e testes será apresentado o pacote HPC e seu
orçamento exato. Os 210 solves e preparações adicionais continuam uma proposta.
Tabelas e figuras prospectivas dependem de execução especificamente autorizada;
nenhuma conclusão de superioridade, generalização ou speedup foi acrescentada.

## Preparação prospectiva integrada: raízes e custos (12/10)

**O quê:** `pr86_root_preparation.py` e `operate_pr86_roots.sh` preparam as dez
raízes dos mesmos pais já vinculados. É trabalho útil para a futura construção
dos grafos/inícios e para medir sua preparação, não um novo teste da formulação.
Não há treino, inferência, novos pais ou comparação M0/M1/M2 nesta etapa.

**Como:** um job CPU, dez filhos isolados sequenciais, no máximo uma chamada
`optimize` por pai. Preserva a política existente: primeiro callback MIPNODE
ótimo do nó zero, Presolve=0, NodeLimit=1, Threads=1, Seed=42, TimeLimit=600 s,
Gurobi 13.0.1 e MINIMIZE obrigatório. Não substitui essa raiz por `model.relax()`.
Um modelo sem essa observação para e preserva a evidência; não se inventa raiz.
O adaptador fecha modelo/ambiente mesmo após exceção. Coeficientes, restrições,
domínios e arquivos originais não são alterados.

**Por quê:** faltam custos prospectivos da preparação. Os artefatos históricos
continuam preservados, mas seus tempos ausentes não podem virar zero. Raiz nova
exige features/inferência coerentes na próxima etapa; não será misturada
tacitamente com predições geradas de outra raiz.

### Orçamento proposto, ainda não autorizado

| Item | Limite |
| --- | --- |
| Submissões | 1, sem requeue ou retry automático |
| Recursos | batch, 1 nó, 1 tarefa, 1 núcleo físico, 64 GiB, sem GPU/exclusividade |
| Preparações | 10 sequenciais, até 600 s de solver cada: 6.000 s no total |
| Filho / job | 1.140 s por filho; 12.000 s (3 h 20 min) para o job |
| Memória | SoftMemLimit 48 GB decimais; parada amostrada 56 GiB; cgroup até 64 GiB |

Agrupar as dez preparações substitui a proposta anterior de dez reservas de
1.200 s por uma reserva de 12.000 s, sem aumentar esse teto agregado. A mudança
de agrupamento não constitui aprovação: o autor deve autorizar este job antes
de `submit`. O plano mantém `resource_budget_approved=false`; a aprovação
separada referencia o hash exato do plano. Nenhuma frase longa será exigida.

`prepare` apenas verifica vínculos e grava o plano. `submit PLAN_SHA256` registra
a autorização declarada pelo operador e submete uma vez. Uma marca exclusiva
de campanha impede submissão repetida inclusive após resposta ambígua do Slurm.
`status` faz uma consulta e retorna; `collect` só coleta estado terminal, sem
aguardar em loop. A execução pausa ao primeiro retorno incompleto. Não apagar
marcas, diretórios ou evidências para tentar novamente.

### Duas entregas e seus limites

1. Dez artefatos de raiz privados, com hash do modelo, ordem das variáveis,
   vetor, parâmetros, assinatura matemática e sentido original/efetivo.
2. Recibo público com tempos de captura e exportação separados, supervisão de
   cada filho, memória amostrada, accounting Slurm, versões e hashes dos logs.

`capture_wall_seconds` inclui leitura/hash, construção, callback e descarte;
`root_export_wall_seconds` mede a escrita do artefato. O tempo supervisionado
inclui o processo e fechamento do log, mas exclui a amostra inicial do supervisor.
O intervalo do batch inclui orquestração; não inclui fila nem escrita final do
próprio resumo. São escopos aninhados: não somá-los entre si. A decomposição
end-to-end da comparação depende ainda de features, inferência e montagem dos
inícios medidos e revisados. Não há promoção científica automática.

Os vetores e textos dos logs permanecem no HPC. A coleta verifica os bytes
privados antes de exportar hashes. A revisão independente valida identidade,
ordem dos pais, sentidos, contagens, estado terminal e elegibilidade falsa.
Retorno parcial continua revisável, mas não é marcado como preparação completa.

### Validação e sequência

T1 usa solver/scheduler sintéticos: sucesso, ausência de raiz ótima, vetor não
finito, SoftMemLimit, exceções, descarte, aprovação divergente, plano alterado,
submissão ambígua, parada imediata, preservação e adulteração de artefatos.
T2 passou em 65 testes PR86 antes da última regressão adicional de plano;
os nove testes da preparação passaram. T3 e CI devem validar a árvore final.
Não se afirma validação instalada antes do retorno HPC.

A primeira execução T3 desta continuação usou equivocadamente TEMP/TMP dentro
do checkout: 838 testes, 111 erros e sete skips. Os contratos de exportação
exigem destino fora do código; a configuração de teste foi corrigida para um
diretório gravável externo ao checkout, sem relaxar esses contratos. O Bash
local também não inicia no sandbox Windows (IPC MSYS negado); a verificação
`bash -n` está incluída no CI, não é declarada aprovada localmente.

Depois da revisão desse retorno: preparar features/inferência com o checkpoint
congelado, revisar os custos e inícios, concluir o operador dos 70 grupos e
solicitar separadamente a execução da comparação. Esta etapa não autoriza
inferência, treinamento, os 210 solves ou merge. A PR86 permanece draft.
