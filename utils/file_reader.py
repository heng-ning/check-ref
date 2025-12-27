from docx import Document
import fitz  # PyMuPDF

def extract_paragraphs_from_docx(file):
    doc = Document(file)
    return [para.text.strip() for para in doc.paragraphs if para.text.strip()]

def extract_paragraphs_from_pdf(file):
    text = ""
    with fitz.open(stream=file.read(), filetype="pdf") as doc:
        for page in doc:
            text += page.get_text("text") + "\n"
    return [p.strip() for p in text.split("\n") if p.strip()]
