# Recuperação autorizada da entrada da PR94

O autor aprovou especificamente a recuperação técnica em 2/11/2026. Depois informou o cancelamento no dgx-dasci e transferiu o pacote de encerramento: SHA256 `e8755224290ad952846689701b1513a1d4f9d845aa53d8f9703d7830f48b7e89`. CRC, manifesto e hashes dos membros foram conferidos. Os 48 jobs estão terminais: quatro FAILED antes do worker e 44 CANCELLED, sem arquivos de execução ou intenções de otimização. O plano completo recebido reproduz o SHA256 `44b443a127af5ec4795e454b534aca8274c8e9a3d3d0ddb91fd67bb4cd4a9600` já aceito. Esse recebimento permite revisar também sua representação completa, além da projeção anterior.

O [encerramento público](../evidence/pr94/evaluation-attempt-10fd1af/closure-public.json) é um derivado identificado, que omite o UID de cancelamento e os relógios do accounting sem fuso explicitado. Os hashes originais e o pacote privado permanecem preservados. O [plano aceito](../evidence/pr94/evaluation-attempt-10fd1af/accepted-plan.json) e o [recibo de submissão original](../evidence/pr94/evaluation-attempt-10fd1af/original-submission.json) foram revistos quanto a caminhos privados/credenciais e conservam seus bytes e hashes. Não se publica o ZIP privado por conveniência.

## O que a recuperação muda

A entrada batch passa a usar o estágio exportado, em vez da localização da cópia do script no spool. Uma única tentativa substituta usa novo estágio e o claim exclusivo `pr94-full-v2-entry-recovery-1.claim.json`. O claim anterior não é removido, renomeado ou sobrescrito. Raízes, grafos, inferências, Starts, checkpoint e fonte instalada original são reutilizados por seus hashes ou preservados como evidência. A recuperação não executa preparação ou treinamento novamente.

O escopo continua sendo 144 solves novos: seis easy e dez medium, B/R/G e seeds 42/43/44, uma thread física e 3.600 s por solve. Os 48 blocos mantêm a ordem e as quatro cadeias. M7 e as restrições de M4/M12 permanecem. Se a substituição for submetida, haverá 98 IDs históricos incluindo preparação e tentativa falha; isso não significa 288 solves científicos. Parede de zero segundos no accounting não certifica custo físico exatamente nulo.

## Um roteiro, com revisão do plano antes de submeter

O pedido mais recente do autor é lançar toda a campanha antes de uma pausa longa. O roteiro único é operado pelo autor e aguarda, por prazo limitado, a aprovação da CI do commit exato. Uma falha, divergência ou expiração interrompe antes de criar o estágio ou alterar a fila. A espera consulta somente o estado da CI no GitHub, não faz polling da campanha nem repete experimentos.

Depois, cria o estágio isolado, repete a inspeção de zero chamadas das 16 cadeias e grava o novo plano. A revisão técnica desse plano é uma comparação integral com o plano completo já aceito. Todos os campos de dados, modelos, Starts, ambiente, parâmetros, ordem, limites e recursos devem conservar sua representação JSON canônica. Há uma lista fechada para as mudanças de fonte técnica revisadas, a proveniência explícita da recuperação e os metadados de consulta/ocupação do estágio. Qualquer outra diferença impede a submissão.

O relatório `recovery-plan-review.json` é gravado de forma exclusiva e ligado ao hash exato do novo plano antes do primeiro sbatch. Ele é identificado como revisão por equivalência ao plano previamente aprovado, não como uma assinatura humana fictícia ou qualificação científica. A submissão confere novamente esse relatório, os dados e o fechamento do pai: os quatro FAILED, os 44 CANCELLED, os arquivos/claims originais e a ausência de execução do worker.

Somente depois o operador submete todos os 48 blocos em hold, confere recursos e dependências e libera as quatro cadeias. Uma submissão completa existente resulta apenas em consulta; claim parcial ou resposta ambígua exige diagnóstico. Não existe caminho de retry automático ou terceira tentativa implícita. O roteiro não altera a PR89 e não autoriza merge ou publicação.
