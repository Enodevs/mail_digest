from groq import Groq

from agent.conversation import get_conversation_context
from main import GROQ_API_KEY, PRIMARY_MODEL

client = Groq(api_key=GROQ_API_KEY)

prompt = """
    You are Jared, a sharp, Gen-Z-toned assistant helping developer Abdullah with his tasks.
    Be concise by default; expand only when the task needs depth.
"""

def ask_ai(message: str) -> str:
    chat_history = get_conversation_context()

    chat_completion = client.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": prompt,
            },
            {
                "role": "system",
                "content": f"Previous chats: {chat_history}",
            },
            {
                "role": "user",
                "content": message,
            }
        ],
        model=PRIMARY_MODEL,
    )

    if chat_completion.choices[0].message.content:
        return chat_completion.choices[0].message.content

    return "No message content"
