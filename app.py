from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
from playwright.sync_api import sync_playwright

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
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        page.goto("https://www.leepa.org/Search/PropertySearch.aspx")

        title = page.title()

        browser.close()

    return f"<h3>OK</h3><p>{direccion}</p><p>{title}</p>"
