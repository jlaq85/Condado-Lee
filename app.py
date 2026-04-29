from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import traceback
import html
import os
import re
import time

app = FastAPI()

VERSION = "VERSION 9 - PDF PARCEL DETAILS"

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

app.mount("/downloads", StaticFiles(directory=DOWNLOAD_DIR), name="downloads")


@app.get("/", response_class=HTMLResponse)
def home():
    return f"""
    <h2>Buscar propiedad y crear PDF</h2>
    <p><b>{VERSION}</b></p>

    <form method="post" action="/buscar">
        Dirección:<br>
        <input name="direccion" style="width:350px"><br><br>
        <button type="submit">Buscar y crear PDF</button>
    </form>
    """


@app.post("/buscar", response_class=HTMLResponse)
def buscar(direccion: str = Form(...)):
    try:
        resultado, pdf_url = buscar_lee_y_crear_pdf(direccion)

        return f"""
        <h2>Resultado</h2>
        <p><b>{VERSION}</b></p>
        <p><b>Dirección:</b> {html.escape(direccion)}</p>

        <p>
            <a href="{pdf_url}" target="_blank" style="font-size:20px;">
                📄 Abrir / Descargar PDF del Parcel Details
            </a>
        </p>

        <hr>

        <div style="white-space: pre-wrap; font-family: monospace; font-size: 13px;">
        {html.escape(resultado)}
        </div>

        <br>
        <a href="/">Volver</a>
        """

    except Exception:
        error = traceback.format_exc()
        return f"""
        <h2>Error interno</h2>
        <p><b>{VERSION}</b></p>
        <pre>{html.escape(error)}</pre>
        <a href="/">Volver</a>
        """


def limpiar_nombre(texto):
    texto = texto.lower()
    texto = re.sub(r"[^a-z0-9]+", "_", texto)
    texto = texto.strip("_")
    return texto[:60]


def buscar_lee_y_crear_pdf(direccion):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            chromium_sandbox=False,
            args=["--disable-dev-shm-usage"]
        )

        page = browser.new_page(viewport={"width": 1280, "height": 1700})

        page.goto("https://www.leepa.org/Search/PropertySearch.aspx", timeout=60000)

        campo = "#ctl00_BodyContentPlaceHolder_WebTab1_tmpl0_AddressTextBox"

        page.wait_for_selector(campo, timeout=30000)
        page.fill(campo, direccion)
        page.press(campo, "Enter")

        page.wait_for_timeout(7000)

        # Click en el link correcto: Parcel Details
        page.get_by_text("Parcel Details", exact=True).click(timeout=30000)

        page.wait_for_timeout(8000)

        texto = page.locator("body").inner_text(timeout=30000)

        nombre_pdf = limpiar_nombre(direccion) + "_parcel_details_" + str(int(time.time())) + ".pdf"
        ruta_pdf = os.path.join(DOWNLOAD_DIR, nombre_pdf)

        page.pdf(
            path=ruta_pdf,
            format="Letter",
            print_background=True,
            margin={
                "top": "0.25in",
                "right": "0.25in",
                "bottom": "0.25in",
                "left": "0.25in"
            }
        )

        browser.close()

        pdf_url = f"/downloads/{nombre_pdf}"

        return texto[:5000], pdf_url
