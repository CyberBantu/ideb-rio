# Painel do IDEB — escolas do Rio de Janeiro

Mapa interativo com o IDEB 2025 das escolas do estado do Rio de Janeiro, feito com
Streamlit e pydeck. Dá para filtrar por etapa de ensino, município, rede e faixa de
nota, e clicar em qualquer escola para ver a ficha completa.

O popup do mapa não mostra só a nota: compara a escola com a média do município e a
do estado, e informa a posição dela no ranking estadual. Uma nota 4,2 significa coisas
bem diferentes em Nova Iguaçu e em Niterói.

## Rodando

```bash
pip install -r requirements.txt
streamlit run app.py
```

As três camadas já vêm no repositório, em `dados/` — não precisa baixar nada.

Para rodar os testes:

```bash
pytest
```

## Organização

```
app.py       a página inteira: filtros, indicadores, mapa, rankings e tabela
leitura.py   constantes, leitura dos .gpkg e formatação de números
dados/       as três camadas .gpkg
tests/       formatação, presença dos dados e o app de ponta a ponta
```

## O que tem no painel

- **Mapa** com as escolas coloridas por faixa de IDEB, hover com o resumo e clique
  abrindo a ficha detalhada (notas de Português e Matemática, aprovação por série).
- **Rankings** de IDEB médio por rede e por município.
- **Escolas**: a tabela do recorte atual, com a posição de cada escola no estado e
  download em CSV.

Oito indicadores no topo acompanham os filtros: total de escolas, IDEB médio e a
variação contra 2023, nota SAEB, aprovação, municípios cobertos, maior e menor IDEB
e o percentual de escolas que chegam a 6,0.

## Dados

INEP — divulgação dos resultados do IDEB 2025 por escola, cruzada com o Censo Escolar
para obter as coordenadas. Cada arquivo em `dados/` é uma etapa de ensino:

| Arquivo | Etapa | Escolas georreferenciadas |
|---|---|---|
| `ensino_iniciais_rio.gpkg` | Anos iniciais | 3.359 |
| `ensino_finais_rio.gpkg` | Anos finais | 2.260 |
| `ensino_medio_rio.gpkg` | Ensino médio | 1.223 |

Escolas sem IDEB apurado aparecem em cinza no mapa e ficam de fora das médias — não
entram como zero, o que rebaixaria a média artificialmente.

Vale um aviso sobre o dado: o INEP suprime o resultado de escolas com poucos
participantes no SAEB, e essas escolas são desproporcionalmente pequenas e rurais.
As médias aqui, como qualquer média do IDEB, são das escolas com resultado divulgado.
