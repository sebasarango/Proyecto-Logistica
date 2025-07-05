# 📌 Paso 1: Instalar librerías necesarias
#!pip install pdfplumber

# 📌 Paso 2: Importar librerías
import requests
from bs4 import BeautifulSoup
from zipfile import ZipFile
import io
import pdfplumber
import pandas as pd
from datetime import datetime
import streamlit as st

# 📌 Paso 3: URL base
URL = "https://www.dane.gov.co/index.php/estadisticas-por-tema/agropecuario/sistema-de-informacion-de-precios-sipsa/componente-precios-mayoristas"

# 📌 Paso 4: Extraer los enlaces más recientes
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

# 📌 Paso 5: Descargar Excel como DataFrame
def obtener_dataframe_excel(url_excel):
    resp = requests.get(url_excel)
    df = pd.read_excel(io.BytesIO(resp.content))
    print("✅ Excel cargado como DataFrame.")
    return df

# 📌 Paso 6: Leer PDF de Bogotá como texto
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
                        print("✅ Texto del PDF de Bogotá extraído.")
                        return texto
    return None

# 📌 Paso 7: Ejecutar el proceso completo
def obtener_datos_sipsa():
    enlace_excel, enlace_zip = extraer_ultimos_enlaces_sipsa(URL)

    # Convertir a enlaces absolutos si es necesario
    if enlace_excel and enlace_excel.startswith('/'):
        enlace_excel = f"https://www.dane.gov.co{enlace_excel}"
    if enlace_zip and enlace_zip.startswith('/'):
        enlace_zip = f"https://www.dane.gov.co{enlace_zip}"

    df_excel = obtener_dataframe_excel(enlace_excel) if enlace_excel else None

    return df_excel

def procesar_bogota(df):
# Paso 1: Crear nombres de columnas combinando fila 1 y 2
  columnas_combinadas = df.iloc[1].fillna(method='ffill') + " - " + df.iloc[2].fillna('')
  df.columns = ['Producto'] + list(columnas_combinadas[1:])  # Renombra columnas

  # Paso 2: Eliminar filas de encabezado y categorías
  df_sipsa_limpio = df.iloc[4:].copy()  # A partir de fila 5 (índice 4)

  # Paso 3: Filtrar columnas de Bogotá
  columnas_bogota = [col for col in df_sipsa_limpio.columns if col.startswith('Bogotá, Corabastos')]
  df_bogota = df_sipsa_limpio[['Producto'] + columnas_bogota].copy()

  # Paso 4: Renombrar columnas
  df_bogota.columns = ['Producto', 'Precio ($/kg)', 'Variación %']

  # Paso 5: Convertir a numérico donde sea posible y limpiar valores
  df_bogota['Precio ($/kg)'] = pd.to_numeric(df_bogota['Precio ($/kg)'], errors='coerce')
  df_bogota['Variación %'] = pd.to_numeric(df_bogota['Variación %'], errors='coerce')

  # Opcional: eliminar filas vacías o sin precio
  df_bogota = df_bogota[df_bogota['Precio ($/kg)'].notna()].reset_index(drop=True).astype({'Precio ($/kg)': 'int64'})
  return df_bogota

# === INTERFAZ STREAMLIT ===
st.set_page_config(page_title="Precios SIPSA - Bogotá", layout="centered")
st.title("📊 Precios Mayoristas - Bogotá (SIPSA)")
st.caption("Consulta los precios publicados por el DANE desde el archivo 'Anexo'")

if st.button("🔄 Obtener precios"):
    df_1 = obtener_datos_sipsa()
    df = procesar_bogota(df_1)

    if df is not None and "Error" not in df.columns:
        st.subheader("📋 Tabla de precios (Bogotá)")
        st.dataframe(df)

        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Descargar CSV", data=csv, file_name="precios_bogota.csv", mime='text/csv')

        st.subheader("📝 Extracto del PDF de Bogotá")
        st.text_area("La fecha de estos datos es", datetime.today().strftime("%Y-%m-%d"), value=texto_pdf, height=300)
    else:
        st.error("❌ No se pudieron cargar los datos de Bogotá.")

