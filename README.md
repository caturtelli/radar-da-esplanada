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
