import os
import requests
from dotenv import load_dotenv

# Load API key from .env file
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def test_gemini_api():
    if not GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY not found in environment variables.")
        return

    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"
    headers = {"Content-Type": "application/json"}

    # Simple test prompt
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": "Explain the OSI Model in 3 bullet points."}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 200
        }
    }

    params = {"key": GEMINI_API_KEY}

    try:
        response = requests.post(url, headers=headers, json=payload, params=params)
        response.raise_for_status()
        data = response.json()

        if "candidates" in data and data["candidates"]:
            print("Gemini API response:\n")
            print(data["candidates"][0]["content"]["parts"][0]["text"])
        else:
            print("No content received from Gemini API.")
    except requests.exceptions.RequestException as e:
        print(f"Error making request: {e}")

if __name__ == "__main__":
    test_gemini_api()
