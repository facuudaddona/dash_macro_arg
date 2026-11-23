import io
import pandas as pd
import plotly.express as px
import requests
import streamlit as st

st.set_page_config(page_title="Monitor Socioeconómico - Argentina", layout="wide")
st.title("Monitor Socioeconómico de Argentina")
st.caption("Datos oficiales vía API de Series de Tiempo (datos.gob.ar)")

@st.cache_data(ttl=3600)
def cargar_datos():
    url = (
        "https://apis.datos.gob.ar/series/api/series/"
        "?ids=145.3_INGNACUAL_DICI_M_38,143.3_NO_PR_2004_A_21,168.1_T_CAMBIOR_D_0_0_26"
        "&start_date=2020-01-01&collapse=month&format=csv"
    )
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/csv,*/*",
    }
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()

    df = pd.read_csv(io.StringIO(resp.text))
    df = df.rename(
        columns={
            "indice_tiempo": "fecha",
            "ipc_ng_nacional_tasa_variacion_mensual": "ipc_mensual",
            "emae_original": "emae",
            "tipo_cambio_bna_vendedor": "tc_bna",
        }
    )
    df["fecha"] = pd.to_datetime(df["fecha"])
    df = df.sort_values("fecha").reset_index(drop=True)
    df["ipc_mensual_pct"] = (df["ipc_mensual"] * 100).round(2)
    df["emae_ia_pct"] = (df["emae"].pct_change(12) * 100).round(2)
    return df

try:
    df = cargar_datos()
except Exception as e:
    st.error(f"No se pudieron actualizar los datos en este momento: {e}")
    st.stop()

fecha_min = df["fecha"].min().to_pydatetime()
fecha_max = df["fecha"].max().to_pydatetime()
inicio = st.sidebar.slider(
    "Mostrar datos desde:",
    min_value=fecha_min,
    max_value=fecha_max,
    value=fecha_min,
    format="YYYY-MM",
)
df_filtrado = df[df["fecha"] >= pd.Timestamp(inicio)]

serie_ipc = df.dropna(subset=["ipc_mensual_pct"]).iloc[-1]
serie_emae = df.dropna(subset=["emae_ia_pct"]).iloc[-1]
serie_tc = df.dropna(subset=["tc_bna"]).iloc[-1]

c1, c2, c3 = st.columns(3)
c1.metric(f"IPC Mensual ({serie_ipc['fecha'].strftime('%Y-%m')})", f"{serie_ipc['ipc_mensual_pct']:.2f}%")
c2.metric(f"EMAE Interanual ({serie_emae['fecha'].strftime('%Y-%m')})", f"{serie_emae['emae_ia_pct']:.2f}%")
c3.metric(f"TC BNA Vendedor ({serie_tc['fecha'].strftime('%Y-%m')})", f"${serie_tc['tc_bna']:.2f}")

col_izq, col_der = st.columns(2)

with col_izq:
    fig1 = px.bar(
        df_filtrado.dropna(subset=["ipc_mensual_pct"]),
        x="fecha",
        y="ipc_mensual_pct",
        title="Inflación Mensual (%)",
    )
    st.plotly_chart(fig1, use_container_width=True)

with col_der:
    fig2 = px.line(
        df_filtrado.dropna(subset=["emae_ia_pct"]),
        x="fecha",
        y="emae_ia_pct",
        title="EMAE Variación Interanual (%)",
        markers=True,
    )
    fig2.add_hline(y=0, line_dash="dash", line_color="gray")
    st.plotly_chart(fig2, use_container_width=True)
