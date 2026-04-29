from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import traceback
import html
import os
import re
import time
from urllib.parse import urljoin, urlparse, parse_qs

app = FastAPI()

VERSION = "VERSION 13 - EXTRAER FOLIO DESDE LINK"

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


def limpiar_nombre(texto):
    texto = texto.lower()
    texto = re.sub(r"[^a-z0-9]+", "_", texto)
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

        page.wait_for_selector(campo)
        page.fill(campo, direccion)
        page.press(campo, "Enter")

        page.wait_for_timeout(7000)

        # 🔥 EXTRAER LINK REAL DE PARCEL DETAILS
        parcel_link = page.evaluate("""
        () => {
            const links = Array.from(document.querySelectorAll('a'));
            const link = links.find(a => a.innerText.includes('Parcel Details'));
            return link ? link.href : null;
        }
        """)

        if not parcel_link:
            raise Exception("No encontré el link Parcel Details")

        # 🔥 EXTRAER FOLIO ID DEL LINK
        parsed = urlparse(parcel_link)
        params = parse_qs(parsed.query)

        if "FolioID" not in params:
            raise Exception("No encontré FolioID en el link")

        folio_id = params["FolioID"][0]

        # Ir directo al parcel
        final_url = f"https://www.leepa.org/Display/DisplayParcel.aspx?FolioID={folio_id}"
        page.goto(final_url)

        page.wait_for_timeout(5000)

        # Aceptar Continue
        try:
            page.evaluate("""
            () => {
                const btns = Array.from(document.querySelectorAll('button, input'));
                const b = btns.find(x =>
                    (x.innerText && x.innerText.toLowerCase().includes('continue')) ||
                    (x.value && x.value.toLowerCase().includes('continue'))
                );
                if (b) b.click();
            }
            """)
            page.wait_for_timeout(8000)
        except:
            pass

        texto = page.locator("body").inner_text()

        # Crear PDF
        nombre = limpiar_nombre(direccion) + "_" + folio_id + "_" + str(int(time.time())) + ".pdf"
        ruta = os.path.join(DOWNLOAD_DIR, nombre)

        page.pdf(path=ruta, format="Letter", print_background=True)

        browser.close()

        return f"FolioID: {folio_id}\nURL: {final_url}", f"/downloads/{nombre}"
