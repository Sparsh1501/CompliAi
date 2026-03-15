"""
Report Export Service for CompliAI (Task #17)

Exports compliance reports in PDF and Word (DOCX) formats:
- Gap analysis reports with RBI citations
- Compliance check summaries
- Remediation plans
- Policy drafts
"""

import logging
import io
import json
from typing import Dict, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class ReportExportService:
    """Exports compliance reports to PDF and Word formats."""

    def __init__(self, db=None, gap_report_service=None):
        self.db = db
        self.gap_report_service = gap_report_service

    async def export_gap_report_docx(self, analysis_id: str) -> Optional[io.BytesIO]:
        """Export gap analysis report as Word document."""
        try:
            from docx import Document
            from docx.shared import Inches, Pt, RGBColor
            from docx.enum.text import WD_ALIGN_PARAGRAPH
        except ImportError:
            logger.warning("python-docx not installed. Install with: pip install python-docx")
            return None

        report = await self._get_or_generate_report(analysis_id)
        if not report or "error" in report:
            return None

        doc = Document()

        # Title
        title = doc.add_heading('Gap Analysis Report', level=0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # Metadata
        doc.add_paragraph(f"Policy: {report.get('policy_title', 'N/A')}")
        doc.add_paragraph(f"Regulation: {report.get('regulation_title', 'N/A')}")
        doc.add_paragraph(f"Generated: {report.get('generated_at', '')[:10]}")
        doc.add_paragraph("")

        # Executive Summary
        summary = report.get("executive_summary", {})
        doc.add_heading('Executive Summary', level=1)
        doc.add_paragraph(summary.get("narrative", ""))

        # Summary table
        table = doc.add_table(rows=5, cols=2)
        table.style = 'Table Grid'
        cells = [
            ("Total Requirements", str(summary.get("total_requirements_assessed", 0))),
            ("Compliant", str(summary.get("compliant_count", 0))),
            ("Compliance %", f"{summary.get('compliance_percentage', 0)}%"),
            ("Critical Gaps", str(summary.get("critical_gaps", 0))),
            ("High Severity", str(summary.get("high_severity_gaps", 0))),
        ]
        for i, (key, val) in enumerate(cells):
            table.rows[i].cells[0].text = key
            table.rows[i].cells[1].text = val

        doc.add_paragraph("")

        # Findings
        doc.add_heading('Detailed Findings', level=1)
        for finding in report.get("findings", []):
            gap_type = finding.get("gap_type", "missing")
            severity = finding.get("severity", "Medium")

            heading = doc.add_heading(
                f"Finding #{finding.get('finding_number', '')} - [{severity}] {gap_type.upper()}",
                level=2
            )

            if finding.get("description"):
                doc.add_paragraph(finding["description"])

            if finding.get("rbi_citation"):
                p = doc.add_paragraph()
                run = p.add_run(f"RBI Citation: {finding['rbi_citation']}")
                run.bold = True

            if finding.get("regulation_text"):
                doc.add_paragraph(f"Regulation Requirement: {finding['regulation_text'][:500]}")

            if finding.get("policy_text"):
                doc.add_paragraph(f"Policy Coverage: {finding['policy_text'][:500]}")

            if finding.get("suggested_fix"):
                p = doc.add_paragraph()
                run = p.add_run(f"Recommended Action: ")
                run.bold = True
                p.add_run(finding["suggested_fix"])

            if finding.get("missing_elements"):
                doc.add_paragraph(f"Missing Elements: {', '.join(finding['missing_elements'][:5])}")

            doc.add_paragraph("")

        # Citation Index
        citation_index = report.get("citation_index", {})
        if citation_index:
            doc.add_heading('RBI Citation Index', level=1)
            for citation, finding_nums in citation_index.items():
                doc.add_paragraph(f"{citation}: Findings #{', #'.join(str(n) for n in finding_nums)}")

        buffer = io.BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        return buffer

    async def export_gap_report_pdf(self, analysis_id: str) -> Optional[io.BytesIO]:
        """Export gap analysis report as PDF."""
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import inch
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.colors import HexColor
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        except ImportError:
            logger.warning("reportlab not installed. Install with: pip install reportlab")
            return None

        report = await self._get_or_generate_report(analysis_id)
        if not report or "error" in report:
            return None

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.75*inch, bottomMargin=0.75*inch)

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('CustomTitle', parent=styles['Title'], fontSize=18, spaceAfter=12)
        heading_style = ParagraphStyle('CustomH1', parent=styles['Heading1'], fontSize=14, spaceAfter=8)
        body_style = styles['Normal']

        story = []

        # Title
        story.append(Paragraph("Gap Analysis Report", title_style))
        story.append(Paragraph(f"Policy: {report.get('policy_title', 'N/A')}", body_style))
        story.append(Paragraph(f"Regulation: {report.get('regulation_title', 'N/A')}", body_style))
        story.append(Paragraph(f"Generated: {report.get('generated_at', '')[:10]}", body_style))
        story.append(Spacer(1, 0.3*inch))

        # Executive Summary
        summary = report.get("executive_summary", {})
        story.append(Paragraph("Executive Summary", heading_style))
        story.append(Paragraph(summary.get("narrative", ""), body_style))
        story.append(Spacer(1, 0.2*inch))

        # Summary table
        summary_data = [
            ["Metric", "Value"],
            ["Total Requirements", str(summary.get("total_requirements_assessed", 0))],
            ["Compliant", str(summary.get("compliant_count", 0))],
            ["Compliance %", f"{summary.get('compliance_percentage', 0)}%"],
            ["Critical Gaps", str(summary.get("critical_gaps", 0))],
            ["High Severity", str(summary.get("high_severity_gaps", 0))],
        ]
        t = Table(summary_data, colWidths=[3*inch, 2*inch])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#059669')),
            ('TEXTCOLOR', (0, 0), (-1, 0), HexColor('#FFFFFF')),
            ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#CCCCCC')),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.3*inch))

        # Findings
        story.append(Paragraph("Detailed Findings", heading_style))
        for finding in report.get("findings", [])[:30]:  # Limit to 30 for PDF size
            severity = finding.get("severity", "Medium")
            gap_type = finding.get("gap_type", "missing")
            story.append(Paragraph(
                f"<b>Finding #{finding.get('finding_number', '')} [{severity}] - {gap_type.upper()}</b>",
                body_style
            ))
            if finding.get("description"):
                story.append(Paragraph(finding["description"][:300], body_style))
            if finding.get("rbi_citation"):
                story.append(Paragraph(f"<i>RBI Citation: {finding['rbi_citation']}</i>", body_style))
            if finding.get("suggested_fix"):
                story.append(Paragraph(f"Action: {finding['suggested_fix'][:200]}", body_style))
            story.append(Spacer(1, 0.1*inch))

        doc.build(story)
        buffer.seek(0)
        return buffer

    async def export_policy_draft_docx(self, draft_id: str) -> Optional[io.BytesIO]:
        """Export a policy draft as Word document."""
        try:
            from docx import Document
            from docx.shared import Pt
            from docx.enum.text import WD_ALIGN_PARAGRAPH
        except ImportError:
            return None

        draft = await self.db.policy_drafts.find_one({"id": draft_id}, {"_id": 0})
        if not draft:
            return None

        doc = Document()
        content = draft.get("content", {})

        title = doc.add_heading(content.get("title", draft.get("title", "Policy Draft")), level=0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER

        doc.add_paragraph(f"Status: {draft.get('status', 'draft').upper()}")
        doc.add_paragraph(f"Type: {draft.get('policy_type', '')}")
        doc.add_paragraph(f"Created: {draft.get('created_at', '')[:10]}")

        if content.get("summary"):
            doc.add_heading("Summary", level=1)
            doc.add_paragraph(content["summary"])

        for section in content.get("sections", []):
            doc.add_heading(section.get("heading", ""), level=1)
            if section.get("content"):
                doc.add_paragraph(section["content"])
            for sub in section.get("sub_sections", []):
                doc.add_heading(sub.get("heading", ""), level=2)
                if sub.get("content"):
                    doc.add_paragraph(sub["content"])

        if content.get("regulatory_references"):
            doc.add_heading("Regulatory References", level=1)
            for ref in content["regulatory_references"]:
                doc.add_paragraph(ref, style='List Bullet')

        buffer = io.BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        return buffer

    async def _get_or_generate_report(self, analysis_id: str) -> Optional[Dict]:
        """Get existing report or generate a new one."""
        if self.gap_report_service:
            report = await self.gap_report_service.get_report(analysis_id)
            if not report:
                report = await self.gap_report_service.generate_report(analysis_id)
            return report
        return None
