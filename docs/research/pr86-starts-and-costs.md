# PR86 — continuação após PR85: vínculos e custos

## O que, como e por quê

PR85 foi merged em `develop` em `bb3f28f8078abde5ed4d95461f04fe675be2f37e`.
Esta entrega prepara os dez pais expostos, sem repetir inferência, raiz ou
treino. Reutiliza as predições privadas do job3505, seus hashes públicos, os
originais e as raízes já numericamente auditadas na PR80. O vinculador dos
seis fáceis permanece byte a byte inalterado; o novo contrato inclui seis
fáceis e quatro médias, sem acrescentar M13/M26.

`bind_pr86_existing_starts.py` verifica hash do modelo/raiz/predição,
declarações binárias do LP, cobertura exata dessas variáveis nas predições,
ordem/vetor da raiz, MINIMIZE e política do primeiro MIPNODE ótimo. Reutiliza
o algoritmo histórico de seleção GNN e LP pareado; não inventa novo início.
Os rótulos não entram na seleção. A revisão pública apenas reconcilia a
contagem positiva com `tp+fp` já publicado, sem ajustar decisões pelo teste.
Uma abstinência inesperada interrompe a vinculação, não exclui o pai.

O recibo público contém somente contagens, identidades e hashes. Arquivos de
atribuições e caminhos ficam em `private/`, no HPC. O diretório `public/`
contém apenas `binding.json` e `SHA256SUMS.txt`, permitindo um único `scp`.
Validação pública estrutural não reabre os bytes privados; a recomputação
determinística ocorre no vinculador instalado. Vínculo não prova viabilidade
completa, aceitação/reparação pelo solver nem semântica econômica de índices.

## Custos: correção de contabilização, não novos tempos

`pr86_cost_accounting.py` fornece relógio monotônico com regiões disjuntas,
sincronização GPU fornecida pelo chamador e estado incompleto em caso de falha.
O adaptador usa os tempos já produzidos pelo executor existente. Nesse esquema,
`other_wall_time_seconds` **inclui** exportação: subtrai-se a exportação de
`other` antes de somar regiões. Nenhum recibo original foi modificado.

`review_pr86_cost_coverage.py` regenera a
[tabela histórica de 18 linhas](../evidence/pr86/preparation/historical_cost_coverage.csv),
a partir do retorno íntegro do job3506. Os tempos medidos abrangem a função
solver, não todo o worker/job: overhead externo não reconciliado permanece
ausente, inclusive em M0. A preparação dos guiados também permanece ausente,
nunca zero. O custo end-to-end fica vazio nos três braços nesta tabela. Não
usar essa tabela como resultado prospectivo da PR86, nem inferir speedup
end-to-end para M1/M2 a partir dela.

M1 e M2 cobram raiz, features e inferência; cada um cobra sua montagem.
Amortização planejada: sete usos por pai/método. O livro-caixa físico da
campanha cobra raiz/features/inferência uma vez e as duas montagens; não soma
os dois cenários contrafactuais como se fossem consumo duplicado.

O relógio/adaptador está testado, **não** plenamente integrado/qualificado no
executor prospectivo. Não há interface de otimização ou submissão nesta entrega.

## Próximo passo CLI delimitado

Depois da publicação e dos quatro braços CI do head exato, executar o bloco
preparado para vinculação instalada: uma leitura limitada em `tfm_env`, sem
Gurobi, Torch, GPU, Slurm, inferência, treino ou novo job. Limites: 600 s no
leitor, timeout externo 660 s, espaço virtual 16 GiB, arquivos de predição
até 128 MiB cada, raiz expandida até 512 MiB, leitura hash até 4 GiB de dados
e 2 GiB de predições. A interpretação expandida tem limites próprios; esses
tetos não são medições de consumo. Diretório novo em `/raid`, sem sobrescrita.
O comando não recebe autorização para resolver a matriz ou medir novos custos.

O retorno instalado é a dependência imediata para conferir os dez vínculos.
Mesmo com sucesso, a campanha não estará autorizada: ainda é necessário
delimitar a correspondência matemática, integrar instrumentação prospectiva,
congelar ambiente/parâmetros/executor e aprovar o orçamento exato. Preparação
prospectiva de nova raiz exige features/predições vinculadas àquela raiz;
os inícios históricos não substituem silenciosamente essa etapa.

## Verificação local

```bash
python -B -m unittest discover -s tests/evidence -p 'test_pr86*.py'
python -B scripts/evidence/review_pr86_cost_coverage.py --output outputs/pr86-cost-review
```

Testes cobrem índices LP/GNN distintos mas contagens iguais, exclusão de
contínuas, identidade de raiz/limiar, schema público estrito, zero execução,
falhas de relógio, ausência de custos, dupla contagem e reprodução dos CSVs.
A suíte completa/CI verifica regressões; nenhum teste invoca solver ou GPU.
PR86 mantém draft. PR87 serial1GPU/DDP4GPU e PR88 manuscrito mantêm os
contratos aprovados e autorizações separadas.
