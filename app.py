from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
import traceback

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <h2>Buscar propiedad</h2>
    <form method="post" action="/buscar">
        Dirección:<br>
        <input name="direccion" style="width:300px"><br><br>
        <button type="submit">Buscar</button>
    </form>
    """

@app.post("/buscar", response_class=HTMLResponse)
def buscar(direccion: str = Form(...)):
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"]
            )
            page = browser.new_page()
            page.goto("https://www.leepa.org/Search/PropertySearch.aspx", timeout=60000)
            title = page.title()
            browser.close()

        return f"""
        <h3>OK</h3>
        <p><b>Dirección:</b> {direccion}</p>
        <p><b>Título:</b> {title}</p>
        <a href="/">Volver</a>
        """

    except Exception as e:
        error = traceback.format_exc()
        return f"""
        <h3>Error interno</h3>
        <p>Esto es lo que falló:</p>
        <pre>{error}</pre>
        <a href="/">Volver</a>
        """
