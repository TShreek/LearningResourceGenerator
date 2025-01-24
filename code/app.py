from flask import Flask, render_template, request
import requests
import os
from dotenv import load_dotenv

app = Flask(__name__)
# Load API keys from .env file to avoid hardcoding them in the script
load_dotenv()

##########################
# API Keys (replace these in .env file)
##########################
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
CX_ID = os.getenv("CX_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

##########################
# Helper Functions
##########################
import textwrap
import isodate
import requests

def fetch_youtube_links(topic, youtube_api_key, max_results=3):
    # Step 1: Search for videos based on the topic
    search_url = "https://www.googleapis.com/youtube/v3/search"
    search_params = {
        "part": "snippet",
        "q": topic,
        "maxResults": max_results,
        "type": "video",
        "key": youtube_api_key
    }
    search_response = requests.get(search_url, params=search_params)
    search_data = search_response.json()

    video_items = []
    video_ids = []

    if "items" in search_data:
        for item in search_data["items"]:
            video_id = item["id"]["videoId"]
            video_ids.append(video_id)

    if video_ids:
        # Step 2: Get video statistics and content details (including duration)
        stats_url = "https://www.googleapis.com/youtube/v3/videos"
        stats_params = {
            "part": "snippet,statistics,contentDetails",
            "id": ",".join(video_ids),
            "key": youtube_api_key
        }
        stats_response = requests.get(stats_url, params=stats_params)
        stats_data = stats_response.json()

        for item in stats_data["items"]:
            video_id = item["id"]
            snippet = item.get("snippet", {})
            statistics = item.get("statistics", {})
            content_details = item.get("contentDetails", {})

            video_url = f"https://www.youtube.com/watch?v={video_id}"
            thumbnail_url = snippet.get("thumbnails", {}).get("high", {}).get("url", "")
            title = snippet.get("title", "No Title")
            description = snippet.get("description", "No description available")
            short_description = shorten_description(description, 4)  # Limit to 4-5 lines ending with a full stop
            channel_name = snippet.get("channelTitle", "Unknown Channel")
            views = statistics.get("viewCount", "N/A")
            likes = statistics.get("likeCount", "N/A")
            duration = convert_youtube_duration(content_details.get("duration", "N/A"))

            video_items.append({
                "video_url": video_url,
                "thumbnail_url": thumbnail_url,
                "title": title,
                "description": short_description,
                "channel_name": channel_name,
                "views": f"{int(views):,} views" if views != "N/A" else "N/A",
                "likes": f"{int(likes):,} likes" if likes != "N/A" else "N/A",
                "duration": duration
            })

    return video_items

def convert_youtube_duration(duration):
    try:
        parsed_duration = isodate.parse_duration(duration)
        minutes, seconds = divmod(parsed_duration.total_seconds(), 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{int(hours)}h {int(minutes)}m {int(seconds)}s"
        else:
            return f"{int(minutes)}m {int(seconds)}s"
    except Exception as e:
        return "Unknown"

def shorten_description(description, max_lines):
    """
    Shortens the video description to a maximum number of lines, ensuring it ends at a full stop.
    """
    wrapped_text = textwrap.fill(description, width=80)  # Wrap to 80 characters per line
    lines = wrapped_text.split("\n")
    short_desc = ' '.join(lines[:max_lines])  # Get the first max_lines of wrapped text

    # Ensure description ends with a full stop
    if '.' in short_desc:
        last_full_stop = short_desc.rfind('.')
        short_desc = short_desc[:last_full_stop + 1]
    else:
        short_desc += "..."

    return short_desc


def convert_youtube_duration(duration):
    import isodate
    try:
        parsed_duration = isodate.parse_duration(duration)
        minutes, seconds = divmod(parsed_duration.total_seconds(), 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{int(hours)}h {int(minutes)}m {int(seconds)}s"
        else:
            return f"{int(minutes)}m {int(seconds)}s"
    except Exception as e:
        return "Unknown"





def generate_references_with_gemini(topic, gemini_api_key):
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"
    
    headers = {
        "Content-Type": "application/json"
    }

    # Updated prompt to generate references for books and websites only
    prompt_text = f"""
    Provide exactly 3 book recommendations and 3 website recommendations for the topic '{topic}' 
    that are useful for students. Ensure:
    - The books include the title, author, and a brief reason for recommendation.
    - The websites include the name, URL, and why they are valuable for learning.
    Format your response using bullet points and keep it concise.
    """

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt_text.strip()}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 500
        }
    }

    response = requests.post(url, headers=headers, json=payload, params={"key": gemini_api_key})
    
    if response.status_code == 200:
        result = response.json()
        if "candidates" in result and result["candidates"]:
            return result["candidates"][0]["content"]["parts"][0]["text"]
        else:
            return "No references available."
    else:
        return f"Error: {response.status_code} - {response.text}"


    response = requests.post(url, headers=headers, json=payload, params={"key": gemini_api_key})
    
    if response.status_code == 200:
        result = response.json()
        if "candidates" in result and result["candidates"]:
            return result["candidates"][0]["content"]["parts"][0]["text"]
        else:
            return "No summary or references available."
    else:
        return f"Error: {response.status_code} - {response.text}"



import requests

def generate_summary_with_gemini(topic, gemini_api_key):
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"
    
    headers = {
        "Content-Type": "application/json"
    }

    # The updated prompt requests both summary and references
    prompt_text = f"""
Please do the following for '{topic}':
1. Give a bullet-point explaination so that a college student can understand it.
2. make them understand {topic} using simple words
Do not include repeated blank lines or <br> tags. Keep it minimal but structured.
"""

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt_text.strip()
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 450
        }
    }

    params = {"key": gemini_api_key}

    response = requests.post(url, headers=headers, json=payload, params=params)
    
    if response.status_code == 200:
        result = response.json()
        if "candidates" in result and result["candidates"]:
            # Return the text from the first candidate
            # This may contain both summary + references
            return result["candidates"][0]["content"]["parts"][0]["text"]
        else:
            return "No summary or references available."
    else:
        return f"Error: {response.status_code} - {response.text}"


# Home page route
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/results', methods=['POST'])
def results():
    user_topics = request.form.get('topics')
    resource_types = request.form.getlist('resources')

    topics = [t.strip() for t in user_topics.split(',') if t.strip()]

    results_data = {}
    for topic in topics:
        results_data[topic] = {}

        if 'youtube' in resource_types:
            yt_links = fetch_youtube_links(topic, YOUTUBE_API_KEY)
            results_data[topic]['youtube'] = yt_links

        if 'summaries' in resource_types:
            summary = generate_summary_with_gemini(topic, GEMINI_API_KEY)
            results_data[topic]['summary'] = summary

        if 'references' in resource_types:
            references = generate_references_with_gemini(topic, GEMINI_API_KEY)
            results_data[topic]['references'] = references

    return render_template('results.html', results=results_data)



if __name__ == "__main__":
    app.run(debug=True)
