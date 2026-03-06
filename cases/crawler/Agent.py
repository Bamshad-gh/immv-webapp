from groq import Groq
import os
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def chat_groq(messages: list, model: str = "llama-3.3-70b-versatile") -> str:
    response = client.chat.completions.create(
        model=model,
        messages=messages,
    )
    return response.choices[0].message.content

# ── USAGE ─────────────────────────────────────────────────────────────
crowl_Link ='https://www.canada.ca/en/immigration-refugees-citizenship/services/iran.html'
application_prohram= 'work permit'
messages = [
    {"role": "system", "content": "you are a immagration consultant and you have to read the website and return the requirements, eligibility criteria or any information needs as a list i want to use them in code and automation , dont add something yourself just read the website and return the information as a list"},
    {"role": "user",   
     "content": f"read the website {crowl_Link} for {application_prohram} "},
]
reply = chat_groq(messages)
print(reply)


