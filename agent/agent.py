import json

from groq import Groq
from groq.types.chat import (
    ChatCompletionAssistantMessageParam,
    ChatCompletionMessageParam,
    ChatCompletionMessageToolCallParam,
    ChatCompletionToolParam,
)

from agent.conversation import get_conversation_context
from agent.tools import get_emails
from lib.schemas import GetEmailsInput
from main import GROQ_API_KEY, PRIMARY_MODEL

tools: list[ChatCompletionToolParam] = [
    {
        "type": "function",
        "function": {
            "name": "get_emails",
            "description": "Get emails from the user's Gmail inbox using a Gmail search query.",
            "parameters": GetEmailsInput.model_json_schema(),
        },
    }
]


client = Groq(api_key=GROQ_API_KEY)


prompt = """
You are Jared, a sharp, Gen-Z-toned assistant helping developer Abdullah with his tasks.
Be concise by default; expand only when the task needs depth.

You have access to the user's Gmail through tools.
When the user asks about their emails, use the appropriate tool instead of guessing.
"""


def ask_ai(message: str) -> str:
    chat_history = get_conversation_context()

    messages: list[ChatCompletionMessageParam] = [
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
        },
    ]

    chat_completion = client.chat.completions.create(
        messages=messages,
        model=PRIMARY_MODEL,
        tools=tools,
    )

    assistant_message = chat_completion.choices[0].message
    tool_calls = assistant_message.tool_calls

    # No tool needed — return Jared's normal response.
    if not tool_calls:
        if assistant_message.content:
            return assistant_message.content

        return "No message content"

    # Add Groq's tool-call message to the conversation.
    messages.append(
        ChatCompletionAssistantMessageParam(
            role="assistant",
            content=assistant_message.content,
            tool_calls=[
                ChatCompletionMessageToolCallParam(
                    id=tool_call.id,
                    type="function",
                    function={
                        "name": tool_call.function.name,
                        "arguments": tool_call.function.arguments,
                    },
                )
                for tool_call in tool_calls
            ],
        )
    )

    # Execute every tool Groq requested.
    for tool_call in tool_calls:
        if tool_call.function.name != "get_emails":
            continue

        arguments = json.loads(tool_call.function.arguments)

        validated_args = GetEmailsInput.model_validate(arguments)

        result = get_emails(
            query=validated_args.query,
            max_results=validated_args.max_results,
        )

        # Keep the tool response small enough for the LLM context.
        # The full email is still available through get_emails().
        tool_result = [
            {
                "id": email["id"],
                "from": email["from"],
                "to": email["to"],
                "subject": email["subject"],
                "date": email["date"],
                "body": email["body"][:1000],
            }
            for email in result
        ]

        messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(tool_result),
            }
        )

    # Give the tool results back to Groq so Jared can formulate the answer.
    final_completion = client.chat.completions.create(
        messages=messages,
        model=PRIMARY_MODEL,
        tools=tools,
    )

    final_message = final_completion.choices[0].message

    if final_message.content:
        return final_message.content

    return "No message content"
