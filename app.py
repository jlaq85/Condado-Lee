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

VERSION = "VERSION 20 - LEE + DEBUG COLLIER"

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
        <input name="direccion" style="width:420px"><br><br>
        <button type="submit">Buscar</button>
    </form>
    """


@app.post("/buscar", response_class=HTMLResponse)
def buscar(direccion: str = Form(...)):
    try:
        # 🔥 INTENTAR LEE
        try:
            resultado, pdf_url = buscar_lee(direccion)
            return f"""
            <h2>Resultado - Lee County</h2>
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
        except:
            pass

        # 🔥 SI FALLA LEE → DEBUG COLLIER
        resultado = debug_collier(direccion)

        return f"""
        <h2>Debug Collier County</h2>
        <p><b>{VERSION}</b></p>

        <p><b>Dirección:</b> {html.escape(direccion)}</p>

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


def limpiar(texto):
    return re.sub(r"[^a-z0-9]", "_", texto.lower())[:60]


# 🔥 LEE (YA FUNCIONANDO)
def buscar_lee(direccion):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            chromium_sandbox=False,
            args=["--disable-dev-shm-usage"]
        )

        page = browser.new_page(viewport={"width": 1280, "height": 1800})
        page.goto("https://www.leepa.org/Search/PropertySearch.aspx", timeout=60000)

        campo = "#ctl00_BodyContentPlaceHolder_WebTab1_tmpl0_AddressTextBox"

        page.wait_for_selector(campo, timeout=30000)
        page.fill(campo, direccion)
        page.press(campo, "Enter")

        page.wait_for_timeout(9000)

        link = page.evaluate("""
        () => {
            const links = Array.from(document.querySelectorAll('a'));
            const parcel = links.find(a =>
                a.innerText &&
                a.innerText.toLowerCase().includes('parcel details')
            );
            return parcel ? parcel.href : null;
        }
        """)

        if not link:
            raise Exception("Lee no encontró resultados")

        parsed = urlparse(link)
        params = parse_qs(parsed.query)
        folio = params.get("FolioID", [""])[0]

        url = f"https://www.leepa.org/Display/DisplayParcel.aspx?FolioID={folio}"
        page.goto(url)

        page.wait_for_timeout(5000)

        try:
            page.locator("text=Continue").click(timeout=8000)
            page.wait_for_timeout(8000)
        except:
            pass

        nombre = limpiar(direccion) + "_" + folio + "_" + str(int(time.time())) + ".pdf"
        ruta = os.path.join(DOWNLOAD_DIR, nombre)

        page.pdf(path=ruta, format="Letter", print_background=True)

        browser.close()

        return f"Folio: {folio}\nURL: {url}", f"/downloads/{nombre}"


# 🔥 DEBUG COLLIER
def debug_collier(direccion):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            chromium_sandbox=False,
            args=["--disable-dev-shm-usage"]
        )

        page = browser.new_page()
        page.goto("https://www.collierappraiser.com/", timeout=60000)

        page.wait_for_timeout(8000)

        # 🔍 Extraer TODOS los inputs y botones
        elementos = page.evaluate("""
        () => {
            const items = Array.from(document.querySelectorAll('input, button, select, textarea'));
            return items.map(el => ({
                tag: el.tagName,
                type: el.getAttribute('type'),
                id: el.id,
                name: el.name,
                placeholder: el.placeholder,
                value: el.value
            }));
        }
        """)

        browser.close()

        reporte = "=== ELEMENTOS DETECTADOS EN COLLIER ===\\n\\n"

        for e in elementos:
            reporte += str(e) + "\\n"

        return reporte
