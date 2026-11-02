# PR94 — matriz prospectiva completa de 16 instâncias

A orientação do autor de 2 de novembro de 2026 pede acelerar a campanha de dez medium e seis easy, com B/R/G e seeds do solver 42/43/44. Este pacote define **144 avaliações novas**, substituindo a proposta de completar a matriz com 90 observações históricas mais 54 novas. Os 90 registros permanecem intactos como referência independente. Não são reportados como novas execuções.

## Perguntas e unidade de comparação

O objetivo é verificar como a utilidade dos Starts varia entre instâncias e perturbações do solver, sob um orçamento de uma hora e uma thread física por solve. As perguntas são: G melhora qualidade ou tempo para um mesmo alvo em relação a B? O contraste com R persiste com suporte e quantidade de positivos iguais? Qual custo de preparação é recuperado quando o mesmo par de Starts serve às três seeds?

Os seis easy são F0/F3/F6/F14/F27/F29; os dez medium são M0/M4/M7/M12/M5/M6/M9/M13/M20/M26. M7 permanece. M4/M12 conservam as limitações numéricas; cumprir o critério reportado não as elimina. A avaliação de otimização não redefine os folds de aprendizado. O corpus de 54, split 34/10/10, checkpoint CPU, limiar, arquitetura e normalização continuam congelados. Não há novo treinamento ou ablação de arquitetura. As seis medium adicionais não são declaradas amostra intocada.

## Planejamento reprodutível

`planned-cells.csv` contém 144 identidades novas, com hashes dos modelos, método histórico e alias B/R/G, seed, limite, bloco e posição. `plan.json` contém 48 blocos instância–seed. Cada bloco executa três modelos frescos, um por método, sequencialmente. O par de Starts é congelado por instância e não volta a ser selecionado para cada seed.

A ordem dos três métodos é rotacionada sem consultar resultados: para cada instância, cada método ocupa uma vez cada posição nas três seeds. Os blocos são distribuídos deterministicamente em quatro cadeias; cada sucessor exige `afterok` e recibo fechado do predecessor. É uma proposta de até quatro blocos simultâneos, não quatro threads por solve nem 144 solves simultâneos. Submeter todos os blocos não significa liberar execução antes dos gates. Erro, claim ambíguo, ausência ou falha não autorizam retry, cancelamento ou substituição automática.

`scripts/evidence/plan_pr94_full_matrix.py` reproduz o pacote offline usando os inventários v1. Não importa solver, Torch ou Slurm. Seus nove testes cobrem o pareamento completo, retenção de M7, ordem, ausência de ciclos, adulteração de identidades e preservação dos gates de execução. Flags falsos e IDs vazios descrevem o estado real; não devem ser promovidos por um teste ou por mera aprovação do planejamento.

## Recursos propostos

| Etapa | Jobs | Teto de parede/job | Núcleos físicos/job | RAM/job | GPU/job |
| --- | ---: | ---: | ---: | ---: | ---: |
| Seis raízes, filhos sequenciais | 1 | 2 h | 1 | 64 GiB | 0 |
| Grafos, inferência congelada e Starts | 1 | 1 h | 4 | 64 GiB | 1 V100 |
| Blocos instância–seed, três solves de até 1 h | 48 | 4 h | 1 | 64 GiB | 0 |

São 50 jobs no conjunto, até 150 chamadas de otimização (seis raízes e 144 avaliações), teto de 145 solver-h, 195 horas somadas de reserva de jobs, 198 core-h físicos e uma GPU-h. A memória somada é 12.480 GiB-h de reserva. Com quatro avaliações simultâneas, o pico proposto é quatro núcleos físicos e 256 GiB; a preparação precede essa fase. O empacotamento ideal das avaliações ocupa 48 horas, além de preparação, filas, revisão e falhas. Não é uma previsão de conclusão, utilização ou cobrança.

O orçamento v1 de 55 solver-h/75 job-h/78 core-h cobria outra proposta e não é reutilizado como autorização para 144 solves. A nova orientação do autor fica registrada, mas o plano privado, os recursos reais e o ato de submissão precisam corresponder a este pacote. A capacidade disponível, licenças concorrentes, cgroups, afinidade e armazenamento devem ser verificados antes da CLI de avaliações. O antigo allowance de 64 GiB e o piso de 80 GiB livres não demonstram que todos os vetores/logs de 144 solves caberão: falta dimensionar esse fechamento.

## Preflight e implementação ainda necessários

O estágio instalado c623fe858f62 e o plano b41953a8 são preservados para as seis raízes/guidance. O job de raízes **3783 terminou em 340 s**, COMPLETED/0:0. O ZIP de 4.523 bytes, SHA256 7f6e2be4…84024a, e o membro de metadados 8655247f…359d5 foram conferidos. O retorno registra seis capturas completas, com os modelos/parâmetros esperados, seis chamadas de otimização e zero forwards/treinos; 32 selos de artefatos fechados, resultado/summary e supervisão foram reconciliados. A consulta terminal é de 2/11/2026, 13:57:38 UTC. Trata-se de revisão de metadados; os vetores privados não vieram para reprodução independente. Ver [laudo de recebimento](../pr94-root-review-20261102.json). A CLI separada aceitou somente esse hash. O autor reportou **guidance job 3784 RUNNING**, elapsed 25 s, oito AllocCPUS e CLI exit 0, sem timestamp da consulta. O retorno de grafos, predições e Starts ainda não foi recebido.

As seis identidades originais já têm preflight de leitura. Para a campanha completa, ainda conferir no armazenamento atual os 16 modelos e os dez pares históricos de Starts; completar e revisar os seis pares novos. Não repetir raízes/inferências antigas apenas para preencher o inventário. Conferir versão, ambiente, checkpoint, assinaturas matemáticas e a igualdade de suporte/positivos em R/G. Não afrouxar a captura de raiz, tolerâncias ou restrições para tornar uma instância executável.

O executor PR86 existente valida uma matriz histórica e rejeita as seis medium adicionais. Logo, não se deve invocá-lo com índices trocados nem monkey-patch de identificadores. Falta concluir o adaptador de avaliação isolado, os contratos dos 144 filhos, claims por célula/bloco, submissão held e validação de recursos, quatro cadeias, coleta terminal e testes de falha. A revisão da preparação e a CI desse adaptador precedem a CLI de lançamento. O compilador deste pacote **não é esse dispatcher** e não declara jobs PENDING ou RUNNING.

## Análise prevista

Relatar resultados por instância e separar easy/medium. Caracterizar os medium por descritores estruturais prévios (tamanho, densidade, proporções de domínios e escala numérica); não selecionar ou excluir casos depois de observar qual método venceu. Dificuldade empírica de B pode ser apresentada como descrição, sem chamá-la de estrato independente dos resultados.

Para cada alvo de gap, distinguir atingimento observado, censura, falha e ausência. Reportar primal, bound e gap no orçamento, junto ao tempo e custo. Não tratar timeout como solução em 3.600 s, extrapolar um run encerrado ou combinar o orçamento de uma hora com o de 12 horas da PR89. As seeds perturbam o solver com a rede fixa; não medem incerteza de treinamento. Há três observações pareadas por instância, e não 48 instâncias independentes. Um modelo estatístico ou reamostragem deve respeitar esse agrupamento; com seis/dez instâncias, a inferência permanece limitada.

Razões de tempo só se aplicam a alvos comparáveis e métricas elegíveis. A média geométrica de razões positivas pareadas pode resumir efeitos relativos, mas não substitui a apresentação por instância e não incorpora censuras como tempos observados. A concorrência entre jobs muda o regime de medição: registrar CPU/afinidade, memória, tempos de início/fim e sobreposição; não atribuir toda diferença de tempo à GNN ou comparar diretamente com a campanha serial anterior. Retornos numéricos de M4/M12 continuam descritivos até qualificação própria.

S1–S4 avançam agora com protocolo, implementação, curadoria e a síntese completa da PR89. Depois da submissão real, seus IDs/estado e a versão do protocolo serão registrados na PR93; o manuscrito poderá descrever o desenho prospectivo, sem resultados antecipados nem instruções operacionais para seus leitores. S5/S6 receberão a análise final e o fechamento editorial após os resultados da PR94.
