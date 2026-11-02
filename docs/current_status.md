# Estado atual do CFL-GNN

Atualizado em 2 de novembro de 2026. Este resumo substitui os estados operacionais antigos; a [versão anterior](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/9453b82314a4ca5ffaf1850d26e5eac5dbc3d98f/docs/current_status.md) preserva a cronologia. Contrato científico, decisões humanas e recibos originais continuam vigentes.

## Campanha CPU existente — PR89

Concluída e recebida: 60 jobs COMPLETED/0:0, 60 resultados e nenhuma ausência. O job 3734 está no retorno final, com duração 03:38:57, resultado, vetor, log, custos e supervisão. O autor voltou a verificar no HPC o mesmo ZIP 12b07fce… recebido e analisado; não há coleta 89 pendente.

O [retorno completo](evidence/pr89/final-20261101/manifest.json) resulta da união selada 50+4+6 e da consulta conjunta de 2/11,02:24:05 UTC (1/11,23:24:05 Fortaleza). São 47 alvos terminais reportados e 13 censuras M7. A fonte 9ab7823c, MINIMIZE, seed 42, cinco caps, checkpoint, Starts, parâmetros e sequência permanecem intactos. A [reconciliação](research/pr89-complete-reconciliation-20261101.md) e o [registro por métrica](research/pr89-qualification-register-20261101.csv) preservam os limites de M4/M12/M0. A recepção completa não é um certificado de ótimo exato.

## Artigo e apêndices — PR93

A versão científica 9453b823 integra as 60 células e mantém M7 na amostra. Foram entregues dois PDFs separados em abas do Codex: artigo 24 páginas, referências a partir da 20ª; apêndices 44 páginas. Todas as 68 páginas foram inspecionadas, sem referências não resolvidas ou caracteres fora da página. Os 101 testes do manuscrito, os gates de fonte/renderização/texto e o CI Manuscript 41381562593 passaram.

O CI geral passou no Linux e falhou no Windows por conversão LF→CRLF do novo manifesto. O digest convertido reproduz exatamente o erro do runner. A correção corrente protege os bytes dos recibos com `-text`; não altera os dados nem relaxa seus hashes. Cinco testes rápidos verificam os snapshots 50/54/60, sua continuidade, as disposições e a rejeição de adulteração. A execução desses testes foi antecipada no CI para detectar problemas de checkout antes da regressão longa. O novo CI completo ainda precisa concluir com sucesso.

A [síntese R2-D8](research/mvp2-integrated-assessment.md) e o [plano por Sprints/PRs](research/mvp2-closeout-plan.md) estão atualizados. A auditoria final continua aberta para o CI e a combinação efetiva PR89+PR93, a revisão científica humana e a release editorial. Nenhum merge, publicação ou envio a coautores foi realizado. Mudanças apenas de governança/testes não exigem regenerar os PDFs científicos já entregues.

## Preparação da extensão — PR94

Instalação zero-call conferida: fonte c623fe858f62d8fa2a70eebf6f3aeee5692e8f90, plano b41953a81f48a91d73c8112bb6794ccce78e72c41ce6ddef7a28ff7e4c098a77. Não atualizar essa cópia para seguir commits documentais. Seu CI e recibo de instalação foram revistos.

Aguarda-se o job_id e o código de saída da CLI de raízes entregue ao autor. Sem esse retorno não se presume submissão. O job previsto usa 2 h, um core físico,64 GiB e até seis chamadas 600 s para M5/M6/M9/M13/M20/M26. Após terminalidade e coleta, o retorno deve ser conferido antes da aceitação por hash e de uma CLI separada de guidance. Esse segundo job tem 1 h, quatro cores físicos,64 GiB e uma V100 de 32 GB, com até seis forwards; não faz treinamento.

O protocolo continua 144 células: 90 candidatas históricas e 54 novas, seis easy/dez medium e solver seeds 42/43/44, sem alterar o split 54/34/10/10, o modelo ou o threshold. Identidade de arquivo não equivale a elegibilidade por métrica; 18 candidatas M4/M12 continuam restritas. O adaptador instalado não despacha as 54 avaliações. Não há novo job, raiz, grafo, predição ou Start recebido nesta etapa.

## Próximas decisões

1. Fechar o CI da correção Windows e a revisão integrada do estudo atual.
2. Receber a submissão e, depois, o retorno terminal das seis raízes pela CLI do autor; não repetir a coleta da PR89.
3. Qualificar os artefatos e só então liberar, por CLI separada, a preparação graph/prediction/Start.
4. Preparar o dispatcher das novas avaliações após a conferência dos artefatos, sem retries automáticos ou ampliação do orçamento.
5. Solicitar aprovações específicas de PR89→develop, PR93→develop e da release→main conforme os gates. Preservar 15/12/2026 para a versão completa aos coautores e 14/1/2027 como prazo máximo de submissão.
