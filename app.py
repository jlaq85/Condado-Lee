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

VERSION = "VERSION 28 - LEE + DEBUG CHARLOTTE MENU"

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
        try:
            resultado, pdf_url = buscar_lee(direccion)

            return f"""
            <h2>Resultado - Lee County</h2>
            <p><b>{VERSION}</b></p>
            <p><b>Dirección:</b> {html.escape(direccion)}</p>
            <p><a href="{pdf_url}" target="_blank" style="font-size:20px;">📄 Descargar PDF</a></p>
            <hr>
            <pre>{html.escape(resultado)}</pre>
            <br><a href="/">Volver</a>
            """

        except Exception:
            pass

        resultado = debug_charlotte(direccion)

        return f"""
        <h2>Debug Charlotte County</h2>
        <p><b>{VERSION}</b></p>
        <p><b>Dirección:</b> {html.escape(direccion)}</p>
        <hr>
        <pre>{html.escape(resultado)}</pre>
        <br><a href="/">Volver</a>
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

        nombre = limpiar(direccion) + "_" + folio + "_" + str(int(time.time())) + ".pdf"
        ruta = os.path.join(DOWNLOAD_DIR, nombre)

        page.pdf(path=ruta, format="Letter", print_background=True)

        browser.close()

        return f"Lee OK\nFolio: {folio}\nURL: {url}", f"/downloads/{nombre}"


def debug_charlotte(direccion):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            chromium_sandbox=False,
            args=["--disable-dev-shm-usage"]
        )

        page = browser.new_page(viewport={"width": 1400, "height": 1200})

        page.goto("https://www.ccappraiser.com/", timeout=60000)
        page.wait_for_timeout(5000)

        reporte = []
        reporte.append("=== CHARLOTTE DEBUG MENU ===")
        reporte.append(f"Dirección recibida: {direccion}")
        reporte.append(f"URL inicial: {page.url}")
        reporte.append(f"Título inicial: {page.title()}")
        reporte.append("")

        try:
            page.locator("text=Real Property").first.hover(timeout=10000)
            page.wait_for_timeout(2000)

            page.locator("text=Real Property").nth(1).click(timeout=10000)
            page.wait_for_timeout(7000)

            reporte.append("Navegación menú Real Property: OK")
        except Exception as e:
            reporte.append("Navegación menú Real Property: FALLÓ")
            reporte.append(str(e))

        reporte.append("")
        reporte.append(f"URL final: {page.url}")
        reporte.append(f"Título final: {page.title()}")
        reporte.append("")

        try:
            texto = page.locator("body").inner_text(timeout=10000)
            reporte.append("=== TEXTO DE LA PÁGINA ===")
            reporte.append(texto[:4000])
            reporte.append("")
        except Exception as e:
            reporte.append(f"No pude leer texto: {e}")
            reporte.append("")

        try:
            elementos = page.evaluate("""
            () => {
                const els = Array.from(document.querySelectorAll('input, button, select, textarea, a'));
                return els.map((el, i) => ({
                    index: i,
                    tag: el.tagName,
                    type: el.getAttribute('type'),
                    id: el.id,
                    name: el.getAttribute('name'),
                    placeholder: el.getAttribute('placeholder'),
                    value: el.getAttribute('value'),
                    text: el.innerText,
                    visible: !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length)
                }));
            }
            """)

            reporte.append("=== ELEMENTOS DETECTADOS ===")
            for e in elementos[:180]:
                reporte.append(str(e))

        except Exception as e:
            reporte.append(f"No pude leer elementos: {e}")

        browser.close()

        return "\n".join(reporte)
