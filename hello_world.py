# from pathlib import Path
from dotenv import load_dotenv
from anthropic import Anthropic
import json

load_dotenv()

client = Anthropic()
model="claude-sonnet-4-6"

messages = []
system_prompt = """You are a beauty advisor. 
  Given the skin analysis recommend products as per skin tone.
  Give real world products for recommendations.
  Respond only in JSON
  """
# helper function to keep track of user text messages
def add_user_message(messages, text):
  user_message = {"role":"user", "content": text}
  messages.append(user_message)

# helper function to keep track of assitant text messages
def add_assitant_message(messages, text):
  assistant_message = {"role":"assistant", "content": text}
  messages.append(assistant_message)

def chat(messages,system=None, temperature=1.0, stop_sequences=None):
  params = {
    "model": model,
    "max_tokens": 1000,
    "messages": messages,
    "temperature": temperature, 
    # stream = True
  }
  if system: 
    params["system"] = system
  if stop_sequences:
    params["stop_sequences"] = stop_sequences
  
  message = client.messages.create(**params)
  return message.content[0].text

#Take user's input 
# while True:
#   #Get user's input 
#   user_input = input("> ")

#   add_user_message(messages, user_input)
#   answer = chat(messages, temperature=1.0)
#   add_assitant_message(messages, answer)

#   if "```" in answer:                         # unwrap if wrapped
#         clean = answer.split("```")[1]
#         if clean.startswith("json"):
#             clean = clean[4:]
#   else:
#         clean = answer                          # wasn't wrapped, use as is
#   print(clean.strip())




def generate_dataset():
  prompt = """
Generate a evaluation dataset for a prompt evaluation. The dataset will be used to evaluate prompts
that generate Python, JSON, or Regex specifically for AWS-related tasks. Generate an array of JSON objects,
each representing task that requires Python, JSON, or a Regex to complete.

Example output:
```json
[
    {
        "task": "Description of task",
    },
    ...additional
]
```

* Focus on tasks that can be solved by writing a single Python function, a single JSON object, or a regular expression.
* Focus on tasks that do not require writing much code

Please generate 3 objects.
"""

  messages = []
  add_user_message(messages, prompt)
  text = chat(messages)

  if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]

  return json.loads(text.strip())

data = generate_dataset()
print(data)
  
with open("dataset.json","w") as f:
  json.dump(data,f, indent=2)
  


