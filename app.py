from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
import traceback
import html

app = FastAPI()

VERSION = "VERSION 6 - BUSQUEDA CON ENTER"

@app.get("/", response_class=HTMLResponse)
def home():
    return f"""
    <h2>Buscar propiedad</h2>
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
        resultado = buscar_lee(direccion)

        return f"""
        <h2>Resultado</h2>
        <p><b>{VERSION}</b></p>
        <p><b>Dirección:</b> {html.escape(direccion)}</p>
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

def buscar_lee(direccion):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            chromium_sandbox=False,
            args=["--disable-dev-shm-usage"]
        )

        page = browser.new_page()
        page.goto("https://www.leepa.org/Search/PropertySearch.aspx", timeout=60000)

        campo_direccion = "#ctl00_BodyContentPlaceHolder_WebTab1_tmpl0_AddressTextBox"

        page.wait_for_selector(campo_direccion, timeout=30000)
        page.fill(campo_direccion, direccion)

        # En vez de buscar el botón, presionamos ENTER dentro del campo
        page.press(campo_direccion, "Enter")

        page.wait_for_timeout(8000)

        texto = page.locator("body").inner_text(timeout=30000)

        browser.close()

        return texto[:8000]
