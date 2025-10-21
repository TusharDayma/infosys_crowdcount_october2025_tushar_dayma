from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
import os
import datetime
import logging
from typing import Dict

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def generate_pdf(person_id: str, info: Dict) -> str:
    """Generate a PDF report for a person with a table format."""
    filename = f"{person_id}_report.pdf"
    filepath = os.path.join("reports", filename)
    os.makedirs("reports", exist_ok=True)

    try:
        doc = SimpleDocTemplate(filepath, pagesize=A4)
        elements = []
        styles = getSampleStyleSheet()

        # Title
        elements.append(Paragraph("Crowd Monitoring Report", styles['Title']))

        # Timestamp
        elements.append(Paragraph(f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))

        # Table data
        data = [["Person ID", person_id]]
        for key, value in info.items():
            if key != "Neutral Time (s)":  # Exclude neutral time
                data.append([key, str(value)])
        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(table)

        doc.build(elements)
        logger.info(f"Generated PDF report: {filepath}")
        return filepath
    except Exception as e:
        logger.error(f"Error generating PDF: {e}")
        raise