import os
from dotenv import load_dotenv
from openai import OpenAI
import json
from utils.notes import parse_notes

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def question(text, title):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
        {"role": "system", "content": """You are generating quiz questions from the following text. 
Decide whether to create one of these types: 
- "fill-in-blank" 
- "true-false" 
- "multiple-choice" 
- "short-answer" 
- "ordering" 

Rules:
- Use "fill-in-blank" if the text contains key facts, numbers, or definitions.  
- Use "true-false" if the text can be slightly modified into a correct or incorrect statement.  
- Use "multiple-choice" if the text offers clear alternatives or categories.  
- Use "short-answer" if the text requires explanation or reasoning in own words.  
- Use "ordering" if the text contains steps, sequences, or chronology.  

Output strictly in JSON format, using one of the following schemas:  

Fill-in-the-blank:
{
  "type": "fill-in-blank",
  "question": "Sentence with {blank} placeholders",
  "answer": ["correct term", "another correct term"]
}

True/False:
{
  "type": "true-false",
  "question": "Statement",
  "answer": true or false
}

Multiple-choice:
{
  "type": "multiple-choice",
  "question": "Question text?",
  "options": ["option A", "option B", "option C", "option D"],
  "answer": "correct option"
}

Short-answer:
{
  "type": "short-answer",
  "question": "Open-ended question requiring a short response",
  "answer": "expected key idea or phrase, only one word or key short phrase in length"
}

Ordering:
{
  "type": "ordering",
  "question": "Arrange the following in the correct order",
  "options": ["step 1", "step 2", "step 3"],
  "answer": ["step 1", "step 2", "step 3"]
}

Your output must be a single JSON object, matching exactly one schema above, with no extra text.
"""},

        {"role": "user", "content": f"Generate a question from the following text:\n<<<{text}>>>"} 
    ]
    )

    response = json.loads(response.choices[0].message.content)
    response["title"] = title

    return response


# # def extract_definitions(text):
# #     response = client.chat.completions.create(
# #         model="gpt-4o-mini",
# #         messages=[
# #         {"role": "system", "content": """You are an assistant that generates flashcards.  
# #     Return output strictly as a JSON array of objects.  
# #     Each object must contain only two keys: "question" and "answer".  
# #     No explanations, no extra text, no formatting outside JSON.  
# #     Example:
# #     {"question": "Sample question?", "answer": "Sample answer."}"""},

# #         {"role": "user", "content": f"Generate flashcards from the following text:\n<<<{text}>>>"} 
# #     ]
# #     )

# #     print(response.choices[0].message.content)
# #     return json.loads(response.choices[0].message.content)

def extract_definitions(text):
    chunks = chunk_text(text)
    response_text = ""
    print(chunks)
    for chunk in chunks:
      response = client.chat.completions.create(
          model="gpt-4o-mini",
          messages=[
            {"role": "system", "content": """Act as a study-notes assistant. Given an educational text or notes on any topic, produce a concise, well-structured summary for revision. Use the following Markdown format exactly:

### [Main Heading]
## [Subheading (main point)]
- [Bullet point with key idea or definition]
-- [Sub-bullet with a supporting detail or example]

Only include essential definitions, concepts, processes, and relevant examples needed for understanding or exams. Exclude irrelevant details like extra dates or background not needed for core concepts. Use clear, simple language and present information in short bullet points as above. Do not make any text bold or itallics. """},

          {"role": "user", "content": f"Text for notes:\n<<<{chunk}>>>"} 
      ]
      )

      response_text = response_text + response.choices[0].message.content + "\n"

    return parse_notes(response_text)


# Splits text into chunks for higher quality repsonse
def chunk_text(text, chunk_size=850, step=800):
    chunks = []
    i = 0
    text_length = len(text)

    while i < text_length:
        # take up to chunk_size characters, but not beyond the text length
        chunk = text[i:min(i+chunk_size, text_length)]
        chunks.append(chunk)

        # move forward by step
        i += step

    return chunks

       
        
