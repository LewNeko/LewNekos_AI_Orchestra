from ollama import chat
SYSTEM_PROMPT= """
You are a routing assistant. For each user message, decide which category it falls into:
- general_chat: can be answered directly
- needs_tool: requires a tool/function call to be answered correctly
- needs_docs: requires searching documents/context

Respond with just the category and a one-sentence reason.
"""
messages=[
    {
        "role": "system",
        "content": SYSTEM_PROMPT
    }
]

def ask(user_input):
    messages.append(
        {
            "role": "user",
            "content":user_input
        }
    )
    response = chat(
        model="gemma3:4b",
        messages=messages
    )
    reply = response.message.content
    messages.append(
        {
            "role": "assistant",
            "content": reply
        }
    )
    return reply
#now this should get me persistent history, and this Gemma model will begin to think like a router
print(ask("there is no docs"))
print(ask("what did i just ask? this can answered directly."))