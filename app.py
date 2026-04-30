from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import traceback, html, os, re, time
from urllib.parse import urlparse, parse_qs, urljoin

app = FastAPI()
VERSION = "VERSION 35 - DEEDS ROBUST DEBUG"

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
    errores = []

    try:
        try:
            resultado = buscar_lee(direccion)
            condado = "Lee"
        except Exception as e:
            errores.append("LEE FALLÓ:\n" + traceback.format_exc())
            resultado = buscar_charlotte(direccion)
            condado = "Charlotte"

        deed_html = ""
        if resultado.get("deed_pdf"):
            deed_html = f'<p><a href="{resultado["deed_pdf"]}" target="_blank" style="font-size:20px;">📄 Descargar Deed PDF</a></p>'
        else:
            deed_html = "<p><b>No se pudo crear Deed PDF todavía.</b></p>"

        return f"""
        <h2>Resultado</h2>
        <p><b>{VERSION}</b></p>
        <p><b>Dirección:</b> {html.escape(direccion)}</p>
        <p><b>Condado:</b> {condado}</p>

        <p><a href="{resultado['parcel_pdf']}" target="_blank" style="font-size:20px;">📄 Descargar Property PDF</a></p>
        {deed_html}

        <hr>
        <pre>{html.escape(resultado['reporte'])}</pre>
        <br><a href="/">Volver</a>
        """

    except Exception:
        error = traceback.format_exc()
        if errores:
            error = "\n\n".join(errores) + "\n\nERROR FINAL:\n" + error

        return f"""
        <h2>Error interno</h2>
        <p><b>{VERSION}</b></p>
        <pre>{html.escape(error)}</pre>
        <a href="/">Volver</a>
        """


def limpiar(texto):
    return re.sub(r"[^a-z0-9]", "_", texto.lower())[:60]


def normalizar(texto):
    texto = texto.upper().strip()
    texto = texto.replace("STREET", "ST")
    texto = texto.replace("AVENUE", "AVE")
    texto = texto.replace("ROAD", "RD")
    texto = texto.replace("DRIVE", "DR")
    texto = texto.replace("CIRCLE", "CIR")
    texto = texto.replace("COURT", "CT")
    texto = texto.replace("LANE", "LN")
    texto = re.sub(r"[^A-Z0-9 ]", " ", texto)
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def separar_direccion_charlotte(direccion):
    partes = direccion.strip().split(" ", 1)
    numero = partes[0]
    calle = partes[1] if len(partes) > 1 else ""
    return numero, calle


def guardar_pdf(page, nombre):
    ruta = os.path.join(DOWNLOAD_DIR, nombre)
    page.pdf(path=ruta, format="Letter", print_background=True)
    return f"/downloads/{nombre}"


def abrir_url_y_guardar_pdf(context, url, nombre_pdf):
    page = context.new_page()
    page.goto(url, timeout=60000)
    page.wait_for_timeout(8000)
    pdf_url = guardar_pdf(page, nombre_pdf)
    return pdf_url, page.url


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

        page.wait_for_timeout(4000)

        parcel_pdf = guardar_pdf(
            page,
            limpiar(direccion) + "_lee_property_" + folio + "_" + str(int(time.time())) + ".pdf"
        )

        deed_info = page.evaluate("""
        () => {
            const links = Array.from(document.querySelectorAll("a"));
            const candidates = links
                .map(a => ({
                    text: (a.innerText || "").trim(),
                    href: a.href || "",
                    row: a.closest("tr") ? a.closest("tr").innerText : ""
                }))
                .filter(x => /^\\d{8,}$/.test(x.text));

            return candidates;
        }
        """)

        deed_pdf = None
        deed_url = None

        if deed_info:
            deed_url = deed_info[0]["href"]
            deed_pdf, deed_final_url = abrir_url_y_guardar_pdf(
                context,
                deed_url,
                limpiar(direccion) + "_lee_deed_" + str(int(time.time())) + ".pdf"
            )
            deed_url = deed_final_url

        browser.close()

        reporte = f"""Lee OK
Folio: {folio}
Parcel URL: {parcel_url}

Deed candidates found:
{deed_info}

Deed URL opened:
{deed_url}
"""

        return {
            "parcel_pdf": parcel_pdf,
            "deed_pdf": deed_pdf,
            "reporte": reporte
        }


def buscar_charlotte(direccion):
    from playwright.sync_api import sync_playwright

    numero, calle = separar_direccion_charlotte(direccion)
    direccion_usuario = normalizar(direccion)

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
        (direccionUsuario) => {
            function norm(t) {
                return (t || "")
                    .toUpperCase()
                    .replace(/STREET/g, "ST")
                    .replace(/AVENUE/g, "AVE")
                    .replace(/ROAD/g, "RD")
                    .replace(/DRIVE/g, "DR")
                    .replace(/CIRCLE/g, "CIR")
                    .replace(/COURT/g, "CT")
                    .replace(/LANE/g, "LN")
                    .replace(/[^A-Z0-9 ]/g, " ")
                    .replace(/\\s+/g, " ")
                    .trim();
            }

            const rows = Array.from(document.querySelectorAll("tr"));
            const matches = [];

            for (const row of rows) {
                const rowText = norm(row.innerText);
                const link = row.querySelector("a");

                if (link && rowText.includes(direccionUsuario)) {
                    matches.push({
                        href: link.href,
                        text: row.innerText
                    });
                }
            }

            if (matches.length > 0) {
                return {found: true, href: matches[0].href, text: matches[0].text, all: matches};
            }

            return {
                found: false,
                href: null,
                text: document.body.innerText.slice(0, 3000),
                all: []
            };
        }
        """, direccion_usuario)

        if not parcel_info["found"]:
            raise Exception(
                "No encontré parcela exacta en Charlotte.\n"
                + "Dirección normalizada: " + direccion_usuario + "\n\n"
                + parcel_info["text"]
            )

        page.goto(parcel_info["href"], timeout=60000)
        page.wait_for_timeout(7000)

        parcel_pdf = guardar_pdf(
            page,
            limpiar(direccion) + "_charlotte_property_" + str(int(time.time())) + ".pdf"
        )

        deed_info = page.evaluate("""
        () => {
            const links = Array.from(document.querySelectorAll("a"));
            const candidates = links
                .map(a => ({
                    text: (a.innerText || "").trim(),
                    href: a.href || "",
                    row: a.closest("tr") ? a.closest("tr").innerText : ""
                }))
                .filter(x => /^\\d{5,}$/.test(x.text));

            return candidates;
        }
        """)

        deed_pdf = None
        deed_url = None

        if deed_info:
            deed_url = deed_info[0]["href"]
            deed_pdf, deed_final_url = abrir_url_y_guardar_pdf(
                context,
                deed_url,
                limpiar(direccion) + "_charlotte_deed_" + str(int(time.time())) + ".pdf"
            )
            deed_url = deed_final_url

        browser.close()

        reporte = f"""Charlotte OK
Número: {numero}
Calle: {calle}
Dirección normalizada: {direccion_usuario}
Parcel URL: {parcel_info['href']}

Fila encontrada:
{parcel_info['text']}

Deed candidates found:
{deed_info}

Deed URL opened:
{deed_url}
"""

        return {
            "parcel_pdf": parcel_pdf,
            "deed_pdf": deed_pdf,
            "reporte": reporte
        }
