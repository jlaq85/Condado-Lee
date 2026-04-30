from flask import Flask, request, send_file
from playwright.sync_api import sync_playwright
import time
import os

app = Flask(__name__)

# =========================
# 🔹 DETECTAR CONDADO
# =========================
def detectar_condado(direccion):
    direccion = direccion.lower()

    if "cape coral" in direccion or "fort myers" in direccion:
        return "lee"

    if "port charlotte" in direccion or "charlotte" in direccion:
        return "charlotte"

    # fallback
    return "lee"


# =========================
# 🔹 SEPARAR DIRECCIÓN (Charlotte)
# =========================
def separar_direccion(direccion):
    partes = direccion.strip().split(" ", 1)

    numero = partes[0]
    calle = partes[1] if len(partes) > 1 else ""

    return numero, calle


# =========================
# 🔹 LEE COUNTY
# =========================
def buscar_lee(playwright, direccion):
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page()

    page.goto("https://www.leepa.org/Search/PropertySearch.aspx")

    page.fill("#ctl00_BodyContentPlaceHolder_WebTab1_tmpl0_AddressSearch1_txtAddress", direccion)
    page.click("#ctl00_BodyContentPlaceHolder_WebTab1_tmpl0_AddressSearch1_btnSearch")

    page.wait_for_timeout(5000)

    # entrar al primer resultado
    page.click("a[href*='Details']")
    page.wait_for_timeout(5000)

    # aceptar condiciones si aparece
    try:
        page.click("text=Continue", timeout=3000)
    except:
        pass

    page.wait_for_timeout(3000)

    pdf_path = f"downloads/lee_{int(time.time())}.pdf"
    page.pdf(path=pdf_path)

    browser.close()
    return pdf_path


# =========================
# 🔹 CHARLOTTE COUNTY
# =========================
def buscar_charlotte(playwright, direccion):
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page()

    page.goto("https://www.ccappraiser.com/RPSearchEnter.asp")

    numero, calle = separar_direccion(direccion)

    # llenar campos
    page.fill('input[name="PropertyAddressNumber"]', numero)
    page.fill('input[name="PropertyAddressStreet"]', calle)

    # click search
    page.click('text=Run Search')

    page.wait_for_timeout(6000)

    # entrar al primer resultado
    try:
        page.click("a[href*='RPDetail']", timeout=5000)
    except:
        pass

    page.wait_for_timeout(5000)

    pdf_path = f"downloads/charlotte_{int(time.time())}.pdf"
    page.pdf(path=pdf_path)

    browser.close()
    return pdf_path


# =========================
# 🔹 BUSCADOR PRINCIPAL
# =========================
def buscar(direccion):
    condado = detectar_condado(direccion)

    with sync_playwright() as playwright:

        if condado == "lee":
            return buscar_lee(playwright, direccion)

        if condado == "charlotte":
            return buscar_charlotte(playwright, direccion)

        return buscar_lee(playwright, direccion)


# =========================
# 🔹 RUTA WEB
# =========================
@app.route("/buscar")
def buscar_route():
    direccion = request.args.get("direccion")

    if not direccion:
        return "Falta dirección"

    pdf_path = buscar(direccion)

    return send_file(pdf_path, as_attachment=True)


# =========================
# 🔹 MAIN
# =========================
if __name__ == "__main__":
    os.makedirs("downloads", exist_ok=True)
    app.run(debug=True)
