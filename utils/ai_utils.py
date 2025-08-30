import ollama, json

def extract_definitions(text):
    messages = [{"role": "system", "content": """Generate flashcards from the following text. Output must be valid JSON only. Each flashcard must have "question" and "answer" keys. Do NOT use bold, italics, Markdown, or any extra text. Do not include any notes or commentary. Use plain text only."""}]
    messages.append({"role": "user", "content": "Here is the text to utilise: " + text + "provide the question and answers as a json"})
    response = ollama.chat(model='gemma3', messages=messages)
    print(response)
    response = response['message']['content'].replace("`", "").removeprefix("json")
    return json.loads(response)
