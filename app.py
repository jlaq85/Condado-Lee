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

VERSION = "VERSION 15 - AUTO CONDADO"

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
        <input name="direccion" style="width:350px"><br><br>
        <button type="submit">Buscar</button>
    </form>
    """


@app.post("/buscar", response_class=HTMLResponse)
def buscar(direccion: str = Form(...)):
    try:
        condado = detectar_condado(direccion)

        if condado == "lee":
            resultado, pdf_url = buscar_lee(direccion)
        else:
            return f"""
            <h2>Condado no implementado</h2>
            <p>Detectado: {condado}</p>
            <a href="/">Volver</a>
            """

        return f"""
        <h2>Resultado</h2>
        <p><b>{VERSION}</b></p>

        <p><b>Dirección:</b> {html.escape(direccion)}</p>
        <p><b>Condado detectado:</b> {condado.upper()}</p>

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
        <pre>{html.escape(error)}</pre>
        <a href="/">Volver</a>
        """


# 🔥 DETECTAR CONDADO (VERSIÓN SIMPLE)
def detectar_condado(direccion):
    d = direccion.lower()

    if any(x in d for x in [
        "cape coral", "fort myers", "lehigh", "bonita springs",
        "estero", "sanibel", "pine island"
    ]):
        return "lee"

    if any(x in d for x in [
        "naples", "marco island", "immokalee"
    ]):
        return "collier"

    if any(x in d for x in [
        "labelle", "clewiston"
    ]):
        return "hendry"

    return "desconocido"


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
        page.wait_for_selector(campo)
        page.fill(campo, direccion)
        page.press(campo, "Enter")

        page.wait_for_timeout(7000)

        link = page.evaluate("""
        () => {
            const a = Array.from(document.querySelectorAll('a'))
            .find(x => x.innerText.includes('Parcel Details'));
            return a ? a.href : null;
        }
        """)

        if not link:
            raise Exception("No se encontró Parcel Details")

        parsed = urlparse(link)
        params = parse_qs(parsed.query)
        folio = params.get("FolioID", [""])[0]

        if not folio:
            raise Exception("No se pudo extraer FolioID")

        url = f"https://www.leepa.org/Display/DisplayParcel.aspx?FolioID={folio}"
        page.goto(url)

        page.wait_for_timeout(4000)

        # Click Continue
        try:
            page.locator("text=Continue").click(timeout=5000)
            page.wait_for_timeout(8000)
        except:
            pass

        texto = page.locator("body").inner_text()

        nombre = limpiar(direccion) + "_" + folio + "_" + str(int(time.time())) + ".pdf"
        ruta = os.path.join(DOWNLOAD_DIR, nombre)

        page.pdf(path=ruta, format="Letter", print_background=True)

        browser.close()

        return f"Folio: {folio}\nURL: {url}", f"/downloads/{nombre}"
