"""Painel do IDEB das escolas do Rio de Janeiro.

- Elaborado Por Christian Basilio
Mapa das escolas do estado com o IDEB de 2025, filtros por município, rede e
faixa de nota. O popup do hover compara a escola com a média do município e do
estado
"""

import streamlit as st

st.set_page_config(page_title="IDEB · Rio de Janeiro", layout="wide")

import pandas as pd  
import pydeck as pdk  
from leitura import (  
    CINZA,
    DATASETS,
    FAIXAS,
    LAYER_ID,
    SERIES,
    Recorte,
    carregar,
    cor_ideb,
    fmt,
    hexa,
    inteiro,
)


def barra_lateral() -> Recorte:
    
    with st.sidebar:
        st.subheader("Filtros")
        etapa = st.selectbox("Etapa de ensino", list(DATASETS))

    base = carregar(etapa)

    if base.empty:
        st.error(
            "Nenhuma escola do RJ encontrada. Verifique se um destes arquivos "
            f"está em dados/: {', '.join(DATASETS[etapa])}"
        )
        st.stop()

    with st.sidebar:
        municipios = sorted(m for m in base["municipio"].unique() if m and m != "nan")
        sel_mun = st.multiselect("Municípios", municipios, placeholder="Todos")

        redes = sorted(r for r in base["rede"].unique() if r and r != "nan")
        sel_rede = st.multiselect("Rede", redes, default=redes)

        tem_nota = base["ideb"].notna().any()
        piso = round(float(base["ideb"].min()), 1) if tem_nota else 0.0
        teto = round(float(base["ideb"].max()), 1) if tem_nota else 10.0
        faixa = st.slider("Faixa de IDEB 2025", piso, teto, (piso, teto), step=0.1)

        st.caption("Escolas sem IDEB de 2025 aparecem em cinza no mapa.")
        # colocando um texto no side bar para falar que Christian Basilio é o autor do painel
        st.write('Elaborado Por Christian Basilio')

        st.divider()
        limite_mapa = st.slider(
            "Máximo de pontos no mapa", 500, 20000, 5000, step=500,
            help="Os pontos plotados são os de maior IDEB 2025 dentro do filtro. "
                 "Reduza se o mapa ficar lento.",
        )

    df = base.copy()

    if sel_mun:
        df = df[df["municipio"].isin(sel_mun)]

    if sel_rede and len(sel_rede) < len(redes):
        df = df[df["rede"].isin(sel_rede)]

    # só filtra se o slider foi mesmo estreitado: sem isso o between() derruba
    if faixa[0] > piso + 1e-9 or faixa[1] < teto - 1e-9:
        df = df[df["ideb"].between(*faixa)]

    return Recorte(etapa=etapa, base=base, df=df,
                   limite_mapa=limite_mapa, municipios=sel_mun)


# indicadores

def indicadores(df: pd.DataFrame) -> None:
    # dropna() de propósito: escola sem nota não pode entrar como zero
    ideb = df["ideb"].dropna()
    variacao = df["variacao"].dropna()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Escolas", inteiro(len(df)))
    c2.metric(
        "IDEB médio 2025",
        fmt(ideb.mean() if len(ideb) else None),
        fmt(variacao.mean(), sinal=True) if len(variacao) else None,
        help="A variação abaixo do número compara com o IDEB de 2023.",
    )
    c3.metric("Nota média SAEB", fmt(df["nota_media"].mean()))
    c4.metric("Aprovação média", fmt(df["aprov_total"].mean(), "%"))

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Municípios", inteiro(df["municipio"].nunique()))
    c6.metric("Maior IDEB 2025", fmt(ideb.max() if len(ideb) else None))
    c7.metric("Menor IDEB 2025", fmt(ideb.min() if len(ideb) else None))

    # uma casa decimal: são 4 escolas em 966 no médio, inteiro mostraria "0%"
    acima_de_6 = int((ideb >= 6).sum())
    c8.metric(
        "IDEB 2025 ≥ 6,0",
        "—" if not len(ideb) else f"{acima_de_6 / len(ideb) * 100:.1f}%".replace(".", ","),
        help=(f"{inteiro(acima_de_6)} de {inteiro(len(ideb))} escolas com IDEB apurado"
              if len(ideb) else "Nenhuma escola com IDEB apurado no recorte."),
    )


# mapa

TOOLTIP_HTML = (
    "<div style='font-size:12.5px;line-height:1.45;max-width:290px'>"
    "<div style='font-weight:700;font-size:13.5px'>{escola}</div>"
    "<div style='opacity:.7;margin-bottom:7px'>{municipio} · {rede}</div>"
    "<div><span style='opacity:.7'>IDEB 2025:</span> "
    "<b style='font-size:15px'>{t_ideb}</b> "
    "<span style='opacity:.7'>({t_var} vs 2023)</span></div>"
    "<div><span style='opacity:.7'>Ante a média do município:</span> <b>{t_mun}</b></div>"
    "<div><span style='opacity:.7'>Ante a média do estado:</span> <b>{t_est}</b></div>"
    "<div><span style='opacity:.7'>Posição no RJ:</span> <b>{t_rank}</b></div>"
    "<div style='margin-top:6px'><span style='opacity:.7'>Português / Matemática:</span> "
    "<b>{t_port}</b> / <b>{t_mat}</b></div>"
    "<div><span style='opacity:.7'>Aprovação total:</span> <b>{t_aprov}</b></div>"
    "</div>"
)


def montar_pontos(df: pd.DataFrame, base: pd.DataFrame, rotulos_serie: list,
                  limite: int) -> pd.DataFrame:
    """Recorta, colore e formata os textos que o tooltip vai exibir."""
    # df vem ordenado por IDEB, então head() fica com as de maior nota
    pontos = df.head(limite).copy()
    pontos["cor"] = [cor_ideb(v) for v in pontos["ideb"]]

    # o tooltip do pydeck só troca {campo} por texto puro - não formata número
    pontos["t_ideb"] = [fmt(v) for v in pontos["ideb"]]
    pontos["t_var"] = [fmt(v, sinal=True) for v in pontos["variacao"]]
    pontos["t_mun"] = [fmt(v, sinal=True) for v in pontos["vs_municipio"]]
    pontos["t_est"] = [fmt(v, sinal=True) for v in pontos["vs_estado"]]
    pontos["t_port"] = [fmt(v) for v in pontos["nota_port"]]
    pontos["t_mat"] = [fmt(v) for v in pontos["nota_mat"]]
    pontos["t_aprov"] = [fmt(v, "%") for v in pontos["aprov_total"]]

    total_com_nota = int(base["ideb"].notna().sum())
    pontos["t_rank"] = [
        f"{int(r)}º de {total_com_nota}" if pd.notna(r) else "—"
        for r in pontos["rank_uf"]
    ]

    for i, _rotulo in enumerate(rotulos_serie, start=1):
        pontos[f"t_ap{i}"] = [fmt(v, "%") for v in pontos[f"ap{i}"]]

    return pontos


def desenhar_mapa(pontos: pd.DataFrame, df: pd.DataFrame, aproximar: bool) -> list:
    camada = pdk.Layer(
        "ScatterplotLayer",
        id=LAYER_ID,
        data=pontos,
        get_position=["lon", "lat"],
        get_fill_color="cor",
        get_radius=140,        # em metros; os limites em pixels evitam que
        radius_min_pixels=4,   # o ponto suma no zoom de longe ou vire uma
        radius_max_pixels=16,  # bolha gigante no zoom de perto
        pickable=True,         # sem isto não há hover nem clique
        auto_highlight=True,
        opacity=0.85,
    )

    deck = pdk.Deck(
        layers=[camada],
        initial_view_state=pdk.ViewState(
            latitude=float(df["lat"].median()),
            longitude=float(df["lon"].median()),
            zoom=10 if aproximar else 8.2,
        ),
        tooltip={"html": TOOLTIP_HTML,
                 "style": {"backgroundColor": "#161b22", "color": "#fff", "padding": "10px"}},
        map_style="light",
    )
    try:
        evento = st.pydeck_chart(deck, on_select="rerun", selection_mode="single-object")
        return evento.selection.get("objects", {}).get(LAYER_ID, [])
    except TypeError:
        st.pydeck_chart(deck)
        st.info("Atualize o Streamlit (≥ 1.39) para habilitar o clique nos pontos.")
        return []


def legenda() -> None:
    html = " ".join(
        f"<span style='margin-right:16px'>"
        f"<i style='background:{hexa(cor)};width:11px;height:11px;border-radius:50%;"
        f"display:inline-block;margin-right:5px'></i>{rotulo}</span>"
        for _, cor, rotulo in FAIXAS
    )
    html += (
        f"<span><i style='background:{hexa(CINZA)};width:11px;height:11px;"
        "border-radius:50%;display:inline-block;margin-right:5px'></i>sem dado</span>"
    )
    st.markdown(f"<div style='font-size:.82rem;color:#475569'>{html}</div>",
                unsafe_allow_html=True)


def ficha(escolhidos: list, rotulos_serie: list) -> None:
    """Ficha da escola clicada."""
    st.divider()
    if not escolhidos:
        st.caption("Clique em uma escola no mapa para ver a ficha completa.")
        return

    # o dicionário que o pydeck devolve traz as colunas da camada
    item = escolhidos[0]
    st.subheader(item.get("escola", ""))
    st.caption(f"{item.get('municipio', '—')} · rede {item.get('rede', '—')}")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("IDEB 2025", item.get("t_ideb", "—"), item.get("t_var", None))
    m2.metric("Ante o município", item.get("t_mun", "—"))
    m3.metric("Ante o estado", item.get("t_est", "—"))
    m4.metric("Posição no RJ", item.get("t_rank", "—"))

    detalhe = {
        "Nota de Português": item.get("t_port", "—"),
        "Nota de Matemática": item.get("t_mat", "—"),
        "Aprovação total": item.get("t_aprov", "—"),
    }
    for i, rotulo in enumerate(rotulos_serie, start=1):
        detalhe[f"Aprovação {rotulo}"] = item.get(f"t_ap{i}", "—")

    st.dataframe(
        pd.DataFrame({"Indicador": list(detalhe), "Valor": list(detalhe.values())}),
        hide_index=True,
    )


def mapa(recorte: Recorte) -> None:
    df = recorte.df
    rotulos_serie = SERIES[recorte.etapa]
    pontos = montar_pontos(df, recorte.base, rotulos_serie, recorte.limite_mapa)

    if len(pontos) < len(df):
        st.caption(
            f"{inteiro(len(pontos))} pontos plotados "
            f"(recorte com {inteiro(len(df))} escolas)"
        )

    escolhidos = desenhar_mapa(pontos, df, aproximar=bool(recorte.municipios))
    legenda()
    ficha(escolhidos, rotulos_serie)


# rankings

def rankings(df: pd.DataFrame) -> None:
    com_nota = df.dropna(subset=["ideb"])

    if com_nota.empty:
        st.info("Nenhuma escola com IDEB de 2025 no recorte atual.")
        return

    st.subheader("IDEB médio por rede")
    por_rede = (
        com_nota.groupby("rede")["ideb"]
        .agg(Escolas="count", IDEB="mean")
        .sort_values("IDEB", ascending=False)
    )
    st.bar_chart(por_rede["IDEB"], height=260, color="#14657f")
    st.dataframe(por_rede.round(2))

    st.divider()

    st.subheader("Municípios")

    # a variação sai da média das diferenças por escola
    por_mun = (
        com_nota.groupby("municipio")
        .agg(
            Escolas=("escola", "count"),
            ideb_2019=("ideb_2019", "mean"),
            ideb_2021=("ideb_2021", "mean"),
            ideb_2023=("ideb_2023", "mean"),
            ideb_2025=("ideb", "mean"),
            variacao=("variacao", "mean"),
            port=("nota_port", "mean"),
            mat=("nota_mat", "mean"),
            aprov=("aprov_total", "mean"),
        )
        .reset_index()
        .rename(columns={
            "municipio": "Município",
            "ideb_2019": "2019", "ideb_2021": "2021", "ideb_2023": "2023",
            "ideb_2025": "IDEB 2025", "variacao": "Δ 23→25",
            "port": "SAEB Port.", "mat": "SAEB Mat.", "aprov": "Aprovação",
        })
        .sort_values("IDEB 2025", ascending=False)
    )

    st.dataframe(
        por_mun.round(2),
        hide_index=True,
        height=460,
        column_config={
            "IDEB 2025": st.column_config.ProgressColumn(
                "IDEB 2025", format="%.1f",
                min_value=0, max_value=float(por_mun["IDEB 2025"].max()),
            ),
            "2019": st.column_config.NumberColumn(format="%.1f"),
            "2021": st.column_config.NumberColumn(format="%.1f"),
            "2023": st.column_config.NumberColumn(format="%.1f"),
            "Δ 23→25": st.column_config.NumberColumn(
                format="%+.1f", help="Média da variação de cada escola entre 2023 e 2025"),
            "SAEB Port.": st.column_config.NumberColumn(format="%.0f"),
            "SAEB Mat.": st.column_config.NumberColumn(format="%.0f"),
            "Aprovação": st.column_config.NumberColumn(format="%.1f%%"),
        },
    )

    disponivel = {ano: int(com_nota[col].notna().sum())
                  for ano, col in [("2019", "ideb_2019"), ("2021", "ideb_2021"),
                                   ("2023", "ideb_2023"), ("2025", "ideb")]}
    st.caption(
        "Escolas com IDEB apurado em cada ano: "
        + " · ".join(f"{ano} {inteiro(n)}" for ano, n in disponivel.items())
        + ". As colunas de anos anteriores são médias das escolas que tinham nota "
        "naquele ano, então a composição muda de coluna para coluna — em 2021, "
        "muitas escolas ficaram sem resultado divulgado. A variação é a única "
        "coluna calculada escola a escola."
    )


# tabela de escolas

RENOME = {
    "escola": "Escola", "municipio": "Município", "rede": "Rede",
    "ideb": "IDEB 2025", "ideb_2023": "IDEB 2023", "variacao": "Variação",
    "nota_media": "Nota SAEB", "aprov_total": "Aprovação",
    "rank_uf": "Posição no RJ",
}


def escolas(df: pd.DataFrame, etapa: str) -> None:
    tabela = df[list(RENOME)].rename(columns=RENOME).round(2)

    st.dataframe(
        tabela,
        hide_index=True,
        height=520,
        column_config={
            "Aprovação": st.column_config.NumberColumn(format="%.1f%%"),
            "Posição no RJ": st.column_config.NumberColumn(format="%d"),
        },
    )
    st.download_button(
        "Baixar recorte em CSV",
        tabela.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
        file_name=f"ideb_rj_{etapa.lower().replace(' ', '_')}.csv",
        mime="text/csv",
    )
    st.caption(
        "Fonte: INEP/IDEB. As médias desconsideram escolas sem valor apurado, "
        "por isso o total de escolas do recorte pode ser maior que o número de "
        "escolas com IDEB."
    )


# a página

st.title("Painel do IDEB · Estado do Rio de Janeiro")

recorte = barra_lateral()

st.caption(
    f"{recorte.etapa} · {inteiro(len(recorte.df))} escolas georreferenciadas em "
    f"{inteiro(recorte.df['municipio'].nunique())} municípios"
)

if recorte.df.empty:
    st.warning("Nenhuma escola atende aos filtros selecionados.")
    st.stop()

indicadores(recorte.df)

aba_mapa, aba_rank, aba_dados = st.tabs(["Mapa", "Rankings", "Escolas"])

with aba_mapa:
    mapa(recorte)

with aba_rank:
    rankings(recorte.df)

with aba_dados:
    escolas(recorte.df, recorte.etapa)
