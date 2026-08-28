"""Constantes, leitura das camadas .gpkg e formatação de números."""

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import streamlit as st

DADOS = Path(__file__).parent / "dados"

UF_ALVO = "RJ"

# precisa ser o mesmo na criação da camada e na leitura do clique, senão o
# pydeck não devolve o ponto selecionado
LAYER_ID = "escolas"

# recorte do Rio primeiro; a base nacional serve de alternativa
DATASETS = {
    "Ensino Médio": ["ensino_medio_rio.gpkg", "ensino_medio_nacional.gpkg"],
    "Anos Iniciais": ["ensino_iniciais_rio.gpkg", "anos_iniciais_nacional.gpkg"],
    "Anos Finais": ["ensino_finais_rio.gpkg", "anos_finais_nacional.gpkg"],
}

# vl_aprovacao_2025_1..4 são séries diferentes em cada etapa
SERIES = {
    "Ensino Médio": ["1ª série", "2ª série", "3ª série", "4ª série"],
    "Anos Iniciais": ["2º ano", "3º ano", "4º ano", "5º ano"],
    "Anos Finais": ["6º ano", "7º ano", "8º ano", "9º ano"],
}

# (limite superior, cor RGB, rótulo) - lido como "menor que o limite"
FAIXAS = [
    (3.5, [214, 69, 65], "abaixo de 3,5"),
    (4.5, [224, 139, 60], "3,5 a 4,5"),
    (5.5, [216, 185, 63], "4,5 a 5,5"),
    (99.0, [46, 125, 84], "5,5 ou mais"),
]
CINZA = [155, 163, 173]  # escolas sem IDEB apurado

LIMITES_RJ = {"lat": (-24, -20), "lon": (-45, -40)}


def para_numero(serie: pd.Series) -> pd.Series:
    if serie.dtype == object:
        serie = (
            serie.astype(str).str.strip()
            .str.replace("%", "", regex=False)
            .str.replace(",", ".", regex=False)
        )
    return pd.to_numeric(serie, errors="coerce")


@st.cache_data(show_spinner="Carregando base do Rio de Janeiro…")
def carregar(etapa: str) -> pd.DataFrame:
    """Lê o .gpkg da etapa e devolve um DataFrame plano só com o RJ.

    Sai com nomes de coluna padronizados (escola, municipio, rede, ideb...).
    """
    import geopandas as gpd

    caminho = next((DADOS / n for n in DATASETS[etapa] if (DADOS / n).exists()), None)
    if caminho is None:
        return pd.DataFrame()

    gdf = gpd.read_file(caminho)

    # aceita NO_ESCOLA, no_escola ou "No_Escola " com espaço sobrando
    cols = {str(c).strip().lower(): c for c in gdf.columns}

    # se a base for a nacional, fica só o RJ
    if "sg_uf" in cols:
        gdf = gdf[gdf[cols["sg_uf"]].astype(str).str.upper().str.strip() == UF_ALVO]
    if len(gdf) == 0:
        return pd.DataFrame()

    # usa lat/lon quando existirem; senão tira um ponto de dentro da geometria
    if "latitude" in cols and "longitude" in cols:
        lat = para_numero(gdf[cols["latitude"]]).values
        lon = para_numero(gdf[cols["longitude"]]).values
    else:
        g = gdf.to_crs(4326) if gdf.crs is not None else gdf
        ponto = g.geometry.representative_point()
        lat, lon = ponto.y.values, ponto.x.values

    def texto(chave):
        """Coluna de texto, ou vazio se não existir."""
        return gdf[cols[chave]].astype(str).values if chave in cols else ""

    def valor(chave):
        """Coluna numérica, ou NA se não existir."""
        return para_numero(gdf[cols[chave]]).values if chave in cols else pd.NA

    df = pd.DataFrame({
        "escola": texto("no_escola"),
        "municipio": texto("no_municipio"),
        "rede": texto("rede"),
        "lat": lat,
        "lon": lon,
        "ideb": valor("vl_observado_2025"),
        "ideb_2023": valor("vl_observado_2023"),
        "ideb_2021": valor("vl_observado_2021"),
        "ideb_2019": valor("vl_observado_2019"),
        "nota_media": valor("vl_nota_media_2025"),
        "nota_port": valor("vl_nota_portugues_2025"),
        "nota_mat": valor("vl_nota_matematica_2025"),
        "aprov_total": valor("vl_aprovacao_2025_si_4"),
        "ap1": valor("vl_aprovacao_2025_1"),
        "ap2": valor("vl_aprovacao_2025_2"),
        "ap3": valor("vl_aprovacao_2025_3"),
        "ap4": valor("vl_aprovacao_2025_4"),
    })

    df = df.dropna(subset=["lat", "lon"])
    df = df[df["lat"].between(*LIMITES_RJ["lat"]) & df["lon"].between(*LIMITES_RJ["lon"])]

    df["variacao"] = df["ideb"] - df["ideb_2023"]
    df["media_municipio"] = df.groupby("municipio")["ideb"].transform("mean")
    df["vs_municipio"] = df["ideb"] - df["media_municipio"]
    df["vs_estado"] = df["ideb"] - df["ideb"].mean()
    df["rank_uf"] = df["ideb"].rank(ascending=False, method="min")

    return df.sort_values("ideb", ascending=False, na_position="last").reset_index(drop=True)


def fmt(valor, sufixo="", casas=1, sinal=False) -> str:
    """Número no padrão br. Travessão se nulo; sinal=True para "+0,3"."""
    if valor is None or pd.isna(valor):
        return "—"
    texto = f"{valor:+.{casas}f}" if sinal else f"{valor:.{casas}f}"
    return texto.replace(".", ",") + sufixo


def inteiro(n) -> str:
    """Contagem com ponto como separador de milhar."""
    return f"{int(n):,}".replace(",", ".")


def cor_ideb(valor):
    """Cor RGB da faixa em que o IDEB se encaixa."""
    if pd.isna(valor):
        return CINZA
    for limite, cor, _ in FAIXAS:
        if valor < limite:
            return cor
    return FAIXAS[-1][1]


def hexa(rgb) -> str:
    """[r, g, b] -> "#rrggbb", para a legenda em HTML."""
    return "#{:02x}{:02x}{:02x}".format(*rgb)

@dataclass
class Recorte:
    """O que a barra lateral produziu."""

    etapa: str
    base: pd.DataFrame        # a etapa inteira, sem filtro
    df: pd.DataFrame          # o recorte atual
    limite_mapa: int
    municipios: list = field(default_factory=list)
