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

VERSION = "VERSION 30 - FASTAPI LEE + CHARLOTTE FIX STREET"

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
        <button type="submit">Buscar y crear PDF</button>
    </form>
    """


@app.post("/buscar", response_class=HTMLResponse)
def buscar(direccion: str = Form(...)):
    try:
        try:
            resultado, pdf_url = buscar_lee(direccion)
            condado = "Lee"
        except Exception:
            resultado, pdf_url = buscar_charlotte(direccion)
            condado = "Charlotte"

        return f"""
        <h2>Resultado</h2>
        <p><b>{VERSION}</b></p>
        <p><b>Dirección:</b> {html.escape(direccion)}</p>
        <p><b>Condado:</b> {condado}</p>

        <p><a href="{pdf_url}" target="_blank" style="font-size:20px;">📄 Descargar PDF</a></p>

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


def separar_direccion_charlotte(direccion):
    partes = direccion.strip().split(" ", 1)
    numero = partes[0]
    calle = partes[1] if len(partes) > 1 else ""
    return numero, calle


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
        folio = parse_qs(parsed.query).get("FolioID", [""])[0]

        if not folio:
            raise Exception("Lee encontró link, pero no FolioID")

        url = f"https://www.leepa.org/Display/DisplayParcel.aspx?FolioID={folio}"
        page.goto(url, timeout=60000)

        page.wait_for_timeout(5000)

        try:
            page.locator("text=Continue").click(timeout=8000)
            page.wait_for_timeout(8000)
        except:
            pass

        nombre = limpiar(direccion) + "_lee_" + folio + "_" + str(int(time.time())) + ".pdf"
        ruta = os.path.join(DOWNLOAD_DIR, nombre)

        page.pdf(path=ruta, format="Letter", print_background=True)

        browser.close()

        return f"Lee OK\nFolio: {folio}\nURL: {url}", f"/downloads/{nombre}"


def buscar_charlotte(direccion):
    from playwright.sync_api import sync_playwright

    numero, calle = separar_direccion_charlotte(direccion)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            chromium_sandbox=False,
            args=["--disable-dev-shm-usage"]
        )

        page = browser.new_page(viewport={"width": 1400, "height": 1400})

        page.goto("https://www.ccappraiser.com/RPSearchEnter.asp", timeout=60000)
        page.wait_for_timeout(5000)

        page.fill('input[name="PropertyAddressNumber"]', numero)

        # Detectar automáticamente el campo de nombre de calle
        campo_calle = page.evaluate("""
        () => {
            const inputs = Array.from(document.querySelectorAll('input'));
            const match = inputs.find(i => {
                const id = (i.id || '').toLowerCase();
                const name = (i.name || '').toLowerCase();
                return (
                    (id.includes('propertyaddress') || name.includes('propertyaddress')) &&
                    !id.includes('number') &&
                    !name.includes('number') &&
                    i.type !== 'hidden'
                );
            });
            return match ? (match.name || match.id) : null;
        }
        """)

        if not campo_calle:
            inputs = page.evaluate("""
            () => Array.from(document.querySelectorAll('input')).map(i => ({
                type: i.type,
                id: i.id,
                name: i.name,
                value: i.value
            }))
            """)
            raise Exception("No pude detectar campo de calle en Charlotte. Inputs: " + str(inputs))

        page.fill(f'input[name="{campo_calle}"]', calle)

        # Click en Run Search
        try:
            page.click('input[value*="Run Search"]', timeout=10000)
        except:
            try:
                page.click('button:has-text("Run Search")', timeout=10000)
            except:
                page.locator("text=Run Search").click(timeout=10000)

        page.wait_for_timeout(9000)

        nombre = limpiar(direccion) + "_charlotte_" + str(int(time.time())) + ".pdf"
        ruta = os.path.join(DOWNLOAD_DIR, nombre)

        page.pdf(path=ruta, format="Letter", print_background=True)

        browser.close()

        return f"Charlotte OK\nNúmero: {numero}\nCalle: {calle}\nCampo calle usado: {campo_calle}", f"/downloads/{nombre}"
