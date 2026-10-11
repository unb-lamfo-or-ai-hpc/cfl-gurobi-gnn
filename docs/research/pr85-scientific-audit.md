# PR85 — auditoria científica e correção do sentido do objetivo

Checkpoint: 11/10/2026. Base: `develop` em
`5d7b00d4c650c3145bd376e8e270711eba984dbd`, depois dos merges das PR83/84.
Escopo autorizado: auditoria dos materiais existentes. Não autoriza merge,
novos experimentos, otimização, treinamento, submissões ou mudanças no ambiente.

## O que, como e por quê

Antes das comparações CPU e GPU, conferir quais dados, modelos e métricas
sustentam as afirmações do artigo. O auditor local usa exclusivamente a
biblioteca padrão do Python e reutiliza validadores dos recibos existentes.
Não importa Torch/Gurobi, não desserializa checkpoints, não consulta o Slurm
e não lê licenças. As tabelas e o manifesto estão em
[`docs/evidence/e0/pr85/`](../evidence/e0/pr85/).

```bash
python -B scripts/evidence/audit_pr85_scientific.py --output outputs/pr85-review
python -B -m unittest discover -s tests/evidence -p test_pr85_scientific_audit.py
```

O diretório de saída deve ser novo: nenhum recibo é sobrescrito. Os hashes
dos recibos usam seus bytes originais. Somente os arquivos de código/texto
explicitamente listados no manifesto normalizam CRLF para LF; isso evita
confundir finais de linha do Windows com alteração da partição canônica.

## Resultado verificável desta primeira entrega

- População: 90 pais; amostra admitida: 54 (30 fáceis, 24 médias).
- Treino: 18 fáceis + 16 médias; validação: 6 + 4; teste: 6 + 4.
- Os 54 pais têm identidade, papel e recibos numéricos reconciliados.
  Os hashes selecionados de modelo, grafo, raiz e rótulo não se repetem entre
  pais distintos. O reaproveitamento do mesmo pai entre coortes é esperado.
- Os 54 recibos numéricos registram origem `MAXIMIZE` e execução `MINIMIZE`,
  com verificações de restrições, limites, integralidade e objetivo aprovadas.
  Trata-se de revisão das verificações históricas, não de nova leitura das
  matrizes privadas nem de nova certificação de otimalidade.
- Duas cadeias de checkpoint foram vinculadas aos planos, artefatos, arquitetura
  e limiares congelados; 20 inferências foram reconciliadas. A checagem de bytes
  dos checkpoints foi realizada pelo job3505; aqui não os carregamos novamente.
- Os dez pais de teste têm exposição histórica. M13/M26 são pais de treino
  canônico excluídos da amostra de 54, não um teste independente adicional.
- Os planos selecionados têm 30/54 registros vinculados aos artefatos
  revisados. Nenhum derivado adicional é admitido. Isso não qualifica todos os
  planos exploratórios, amostras derivadas ou buscas anteriores do repositório.
- O vínculo histórico de seis fáceis também foi reconciliado com as 18
  resoluções do job3506: 12 inícios registrados como aceitos. A tabela
  `warmstart_trace.csv` encadeia modelo, grafo, raiz, predição, atribuições e
  recibos; confere o suporte e o número de valores positivos nos dois métodos
  guiados. Reutiliza verificações instaladas de identidade/ordem, sem recarregar
  vetores privados. Não qualifica inícios das quatro médias nem custos totais.
  O controle LP continua dependente do suporte/contagem positiva da GNN.

### Métricas: denominadores explícitos

| Modelo congelado | F1 macro: 6 fáceis | F1 macro: 4 médias | F1 macro: 10 pais | F1 micro: 10 pais |
| --- | --- | --- | --- | --- |
| Treinado só em fáceis | 0,590401 | 0,187750 | 0,429341 | 0,397712 |
| Treinado na coorte mista | 0,712265 | 0,688283 | 0,702672 | 0,699257 |

Macro é a média de F1 dos pais, dando o mesmo peso a cada instância. Micro
soma TP/FP/FN antes de calcular `2 TP / (2 TP + FP + FN)`; pais maiores pesam
mais. São descrições dos modelos existentes, não prova causal de que apenas
a composição do treino explica a diferença. A prevalência positiva é
0,256689% nas fáceis e 0,064477% nas médias: acurácia isolada é enganosa.
PR-AUC é mantida como métrica registrada, identificada como **não recalculada
independentemente**; probabilidades/rótulos completos não foram exportados.
Calibração e intervalos de incerteza não são inventados a partir de contagens.

## Por que MINIMIZE é obrigatório

O objeto científico adotado é CFL de **minimização de custos**, não maximização
de despesas. Em uma representação usual com fluxo, a função é

`min sum_j f_j y_j + sum_i sum_j c_ij q_ij + c0`,

com abertura `y_j` binária, fluxo `q_ij >= 0`, atendimento da demanda e
capacidade vinculada à abertura. Se a variável representa uma fração de demanda,
o termo de transporte deve incorporar a demanda; se representa atribuição
indivisível, seu domínio é binário. Essa formulação de referência é compatível
com o [exemplo oficial de localização da Gurobi](https://docs.gurobi.com/projects/examples/en/current/examples/python/facility.html),
que minimiza custos fixos e variáveis. Ela NÃO substitui a inspeção das
restrições/domínios da variante efetivamente fornecida pelo benchmark.

Com custos positivos, maximizar a mesma expressão incentiva maiores despesas;
por exemplo, pode favorecer abrir instalações desnecessárias. Portanto, trocar
apenas o sentido não é uma equivalência algébrica. A equivalência seria
`max(-cost) = -min(cost)`, com sinais e limites transformados; não é o que o
pipeline faz. O protocolo corrige a declaração incorreta para o objetivo
econômico pretendido, conservando coeficientes, constante, região viável e
bytes originais. Resultados devem ser descritos como obtidos nas **instâncias
MILPBench com sentido do objetivo corrigido para minimização de custos**.
Não comparar diretamente seus valores ou tempos com maximizações não corrigidas.

A decisão de tratar `MAXIMIZE` como erro do benchmark foi confirmada pelo
autor em 11/10. A observação de que os casos hard ficam triviais em segundos
sob maximização é registrada como relato do autor; esta PR não repetiu essa
experiência nem dispõe de um recibo público de cronometragem que a certifique.
O tempo menor, sozinho, não demonstra erro matemático: a justificativa é a
semântica de custos, reforçada por essa observação. A [origem MILPBench](https://github.com/thuiar/MILPBench)
identifica a família CFL, mas sua tabela pública não prova os coeficientes e
domínios dos nossos 54 arquivos. Suas dimensões publicadas também não devem
substituir as dimensões medidas nos nossos recibos.

O novo auditor rejeita qualquer recibo selecionado com sentido efetivo diferente
de `MINIMIZE`. Os executores existentes já aplicam essa correção; não há motivo
para alterar seus parâmetros, relabelar ou repetir resultados nesta entrega.

## Proveniência: o que não foi demonstrado de novo

O caminho de código de `gasse_reconnected.py` ajusta pré-normalização e peso
positivo pelo conjunto de treino; checkpoint e limiar usam validação.
`versioning.py` encaminha o modelo calibrado ao ajuste no dataset de treino.
Os planos/relatórios foram verificados pelo fluxo instalado antes das inferências.
Entretanto, os resumos públicos não incluem todos os valores de normalização,
peso positivo, relatórios completos e identificadores de amostras efetivamente
consumidas durante o ajuste histórico. Isso impede certificar retrospectivamente
cada operação apenas com os dados públicos atuais. Identidade de checkpoint
verificada não é demonstração completa de ausência de qualquer fuga histórica.

Os avisos do auditor metadata-only inicial (`declared_parent_roles_mismatch` e
`invalid_graph_manifest_hash`) permanecem visíveis na tabela de checkpoints.
Aquela visão genérica antecedeu o verificador específico de relatórios; os
recibos posteriores conferiram os artefatos selecionados e as partições.
Esta auditoria reconcilia os registros selecionados; não reescreve os avisos
originais nem considera todos os 17 planos exploratórios aprovados.

## Pendências delimitadas da mesma PR85

Continuação preparada: [coleta única de contexto privado](pr85-private-context-runbook.md),
com leitor LP restrito, extração sanitizada dos relatórios congelados e
verificação local do retorno. Ainda não executada no HPC. Os hashes do pedido
são gerados dos recibos já revisados; não há novo experimento nem carregamento
de modelos. F0/M0 são representativos, não substituem a amostra de 54.

1. Mapear nos arquivos originais a variante exata de CFL: termos de custo,
   constante, sinais, domínios mistos observados, unidades/escala, atendimento,
   capacidade e eventual vínculo adicional. Os recibos têm correspondência
   numérica grafo/modelo e viabilidade, mas não exportam essa descrição completa.
   Não declarar todos os fluxos binários, nem atribuição única, sem essa inspeção.
2. Completar a evidência documental do ajuste histórico de pré-normalização e
   peso positivo com os relatórios já existentes, se disponíveis; desconhecidos
   permanecem explícitos. Não treinar para substituir essa prova.
3. Produzir uma coleta privada estritamente de leitura, pequena e sanitizada,
   caso esses detalhes não estejam nos materiais já publicados. Qualquer CLI
   será apresentada ao operador antes da execução; nenhum job está autorizado.

Essas pendências não reabrem a escolha entre MIN/MAX e não invalidam
automaticamente as contagens ou métricas reconciliadas. Delimitam quais
afirmações ainda não são admissíveis. A campanha nova permanece bloqueada
até concluir os gates pertinentes e aprovar o orçamento exato. Os protocolos
PR86/87 foram aceitos preliminarmente, não suas execuções; 210 resoluções
continuam sendo previsão. A PR87 mantém 1 GPU serial versus 4 GPUs DDP como
entrega obrigatória. Esta primeira entrega permanece draft, sem merge.
