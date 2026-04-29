from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import traceback
import html
import os
import re
import time

app = FastAPI()

VERSION = "VERSION 12 - PDF POR FOLIO ID"

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

        # Buscar dirección
        page.goto("https://www.leepa.org/Search/PropertySearch.aspx", timeout=60000)

        campo = "#ctl00_BodyContentPlaceHolder_WebTab1_tmpl0_AddressTextBox"

        page.wait_for_selector(campo, timeout=30000)
        page.fill(campo, direccion)
        page.press(campo, "Enter")

        page.wait_for_timeout(7000)

        texto_resultado = page.locator("body").inner_text(timeout=30000)

        # Buscar Folio ID de 7 dígitos en los resultados
        folios = re.findall(r"\b\d{7}\b", texto_resultado)

        if not folios:
            raise Exception("No pude encontrar el Folio ID en los resultados.")

        folio_id = folios[0]

        # Abrir directamente el Parcel Details correcto
        parcel_url = f"https://www.leepa.org/Display/DisplayParcel.aspx?FolioID={folio_id}"
        page.goto(parcel_url, timeout=60000)

        page.wait_for_timeout(5000)

        # Aceptar Continue si aparece
        try:
            page.evaluate("""
            () => {
                const buttons = Array.from(document.querySelectorAll('button, input, a'));
                const btn = buttons.find(b =>
                    (b.innerText && b.innerText.trim().toLowerCase() === 'continue') ||
                    (b.value && b.value.trim().toLowerCase() === 'continue')
                );
                if (btn) btn.click();
            }
            """)
            page.wait_for_timeout(8000)
        except:
            pass

        texto = page.locator("body").inner_text(timeout=30000)

        nombre_pdf = limpiar_nombre(direccion) + "_folio_" + folio_id + "_" + str(int(time.time())) + ".pdf"
        ruta_pdf = os.path.join(DOWNLOAD_DIR, nombre_pdf)

        page.pdf(
            path=ruta_pdf,
            format="Letter",
            print_background=True,
            margin={
                "top": "0.20in",
                "right": "0.20in",
                "bottom": "0.20in",
                "left": "0.20in"
            }
        )

        browser.close()

        pdf_url = f"/downloads/{nombre_pdf}"

        reporte = f"""
PDF creado correctamente.

Folio ID usado:
{folio_id}

Página usada para el PDF:
{parcel_url}

Texto inicial:
{texto[:3000]}
"""

        return reporte, pdf_url
