
import pdfplumber
import ollama
from flask import Flask, request, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import json
app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///flashcards.db'
db = SQLAlchemy(app)

# Import models after db is defined
class Flashcard(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

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
    
    return extract_definitions(text)

# Extract definitions from pdf text
def extract_definitions(text):
      messages = [{"role": "system", "content": """Generate flashcards from the following text. Output must be valid JSON only. Each flashcard must have "question" and "answer" keys. Do NOT use bold, italics, Markdown, or any extra text. Do not include any notes or commentary. Use plain text only."""}]
      messages.append({"role": "user", "content": "Here is the text to utilise: " + text + "provide the question and answers as a json"})
      response = ollama.chat(model='gemma3', messages=messages)
      response = response['message']['content'].replace("`", "").removeprefix("json")

      json_str = json.loads(response)
      return json_str



@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        if 'pdfUpload' not in request.files:
            return "No file part"
        file = request.files['pdfUpload']
        if file.filename == '':
            return "No selected file"
        if file and file.filename.endswith('.pdf'):
            print("file read!")
            render_template('loading.html')
            return redirect('/flashcards')
        else:
            return "Invalid file type. Please upload a PDF."
    return render_template('pdf-upload.html')

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/flashcards')
def flashcards():
    flashcards = extract_text()
    return render_template('flashcards.html',flashcards = flashcards)

@app.route('/save-flashcards', methods=['POST'])
def save_flashcards():
    data = json.loads(request.form['flashcards'])
    for card in data["questions"]:
        new_card = Flashcard(question=card["question"], answer=card["answer"])
        db.session.add(new_card)
    db.session.commit()
    return redirect('/')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)

