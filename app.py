from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import traceback, html, os, re, time
from urllib.parse import urlparse, parse_qs

app = FastAPI()
VERSION = "VERSION 34 - FIX DEED LOCATOR"

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
app.mount("/downloads", StaticFiles(directory=DOWNLOAD_DIR), name="downloads")


@app.get("/", response_class=HTMLResponse)
def home():
    return f"""
    <h2>Buscar propiedad + Deed</h2>
    <p><b>{VERSION}</b></p>
    <form method="post" action="/buscar">
        Dirección:<br>
        <input name="direccion" style="width:420px"><br><br>
        <button type="submit">Buscar y crear PDFs</button>
    </form>
    """


@app.post("/buscar", response_class=HTMLResponse)
def buscar(direccion: str = Form(...)):
    try:
        try:
            resultado = buscar_lee(direccion)
            condado = "Lee"
        except Exception:
            resultado = buscar_charlotte(direccion)
            condado = "Charlotte"

        return f"""
        <h2>Resultado</h2>
        <p><b>{VERSION}</b></p>
        <p><b>Dirección:</b> {html.escape(direccion)}</p>
        <p><b>Condado:</b> {condado}</p>

        <p><a href="{resultado['parcel_pdf']}" target="_blank" style="font-size:20px;">📄 Descargar Property PDF</a></p>
        <p><a href="{resultado['deed_pdf']}" target="_blank" style="font-size:20px;">📄 Descargar Deed PDF</a></p>

        <hr>
        <pre>{html.escape(resultado['reporte'])}</pre>
        <br><a href="/">Volver</a>
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


def normalizar_direccion(texto):
    texto = texto.upper().strip()
    texto = re.sub(r"[^A-Z0-9 ]", " ", texto)
    texto = re.sub(r"\s+", " ", texto)
    return texto


def separar_direccion_charlotte(direccion):
    partes = direccion.strip().split(" ", 1)
    numero = partes[0]
    calle = partes[1] if len(partes) > 1 else ""
    return numero, calle


def guardar_pdf(page, nombre):
    ruta = os.path.join(DOWNLOAD_DIR, nombre)
    page.pdf(path=ruta, format="Letter", print_background=True)
    return f"/downloads/{nombre}"


def abrir_link_y_guardar_pdf(context, page, link_locator, nombre_pdf):
    try:
        with context.expect_page(timeout=10000) as nueva:
            link_locator.click(timeout=10000)
        deed_page = nueva.value
        deed_page.wait_for_timeout(7000)
    except:
        link_locator.click(timeout=10000)
        deed_page = page
        deed_page.wait_for_timeout(7000)

    pdf_url = guardar_pdf(deed_page, nombre_pdf)
    return pdf_url, deed_page.url


def buscar_lee(direccion):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            chromium_sandbox=False,
            args=["--disable-dev-shm-usage"]
        )

        context = browser.new_context()
        page = context.new_page()
        page.set_viewport_size({"width": 1280, "height": 1800})

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

        folio = parse_qs(urlparse(link).query).get("FolioID", [""])[0]

        if not folio:
            raise Exception("Lee encontró link, pero no FolioID")

        parcel_url = f"https://www.leepa.org/Display/DisplayParcel.aspx?FolioID={folio}&SalesDetails=True#SalesDetails"
        page.goto(parcel_url, timeout=60000)
        page.wait_for_timeout(6000)

        try:
            page.locator("text=Continue").click(timeout=8000)
            page.wait_for_timeout(8000)
        except:
            pass

        parcel_pdf = guardar_pdf(
            page,
            limpiar(direccion) + "_lee_property_" + folio + "_" + str(int(time.time())) + ".pdf"
        )

        deed_link = page.locator("a").filter(has_text=re.compile(r"^\d{10,}$")).first

        if deed_link.count() == 0:
            raise Exception("No encontré Clerk File Number / Deed en Lee.")

        deed_pdf, deed_url = abrir_link_y_guardar_pdf(
            context,
            page,
            deed_link,
            limpiar(direccion) + "_lee_deed_" + str(int(time.time())) + ".pdf"
        )

        browser.close()

        return {
            "parcel_pdf": parcel_pdf,
            "deed_pdf": deed_pdf,
            "reporte": f"Lee OK\nFolio: {folio}\nParcel URL: {parcel_url}\nDeed URL: {deed_url}"
        }


def buscar_charlotte(direccion):
    from playwright.sync_api import sync_playwright

    numero, calle = separar_direccion_charlotte(direccion)
    direccion_exacta = normalizar_direccion(direccion)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            chromium_sandbox=False,
            args=["--disable-dev-shm-usage"]
        )

        context = browser.new_context()
        page = context.new_page()
        page.set_viewport_size({"width": 1400, "height": 1400})

        page.goto("https://www.ccappraiser.com/RPSearchEnter.asp", timeout=60000)
        page.wait_for_timeout(5000)

        page.fill('input[name="PropertyAddressNumber"]', numero)

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
            raise Exception("No pude detectar campo de calle en Charlotte.")

        page.fill(f'input[name="{campo_calle}"]', calle)

        try:
            page.click('input[value*="Run Search"]', timeout=10000)
        except:
            page.locator("text=Run Search").click(timeout=10000)

        page.wait_for_timeout(9000)

        parcel_info = page.evaluate("""
        (direccionExacta) => {
            function norm(t) {
                return (t || "")
                    .toUpperCase()
                    .replace(/[^A-Z0-9 ]/g, " ")
                    .replace(/\\s+/g, " ")
                    .trim();
            }

            const rows = Array.from(document.querySelectorAll("tr"));

            for (const row of rows) {
                const rowText = norm(row.innerText);
                if (rowText.includes(direccionExacta)) {
                    const link = row.querySelector("a");
                    if (link) {
                        return {
                            found: true,
                            href: link.href,
                            text: row.innerText
                        };
                    }
                }
            }

            return {
                found: false,
                href: null,
                text: document.body.innerText.slice(0, 3000)
            };
        }
        """, direccion_exacta)

        if not parcel_info["found"]:
            raise Exception("No encontré parcela exacta en Charlotte.")

        page.goto(parcel_info["href"], timeout=60000)
        page.wait_for_timeout(7000)

        parcel_pdf = guardar_pdf(
            page,
            limpiar(direccion) + "_charlotte_property_" + str(int(time.time())) + ".pdf"
        )

        deed_link = page.locator("a").filter(has_text=re.compile(r"^\d{5,}$")).first

        if deed_link.count() == 0:
            raise Exception("No encontré Instrument Number / Deed en Charlotte.")

        deed_pdf, deed_url = abrir_link_y_guardar_pdf(
            context,
            page,
            deed_link,
            limpiar(direccion) + "_charlotte_deed_" + str(int(time.time())) + ".pdf"
        )

        browser.close()

        return {
            "parcel_pdf": parcel_pdf,
            "deed_pdf": deed_pdf,
            "reporte": f"Charlotte OK\nNúmero: {numero}\nCalle: {calle}\nParcel URL: {parcel_info['href']}\nDeed URL: {deed_url}"
        }
