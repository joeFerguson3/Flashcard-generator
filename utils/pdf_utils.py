import pdfplumber
from utils.ai_utils import extract_definitions

def extract_text(file):
    with pdfplumber.open(file) as pdf:
        text = "".join([page.extract_text() or "" for page in pdf.pages])
    print("text extracted")
    return extract_definitions(text)


# Split text, with overlap
def split_by_words(text, chunk_size=600, overlap=80):
    words = text.split()
    chunks = []
    start = 0

    while start < len(words):
        end = start + chunk_size
        chunk = words[start:end]
        chunks.append(" ".join(chunk))
        start += chunk_size - overlap

    return chunks
