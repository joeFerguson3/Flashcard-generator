import os
from dotenv import load_dotenv
from openai import OpenAI
import json

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def question(text, title):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
        {"role": "system", "content": """You are generating quiz questions from the following text. 
Decide whether to create a "fill-in-blank" or "true-false" question. 
Follow these rules:
- Use "fill-in-blank" if the text contains key facts, numbers, or definitions.
- Use "true-false" if the text can be slightly modified into a correct or incorrect statement.
- Output strictly in JSON format, using one of the following schemas:

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
}"""},

        {"role": "user", "content": f"Generate a question from the following text:\n<<<{text}>>>"} 
    ]
    )

    response = json.loads(response.choices[0].message.content)
    response["title"] = title
    print(response)
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
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
        {"role": "system", "content": """
    From the following text, extract complete lecture notes:

    - Ignore introductions, lecture purpose statements, summarys, overviews or any content which a student would not be expecv=ted to memorise for a test.
    - Organize notes into clear sections with topic headings (use level-2 headings: ## Topic).
    - Use bullet points for readability.
    - Nest sub-points with a maximum of two levels (e.g., - main point,   - sub-point).
    - Preserve all important details, examples, and explanations needed for learning.
    - Avoid unnecessary repetition or filler text.
    - Ensure the output is clean, consistent, and easy to read for study purposes.
    - Format output in Markdown."""},

        {"role": "user", "content": f"Generate flashcards from the following text:\n<<<{text}>>>"} 
    ]
    )
    print(response.choices[0].message.content)


       
        
