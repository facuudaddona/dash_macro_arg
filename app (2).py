import io
import pandas as pd
import plotly.express as px
import requests
import streamlit as st

st.set_page_config(page_title="Monitor Socioeconómico - Argentina", layout="wide")
st.title("Monitor Socioeconómico de Argentina")
st.caption("Datos oficiales vía API de Series de Tiempo (datos.gob.ar)")

IDS_SERIES = [
    "145.3_INGNACUAL_DICI_M_38",     # IPC mensual
    "143.3_NO_PR_2004_A_21",         # EMAE
    "168.1_T_CAMBIOR_D_0_0_26",      # TC BNA vendedor
    "149.1_TL_INDIIOS_OCTU_0_21",    # Índice de salarios
    "174.1_RRVAS_IDOS_0_0_36",       # Reservas internacionales BCRA (saldos)
    "42.3_EPH_PUNTUATAL_0_M_30",     # Tasa de desocupación total (EPH)
]

@st.cache_data(ttl=3600)
def cargar_datos():
    url = (
        "https://apis.datos.gob.ar/series/api/series/"
        f"?ids={','.join(IDS_SERIES)}&start_date=2020-01-01&format=csv"
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
            "indice_salarios": "salarios_indice",
            "reservas_internacionales_bcra_saldos": "reservas_bcra",
            "eph_continua_desocupacion_total": "desempleo_prop",
        }
    )

    df["fecha"] = pd.to_datetime(df["fecha"])
    df = df.sort_values("fecha").reset_index(drop=True)

    # Porcentajes y variaciones
    if "ipc_mensual" in df.columns:
        df["ipc_mensual_pct"] = (df["ipc_mensual"] * 100).round(2)
    if "emae" in df.columns:
        df["emae_ia_pct"] = (df["emae"].pct_change(12) * 100).round(2)

    # Salarios: medimos la distancia real entre fechas válidas de la serie
    if "salarios_indice" in df.columns:
        s_sal = df["salarios_indice"].dropna()
        if len(s_sal) >= 2:
            fechas_sal = df.loc[s_sal.index, "fecha"]
            mediana_dias = fechas_sal.diff().dt.days.median()
            periodos_ia = 4 if (pd.notna(mediana_dias) and mediana_dias > 60) else 12
        else:
            periodos_ia = 12
        df["salarios_ia_pct"] = (df["salarios_indice"].pct_change(periodos_ia) * 100).round(2)

    if "desempleo_prop" in df.columns:
        df["desempleo_pct"] = (df["desempleo_prop"] * 100).round(2)

    return df

def ultimo_valido(df_obj, col):
    if col not in df_obj.columns:
        return None
    s = df_obj.dropna(subset=[col])
    return None if s.empty else s.iloc[-1]

try:
    df = cargar_datos()
except Exception as e:
    st.error(f"No se pudieron cargar los datos: {e}")
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
df_f = df[df["fecha"] >= pd.Timestamp(inicio)]

u_ipc = ultimo_valido(df, "ipc_mensual_pct")
u_emae = ultimo_valido(df, "emae_ia_pct")
u_tc = ultimo_valido(df, "tc_bna")
u_sal = ultimo_valido(df, "salarios_ia_pct")
u_res = ultimo_valido(df, "reservas_bcra")
u_des = ultimo_valido(df, "desempleo_pct")

m1, m2, m3 = st.columns(3)
if u_ipc is not None:
    m1.metric(f"IPC Mensual ({u_ipc['fecha'].strftime('%Y-%m')})", f"{u_ipc['ipc_mensual_pct']:.2f}%")
if u_emae is not None:
    m2.metric(f"EMAE Interanual ({u_emae['fecha'].strftime('%Y-%m')})", f"{u_emae['emae_ia_pct']:.2f}%")
if u_tc is not None:
    m3.metric(f"TC BNA Vendedor ({u_tc['fecha'].strftime('%Y-%m')})", f"${u_tc['tc_bna']:.2f}")

m4, m5, m6 = st.columns(3)
if u_sal is not None:
    m4.metric(f"Salarios Interanual ({u_sal['fecha'].strftime('%Y-%m')})", f"{u_sal['salarios_ia_pct']:.2f}%")
if u_res is not None:
    m5.metric(f"Reservas BCRA ({u_res['fecha'].strftime('%Y-%m')})", f"{u_res['reservas_bcra']:,.0f}")
if u_des is not None:
    m6.metric(f"Desocupación EPH ({u_des['fecha'].strftime('%Y-%m')})", f"{u_des['desempleo_pct']:.1f}%")

tab1, tab2 = st.tabs(["Macro y Precios", "Salarios, Reservas y Empleo"])

with tab1:
    c_izq, c_der = st.columns(2)
    with c_izq:
        if "ipc_mensual_pct" in df_f.columns:
            fig = px.bar(
                df_f.dropna(subset=["ipc_mensual_pct"]),
                x="fecha", y="ipc_mensual_pct",
                title="Inflación Mensual (%)",
            )
            st.plotly_chart(fig, use_container_width=True)
    with c_der:
        if "emae_ia_pct" in df_f.columns:
            fig = px.line(
                df_f.dropna(subset=["emae_ia_pct"]),
                x="fecha", y="emae_ia_pct",
                title="EMAE Variación Interanual (%)",
                markers=True,
            )
            fig.add_hline(y=0, line_dash="dash", line_color="gray")
            st.plotly_chart(fig, use_container_width=True)

    if "tc_bna" in df_f.columns:
        fig_tc = px.line(
            df_f.dropna(subset=["tc_bna"]),
            x="fecha", y="tc_bna",
            title="Tipo de Cambio BNA Vendedor ($/USD)",
        )
        st.plotly_chart(fig_tc, use_container_width=True)

with tab2:
    if "salarios_ia_pct" in df_f.columns:
        fig_sal = px.line(
            df_f.dropna(subset=["salarios_ia_pct"]),
            x="fecha", y="salarios_ia_pct",
            title="Índice de Salarios - Variación Interanual (%)",
            markers=True,
        )
        fig_sal.add_hline(y=0, line_dash="dash", line_color="gray")
        st.plotly_chart(fig_sal, use_container_width=True)

    c_b1, c_b2 = st.columns(2)
    with c_b1:
        if "reservas_bcra" in df_f.columns:
            fig_res = px.line(
                df_f.dropna(subset=["reservas_bcra"]),
                x="fecha", y="reservas_bcra",
                title="Reservas Internacionales BCRA (Saldos)",
            )
            st.plotly_chart(fig_res, use_container_width=True)
    with c_b2:
        if "desempleo_pct" in df_f.columns:
            fig_des = px.bar(
                df_f.dropna(subset=["desempleo_pct"]),
                x="fecha", y="desempleo_pct",
                title="Tasa de Desocupación Total - EPH (%)",
            )
            st.plotly_chart(fig_des, use_container_width=True)
