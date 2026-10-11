# PR85 — uma coleta documental, sem novo experimento

> Coleta já concluída; não repetir. O [encerramento](pr85-closure.md) e o
> recibo versionado registram o resultado e seus limites. Os comandos abaixo
> preservam o procedimento histórico, não são uma nova solicitação de CLI.

## O que, como e por quê

Esta continuação reúne as duas pendências da auditoria numa única intervenção
do operador: estrutura dos LPs originais F0/M0 e campos dos dois relatórios de
treinamento congelados. O coletor usa somente Python padrão. Não importa
Gurobi/Torch, não lê licença/checkpoints/grafos/rótulos, não chama Slurm,
não treina e não otimiza. Não muda `tfm_env` nem arquivos de entrada.

O pedido é gerado de recibos públicos já revisados e fixa os hashes dos dois
LPs, dois planos, dois relatórios e checkpoints associados. Os checkpoints
não são relidos: verifica-se a identidade declarada nos relatórios cujos bytes
são conferidos. Cópias idênticas de documentos são aceitas por hash; não há
seleção de modelo por resultado novo.

Limites: 180 segundos cooperativos, 20 mil entradas nas quatro pastas de dados
já utilizadas pelo auditor, 512 MiB de leitura para hashes/documentos, 8 MiB
por JSON, 256 MiB descompactados por LP e 1 MiB por linha. A leitura
descompactada é adicional ao orçamento de bytes para hashes/documentos.
São apenas dois LPs, processados sequencialmente. Não são 54 novas auditorias
numéricas. O limite de tempo é conferido entre leituras, não uma garantia de
interrupção imediata de uma operação de I/O bloqueada. Não há job ou reserva.

## Saída e limites de interpretação

O único arquivo de retorno é `context.json`. Ele contém hashes, campos
numéricos permitidos dos relatórios e resumos estruturais dos LPs: sentido,
constante/custos por família, domínios explícitos, sentidos das restrições,
formatos de limites e até 12 resumos agregados de linhas representativas.
Não inclui nomes/índices de variáveis, linhas da matriz, caminhos privados,
texto livre de relatórios, logs ou credenciais. Prefixos alfabéticos de famílias
são mantidos para interpretação, não identificadores completos.

O leitor LP é deliberadamente restrito a sintaxe linear conhecida. Sintaxe
não suportada produz estado não qualificado, nunca um modelo interpretado
silenciosamente como outro. Não é um parser alternativo de Gurobi. Os números
são contagens lexicais: termos duplicados ou coeficientes nulos não equivalem
automaticamente aos não zeros de uma matriz consolidada.

Unidades econômicas e significado físico não são inferidos de nomes. Uma
inspeção representativa não prova a semântica de todos os 54 LPs. A correção
obrigatória para `MINIMIZE` permanece, sem negarmos os coeficientes e sem
alterar os arquivos originais. A revisão posterior deve distinguir o que a
estrutura demonstra do que ainda exige documentação do benchmark.

O relatório histórico pode atestar ajuste de pré-normalização no treino;
isso não reproduz todas as operações históricas. O peso positivo é exportado
e vinculado ao relatório; o caminho de código treino-only já foi revisado,
mas não se inventa um registro histórico de cada amostra consumida.

## Execução e retorno

O pacote de transporte contém somente o coletor, duas dependências padrão e
`request.json`. O operador confere o SHA256 do pacote antes de extrair em uma
pasta nova sob `/raid/vrcelestino/data/cfl-mvp2-evidence/pr85/`.

```bash
conda activate tfm_env
python -B collect_pr85_private_context.py collect \
  --request request.json \
  --data-root /raid/vrcelestino/data/cfl-gurobi-gnn/data \
  --output context.json
sha256sum context.json
```

Executar somente depois de transferir/conferir o pacote e entrar na pasta
correta. Se falhar, preservar a pasta e enviar o código sanitizado; não repetir
automaticamente. Sucesso operacional não torna a PR ready nem autoriza merge.

Baixar apenas `context.json` em **uma chamada SCP** (uma autenticação). No
computador local, o comando `review` confere SHA256, vínculo ao pedido,
identidades e escopo sem operações novas. O JSON preserva falhas parciais.
Compartilhar o hash e o diretório baixado, não os documentos privados originais.

```bash
python -B scripts/evidence/collect_pr85_private_context.py review \
  --request docs/evidence/e0/pr85-context-request.json \
  --receipt CAMINHO_LOCAL/context.json --expected-sha256 SHA256_DO_RETORNO
```

Nenhum treinamento, resolução, retry, orçamento PR86/87 ou merge é autorizado
por este runbook. A PR85 permanece draft até a revisão desta evidência e das
limitações correspondentes.
