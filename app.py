from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
import traceback
import html

app = FastAPI()

VERSION = "VERSION 4 - DEBUG LEEPA"

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
        page.wait_for_timeout(5000)

        title = page.title()
        url_inicial = page.url

        # Obtener todos los campos y botones para saber exactamente cómo se llaman
        campos = page.evaluate("""
        () => {
            const elementos = Array.from(document.querySelectorAll('input, button, select, textarea'));
            return elementos.map((e, i) => ({
                index: i,
                tag: e.tagName,
                type: e.getAttribute('type'),
                id: e.id,
                name: e.getAttribute('name'),
                value: e.getAttribute('value'),
                placeholder: e.getAttribute('placeholder'),
                text: e.innerText,
                visible: !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length)
            }));
        }
        """)

        reporte = []
        reporte.append("=== ESTADO INICIAL ===")
        reporte.append(f"Título: {title}")
        reporte.append(f"URL: {url_inicial}")
        reporte.append("")
        reporte.append("=== CAMPOS DETECTADOS EN LEEPA ===")

        for c in campos:
            reporte.append(
                f"[{c.get('index')}] tag={c.get('tag')} "
                f"type={c.get('type')} "
                f"id={c.get('id')} "
                f"name={c.get('name')} "
                f"value={c.get('value')} "
                f"placeholder={c.get('placeholder')} "
                f"visible={c.get('visible')} "
                f"text={c.get('text')}"
            )

        reporte.append("")
        reporte.append("=== INTENTANDO BUSCAR DIRECCIÓN ===")

        intento = False

        selectores_direccion = [
            "input[id*='Address']",
            "input[name*='Address']",
            "input[id*='address']",
            "input[name*='address']",
            "xpath=//*[contains(normalize-space(.), 'Street Address')]/following::input[1]"
        ]

        for selector in selectores_direccion:
            try:
                loc = page.locator(selector).first()
                if loc.count() > 0:
                    loc.fill(direccion, timeout=5000)
                    reporte.append(f"Dirección escrita usando selector: {selector}")
                    intento = True
                    break
            except Exception as e:
                reporte.append(f"No funcionó selector dirección: {selector} | {str(e)}")

        if not intento:
            reporte.append("NO pude encontrar el campo de dirección.")
        else:
            selectores_boton = [
                "input[type='submit']",
                "button:has-text('Search')",
                "input[value*='Search']",
                "input[id*='Search']",
                "input[name*='Search']",
                "xpath=//*[contains(normalize-space(.), 'Search')]/following::input[1]"
            ]

            click_hecho = False

            for selector in selectores_boton:
                try:
                    loc = page.locator(selector).first()
                    if loc.count() > 0:
                        loc.click(timeout=5000)
                        reporte.append(f"Click hecho usando selector: {selector}")
                        click_hecho = True
                        break
                except Exception as e:
                    reporte.append(f"No funcionó selector botón: {selector} | {str(e)}")

            if not click_hecho:
                reporte.append("NO pude hacer click en el botón Search.")

            page.wait_for_timeout(7000)

        reporte.append("")
        reporte.append("=== DESPUÉS DEL INTENTO ===")
        reporte.append(f"Título final: {page.title()}")
        reporte.append(f"URL final: {page.url}")
        reporte.append("")
        reporte.append("=== TEXTO DE LA PÁGINA ===")
        reporte.append(page.locator("body").inner_text(timeout=10000)[:5000])

        browser.close()

        return "\n".join(reporte)
