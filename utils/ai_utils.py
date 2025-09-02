import os
from dotenv import load_dotenv
from openai import OpenAI
import json

load_dotenv()


client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
def extract_definitions(text):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
        {"role": "system", "content": """You are an assistant that generates flashcards.  
    Return output strictly as a JSON array of objects.  
    Each object must contain only two keys: "question" and "answer".  
    No explanations, no extra text, no formatting outside JSON.  
    Example:
    {"question": "Sample question?", "answer": "Sample answer."}"""},

        {"role": "user", "content": f"Generate flashcards from the following text:\n<<<{text}>>>"} 
    ]
    )

    print(response.choices[0].message.content)
    return json.loads(response.choices[0].message.content)

# def extract_definitions(text):
#     messages = [{"role": "system", "content": """Make flash cards as a JSON, in the following format: "flashcards":[{'question':'generated question', 'answer':'generated answer'}]. Include no addition text other than the flash cards and do not include markup or new lines."""}]
#     messages.append({"role": "user", "content": "Here is the text to utilise: " + text + "provide the question and answers as a json, follow the given instructions."})
#     response = ollama.chat(model='gemma3', messages=messages)
#     print(response)
#     response = response['message']['content'].replace("`", "").removeprefix("json")
#     return json.loads(response)

