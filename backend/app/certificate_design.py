import io

import qrcode
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


def draw_logo(pdf, x, y):
    """логотип сайта"""
    pdf.saveState()
    pdf.translate(x - 34, y + 34)
    pdf.scale(68 / 48, -68 / 48)
    pdf.setStrokeColor(HexColor("#176B9A"))
    pdf.setFillColor(HexColor("#176B9A"))
    pdf.setLineWidth(1.7)
    outline = pdf.beginPath()
    outline.moveTo(24, 3)
    for point in [(40, 13), (40, 34), (24, 45), (8, 34), (8, 13)]:
        outline.lineTo(*point)
    outline.close()
    pdf.drawPath(outline, stroke=1, fill=0)
    mountain = pdf.beginPath()
    mountain.moveTo(13, 31)
    mountain.lineTo(24, 13)
    mountain.lineTo(35, 31)
    mountain.close()
    pdf.drawPath(mountain, fill=1, stroke=0)
    pdf.setStrokeColor(HexColor("#FFFFFF"))
    pdf.setLineWidth(1.6)
    notch = pdf.beginPath()
    notch.moveTo(19, 22)
    notch.lineTo(24, 25)
    notch.lineTo(29, 22)
    pdf.drawPath(notch)
    pdf.setStrokeColor(HexColor("#176B9A"))
    pdf.setLineWidth(1.4)
    for points in [
        (24, 3, 24, 10),
        (24, 38, 24, 45),
        (8, 13, 14, 17),
        (34, 31, 40, 34),
        (8, 34, 14, 31),
        (34, 17, 40, 13),
    ]:
        pdf.line(*points)
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
    draw_logo(pdf, 100, 465)
    pdf.showPage()
    pdf.save()
    return output.getvalue()
