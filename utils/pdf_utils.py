import pdfplumber
from utils.ai_utils import extract_definitions

def extract_text():
    with pdfplumber.open("Lecture12.pdf") as pdf:
        text = "".join([page.extract_text() or "" for page in pdf.pages])
    print("text extracted")
    return extract_definitions(text)