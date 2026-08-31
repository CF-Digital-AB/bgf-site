"""Generate the printable Boden GameFest 2027 interest survey as a PDF.

Fixed version:
- writes the HTML and PDF inside this project (output/), not /mnt/data
- creates the output directory if it is missing

Run with:  .venv/bin/python generate_pdf.py
"""

import os

from weasyprint import HTML

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

html_content = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
    @page {
        size: A4;
        margin: 20mm;
        background-color: #ffffff;
    }
    body {
        font-family: "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        color: #1a1a24;
        margin: 0;
        padding: 0;
        line-height: 1.5;
    }
    *, *::before, *::after {
        box-sizing: border-box;
    }
    .header {
        text-align: center;
        border-bottom: 3px solid #7b2cbf;
        padding-bottom: 15px;
        margin-bottom: 30px;
    }
    h1 {
        font-size: 28pt;
        font-weight: 900;
        margin: 0 0 10px 0;
        text-transform: uppercase;
        letter-spacing: 2px;
        color: #100f14;
    }
    .subtitle {
        font-size: 16pt;
        font-weight: 700;
        color: #7b2cbf;
        margin: 0 0 10px 0;
    }
    .tags {
        font-size: 11pt;
        font-weight: 600;
        color: #555;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    h2 {
        font-size: 20pt;
        margin-bottom: 5px;
    }
    h3 {
        font-size: 14pt;
        font-weight: 400;
        color: #666;
        margin-top: 0;
        margin-bottom: 25px;
    }
    .form-group {
        margin-bottom: 20px;
        page-break-inside: avoid;
    }
    .question {
        font-weight: 600;
        font-size: 11pt;
        margin-bottom: 8px;
        display: block;
    }
    .option-item {
        display: inline-block;
        margin-right: 20px;
        margin-bottom: 8px;
        font-size: 10.5pt;
    }
    .box {
        display: inline-block;
        width: 14px;
        height: 14px;
        border: 2px solid #888;
        border-radius: 2px;
        vertical-align: middle;
        margin-right: 6px;
        position: relative;
        top: -2px;
    }
    .text-line {
        border-bottom: 1px solid #999;
        width: 100%;
        height: 25px;
        display: block;
        margin-top: 5px;
    }
    .text-area {
        border: 1px solid #999;
        border-radius: 4px;
        width: 100%;
        height: 50px;
        display: block;
        margin-top: 5px;
    }
    .note {
        font-size: 9pt;
        color: #666;
        font-style: italic;
        margin-top: 4px;
    }
    .highlight-box {
        background-color: #f4f0fa;
        border-left: 4px solid #7b2cbf;
        padding: 15px;
        margin: 25px 0;
        page-break-inside: avoid;
    }
    .highlight-box .question {
        color: #5a1e8c;
        font-size: 12pt;
    }
</style>
</head>
<body>
    <div class="header">
        <h1>BODEN GAMEFEST 2027</h1>
        <div class="subtitle">6–9 MAJ &bull; BODEN</div>
        <div class="tags">Gaming &bull; LAN &bull; Esport &bull; Game Dev &bull; Indie &bull; Creators</div>
    </div>

    <h2>Är du intresserad?</h2>
    <h3>Intresseformulär</h3>

    <div class="form-group">
        <span class="question">1. Ålder/intervall</span>
        <div class="option-item"><span class="box"></span> Under 15</div>
        <div class="option-item"><span class="box"></span> 15-18</div>
        <div class="option-item"><span class="box"></span> 19-25</div>
        <div class="option-item"><span class="box"></span> 26-35</div>
        <div class="option-item"><span class="box"></span> 36+</div>
    </div>

    <div class="form-group">
        <span class="question">2. Ort (Var bor du?)</span>
        <div class="text-line" style="max-width: 400px;"></div>
    </div>

    <div class="form-group">
        <span class="question">3. Skulle du vilja delta på LAN?</span>
        <div class="option-item"><span class="box"></span> Ja</div>
        <div class="option-item"><span class="box"></span> Nej</div>
        <div class="option-item"><span class="box"></span> Kanske</div>
    </div>

    <div class="form-group">
        <span class="question">4. Skulle du komma som vanlig besökare?</span>
        <div class="option-item"><span class="box"></span> Ja</div>
        <div class="option-item"><span class="box"></span> Nej</div>
        <div class="option-item"><span class="box"></span> Kanske</div>
    </div>

    <div class="highlight-box">
        <span class="question">Viktig fråga: Vilket av detta skulle få dig att åka till Boden GameFest? (Flera val möjliga)</span>
        <div class="option-item" style="width: 45%;"><span class="box"></span> LAN & spela med vänner</div>
        <div class="option-item" style="width: 45%;"><span class="box"></span> E-sport turneringar</div>
        <div class="option-item" style="width: 45%;"><span class="box"></span> Indie games-utställning</div>
        <div class="option-item" style="width: 45%;"><span class="box"></span> Game-dev & nätverkande</div>
        <div class="option-item" style="width: 45%;"><span class="box"></span> Föreläsningar & inspiration</div>
        <div class="option-item" style="width: 45%;"><span class="box"></span> Retro-gaming</div>
        <div class="option-item" style="width: 45%;"><span class="box"></span> Gemenskapen & stämningen</div>
        <div class="option-item" style="width: 45%;"><span class="box"></span> Annat: <span style="border-bottom: 1px solid #999; width: 120px; display: inline-block;"></span></div>
    </div>

    <div class="form-group">
        <span class="question">5. Vilka spel spelar du?</span>
        <div class="text-area"></div>
    </div>

    <div class="form-group">
        <span class="question">6. Vilka turneringar vill du se?</span>
        <div class="text-area"></div>
    </div>

    <div class="form-group">
        <span class="question">7. Vilket av följande är du också intresserad av? (Kryssa för)</span>
        <div class="option-item" style="width: 100%;"><span class="box"></span> Game-dev (Spelutveckling)</div>
        <div class="option-item" style="width: 100%;"><span class="box"></span> Föreläsningar</div>
        <div class="option-item" style="width: 100%;"><span class="box"></span> Indie games</div>
        <div class="option-item" style="width: 100%;"><span class="box"></span> Retro</div>
    </div>

    <div class="form-group" style="margin-top: 15px;">
        <span class="question">8. Hur långt skulle du kunna resa?</span>
        <div class="option-item"><span class="box"></span> Lokalt (Boden/Fyrkanten)</div>
        <div class="option-item"><span class="box"></span> Inom Norrbotten</div>
        <div class="option-item"><span class="box"></span> Utanför länet / Längre</div>
    </div>

    <div class="form-group">
        <span class="question">9. Ungefär vilket pris känns rimligt för LAN-pass?</span>
        <div class="text-line" style="max-width: 250px;"></div>
    </div>

    <div class="form-group">
        <span class="question">10. Vill du hjälpa till som funktionär?</span>
        <div class="option-item"><span class="box"></span> Ja</div>
        <div class="option-item"><span class="box"></span> Nej</div>
        <div class="option-item"><span class="box"></span> Kanske, berätta mer</div>
    </div>

    <div class="form-group" style="margin-top: 20px;">
        <span class="question">11. E-post för information när biljetter släpps (Frivilligt)</span>
        <div class="text-line"></div>
        <div class="note">* För att undvika att samla onödig persondata används e-postadressen enbart för informationsutskick och raderas därefter. Inga andra uppgifter knyts till dig.</div>
    </div>
</body>
</html>"""


def main() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    html_path = os.path.join(OUTPUT_DIR, "Boden_GameFest_Form.html")
    pdf_path = os.path.join(OUTPUT_DIR, "Boden_GameFest_Formular.pdf")

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    HTML(filename=html_path).write_pdf(pdf_path)
    print(f"Generated PDF at {pdf_path}")


if __name__ == "__main__":
    main()
