# PR86 — matriz controlada e orçamento proposto

Checkpoint 11/10/2026: **primeira entrega offline; draft; sem execução**.
Atualização posterior ao merge PR85: ver [vínculos e custos](pr86-starts-and-costs.md).
O texto e manifesto iniciais abaixo registram a proposta original, não o
estado corrente de cada gate. O merge documental foi confirmado; os gates
científicos/de execução continuam pendentes.
Branch independente, a partir de `develop` após PR84. Depende cientificamente
do encerramento PR85 e da resolução dos gates afetados, não apenas de seu merge.

## O que, como e por quê

Gerar um manifesto verificável antes de solicitar recursos, reaproveitando
split, hashes e modelos existentes. Não treina, infere, importa Gurobi/Torch,
consulta Slurm ou transfere dados. O programa valida recibos públicos e escreve
uma pasta nova; não contém interface de submissão/aprovação.

```bash
python -B scripts/evidence/plan_pr86_comparison.py --output outputs/pr86-proposal-review
python -B -m unittest discover -s tests/evidence -p test_pr86_comparison_plan.py
```

Reprodução local, **não uma solicitação de CLI no HPC**. Saída versionada:
[`docs/evidence/pr86/proposal/`](../evidence/pr86/proposal/), com `plan.json`,
`planned_cells.csv` e `manifest.json`. Não há resultados fictícios: cada célula
diz `planned_not_executed`. Todos os gates de execução estão falsos.

## Comparação proposta

Dez pais historicamente expostos: F0,F3,F6,F14,F27,F29 e M0,M4,M7,M12.
Não são teste independente; não incluir M13/M26 nem trocar a partição.

| Método | Início externo | Preparação necessária |
| --- | --- | --- |
| M0 | Nenhum | Leitura do modelo |
| M1 | Parcial, ranking da raiz LP | Raiz, features/inferência GNN para orçamento pareado e montagem LP |
| M2 | Parcial, GNN congelada | Raiz, features/inferência GNN e montagem neural |

M1 iguala cardinalidade e contagem positiva de M2, **não** necessariamente
os mesmos índices. Política histórica:
`min(n_binary,20000,max(1,floor(0.10*n_binary)))`, incluindo abstinência.
Somente binárias selecionadas; demais variáveis indefinidas, sem fixar limites.
Nenhum rótulo de teste seleciona início, suporte, checkpoint ou limiar.

Checkpoint proposto: misto congelado
`a1868134028694e0f807b5627100a77fcd1dc41e6c884b176290caee253a4028`,
por escopo da coorte mista/seleção histórica em validação, não por velocidade
de solver nem escolha pelo F1 do teste. Manter arquitetura, prenorm e limiar.
O modelo fácil permanece na avaliação preditiva histórica; nenhuma busca nova.

- Seed 42: 10 pais × 3 métodos × threads `{1,2,4,8,16}` = 150 resoluções.
- Seeds 43/44: 10 pais × 3 métodos, **somente um thread** = 60 adicionais.
- 210 resoluções, em 70 grupos de três. Cada grupo fixa pai, seed, cap e recursos.
  Nos três seeds de um thread, cada método ocupa cada posição uma vez por pai.
  Nos demais caps a ordem é determinística, não evidência de repetibilidade.
- `MINIMIZE`, `TimeLimit=3600`, `MIPGap=1e-4` (0,01%), `SoftMemLimit=48`
  GB decimais. Registrar demais parâmetros efetivos e versão antes de executar.
  Não misturar linhas históricas com protocolos distintos.

Até uma preparação prospectiva de raiz por pai, seed 42, um thread,
`Presolve=0`, `NodeLimit=1`, até 600 s: primeiro MIPNODE ótimo da raiz, não
`model.relax()`. Compartilhar a mesma preparação entre métodos/seeds/caps.
Até dez inferências congeladas num único job de uma GPU, sem ajuste.
Proveniência histórica não substitui novos custos ainda não medidos.

## Envelope proposto — não aprovado

Um nó DGX, jobs sequenciais, sem exclusividade, requeue, retry ou extensão.
Cada grupo pede tantos **cores físicos quanto seu cap**, não 16 em todos.
Afinidade a um processador lógico por core; `AllocCPUS` não é essa contagem.

| Componente | Máximo de jobs | Recursos por job | Parede por job |
| --- | ---: | --- | ---: |
| Grupos principais | 70 | 1/2/4/8/16 cores; 0 GPU; 64 GiB | 4 h |
| Raiz | 10 | 1 core; 0 GPU; 64 GiB | 20 min |
| Inferência | 1 | 4 cores; 1 V100; 64 GiB | 40 min |

Até **81 jobs** e **220 chamadas optimize** (210 principais + 10 de raiz),
nenhum treino. Deadline principal de 3780 s por filho: três filhos <=11 340 s
num grupo de 14 400 s. Isso não prova que toda preparação/exportação cabe;
se faltar tempo, parar e preservar, sem extensão automática.

Teto solver principal **210 h**; raiz **1 h 40 min**. Capacidade principal
ponderada por cores **990 core-h**. Reserva total: **284 job-h sequenciais**,
**1326 core-h físicos**, **40 GPU-min**, incluindo parede da preparação e
inferência. Filas excluídas. São limites teóricos, **não consumo medido,
previsão de duração ou prova de viabilidade**. O programa testa a aritmética.
Uma redução deve ser prospectiva, não escolhida após resultados da GNN.

Manter `tfm_env`, sem upgrade; solver soft 48 GB decimais; stop amostrado
job-scoped 56 GiB; kernel RAM <=64 GiB. Perda de observação/cgroup, memória,
falha de identidade ou filho incompleto pausa o restante sem desativar guardas.
Registrar RSS, RAM job-scoped e memória solver separadamente. A adequação
de memória/tempo da preparação e inferência é risco a aceitar antes de executar;
esta proposta não certifica treinamento DDP.

## Custos, estatística e figuras

Instrumentar raiz, leitura/construção de features, inferência GPU sincronizada,
montagem de cada início, leitura do modelo, solver e exportação separadamente.
Cache é explícito; custos históricos desconhecidos não viram zero. M1 depende
da inferência para as contagens pareadas, portanto ela deve ser cobrada.

Relatar custo frio por método e amortizado sobre sete usos por pai/método
(cinco caps + dois repeats). O livro-caixa da campanha cobra a preparação
compartilhada uma vez; o cenário contrafactual de um método isolado cobra tudo
de que ele necessita. Não somar cenários contrafactuais como consumo duplicado.

Saídas exigidas: todas as 210 células com estado/hashes; efeitos pareados por
pai; CPU 1/2/4/8/16; qualidade no horizonte; memória por método; custo frio
versus amortizado; índice de afirmações/evidências. Fontes CSV e figuras SVG
regeneráveis, sem curvas de resultados inventadas a partir do planejamento.

Registrar primal/bound/gap, primeiro incumbente, término, aceitação/reparação
do início e compartilhamento do nó. Timeout é censura para tempo ao alvo,
não tempo exato de conclusão. Seeds são repetições aninhadas: **n=10 pais**,
não 210 observações independentes. Relatar fáceis/médias e incerteza agrupada
por pai; quatro médias limitam precisão. Não interpolar trajetórias ausentes
nem presumir superioridade ou generalização independente.

## Próximas etapas desta mesma PR

1. Incorporar a revisão PR85; documentar correspondência semântica relevante
   com gerador/código/artefatos existentes. Merge de auditoria não aprova o gate.
2. Estender o vínculo instalado dos seis inícios fáceis às quatro médias,
   preservando hashes, índices e política, sem treino ou novos rótulos.
3. Instrumentar custos e adaptar executor isolado/fluxo não bloqueante existente;
   testar contratos/falhas localmente sem solver. Congelar commit, parâmetros
   efetivos, orçamento e escopo cgroup. Não ampliar o pipeline por refatoração.
4. Pedir autorização do pacote final de orçamento **antes de qualquer job**.
   Submissão futura retorna imediatamente; consulta/coleta sem loops bloqueantes
   e sem frases longas de confirmação CLI. Nenhum comando HPC é emitido agora.
5. Após execução autorizada, revisar linhas e gerar figuras/tabelas; colocar
   pronta para review e só então pedir merge.

PR87 permanece obrigatória: 1 GPU serial versus 4 GPUs DDP, global batch
quatro, 100 épocas, 3400 updates, mesma inicialização por seed, orçamento
separado. PR88 estrutura o artigo em paralelo, sem resultados antecipados.
Sem expansão de dataset, arquitetura nova ou busca de hiperparâmetros.
