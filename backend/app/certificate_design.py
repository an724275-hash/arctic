import io

import qrcode
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


def draw_bear(pdf, x, y):
    """A small flat mascot, drawn as vector shapes for sharp printing."""
    pdf.saveState()
    pdf.translate(x, y)
    pdf.setStrokeColor(HexColor("#286583"))
    pdf.setLineWidth(1.5)
    pdf.setFillColor(HexColor("#FFFFFF"))
    pdf.circle(-22, 18, 9, fill=1, stroke=1)
    pdf.circle(22, 18, 9, fill=1, stroke=1)
    pdf.ellipse(-30, -28, 30, 30, fill=1, stroke=1)
    pdf.setFillColor(HexColor("#2C7DA8"))
    pdf.roundRect(-30, 17, 60, 19, 7, fill=1, stroke=0)
    pdf.setFillColor(HexColor("#C9EAF8"))
    pdf.roundRect(-31, 13, 62, 8, 4, fill=1, stroke=0)
    pdf.setFillColor(HexColor("#183847"))
    pdf.circle(-12, 1, 2.5, fill=1, stroke=0)
    pdf.circle(12, 1, 2.5, fill=1, stroke=0)
    pdf.ellipse(-5, -12, 5, -5, fill=1, stroke=0)
    pdf.line(0, -12, 0, -17)
    pdf.arc(-10, -21, 10, -9, 200, 140)
    pdf.restoreState()


def render_document(certificate, user, font, verify_url, fit):
    output = io.BytesIO()
    width, height = landscape(A4)
    pdf = canvas.Canvas(output, pagesize=(width, height), pageCompression=1)
    pdf.setTitle(f"Арктика — {certificate.number}")
    pdf.setAuthor("Удивительная и неизведанная Арктика")
    pdf.setFillColor(HexColor("#B7DFF2"))
    pdf.rect(0, 0, width, height, fill=1, stroke=0)
    pdf.setFillColor(HexColor("#2B7CA7"))
    ridge = pdf.beginPath()
    ridge.moveTo(0, 0)
    for x, y in [
        (0, 112),
        (90, 77),
        (176, 132),
        (270, 94),
        (420, 144),
        (535, 75),
        (700, 123),
        (width, 89),
        (width, 0),
    ]:
        ridge.lineTo(x, y)
    ridge.close()
    pdf.drawPath(ridge, fill=1, stroke=0)
    pdf.setFillColor(HexColor("#FFFFFF"))
    pdf.roundRect(32, 32, width - 64, height - 64, 12, fill=1, stroke=0)
    pdf.setFillColor(HexColor("#176B9A"))
    pdf.rect(54, height - 72, width - 108, 4, fill=1, stroke=0)
    pdf.setFont(font, 11)
    pdf.drawCentredString(width / 2, 510, "УДИВИТЕЛЬНАЯ И НЕИЗВЕДАННАЯ АРКТИКА")
    labels = {
        "test_passed": (
            "СЕРТИФИКАТ",
            "об успешном прохождении первого этапа",
            "Участник",
            "Подтверждает проходной результат тестирования",
        ),
        "test_participation": (
            "СЕРТИФИКАТ",
            "участника тестирования",
            "Участник",
            "Подтверждает участие в тестировании",
        ),
        "diploma": (
            "ГРАМОТА",
            "за достижения в конкурсе",
            "Получатель грамоты",
            "Основание награждения",
        ),
        "teacher_thanks": (
            "БЛАГОДАРНОСТЬ",
            "за сопровождение участников конкурса",
            "Наставник",
            "Основание благодарности",
        ),
    }
    title, subtitle, recipient, description = labels.get(certificate.kind, labels["test_participation"])
    pdf.setFillColor(HexColor("#183847"))
    fit(pdf, title, font, width / 2, 459, 620, 50, 34 if certificate.kind == "teacher_thanks" else 40)
    pdf.setFont(font, 14)
    pdf.drawCentredString(width / 2, 419, subtitle)
    pdf.setFillColor(HexColor("#496B7C"))
    pdf.setFont(font, 11)
    pdf.drawCentredString(width / 2, 383, recipient)
    pdf.setFillColor(HexColor("#176B9A"))
    fit(pdf, user.full_name, font, width / 2, 351, 640, 80, 28)
    pdf.setFillColor(HexColor("#496B7C"))
    fit(pdf, description, font, width / 2, 257, 640, 35, 12)
    pdf.setFillColor(HexColor("#183847"))
    fit(pdf, certificate.title, font, width / 2, 223, 620, 45, 17)
    mentor = getattr(certificate, "mentor_name", None)
    if mentor and certificate.kind != "teacher_thanks":
        pdf.setFillColor(HexColor("#496B7C"))
        fit(pdf, "Наставник: " + mentor, font, width / 2, 166, 530, 30, 11)
    pdf.setStrokeColor(HexColor("#B8D8E8"))
    pdf.setLineWidth(0.8)
    pdf.line(70, 125, width - 190, 125)
    pdf.setFillColor(HexColor("#183847"))
    pdf.setFont(font, 10)
    pdf.drawString(70, 100, "Номер документа: " + certificate.number)
    pdf.drawString(70, 80, f"Дата выдачи: {certificate.issued_at:%d.%m.%Y}")
    pdf.setFillColor(HexColor("#496B7C"))
    pdf.setFont(font, 8)
    pdf.drawString(
        70,
        57,
        "Демонстрационный образец, не наградной документ."
        if certificate.number.startswith("PREVIEW")
        else "Электронный документ. Проверка подлинности — по QR-коду.",
    )
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=7, border=4)
    qr.add_data(verify_url)
    qr.make(fit=True)
    png = io.BytesIO()
    qr.make_image(fill_color="#183847", back_color="white").save(png, format="PNG")
    png.seek(0)
    pdf.drawImage(ImageReader(png), width - 170, 57, width=100, height=100)
    draw_bear(pdf, 100, 465)
    pdf.showPage()
    pdf.save()
    return output.getvalue()
