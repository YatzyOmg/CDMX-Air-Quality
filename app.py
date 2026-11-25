
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import folium
from streamlit_folium import st_folium
from pathlib import Path
import calendar

# configuración de la página y estilo -----------

st.set_page_config(
    page_title="CDMX Air Quality Explorer",
    page_icon="🌎",
    layout="wide",
    initial_sidebar_state="expanded"
)

COLOR = "#26C6DA"

RUTA = Path(__file__).resolve().parent / "data" / "raw"

st.markdown("""
<style>
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }

    [data-testid="stMetric"] {
        background-color: rgba(38, 198, 218, 0.07);
        border: 1px solid rgba(38, 198, 218, 0.25);
        padding: 18px;
        border-radius: 12px;
    }

    [data-testid="stMetricValue"] {
        color: #26C6DA;
    }

    div[data-baseweb="tab-list"] {
        gap: 15px;
    }
</style>
""", unsafe_allow_html=True)


# funciones de carga y procesamiento de datos ------------

@st.cache_data
def cargar_datos(ruta):

    datos = pd.read_excel(ruta)

    datos.columns = datos.columns.astype(str).str.strip()

    datos["FECHA"] = pd.to_datetime(
        datos["FECHA"],
        dayfirst=True,
        errors="coerce"
    ).dt.normalize()

    datos["HORA"] = pd.to_numeric(
        datos["HORA"], errors="coerce"
    )

    estaciones = [
        c for c in datos.columns
        if c not in ["FECHA", "HORA"]
    ]

    datos[estaciones] = datos[estaciones].apply(
        pd.to_numeric, errors="coerce"
    ).replace(-99, np.nan)

    datos["FechaHora"] = (
        datos["FECHA"] +
        pd.to_timedelta(datos["HORA"], unit="h")
    )

    return datos


@st.cache_data
def cargar_catalogo(ruta):

    catalogo = pd.read_csv(
        ruta,
        skiprows=1,
        encoding="latin-1"
    )

    catalogo.columns = catalogo.columns.str.strip()

    catalogo["cve_estac"] = (
        catalogo["cve_estac"].astype(str).str.strip()
    )

    for columna in ["latitud", "longitud"]:
        catalogo[columna] = pd.to_numeric(
            catalogo[columna], errors="coerce"
        )

    return catalogo


def obtener_estaciones(datos):

    return [
        c for c in datos.columns
        if c not in ["FECHA", "HORA", "FechaHora"]
    ]


def formato(valor):

    return f"{valor:.2f}" if pd.notna(valor) else "Sin datos"


@st.cache_data
def calidad_historica(rutas):

    resultados = []

    for ruta in rutas:

        datos = cargar_datos(ruta)

        claves = obtener_estaciones(datos)

        mediciones = datos[claves]

        anio_archivo = int(Path(ruta).stem[:4])

        esperadas = (
            8784 if calendar.isleap(anio_archivo)
            else 8760
        )

        resultados.append({
            "Año": str(anio_archivo),
            "Registros": len(datos),
            "Horas esperadas": esperadas,
            "Estaciones": len(claves),
            "Duplicados": datos.duplicated(
                subset=["FECHA", "HORA"]
            ).sum(),
            "Datos faltantes (%)": round(
                mediciones.isna().mean().mean()*100, 2
            ),
            "Cobertura (%)": round(
                mediciones.notna().mean().mean()*100, 2
            ),
            "Valores negativos": int(
                (mediciones < 0).sum().sum()
            ),
            "Estaciones sin datos": ", ".join(
                mediciones.columns[
                    mediciones.isna().all()
                ]
            )
        })

    return pd.DataFrame(resultados)


# inicio -----------

st.title("CDMX Air Quality Explorer")

st.markdown(
    "Análisis espacio-temporal de partículas PM2.5 "
    "en la Zona Metropolitana del Valle de México."
)

archivos = sorted(RUTA.glob("*PM25.xls"))

if not archivos:
    st.error("No se encontraron archivos de PM2.5.")
    st.stop()

anios = [archivo.stem[:4] for archivo in archivos]

catalogo = cargar_catalogo(
    str(RUTA / "cat_estacion.csv")
)

nombres = dict(zip(
    catalogo["cve_estac"],
    catalogo["nom_estac"]
))


# filtro -------------

st.sidebar.title("Filtros de análisis")

st.sidebar.markdown("**Contaminante: PM2.5**")

anio = st.sidebar.selectbox(
    "Año",
    anios,
    index=len(anios)-1
)

df = cargar_datos(
    str(RUTA / f"{anio}PM25.xls")
)

estaciones = obtener_estaciones(df)

estacion = st.sidebar.selectbox(
    "Estación de monitoreo",
    estaciones,
    format_func=lambda x: f"{x} - {nombres.get(x, x)}"
)

fecha_min = df["FECHA"].min().date()
fecha_max = df["FECHA"].max().date()

periodo = st.sidebar.date_input(
    "Periodo de análisis",
    value=(fecha_min, fecha_max),
    min_value=fecha_min,
    max_value=fecha_max
)

if len(periodo) != 2:
    st.info("Selecciona una fecha inicial y una final.")
    st.stop()

inicio, fin = periodo

datos = df[
    (df["FECHA"].dt.date >= inicio) &
    (df["FECHA"].dt.date <= fin)
].copy()

if datos.empty:
    st.warning("No existen registros en este periodo.")
    st.stop()

cobertura_minima = st.sidebar.slider(
    "Cobertura mínima para comparaciones (%)",
    min_value=0,
    max_value=100,
    value=75,
    step=5
)

st.sidebar.divider()

st.sidebar.caption(
    "Fuente: Red Automática de Monitoreo "
    "Atmosférico (RAMA), SIMAT."
)

st.sidebar.caption("Unidad de medición: µg/m³")

if anio == "2026":
    st.sidebar.warning("2026 contiene datos parciales.")


# indicadores principales ------------

serie = datos[estacion]

st.subheader(nombres.get(estacion, estacion))

st.caption(f"{inicio} a {fin} | PM2.5")

c1, c2, c3, c4, c5 = st.columns(5)

c1.metric(
    "Promedio (µg/m³)",
    formato(serie.mean())
)

c2.metric(
    "Máximo (µg/m³)",
    formato(serie.max())
)

c3.metric(
    "Mínimo (µg/m³)",
    formato(serie.min())
)

c4.metric(
    "Cobertura",
    f"{serie.notna().mean()*100:.1f}%"
)

c5.metric(
    "Mediciones válidas",
    f"{serie.count():,}"
)

if serie.notna().mean()*100 < cobertura_minima:
    st.warning(
        "La estación seleccionada tiene una cobertura "
        "inferior al umbral elegido."
    )


# pestaña del sashboard --------

tab1, tab2, tab3, tab4 = st.tabs([
    "Mapa interactivo",
    "Análisis temporal",
    "Comparación de estaciones",
    "Calidad de datos"
])


# mapa ---------------

with tab1:

    st.subheader("Distribución geográfica de estaciones")

    izquierda, derecha = st.columns([3, 1])

    catalogo_mapa = catalogo[
        catalogo["cve_estac"].isin(estaciones)
    ].dropna(
        subset=["latitud", "longitud"]
    )

    with izquierda:
        mapa = folium.Map(
            location=[19.4326, -99.1332],
            zoom_start=10,
            tiles="OpenStreetMap"
        )

        for _, fila in catalogo_mapa.iterrows():

            clave = fila["cve_estac"]

            valores = datos[clave]

            promedio = valores.mean()

            maximo = valores.max()

            cobertura = valores.notna().mean()*100

            informacion = f"""
            <b>{fila['nom_estac']} ({clave})</b><br>
            Contaminante: PM2.5<br>
            Promedio: {formato(promedio)} µg/m³<br>
            Máximo: {formato(maximo)} µg/m³<br>
            Cobertura: {cobertura:.1f}%
            """

            color = COLOR if valores.notna().any() else "#999999"

            folium.CircleMarker(
                location=[
                    fila["latitud"],
                    fila["longitud"]
                ],
                radius=7 if clave == estacion else 6,
                color="#00838F" if clave == estacion else color,
                fill=True,
                fill_color=color,
                fill_opacity=0.9,
                weight=2 if clave == estacion else 1,
                tooltip=folium.Tooltip(informacion),
                popup=folium.Popup(
                    informacion, max_width=300
                )
            ).add_to(mapa)

        st_folium(
            mapa,
            height=550,
            use_container_width=True,
            returned_objects=[]
        )

    with derecha:

        st.markdown("### Red de monitoreo")

        st.metric(
            "Estaciones registradas",
            len(estaciones)
        )

        st.metric(
            "Estaciones con mediciones",
            int(datos[estaciones].notna().any().sum())
        )

        st.metric(
            "Estaciones en el mapa",
            catalogo_mapa["cve_estac"].nunique()
        )

        st.markdown("**Leyenda**")

        st.markdown(
            f'<span style="color:{COLOR}">●</span> '
            'Con mediciones',
            unsafe_allow_html=True
        )

        st.markdown(
            '<span style="color:#999999">●</span> '
            'Sin mediciones',
            unsafe_allow_html=True
        )

    st.caption(
        "Las coordenadas corresponden al catálogo disponible. "
        "Los cambios históricos de ubicación no han sido verificados."
    )


# dashboard analisis temporal ------------

with tab2:

    st.subheader("Evolución temporal de PM2.5")

    frecuencia = st.radio(
        "Resolución temporal",
        ["Horaria", "Diaria", "Mensual"],
        horizontal=True
    )

    temporal = datos[
        ["FECHA", "FechaHora", estacion]
    ].copy()

    temporal = temporal.rename(
        columns={estacion: "PM2.5"}
    )

    if frecuencia == "Horaria":

        temporal = temporal.set_index(
            "FechaHora"
        )[["PM2.5"]]

        temporal = temporal.sort_index().asfreq("h")

        temporal = temporal.reset_index()

    else:

        temporal = temporal.set_index("FECHA")

        regla = "D" if frecuencia == "Diaria" else "MS"

        temporal = temporal["PM2.5"].resample(
            regla
        ).mean().reset_index()

        temporal = temporal.rename(
            columns={"FECHA": "FechaHora"}
        )

    fig = px.line(
        temporal,
        x="FechaHora",
        y="PM2.5",
        color_discrete_sequence=[COLOR],
        labels={
            "FechaHora": "Fecha",
            "PM2.5": "Concentración (µg/m³)"
        }
    )

    fig.update_traces(connectgaps=False)

    fig.update_layout(height=430)

    st.plotly_chart(fig, use_container_width=True)

    st.caption(
        "Los promedios diarios y mensuales utilizan "
        "las mediciones disponibles."
    )

    a, b = st.columns(2)

    with a:

        st.markdown("### Distribución de concentraciones")

        fig_hist = px.histogram(
            datos,
            x=estacion,
            nbins=40,
            color_discrete_sequence=[COLOR],
            labels={
                estacion: "PM2.5 (µg/m³)"
            }
        )

        fig_hist.update_layout(
            yaxis_title="Frecuencia"
        )

        st.plotly_chart(
            fig_hist, use_container_width=True
        )

    with b:

        st.markdown("### Comportamiento por hora del día")

        perfil = datos.groupby("HORA")[estacion].mean()

        perfil = perfil.reset_index()

        fig_hora = px.line(
            perfil,
            x="HORA",
            y=estacion,
            markers=True,
            color_discrete_sequence=[COLOR],
            labels={
                "HORA": "Hora",
                estacion: "Promedio (µg/m³)"
            }
        )

        st.plotly_chart(
            fig_hora, use_container_width=True
        )

    st.markdown("### Evolución histórica de la estación")

    historico = []

    for archivo in archivos:

        datos_anio = cargar_datos(str(archivo))

        if estacion in datos_anio.columns:

            valores = datos_anio[estacion]

            cobertura = valores.notna().mean()*100

            historico.append({
                "Año": archivo.stem[:4],
                "Promedio": valores.mean(),
                "Cobertura": cobertura
            })

    historico = pd.DataFrame(historico)

    if not historico.empty:

        historico.loc[
            historico["Cobertura"] < cobertura_minima,
            "Promedio"
        ] = np.nan

        fig_historico = px.line(
            historico,
            x="Año",
            y="Promedio",
            markers=True,
            hover_data=["Cobertura"],
            color_discrete_sequence=[COLOR],
            labels={
                "Promedio": "PM2.5 (µg/m³)"
            }
        )

        fig_historico.update_traces(
            connectgaps=False
        )

        st.plotly_chart(
            fig_historico,
            use_container_width=True
        )

    st.caption(
        "La evolución histórica utiliza los archivos anuales "
        "completos disponibles, independientemente del filtro "
        "de fechas. Se compara por clave de estación. "
        "2026 es parcial."
    )


# dashboard de comparacion de estaciones -------------

with tab3:
    st.subheader("Comparación espacial de PM2.5")
    comparacion = pd.DataFrame({
        "Estación": estaciones,
        "Promedio": datos[estaciones].mean().values,
        "Máximo": datos[estaciones].max().values,
        "Mínimo": datos[estaciones].min().values,
        "Cobertura": (
            datos[estaciones].notna().mean().values*100
        )
    })
    comparacion["Nombre"] = (
        comparacion["Estación"].map(nombres)
    )
    comparacion = comparacion[
        (comparacion["Cobertura"] >= cobertura_minima) &
        comparacion["Promedio"].notna()
    ].sort_values("Promedio", ascending=False)
    if comparacion.empty:
        st.warning(
            "Ninguna estación cumple el umbral de cobertura."
        )

    else:
        fig_comparacion = px.bar(
            comparacion,
            x="Estación",
            y="Promedio",
            color="Promedio",
            color_continuous_scale=[
                "#B2EBF2", "#00838F"
            ],
            hover_data=["Nombre", "Cobertura"],
            labels={
                "Promedio": "PM2.5 (µg/m³)"
            },
            title="Concentración promedio por estación"
        )
        st.plotly_chart(
            fig_comparacion,
            use_container_width=True
        )
        seleccion = st.multiselect(
            "Estaciones para comparar distribuciones",
            comparacion["Estación"].tolist(),
            default=comparacion["Estación"].head(5).tolist()
        )

        if seleccion:
            datos_box = datos[seleccion].melt(
                var_name="Estación",
                value_name="PM2.5"
            ).dropna()
            fig_box = px.box(
                datos_box,
                x="Estación",
                y="PM2.5",
                color="Estación",
                labels={
                    "PM2.5": "Concentración (µg/m³)"
                },
                title="Distribución de PM2.5 por estación"
            )
            st.plotly_chart(
                fig_box,
                use_container_width=True
            )
        st.dataframe(
            comparacion.round(2),
            use_container_width=True,
            hide_index=True
        )

#----------- dashboard

with tab4:
    st.subheader("Disponibilidad y calidad de los registros")
    mediciones = datos[estaciones]
    cobertura_estaciones = pd.DataFrame({
        "Estación": estaciones,
        "Cobertura (%)": (
            mediciones.notna().mean().values*100
        ),
        "Datos faltantes": mediciones.isna().sum().values
    })
    cobertura_estaciones = (
        cobertura_estaciones.sort_values(
            "Cobertura (%)",
            ascending=False
        )
    )
    q1, q2, q3 = st.columns(3)
    q1.metric(
        "Cobertura general",
        f"{mediciones.notna().mean().mean()*100:.1f}%"
    )
    q2.metric(
        "Duplicados",
        int(datos.duplicated(
            subset=["FECHA", "HORA"]
        ).sum())
    )
    q3.metric(
        "Valores negativos",
        int((mediciones < 0).sum().sum())
    )
#-------------------------
    fig_cobertura = px.bar(
        cobertura_estaciones,
        x="Estación",
        y="Cobertura (%)",
        color="Cobertura (%)",
        color_continuous_scale="RdYlGn",
        range_color=[0, 100],
        title="Cobertura por estación"
    )
    fig_cobertura.add_hline(
        y=cobertura_minima,
        line_dash="dash",
        annotation_text="Umbral seleccionado"
    )
    fig_cobertura.update_yaxes(range=[0, 100])
    st.plotly_chart(
        fig_cobertura,
        use_container_width=True
    )
    st.subheader("Control de calidad histórico")
    tabla_calidad = calidad_historica(
        tuple(str(a) for a in archivos)
    )
    fig_calidad = px.bar(
        tabla_calidad,
        x="Año",
        y="Cobertura (%)",
        color_discrete_sequence=[COLOR],
        title="Cobertura histórica de datos"
    )
    fig_calidad.update_yaxes(range=[0, 100])
    st.plotly_chart(
        fig_calidad,
        use_container_width=True
    )
    st.dataframe(
        tabla_calidad,
        use_container_width=True,
        hide_index=True
    )
    st.caption(
        "La cobertura se calcula respecto a los registros "
        "existentes en cada archivo."
    )
    with st.expander("Verificación histórica de estaciones"):
        resultados = []
        for archivo in archivos:
            datos_anio = cargar_datos(str(archivo))
            claves = set(
                obtener_estaciones(datos_anio)
            )
            faltantes = claves - set(
                catalogo["cve_estac"]
            )
            resultados.append({
                "Año": archivo.stem[:4],
                "Estaciones": len(claves),
                "Sin clave en catálogo": len(faltantes),
                "Claves faltantes": ", ".join(
                    sorted(faltantes)
                )
            })
        st.dataframe(
            pd.DataFrame(resultados),
            hide_index=True
        )
    with st.expander("Consultar datos procesados"):
        st.dataframe(
            datos,
            use_container_width=True
        )
        st.download_button(
            "Descargar datos en CSV",
            data=datos.to_csv(index=False).encode("utf-8"),
            file_name=f"PM25_{anio}_procesado.csv",
            mime="text/csv"
        )

# ---------------------
st.divider()
st.caption(
    "CDMX Air Quality Explorer | "
    "Análisis histórico de PM2.5 | "
    "Fuente: SIMAT - RAMA"
)