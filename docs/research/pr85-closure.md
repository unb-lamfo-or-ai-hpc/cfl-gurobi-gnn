# PR85 — encerramento da auditoria, 11/10/2026

## O que foi concluído e por quê

A auditoria documental está concluída **com limitações explícitas**, conforme
o critério aprovado: um ponto não verificável pode ser encerrado como não
qualificado, sem fabricar prova nem iniciar outro experimento. Isso torna a
entrega revisável; não libera a campanha PR86/87 nem seu merge.
O [primeiro auditor](pr85-scientific-audit.md) permanece inalterado como registro
daquela etapa; esta revisão separada incorpora o retorno instalado e atualiza
sua interpretação, sem reescrever recibos.

Recibo original: [`pr85-context-return.json`](../evidence/e0/pr85-context-return.json),
SHA256 `15136b4d0d22bc97b82ef5f778bca6dbe0686fb32209980dd62b2df0c907a282`.
Zero otimizações, treinos ou submissões adicionais. Não se recarregaram
grafos/checkpoints nem se modificou `tfm_env`. Tabelas e manifesto novos:
[`pr85-closure/`](../evidence/e0/pr85-closure/).

## Como conferir

Executar localmente, em diretório de saída novo:

```bash
python -B scripts/evidence/close_pr85_scientific_audit.py --output outputs/pr85-closure-review
python -B -m unittest discover -s tests/evidence -p test_pr85_scientific_closure.py
```

O revisor confere o hash dos **bytes originais**, a vinculação ao pedido
congelado, as duas cadeias de relatórios e a correspondência das dimensões LP
com o recibo numérico histórico. Reexecuta os verificadores públicos dos 54
pais e das 20 inferências. A saída é determinística e recusa sobrescrita;
o manifesto distingue hashes crus de recibos e normalização LF do código.
Testes negativos rejeitam alteração de época, limiar, contagem, domínio,
sentido do objetivo e promoção indevida da abrangência.

## O que o retorno acrescenta

| Evidência | F0 | M0 |
| --- | ---: | ---: |
| Variáveis | 160 400 | 1 281 600 |
| Binárias explícitas | 148 000 | 1 152 000 |
| Contínuas pelo domínio padrão LP | 12 400 | 129 600 |
| Inteiras gerais | 0 | 0 |
| Restrições | 800 | 2 400 |
| Linhas `>=` / `<=` | 400 / 400 | 800 / 1 600 |
| Constante do objetivo | 0 | 0 |

As dimensões coincidem com as verificações numéricas já publicadas. Nos dois
LPs representativos, os termos lexicais observados do objetivo são positivos,
o cabeçalho é `MAXIMIZE` e não há igualdades. Portanto, **não** descrever essa
representação como modelo de atribuição única com todas as variáveis binárias.
F0/M0 não são uma inspeção semântica de todos os 54 arquivos. O resumo não
identifica unidades econômicas, a função de cada índice achatado `x` nem
todos os valores dos limites; não prova que a solução toda-um é viável.

O enunciado matemático seguro nesta fase é a forma genérica do MILP observado:
`min c^T x + c0`, sujeito às linhas e limites armazenados, com subconjunto
binário e variáveis contínuas. A associação detalhada dos índices a abertura,
atendimento e capacidade permanece não qualificada. A formulação clássica
em [PR85](pr85-scientific-audit.md) é referência conceitual, não transcrição
certificada dessa variante.

**MINIMIZE continua obrigatório**, por decisão científica dos autores de
corrigir o sentido de um problema de custos; os coeficientes positivos
representativos reforçam essa interpretação, mas não são, sozinhos, prova
da semântica econômica de todas as variáveis. Preservar coeficientes, região
viável e arquivos originais. Não chamar a correção de equivalência à
maximização original. O relato de trivialidade dos hard sob MAXIMIZE continua
relato do autor, sem nova medição ou recibo de tempo independente nesta PR.

| Relatório congelado | Só fáceis | Coorte mista |
| --- | ---: | ---: |
| Pais de treino / grafos de pré-normalização | 18 / 18 | 34 / 34 |
| Épocas concluídas | 100 | 100 |
| Peso da classe positiva | 388,283600 | 1 132,975830 |
| Limiar de decisão | 0,9975354671 | 0,9991843104 |
| Grafos de teste carregados no ajuste, conforme relatório | 0 | 0 |

Os hashes de plano, relatório, checkpoint e limiar foram reconciliados.
Os relatórios atestam pré-normalização com grafos de treino; o código limita
o ajuste do peso positivo ao treino. **Atestação documental não é reexecução
independente do ajuste histórico**, nem prova de toda a história exploratória.
Os avisos dos resumos iniciais permanecem preservados. Não se alterou modelo,
limiar ou partição com base no teste.

## Decisão de elegibilidade e próximo passo

- Admitidos: identidade/partição dos 54 pais, contagens das 20 inferências,
  métricas micro e macro recalculadas, atestações delimitadas dos dois
  relatórios e dimensões dos dois LPs representativos.
- Mantidos: exposição histórica dos dez pais de teste; seleção da amostra
  pela qualidade dos rótulos; ausência de reescore independente de PR-AUC;
  custos históricos de preparação desconhecidos. Não alegar generalização
  independente nem superioridade consistente da GNN.
- Os seis inícios fáceis do E0 mantêm a rastreabilidade existente; os quatro
  médios não ganham automaticamente qualificação de início. M1 iguala
  **cardinalidade e contagem positiva**, não necessariamente os mesmos índices
  selecionados por M2. Seu ranking é LP; seu orçamento depende da GNN.
- PR86 pode preparar código, manifesto das 210 células e orçamento sem solver.
  A execução permanece bloqueada até documentar a correspondência semântica
  relevante, vincular os inícios médios, congelar custos/recursos e obter
  autorização específica. Não há retry, novo piloto ou coleta adicional
  obrigatória criada por este encerramento; reutilizar primeiro código,
  gerador e arquivos existentes.
- PR87 mantém comparação obrigatória 1 GPU serial versus 4 GPUs DDP, com
  trabalho/global batch equivalentes e orçamento separado. PR88 pode iniciar
  estrutura e índice de afirmações/evidências, sem resultados antecipados.

Os campos originais `scientific_reporting_eligible=false` são preservados.
A revisão nomeia quais afirmações são sustentadas; não promove em bloco
recibos ou experimentos. Aprovação/merge da PR85 não é aprovação de execução.
