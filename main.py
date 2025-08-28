
import pdfplumber

# Extract text form pdf
def extract_text():
    # Open the PDF file
    with pdfplumber.open("Lecture12.pdf") as pdf:
        text = []
        # Loop through each page
        for page in pdf.pages:
            page_text = page.extract_text()   # extract text from page
            if page_text:                     # check in case page is blank
                text.append(page_text)

    print(text)

def extract_definitions():
    s

extract_text()