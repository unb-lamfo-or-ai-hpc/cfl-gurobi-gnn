# PR89 — recebimento completo e qualificação por métrica

A campanha terminou e suas60 células foram recebidas. O ZIP final tem SHA256 `12b07fce5b49dd7540bd5cd26be2a54cfad2cfccc5b42999373da5d7ae29f85f`: seus79 membros,78 selos e18 vínculos internos de resultado/custos/supervisão foram conferidos. Os controles são idênticos aos das duas coletas anteriores. A consulta conjunta foi realizada em2novembro2026,02:24:05.722194–02:24:05.784312UTC (1novembro,23:24:05 em Fortaleza), e contém60 jobs e180 linhas de accounting, todos COMPLETED/0:0. Este é o gate de recepção/reconciliação, não uma certificação irrestrita dos resultados.

A fonte permanece9ab7823c, seed42, MINIMIZE, com o checkpoint, as raízes e os Starts originais. Nenhum arquivo remoto, parâmetro, recurso, sequência ou job foi alterado. A análise foi exclusivamente offline. Os50 e54 registros anteriores permanecem intactos; seus exames foram reutilizados e os seis resultados novos foram verificados separadamente. O [snapshot completo](../evidence/pr89/final-20261101/manifest.json) mantém a cadeia dos três arquivos recebidos.

## O que a campanha permite afirmar

Há47 atingimentos do critério terminal reportado de0,01% e13 interrupções pelo limite de12h, todas em M7. Todos60 runs observaram10% de gap;54 observaram5%;47 observaram1% e0,01%. A censura depende do alvo: não observar0,01% não apaga um cruzamento anterior de10%. Os horários dos callbacks não são tempos exatos de primeiro atingimento.

| Instância | Recebidos | Critério terminal reportado / censurados | Disposição científica |
| --- | --- | --- | --- |
| M0 |15|15 /0| Contrastes descritivos no mesmo critério tolerado; a discrepância cruzada de bound de0,000524% impede leitura como certificado exato |
| M4 |15|15 /0| Qualidade, custo e tempo apenas descritivos sob restrição numérica; sem speedup certificado |
| M7 |15|2 /13| Primal terminal comum5,428377599678637; comparar bounds/gaps e alvos observados, sem transformar timeout em sucesso |
| M12 |15|15 /0| Tratar gap interno e custo como relatos do solver; auditoria primal com escopo explícito, sem ótimo global comum certificado |

G atinge o critério reportado antes de B em quatro dos cinco caps de M0, mas é mais lento que ambos controles com dois threads. Em M7 somente B/1 e R/16 encerram o gap; G pode antecipar alvos intermediários sem atingir o alvo terminal. Não existe repetição independente por configuração; os cinco caps não são réplicas.

## M12: os seis vetores finais ampliam o diagnóstico

O [novo laudo](pr89-m12-terminal-audit-20261101.json) estende o [exame anterior](pr89-m12-raw-audit-20261101.json), sem modificá-lo. As seis soluções novas foram avaliadas em todas as linhas, bounds, domínios e objetivo do modelo original, por aritmética racional nas interpretações decimal-LP e binary64. G/8 e G/16 são primalmente viáveis nesse exame, assim como G/4 no laudo anterior. B/8,R/8,B/16,R/16 contêm uma binária fracionária; arredondá-la produz violação de0,0000416587. Uma desigualdade por intervalos exclui qualquer complemento contínuo desse padrão binário arredondado. Isso não constitui reparo nem otimização.

Com oito threads, B/R/G levam16219,853/13488,320/617,228s. Com dezesseis, levam13071,843/16005,814/791,673s. Todos seis reportam gap interno zero. G reporta4,741382854739; os controles reportam4,740937765901 com oito threads e4,740932705477 com dezesseis. Os excessos de aproximadamente0,009388% e0,009495% de G não são perdas frente a soluções inteiras exatamente viáveis melhores: os controles examinados falham nesse requisito.

Os logs sustentam a diferença no esforço: com oito threads G registra558,47 unidades de trabalho e79943 iterações, versus14139,09/4785572 para B e12019,86/5509499 para R; com dezesseis, G registra721,35/103045, B10209,34/8847763 e R12749,97/13452114. O presolve de G contém1729 linhas/661125 colunas, contra2400/1153162 dos controles. Todos seis logs identificam raiz por LP concorrente determinístico. Esses relatos são consistentes com trajetórias e reduções diferentes; não isolam causalidade da GNN.

Um Start não fixa variáveis nem muda a região viável e não restringe o MILP a um ótimo local. Gap zero é a concordância numérica entre incumbent e bound internos daquele run. Não é prova de exatidão numérica, viabilidade inteira exata ou ótimo global comum entre runs. Os cinco pontos M12 não cobertos pelos dois laudos continuam sem exame primal independente; M4 mantém sua restrição própria.

## Custos observados e limites

A soma de Runtime é293,919h; a soma de elapsed dos jobs é295,072h. A reserva efetivamente observada corresponde a1750,185 core-h físicos, ou3500,369 AllocCPU-h lógicos no fator2 observado. Esses produtos de alocação e duração não medem utilização, energia ou cobrança. A diferença job menos Runtime varia64,23–82,93s na campanha e65,15–77,33s nos seis jobs finais; não explica contrastes de horas. Preparação histórica, fila e trabalho humano são escopos separados. Cenários cold/amortizados não se tornam novas medições end-to-end completas.

## Próximo gate

A recepção das60 células está fechada. A revisão integrada de artigo, tabelas, figuras, afirmações e pacote editorial continua na PR93 antes de Ready/merge/PDF. As restrições por métrica estão em disposition.csv; todos os flags científicos originais permanecem falsos. Não há retries propostos para esta campanha. A PR94 pode usar o estágio instalado c623fe8 e plano b41953a8 por uma CLI separada para preparação, com seus gates físicos e de coleta; esta análise não submete raízes, inferências ou as54 avaliações. Merges e publicação permanecem decisões humanas específicas.
