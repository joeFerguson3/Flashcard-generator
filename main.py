
import pdfplumber
import ollama

# Extract text from pdf
def extract_text():
    # Open the PDF file
    with pdfplumber.open("Lecture12.pdf") as pdf:
        text = ''
        # Loop through each page
        for page in pdf.pages:
            page_text = page.extract_text()   # extract text from page
            if page_text:                     # check in case page is blank
                text = text + page_text
    
    print(text)
    extract_definitions(text)

messages = [{"role": "system", "content": """
"I want to create detailed flashcards based on the content of a document I will provide. Please help me generate flashcards that cover every key topic in the document comprehensively. Each flashcard should focus on one clear question-and-answer pair. Present the flashcards in a simple table format like this: 
Question Answer Tags 
Question 1 Answer 1 Tag 1 
Question 2 Answer 2 Tag 2 
Use this structure for all responses. Tags should include the major topics of the document for better organization. Aim for a range of cognitive levels: factual recall, process understanding, application, analysis, and synthesis. Ensure the flashcards are self-contained, so each one provides enough information to understand the context without needing other cards or the document itself. If the document is long, we can work in sections.

"""}]

# Extract definitions from pdf text
def extract_definitions(text):
      messages.append({"role": "user", "content": "Here is the text to utilise: " + text})
      response = ollama.chat(model='gemma3', messages=messages)
      print(response)
      messages.pop()



extract_text()