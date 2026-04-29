from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import traceback
import html
import os
import re
import time
from urllib.parse import urlparse, parse_qs

app = FastAPI()

VERSION = "VERSION 17 - CLICK SEARCH REAL (FIX)"

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

app.mount("/downloads", StaticFiles(directory=DOWNLOAD_DIR), name="downloads")


@app.get("/", response_class=HTMLResponse)
def home():
    return f"""
    <h2>Buscar propiedad automático</h2>
    <p><b>{VERSION}</b></p>

    <form method="post" action="/buscar">
        Dirección:<br>
        <input name="direccion" style="width:400px"><br><br>
        <button type="submit">Buscar y crear PDF</button>
    </form>
    """


@app.post("/buscar", response_class=HTMLResponse)
def buscar(direccion: str = Form(...)):
    try:
        resultado, pdf_url = buscar_lee(direccion)

        return f"""
        <h2>Resultado</h2>
        <p><b>{VERSION}</b></p>
        <p><b>Dirección:</b> {html.escape(direccion)}</p>

        <p>
            <a href="{pdf_url}" target="_blank" style="font-size:20px;">
                📄 Descargar PDF
            </a>
        </p>

        <hr>
        <pre>{html.escape(resultado)}</pre>

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


def limpiar(texto):
    return re.sub(r"[^a-z0-9]", "_", texto.lower())[:60]


def buscar_lee(direccion):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            chromium_sandbox=False,
            args=["--disable-dev-shm-usage"]
        )

        page = browser.new_page(viewport={"width": 1280, "height": 1800})

        page.goto("https://www.leepa.org/Search/PropertySearch.aspx")

        campo = "#ctl00_BodyContentPlaceHolder_WebTab1_tmpl0_AddressTextBox"
        boton = "#ctl00_BodyContentPlaceHolder_WebTab1_tmpl0_btnSearch"

        page.wait_for_selector(campo)
        page.fill(campo, direccion)

        # 🔥 CLICK REAL EN SEARCH (ESTO ES LA CLAVE)
        page.click(boton)

        # Esperar resultados (tabla)
        page.wait_for_timeout(8000)

        # Confirmar que salieron resultados
        contenido = page.locator("body").inner_text()

        if "found" not in contenido.lower():
            raise Exception("No aparecieron resultados. Revisa dirección o espera.")

        # Obtener link Parcel Details
        link = page.evaluate("""
        () => {
            const links = Array.from(document.querySelectorAll('a'));
            const a = links.find(x =>
                x.innerText &&
                x.innerText.toLowerCase().includes('parcel details')
            );
            return a ? a.href : null;
        }
        """)

        if not link:
            raise Exception("No se encontró Parcel Details después de buscar.")

        parsed = urlparse(link)
        params = parse_qs(parsed.query)
        folio = params.get("FolioID", [""])[0]

        if not folio:
            raise Exception("No se pudo extraer FolioID del link.")

        url = f"https://www.leepa.org/Display/DisplayParcel.aspx?FolioID={folio}"
        page.goto(url)

        page.wait_for_timeout(5000)

        # Click Continue
        try:
            page.locator("text=Continue").click(timeout=8000)
            page.wait_for_timeout(8000)
        except:
            pass

        page.wait_for_timeout(5000)

        texto = page.locator("body").inner_text()

        nombre = limpiar(direccion) + "_" + folio + "_" + str(int(time.time())) + ".pdf"
        ruta = os.path.join(DOWNLOAD_DIR, nombre)

        page.pdf(
            path=ruta,
            format="Letter",
            print_background=True
        )

        browser.close()

        return f"Folio: {folio}\nURL: {url}", f"/downloads/{nombre}"
