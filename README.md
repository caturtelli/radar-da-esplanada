# Radar da Esplanada 2.0

Aplicativo Streamlit de monitoramento jornalístico. Executar com `streamlit run app.py`.
Testar com `python -m pytest tests -q` (instalar pytest além de requirements.txt).

## Dados e compatibilidade

`indicacoes.csv` e `noticias.csv` preservam a curadoria, cargos, situações e evidências.
`noticias_coletadas.csv` preserva o histórico original; `catalogo_orgaos.csv` mantém os 79 órgãos.
Coletor, varredura histórica, status e workflows existentes permanecem intactos.
O aplicativo nunca grava nesses arquivos. Índices são derivados em memória e renovados quando os arquivos mudam (cache de até 60 segundos).

`radar_model.py` separa leitura, identidade, classificação, associação e filtros da interface.
A identificação percorre o catálogo inteiro; vínculos entre pessoa e órgão exigem o mesmo trecho.
A simples menção não é indicação. Nomeações relatadas em manchetes não equivalem a confirmação oficial.
Nomes novos são candidatos extraídos por regras, sujeitos a erros; sobrenomes e primeiros nomes só se resolvem quando únicos no registro disponível. Homônimos e apelidos não cadastrados exigem revisão.
O sistema usa manchetes; não lê reportagens integrais. Falsos positivos e negativos ainda são possíveis.

## Fontes e novidades

Cada reportagem conserva sua URL, veículo e data, e jornalista quando disponível.
Republicações com a mesma manchete normalizada compartilham um grupo de possível republicação.
Títulos distintos não demonstram independência. Nenhum contador representa confirmação independente.
A janela de 24 horas usa publicação, não captura, e exclui datas inválidas ou futuras.
O histórico apresenta relatos cronológicos, sem declarar mudança efetiva de situação por comparação automática de manchetes.
A ausência de novas notícias não significa estabilidade de uma indicação.

## Etapa futura: aprendizado supervisionado

Não há modelo nem notas automáticas nesta entrega. Criar módulo separado e persistência própria,
sem acrescentar avaliações ao CSV que o coletor regrava. Contrato proposto:

- `article_id`: hash estável da URL; conservar identificador e origem em migrações.
- `assessment_id`, `article_id`, revisor, data, versão e correção de avaliação anterior.
- Notas distintas de 0 a 10: relevância, credibilidade jornalística e força da indicação.
- Probabilidade de nomeação é um alvo diferente da credibilidade; exigir definição e resultado observado antes de estimar probabilidades.
- Atributos: veículo, jornalista, fontes identificadas, natureza da informação, confirmação independente e histórico, com valores ausentes explícitos.
- Relações de proveniência: apuração original, republicação, derivação, independência desconhecida e revisão manual.

Primeira interface: cerca de 100 notícias avaliadas pela usuária, depois correções e avaliações contínuas.
Guardar histórico de avaliações, sem sobrescrever rótulos. Separar treino e validação por grupo de apuração e tempo para evitar vazamento por republicações.
Validar qualidade e calibração antes de mostrar escores. A amostra inicial é piloto, não garantia de capacidade preditiva.

## Revisão e publicação

Alterações na branch `codex/radar-2.0`, destinadas a pull request para `main`.
Não mesclar ou publicar antes da autorização da proprietária.

## Correção de navegação e cobertura

A abertura mostra cartões clicáveis dos 31 ministérios, sem selecionar uma pasta por padrão.
Há atalhos explícitos para órgãos centrais, entidades e todos os 79 órgãos. Cada cartão apresenta
pessoas e reportagens; a página do órgão permite abrir fichas individuais e voltar à grade.
A consulta inicial considera publicações desde 25/10/2026 às 17h de Brasília (fechamento da votação),
e o histórico anterior continua disponível no filtro de período. Esta data é um recorte operacional,
não uma afirmação de que toda publicação posterior trata do resultado eleitoral.

`expandir_historico.py` executa buscas complementares por todos os órgãos, incluindo o dia 25,
divide consultas que atingem o limite de 100 entradas em buscas diárias e registra consultas,
falhas e limites em `cobertura_historica.json`. A busca não usa o órgão consultado como evidência:
a associação continua dependendo do texto da manchete. Linhas/colunas existentes são preservadas,
e novas URLs são acrescentadas sem duplicar URLs já registradas.

Executar manualmente: `python expandir_historico.py --inicio 2026-10-25 --fim 2026-10-30`.
O relatório deste PR registra 79 órgãos consultados, 1.243 notícias adicionais e nenhuma consulta com falha.
Não representa garantia de cobertura integral da imprensa. O RSS omite fontes e reportagens e
não fornece necessariamente texto integral ou jornalista. A coleta automática e seus workflows
permanecem inalterados; a busca complementar não cria uma nova rotina automática.

O reconhecimento agora filtra expressões institucionais e cabeçalhos, separa construções com duas
pessoas quando há nomes explícitos e não transforma o cliente de um advogado no candidato ao cargo.
Os cartões destacam vínculos com indícios de movimentação; simples menções permanecem nas reportagens.
Ainda pode haver falsos positivos/negativos; não se deduzem nomes ausentes nem confirmações oficiais.


## Navegação por URL e histórico do navegador

A URL é a fonte de verdade das telas, não o último órgão guardado na sessão. Exemplos de rotas relativas:

- `?orgao=fazenda`: Ministério da Fazenda.
- `?pessoa=rafael-fonteles`: ficha de Rafael Fonteles.
- `?tela=noticias&pagina=2`: segunda página de reportagens.
- `?categoria=todos`: grade dos 79 órgãos.

`navigation.py` valida e converte rotas em nomes do catálogo. Slugs removem acentos, usam nomes legíveis e tratam colisões de forma determinística. Identificadores inexistentes apresentam mensagem e seleção segura. Parâmetros externos, como UTM, são preservados.

Callbacks atualizam `st.query_params` uma única vez por ação. A tela lê a URL em cada execução, inclusive nas mudanças recebidas pelo histórico nativo do Streamlit (Voltar/Avançar). Reruns comuns e filtros não reescrevem a rota. Não há JavaScript injetado, acesso à janela pai, nova dependência ou domínio fixo. A implementação foi testada com Streamlit 1.66.1, cuja navegação nativa utiliza pushState e responde a popstate.

Os filtros de busca, veículos, natureza e período continuam pertencendo à sessão: o link compartilha o órgão/pessoa/página, não os filtros do remetente. A categoria da grade é mantida ao abrir e voltar de uma pasta. A aba Pessoas começa pela seleção de um nome, e a seleção abre uma ficha com endereço próprio.

Validação: 20 testes aprovados, incluindo regressões anteriores e testes de rota, query params restaurados para simular Voltar/Avançar, recarga em nova sessão, paginação e URLs inválidas. A verificação dos botões reais do navegador no ambiente publicado deve ocorrer após autorização de publicação. Não foram alterados dados, classificação, coleta ou workflows.
