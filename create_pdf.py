from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch

# Read the text file
with open('test-regulation.txt', 'r') as f:
    content = f.read()

# Create PDF
pdf_path = 'test-regulation.pdf'
doc = SimpleDocTemplate(pdf_path, pagesize=letter)
styles = getSampleStyleSheet()

# Build the story (content)
story = []
for line in content.split('\n'):
    if line.strip():
        story.append(Paragraph(line, styles['Normal']))
        story.append(Spacer(1, 0.1 * inch))

# Generate PDF
doc.build(story)
print(f"PDF created at: {pdf_path}")
