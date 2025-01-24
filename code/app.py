from flask import Flask, render_template, request
import aiohttp
import asyncio
import os
from dotenv import load_dotenv

app = Flask(__name__)

# Load API keys from .env file to avoid hardcoding them in the script
load_dotenv()

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

import textwrap
import isodate


import asyncio

async def fetch_with_retry(session, url, headers, payload, retries=3, delay=5):
    for attempt in range(retries):
        async with session.post(url, headers=headers, json=payload, params={"key": GEMINI_API_KEY}) as response:
            if response.status == 200:
                return await response.json()
            elif response.status == 500:
                print(f"Attempt {attempt + 1} failed. Retrying in {delay} seconds...")
                await asyncio.sleep(delay)
            else:
                return {"error": f"API request failed with status {response.status}"}
    return {"error": "Maximum retries reached. The API is currently unavailable."}

async def fetch_url(session, url, params):
    async with session.get(url, params=params) as response:
        if response.status != 200:
            return {"error": f"API request failed with status {response.status}"}
        return await response.json()

async def fetch_youtube_links(topic, youtube_api_key, max_results=3):
    search_url = "https://www.googleapis.com/youtube/v3/search"
    search_params = {
        "part": "snippet",
        "q": topic,
        "maxResults": max_results,
        "type": "video",
        "key": youtube_api_key
    }
    async with aiohttp.ClientSession() as session:
        search_data = await fetch_url(session, search_url, search_params)
        if "error" in search_data:
            return search_data["error"]

        video_items = []
        video_ids = [item["id"]["videoId"] for item in search_data.get("items", [])]

        if video_ids:
            stats_url = "https://www.googleapis.com/youtube/v3/videos"
            stats_params = {
                "part": "snippet,statistics,contentDetails",
                "id": ",".join(video_ids),
                "key": youtube_api_key
            }
            stats_data = await fetch_url(session, stats_url, stats_params)
            for item in stats_data.get("items", []):
                snippet = item.get("snippet", {})
                statistics = item.get("statistics", {})
                content_details = item.get("contentDetails", {})

                video_items.append({
                    "video_url": f"https://www.youtube.com/watch?v={item['id']}",
                    "thumbnail_url": snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
                    "title": snippet.get("title", "No Title"),
                    "description": shorten_description(snippet.get("description", ""), 4),
                    "channel_name": snippet.get("channelTitle", "Unknown Channel"),
                    "views": f"{int(statistics.get('viewCount', 0)):,} views",
                    "likes": f"{int(statistics.get('likeCount', 0)):,} likes",
                    "duration": convert_youtube_duration(content_details.get("duration", ""))
                })
        return video_items

async def generate_summary_with_gemini(topic, gemini_api_key):
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": f"Provide a bullet-point explanation of '{topic}' for a college student."}]}],
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 500}
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload, params={"key": gemini_api_key}) as response:
            data = await response.json()
            return data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "No summary available.")

def convert_youtube_duration(duration):
    try:
        parsed_duration = isodate.parse_duration(duration)
        total_seconds = int(parsed_duration.total_seconds())
        minutes, seconds = divmod(total_seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}h {minutes}m {seconds}s"
        else:
            return f"{minutes}m {seconds}s"
    except:
        return "Unknown"

def shorten_description(description, max_lines):
    wrapped_text = textwrap.fill(description, width=80)
    lines = wrapped_text.split("\n")
    return ' '.join(lines[:max_lines]) + ("..." if len(lines) > max_lines else "")

async def generate_references_with_gemini(topic, gemini_api_key):
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": f"Provide exactly 3 book recommendations and 3 website recommendations for '{topic}'"}
                ]
            }
        ],
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 500}
    }
    
    async with aiohttp.ClientSession() as session:
        response_data = await fetch_with_retry(session, url, headers, payload)
        if "error" in response_data:
            return response_data["error"]
        
        if "candidates" in response_data and response_data["candidates"]:
            return response_data["candidates"][0]["content"]["parts"][0]["text"]
        else:
            return "No references available."


    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, headers=headers, json=payload, params={"key": gemini_api_key}) as response:
                if response.status != 200:
                    return f"Error fetching references: {response.status}, {await response.text()}"
                
                data = await response.json()
                if "candidates" in data and data["candidates"]:
                    return data["candidates"][0]["content"]["parts"][0]["text"]
                else:
                    return "No references available."
        except Exception as e:
            return f"Error occurred: {str(e)}"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/results', methods=['POST'])
async def results():
    user_topics = request.form.get('topics', '')
    if not user_topics:
        return "Error: No topics provided", 400

    resource_types = request.form.getlist('resources')
    topics = [t.strip() for t in user_topics.split(',') if t.strip()]

    if not topics:
        return "Error: No valid topics provided", 400

    tasks = []
    for topic in topics:
        if 'youtube' in resource_types:
            tasks.append(fetch_youtube_links(topic, YOUTUBE_API_KEY))
        if 'summaries' in resource_types:
            tasks.append(generate_summary_with_gemini(topic, GEMINI_API_KEY))
        if 'references' in resource_types:
            tasks.append(generate_references_with_gemini(topic, GEMINI_API_KEY))
    
    results = await asyncio.gather(*tasks, return_exceptions=True)

    results_data = {}
    idx = 0
    for topic in topics:
        results_data[topic] = {}
        if 'youtube' in resource_types:
            results_data[topic]['youtube'] = results[idx]
            idx += 1
        if 'summaries' in resource_types:
            results_data[topic]['summary'] = results[idx]
            idx += 1
        if 'references' in resource_types:
            results_data[topic]['references'] = results[idx]
            idx += 1

    return render_template('results.html', results=results_data)


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
