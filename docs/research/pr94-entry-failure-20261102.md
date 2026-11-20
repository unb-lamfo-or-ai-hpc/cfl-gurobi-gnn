# PR94: falha de entrada antes das avaliações

## O que aconteceu

A CLI registrou os 48 jobs 3785–3832 e terminou com código zero. Esse retorno comprova a conclusão da submissão/liberação pelo operador, não o sucesso dos solves. No snapshot fornecido pelo autor, as quatro cabeças, 3785–3788, falharam com saída `2:0` e parede reportada de zero segundos; os 44 sucessores permaneceram PENDING. A consulta não veio com horário, portanto esse é o último estado recebido, não um monitoramento atual.

Os logs dos quatro jobs contêm exatamente `PR94_EVALUATION_INVALID_STAGE`. O diagnóstico de leitura encontrou o diretório de execução vazio e nenhuma intenção durável de otimização. A falha ocorreu no guarda do shell, antes de entrar no worker Python. Não há resultados científicos de avaliação recebidos: os 12 braços das quatro cabeças não entraram no worker, e os 132 braços restantes ainda não foram iniciados no snapshot. São falhas de infraestrutura e ausências por dependência; não são censuras temporais de otimização nem observações de desempenho B/R/G.

Os [registros do autor](../evidence/pr94/evaluation-attempt-10fd1af/author-submission.json), o [diagnóstico](../evidence/pr94/evaluation-attempt-10fd1af/author-diagnostic.json) e o [mapa dos jobs](../evidence/pr94/evaluation-attempt-10fd1af/job-map.json) preservam a proveniência. São transcrições normalizadas da saída fornecida no chat; o arquivo privado `submission.json` não foi transferido. O mapa usa a ordem do retorno do operador e o plano prospectivo congelado, sem se apresentar como uma nova consulta ao scheduler.

## Causa e correção proposta

O lançador preparado pelo Codex calculava a fonte a partir de `BASH_SOURCE`, tanto na CLI quanto no modo batch. O Slurm mantém uma cópia do script no spool; nesse modo, a localização do script não é a árvore de fonte instalada. A resolução relativa produz um estágio diferente do esperado, e o guarda encerra com código 2. O erro está no lançador, cuja implementação e testes anteriores não cobriram a execução da cópia de batch.

A correção usa `PR94_EVALUATION_STAGE`, já exportado e vinculado à submissão, quando o comando é `batch`. Na CLI, a resolução a partir do arquivo permanece. A fonte é então o subdiretório `source` do estágio validado. O corpo de verificação de host, recursos, execução e submissão não muda; não há alteração de parâmetros Gurobi, modelos, Starts, seeds ou protocolo.

Uma [referência textual](solver-seed-extension-v2/evaluation-entry-10fd1af.sh.txt) conserva o lançador efetivamente instalado no commit `10fd1af20ff40c43147331e7321adf10c151a6f5`: blob Git `235713ee091ebf67f8a0c550204905450d2f8779`, SHA256 `9eb631ee51d90c2e95a405c5725cde51b32aaba7706a9be2ae08dfa90c46ffe9`. A regressão executa essa referência e a versão corrigida como scripts copiados para um spool sintético. Um guarda de hostname artificial interrompe antes de qualquer Python, Slurm ou solver. O teste distingue a reprodução do erro original da resolução corrigida e verifica estágio ausente, caminho inválido e uso indevido do ambiente na CLI. Os testes de shell destinam-se ao Linux; a validação da referência e do corpo comum também roda no Windows.

## Por que os demais jobs continuam pendentes

As quatro cadeias usam `afterok`: cada sucessor exige sucesso do anterior da mesma cadeia. Uma cabeça FAILED impede o avanço dessa cadeia. A pendência não é evidência de solve lento, consumo excessivo ou dificuldade das instâncias. Não se deve remover dependências, reabrir claims ou reexecutar a CLI de submissão para tentar destravar a fila.

A implementação existente também preserva um claim global entre versões da fonte. Uma correção publicada no GitHub não altera o código instalado, o plano já selado, os scripts copiados pelo scheduler ou as dependências dos 48 jobs.

## Recuperação sujeita a decisão específica

Nenhum retry, cancelamento, alteração da instalação ou novo solve foi executado pelo Codex. O mandato exige diagnóstico e decisão humana específica após falha. A opção proposta, ainda não autorizada, é conservar as quatro falhas e todos os recibos, cancelar somente os 44 jobs que forem novamente confirmados como próprios e PENDING, e preparar uma tentativa substituta em estágio separado com a fonte corrigida e CI aprovada. A recuperação deverá preservar o claim original e exigir nova inspeção de zero chamadas e aceite do plano antes de qualquer submissão substituta.

As seis raízes, os seis forwards e os 16 pares de Starts seriam reutilizados pelos mesmos hashes. A matriz continuaria com 144 solves novos, B/R/G, seeds 42/43/44, uma thread e uma hora, mantendo M7 e as restrições de M4/M12. A evidência disponível sustenta que a primeira tentativa não entrou no worker de avaliação; essa disposição deve ser novamente verificada na admissão da recuperação. O total de IDs registrados passaria de 50 para 98, incluindo os dois jobs de preparação, os 48 desta tentativa e 48 substitutos. Pedidos de reserva, alocação e uso efetivo devem permanecer separados; parede reportada de zero segundos não demonstra custo físico exatamente nulo.

Uma eventual autorização de recuperação não é autorização para refazer treinamento, raízes ou inferência, trocar tolerâncias, acrescentar seeds/modelos ou aumentar o número de avaliações científicas. A PR89 permanece intacta. O incidente e as instruções de fila ficam na documentação operacional, não no texto do artigo ou dos apêndices.

Referências técnicas primárias: [SlurmdSpoolDir](https://slurm.schedmd.com/slurm.conf.html#OPT_SlurmdSpoolDir), [submissão e dependências em sbatch](https://slurm.schedmd.com/sbatch.html#OPT_dependency).
