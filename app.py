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

VERSION = "VERSION 16 - AUTO CONDADO + LEE ROBUSTO"

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
        condado = detectar_condado(direccion)

        # Si no sabe el condado, intenta Lee primero
        if condado in ["lee", "desconocido"]:
            resultado, pdf_url = buscar_lee(direccion)
            condado_final = "LEE"
        elif condado == "collier":
            return """
            <h2>Collier todavía no está programado</h2>
            <p>Primero terminamos Lee, después hacemos Collier.</p>
            <a href="/">Volver</a>
            """
        elif condado == "hendry":
            return """
            <h2>Hendry todavía no está programado</h2>
            <p>Primero terminamos Lee, después hacemos Hendry.</p>
            <a href="/">Volver</a>
            """
        else:
            raise Exception("No pude detectar el condado.")

        return f"""
        <h2>Resultado</h2>
        <p><b>{VERSION}</b></p>
        <p><b>Dirección:</b> {html.escape(direccion)}</p>
        <p><b>Condado usado:</b> {condado_final}</p>

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


def detectar_condado(direccion):
    d = direccion.lower()

    if any(x in d for x in [
        "cape coral", "fort myers", "lehigh", "lehigh acres",
        "bonita springs", "estero", "sanibel", "pine island"
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

        page.goto("https://www.leepa.org/Search/PropertySearch.aspx", timeout=60000)

        campo = "#ctl00_BodyContentPlaceHolder_WebTab1_tmpl0_AddressTextBox"

        page.wait_for_selector(campo, timeout=30000)
        page.fill(campo, direccion)
        page.press(campo, "Enter")

        page.wait_for_timeout(9000)

        texto_resultados = page.locator("body").inner_text(timeout=30000)

        # Buscar link Parcel Details de varias formas
        link = page.evaluate("""
        () => {
            const links = Array.from(document.querySelectorAll('a'));

            let a = links.find(x =>
                x.innerText &&
                x.innerText.toLowerCase().includes('parcel details')
            );

            if (a) return a.href;

            a = links.find(x =>
                x.href &&
                (
                    x.href.includes('DisplayParcel') ||
                    x.href.includes('FolioID')
                )
            );

            if (a) return a.href;

            return null;
        }
        """)

        if not link:
            raise Exception(
                "No se encontró Parcel Details. Texto de la página:\n\n"
                + texto_resultados[:3000]
            )

        parsed = urlparse(link)
        params = parse_qs(parsed.query)
        folio = params.get("FolioID", [""])[0]

        if not folio:
            raise Exception("Encontré el link, pero no pude extraer FolioID: " + link)

        url = f"https://www.leepa.org/Display/DisplayParcel.aspx?FolioID={folio}"
        page.goto(url, timeout=60000)

        page.wait_for_timeout(5000)

        # Click Continue
        try:
            page.locator("text=Continue").click(timeout=8000)
            page.wait_for_timeout(8000)
        except:
            try:
                page.evaluate("""
                () => {
                    const all = Array.from(document.querySelectorAll('*'));
                    const btn = all.find(el =>
                        el.innerText &&
                        el.innerText.trim().toLowerCase() === 'continue'
                    );
                    if (btn) btn.click();
                }
                """)
                page.wait_for_timeout(8000)
            except:
                pass

        page.wait_for_timeout(5000)

        texto_final = page.locator("body").inner_text(timeout=30000)

        nombre = limpiar(direccion) + "_" + folio + "_" + str(int(time.time())) + ".pdf"
        ruta = os.path.join(DOWNLOAD_DIR, nombre)

        page.pdf(
            path=ruta,
            format="Letter",
            print_background=True
        )

        browser.close()

        return f"Folio: {folio}\nURL: {url}\n\nTexto inicial:\n{texto_final[:1500]}", f"/downloads/{nombre}"
