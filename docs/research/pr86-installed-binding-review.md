# PR86 — dez vínculos instalados e revisão dos custos existentes

## Resultado e alcance

O recibo instalado no dgx-dasci, produzido pelo commit
`46802675ff996bc2da26e0e0638543e1aa270f6e`, tem SHA256
`45eab23962f8427b28de1a86557cb03f251f4ecf49d62f23001f54a3215198b2`.
A revisão local verificou seus bytes, esquema, pais, predições, modelos e
raízes contra as evidências públicas anteriores. Os dez vínculos passaram.
O recibo original foi preservado em
[binding.json](../evidence/pr86/bindings-45eab23962f8/binding.json).
Esta revisão não reabre arquivos privados nem altera a elegibilidade original.

| Pais | Variáveis binárias por pai | Valores fornecidos por método guiado | Cobertura |
| --- | ---: | ---: | ---: |
| F0, F3, F6, F14, F27, F29 | 145.200–148.800 | 14.520–14.880 | 10% |
| M0, M4, M7, M12 | 1.152.000–1.188.800 | 20.000 | 1,68–1,74% |

A regra histórica é `min(n, 20000, max(1, floor(0.10*n)))`.
Portanto, não se deve descrever as médias como recebendo início em 10% das
variáveis: nelas prevalece o teto de 20.000. M1 e M2 compartilham a quantidade
de valores fornecidos e de positivos por pai; seus índices podem diferir.
Os dez pais têm exposição histórica. M0/M1/M2, quando métodos, ficam em uma
coluna distinta dos identificadores dos pais médios.

A [tabela por pai](../evidence/pr86/bindings-45eab23962f8/start_coverage.csv)
registra contagens, cobertura e hashes. Vínculo significa que as atribuições
foram reconstruídas com identidade de variáveis verificada. Não significa
solução completa viável, início aceito pelo solver ou desempenho observado.
Nenhuma resolução, inferência, submissão ou treinamento foi acrescentado.

## Custos recuperáveis do job3506

A revisão anterior mantinha o overhead externo à função solver desconhecido.
O recibo original também contém `supervisor_wall_seconds`. A nova revisão
reconcilia esse intervalo com os tempos internos para as 18 tentativas:

`tempo supervisionado = tempo da função solver + restante do intervalo`.

O restante inclui criação/finalização do processo, importações, verificações
externas, produção do relatório e o encerramento do log, sem decomposição
individual desses itens. A região `other` interna já inclui a exportação;
subtrai-se a exportação antes de somar as regiões disjuntas.

O intervalo supervisionado começa após a primeira amostra de memória e termina
após o fechamento do log. Ele não cobre fila Slurm, preparação em outro processo
ou toda a orquestração do job. Por isso, a coluna `cold_attempt_seconds` é
explicitamente um custo da tentativa, não um custo end-to-end do job. Em M0,
não há preparação de orientação. Em M1/M2, os tempos históricos de raiz,
features, inferência e montagem continuam ausentes: seus custos frios e
amortizados permanecem vazios.

As [18 linhas reconciliadas](../evidence/pr86/bindings-45eab23962f8/historical_attempt_costs.csv)
são uma nova análise de dados existentes; não são resultados prospectivos da
PR86. A tabela anterior e todos os recibos originais permanecem intactos.
O módulo `pr86_supervised_costs.py` reutiliza a interface do supervisor existente,
retém o tempo consumido por falhas e só calcula custos completos de tentativas
quando supervisor e relatório são consistentes. Ainda precisa ser conectado
ao executor prospectivo completo e qualificado antes da campanha.

## Sequência restante da PR86

1. Incorporar esta revisão e seus testes ao head da PR e verificar a CI.
2. Concluir o executor prospectivo com configuração explícita de threads/seeds,
   preparação rastreada, medição de custos e os limites de memória já aprovados
   como proposta. Preservar os arquivos de código vinculados aos recibos antigos.
3. Delimitar a correspondência matemática e vincular ambiente, parâmetros,
   preparação e início à mesma instância. `MINIMIZE` continua obrigatório;
   identidade de variáveis, isoladamente, não encerra a interpretação econômica.
4. Apresentar o pacote executável e seu orçamento exato para aprovação. As 210
   resoluções principais continuam preliminares; a coleta dos vínculos não
   aprova nenhuma delas nem as preparações adicionais.
5. Após autorização e execução, revisar resultados e regenerar tabelas/figuras
   comparativas. Solicitar merge somente com a PR concluída e pronta para revisão.

Não há nova CLI no HPC necessária para esta revisão. Os próximos itens de
implementação são locais; autorização de experimentos será solicitada com um
pacote concreto e revisável.

## Reprodução offline

```bash
python -B scripts/evidence/review_pr86_installed_bindings.py \
  --receipt docs/evidence/pr86/bindings-45eab23962f8/binding.json \
  --output outputs/pr86-installed-review
python -B -m unittest discover -s tests/evidence -p 'test_pr86*.py'
```

O gerador exige diretório de saída novo. O manifesto vincula todos os produtos
por SHA256; os testes verificam reprodução dos bytes, contagens, custos
desconhecidos, falhas e intervalos incompatíveis, sem importar Gurobi ou Torch.

Validação local desta entrega: 802 testes da suíte de evidências concluídos
com sucesso em Python 3.10, com sete skips; 30 testes focados também passaram
em Python 3.13. Ruff 0.16.8 aprovou lint e formatação dos 124 arquivos Python.
Esses resultados não substituem a CI do novo commit após sua publicação.
