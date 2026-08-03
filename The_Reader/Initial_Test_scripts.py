from ollama import chat
response = chat(
    model="gemma3:4b",
    messages=[
        {
            "role":"user",
            "content":"do you like potatos?"
        }
    ]
)
print(response.message.content)
response = chat(
    model="gemma3:4b",
    messages=[
        {
            "role":"user",
            "content":"what did i tell you in my previous messages?"
        }
    ]
)
print(response.message.content)