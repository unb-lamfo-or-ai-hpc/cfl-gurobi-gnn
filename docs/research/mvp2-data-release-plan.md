# MVP 2.0 — dados, software e depósito científico

Plano de curadoria de 2 de novembro de 2026. Esta decisão de organização não realiza upload, publicação, criação de DOI ou alteração de um depósito existente. GitHub é o local de desenvolvimento e inspeção; Zenodo deverá preservar uma versão científica identificada. Arquivos temporários continuam somente no scratch local autorizado e no armazenamento de dados do HPC.

## Divisão dos materiais

| Material | GitHub | Zenodo | Condição de liberação |
| --- | --- | --- | --- |
| Código, configuração, ambiente, testes e executores | Fonte legível, histórico e release por commit/tag | Snapshot do mesmo release, sem credenciais ou diretórios privados | CI, integração e licença do software conferidas |
| Contratos e protocolos experimentais | Documentos versionados, com supersessões datadas | Cópia dos contratos que regem cada conjunto experimental | Distinguir protocolo instalado, plano e execução efetiva |
| Inventário das instâncias e partições | Identificadores, folds, hashes, descritores e instruções de obtenção | Mesmo inventário e metadados de origem | Preservar a atribuição e os direitos do benchmark |
| Arquivos originais MILPBench | Não incorporar automaticamente | Somente se os direitos permitirem redistribuição; caso contrário, links de origem e hashes | A correção MINIMIZE é documentada; originais preservados |
| Tabelas, figuras e dados compactos que as reproduzem | CSV/JSON e scripts, incluindo todos os resultados adversos e censurados | Cópia fixa das tabelas, figuras e fontes numéricas | Cada número aponta para um registro e sua disposição por métrica |
| Evidências completas das campanhas CPU/GPU | Recibos sanitizados, índices, selos e sumários | Logs, trajetórias, custos, supervisão e accounting revisados, em partes com inventário | Sanitização, cobertura e direitos conferidos; ausência registrada |
| Checkpoints, estado de normalização, raízes, grafos, scores e Starts | Arquitetura, proveniência, hashes e metadados pequenos | Artefatos necessários à reprodução, se redistribuíveis e revisados | O checkpoint CPU original é preservado; GPU não o substitui |
| Vetores e evidência da auditoria M12 | Método de auditoria, selos, laudos e limitações | Vetores e dados necessários à reprodução dos laudos, se redistribuíveis | Não confundir viabilidade primal exata com ótimo global certificado |
| Artigo e apêndices | Fontes e versão pública revisada, apêndices separados | PDFs e fontes da versão depositada, conforme direitos e decisão editorial | Versões e hashes alinhados; não confundir preprint com artigo aceito |
| Senhas, licenças, tokens, caminhos privados e capturas pessoais | Nunca | Nunca | Não entram no inventário público nem nos pacotes |
| Temporários, caches e ZIPs privados de transferência | Nunca | Nunca como temporários | Não promover um arquivo privado a depósito público por conveniência |

O conjunto completo da PR89 inclui 60 células, inclusive as 15 de M7, suas 13 censuras terminais e as restrições de M4/M12. A curadoria não seleciona somente sucessos. As versões parciais de 50/54 células conservam seu papel histórico e não são somadas novamente à versão de 60. Os resultados da PR94 formarão outro conjunto: 144 avaliações novas planejadas não equivalem a 144 resultados recebidos. Os 90 registros históricos permanecem separados e não preenchem células novas.

## Pacote e rastreabilidade

Preparar partes por função: software; metadados e inventários; modelos e preparação; evidências de otimização; evidências GPU; fontes e produtos editoriais. Cada parte terá inventário de membros, tamanho, SHA256 e descrição. Um catálogo superior deverá ligar campanha, fonte instalada, ambiente, célula, preparação, parâmetros, resultado, custos, accounting e disposição científica. Ele também enumerará materiais retidos, ausentes ou não redistribuíveis, com a consequência para reprodução.

Conservar separadamente o hash do original privado e o hash da cópia sanitizada. Uma redação de host/caminho muda bytes e deve produzir um derivado identificado, nunca um recibo supostamente original. Os arquivos selados da PR89 não serão normalizados para acomodar sistemas operacionais. Binários e objetos pickle/Torch exigem revisão própria; a ausência de texto sensível visível não certifica seu conteúdo.

Os scripts em `scripts/archive/` já inventariam, particionam e verificam arquivos sem publicar. O modo `--private-archive` preserva bytes e pode conter caminhos privados: seu produto não é automaticamente publicável. A execução de inventário/empacotamento no HPC será pela CLI do autor, com destino em dados/RAID e sem alterar evidências de origem. Antes disso, dimensionar os bytes de todo o conjunto; não presumir que o limite de trabalho da preparação de seis raízes cobre uma campanha de 144 avaliações.

## Versão, DOI e licença

O artigo deverá citar a versão efetivamente utilizada e o commit correspondente. A documentação oficial do Zenodo distingue uma nova versão de arquivos de uma simples edição de metadados e fornece um identificador persistente para cada versão ([gestão de versões](https://help.zenodo.org/docs/deposit/manage-versions/)). Código, dados, pesos e manuscrito podem exigir licenças distintas; a licença MIT do código não é uma autorização geral de redistribuição dos demais objetos ([políticas](https://about.zenodo.org/policies/)).

O registro de MVP1 menciona o draft 23113003; referências operacionais anteriores mencionam 22751909. A associação, situação atual e DOI de ambos precisam ser confirmados na conta do autor antes de escolher uma continuidade de versões. Nesta revisão, a consulta pública desses dois endpoints não forneceu metadados utilizáveis. Nenhum deles é apresentado como depósito publicado ou DOI confirmado do MVP2. Não criar um registro duplicado, publicar um draft antigo ou alterar sua relação de versões sem essa conferência.

## Gates de fechamento

Antes de concluir a PR93, a divisão acima, o inventário de categorias e as pendências de direitos/DOI devem estar explícitos. O artigo não afirmará que o depósito já existe. O primeiro release público pode apresentar a campanha PR89 completa e o protocolo prospectivo da PR94, com limites claros, sem fabricar resultados futuros.

Após os resultados da PR94, S5/S6 reconciliarão o inventário final, os 144 destinos por célula, tabelas/figuras e seus hashes, licenças, metadados e a relação entre artigo e apêndices. A revisão do pacote público precede o pedido de aprovação específica de upload/publicação. A integração de código em develop ou a aprovação de um PDF não publica automaticamente um depósito Zenodo.
