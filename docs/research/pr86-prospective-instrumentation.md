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

O novo módulo deliberadamente não fornece um launcher padrão, comando de
submissão, CLI de execução ou aprovação fictícia. Os testes injetam um dispatcher
sintético. A integração com o supervisor real, afinidade física e a política
48 GB / 56 GiB / 64 GiB continua uma tarefa explícita, não qualificada por esses
testes. A função solver é um núcleo interno, não um operador HPC autorizado.

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

Próxima integração: ligar este núcleo a um operador que confira o plano e a
autorização exatos, proveniência da preparação prospectiva, início/hash por
pai, ambiente, afinidade e cgroup; selar logs e reconciliar resultados dos três
métodos dentro de cada grupo. Não combinar predições antigas com uma nova raiz
sem provar a mesma proveniência. O mapeamento econômico da formulação ainda
requer o tratamento delimitado na PR85.

Somente após esses vínculos e testes será apresentado o pacote HPC e seu
orçamento exato. Os 210 solves e preparações adicionais continuam uma proposta.
Tabelas e figuras prospectivas dependem de execução especificamente autorizada;
nenhuma conclusão de superioridade, generalização ou speedup foi acrescentada.
