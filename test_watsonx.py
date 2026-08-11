import os
from dotenv import load_dotenv
from ibm_watsonx_ai import Credentials
from ibm_watsonx_ai.foundation_models import ModelInference


# Load secret values from .env
load_dotenv()


# Read our watsonx settings
api_key = os.getenv("WATSONX_APIKEY")
url = os.getenv("WATSONX_URL")
project_id = os.getenv("WATSONX_PROJECT_ID")
model_id = os.getenv("WATSONX_MODEL_ID")


# Make sure nothing is missing
required_values = {
    "WATSONX_APIKEY": api_key,
    "WATSONX_URL": url,
    "WATSONX_PROJECT_ID": project_id,
    "WATSONX_MODEL_ID": model_id,
}

missing = [name for name, value in required_values.items() if not value]

if missing:
    raise ValueError(
        "Missing environment variables: " + ", ".join(missing)
    )


print("Environment variables loaded successfully.")
print("Connecting to IBM watsonx.ai...")


# Authenticate with IBM
credentials = Credentials(
    url=url,
    api_key=api_key,
)


# Connect to the Granite model
model = ModelInference(
    model_id=model_id,
    credentials=credentials,
    project_id=project_id,
)


# Send our first message to Granite
messages = [
    {
        "role": "user",
        "content": (
            "Reply with one short sentence confirming that "
            "MissionShield AI successfully connected to IBM watsonx.ai."
        ),
    }
]


response = model.chat(messages=messages)


# Display Granite's answer
answer = response["choices"][0]["message"]["content"]

print()
print("IBM GRANITE RESPONSE:")
print("---------------------")
print(answer)
print()
print("SUCCESS: watsonx.ai connection is working.")