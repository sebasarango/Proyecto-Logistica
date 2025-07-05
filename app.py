# app.py

import streamlit as st
import requests
from bs4 import BeautifulSoup
from zipfile import ZipFile
import io
import pdfplumber
import pandas as pd
from datetime import datetime

# 📌 URL base
URL = "https://www.dane.gov.co/index.php/estadisticas-por-tema/agropecuario/sistema-de-informacion-de-precios-sipsa/componente-precios-mayoristas"

# 📌 Extraer enlaces
def extraer_ultimos_enlaces_sipsa(url):
    resp = requests.get(url)
    soup = BeautifulSoup(resp.content, 'html.parser')
    enlaces = soup.find_all('a', href=True)

    enlace_excel = None
    enlace_zip = None

    for enlace in enlaces:
        texto = enlace.get_text().strip().lower()
        if not enlace_excel and texto == "anexo":
            enlace_excel = enlace['href']
        elif not enlace_zip and texto.startswith("informes por ciudades"):
            enlace_zip = enlace['href']
        if enlace_excel and enlace_zip:
            break

    return enlace_excel, enlace_zip

# 📌 Descargar y preprocesar Excel de Bogotá
def obtener_dataframe_bogota(url_excel):
    resp = requests.get(url_excel)
    df_sipsa = pd.read_excel(io.BytesIO(resp.content), header=None)

    # Tu preprocesamiento
    columnas_combinadas = df_sipsa.iloc[1].fillna(method='ffill') + " - " + df_sipsa.iloc[2].fillna('')
    df_sipsa.columns = ['Producto'] + list(columnas_combinadas[1:])
    df_sipsa_limpio = df_sipsa.iloc[4:].copy()

    columnas_bogota = [col for col in df_sipsa_limpio.columns if col.startswith('Bogotá, Corabastos')]
    if not columnas_bogota:
        return pd.DataFrame({"Error": ["No se encontraron columnas de Bogotá."]})

    df_bogota = df_sipsa_limpio[['Producto'] + columnas_bogota].copy()
    df_bogota.columns = ['Producto', 'Precio ($/kg)', 'Variación %']
    df_bogota['Precio ($/kg)'] = pd.to_numeric(df_bogota['Precio ($/kg)'], errors='coerce')
    df_bogota['Variación %'] = pd.to_numeric(df_bogota['Variación %'], errors='coerce')
    df_bogota = df_bogota[df_bogota['Precio ($/kg)'].notna()].reset_index(drop=True).astype({'Precio ($/kg)': 'int64'})

    return df_bogota

# 📌 Leer PDF Bogotá
def obtener_texto_pdf_bogota(url_zip):
    resp = requests.get(url_zip)
    zipfile_bytes = io.BytesIO(resp.content)

    with ZipFile(zipfile_bytes) as zip_ref:
        for name in zip_ref.namelist():
            if name.lower().startswith('bogota') and name.lower().endswith('.pdf'):
                with zip_ref.open(name) as pdf_file:
                    with pdfplumber.open(pdf_file) as pdf:
                        texto = "\n".join(
                            page.extract_text() for page in pdf.pages if page.extract_text()
                        )
                        return texto
    return "No se encontró PDF de Bogotá."

# 📌 Ejecutar scraping y procesar
def obtener_datos_sipsa():
    enlace_excel, enlace_zip = extraer_ultimos_enlaces_sipsa(URL)

    if enlace_excel and enlace_excel.startswith('/'):
        enlace_excel = f"https://www.dane.gov.co{enlace_excel}"
    if enlace_zip and enlace_zip.startswith('/'):
        enlace_zip = f"https://www.dane.gov.co{enlace_zip}"

    df_bogota = obtener_dataframe_bogota(enlace_excel) if enlace_excel else None
    texto_bogota = obtener_texto_pdf_bogota(enlace_zip) if enlace_zip else "No se encontró el PDF de Bogotá."

    return df_bogota, texto_bogota

# === INTERFAZ STREAMLIT ===
st.set_page_config(page_title="Precios SIPSA - Bogotá", layout="centered")
st.title("📊 Precios Mayoristas - Bogotá (SIPSA)")
st.caption("Consulta los precios publicados por el DANE desde el archivo 'Anexo'")

if st.button("🔄 Obtener precios"):
    df, texto_pdf = obtener_datos_sipsa()

    if df is not None and "Error" not in df.columns:
        st.subheader("📋 Tabla de precios (Bogotá)")
        st.dataframe(df)

        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Descargar CSV", data=csv, file_name="precios_bogota.csv", mime='text/csv')

        st.subheader("📝 Extracto del PDF de Bogotá")
        st.text_area("Contenido del informe PDF", texto_pdf[:2000], height=300)
    else:
        st.error("❌ No se pudieron cargar los datos de Bogotá.")
