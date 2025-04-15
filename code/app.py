from flask import Flask, render_template, request
import aiohttp
import asyncio
import os
from dotenv import load_dotenv
import textwrap
import isodate # Make sure to install: pip install isodate

# --- Flask App Setup ---
app = Flask(__name__)

# --- Load Environment Variables ---
load_dotenv() # Load variables from .env file into environment

# --- API Key Configuration ---
# Retrieve keys from environment variables loaded from .env
# Provide None as default, so we can check if they exist
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# --- Gemini Model Configuration ---
# Using known valid model names - adjust if needed based on your key/region
GEMINI_SUMMARY_MODEL = "gemini-2.0-flash" # Changed from gemini-2.0-flash
GEMINI_REFERENCE_MODEL = "gemini-1.5-flash"      # Changed from gemini-pro

# --- Helper Functions ---

def convert_youtube_duration(duration_str):
    """Converts ISO 8601 duration string to human-readable format."""
    if not duration_str:
        return "Unknown"
    try:
        parsed_duration = isodate.parse_duration(duration_str)
        total_seconds = int(parsed_duration.total_seconds())
        minutes, seconds = divmod(total_seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"
    except isodate.ISO8601Error:
        # Handle cases where the duration string might be invalid
        print(f"Warning: Could not parse YouTube duration '{duration_str}'")
        return "Unknown"
    except Exception as e:
        print(f"Error converting duration '{duration_str}': {e}")
        return "Unknown"


def shorten_description(description, max_lines):
    """Shortens text to a max number of lines."""
    if not description:
        return ""
    # Normalize whitespace before wrapping
    normalized_description = ' '.join(description.split())
    wrapped_text = textwrap.fill(normalized_description, width=80) # Adjust width as needed
    lines = wrapped_text.split("\n")
    if len(lines) > max_lines:
        return "\n".join(lines[:max_lines]) + "..." # Join with newline for better formatting
    else:
        return "\n".join(lines)

# --- Asynchronous API Fetching Functions ---

async def fetch_with_retry(session, url, api_key, headers, payload, retries=3, delay=5):
    """Generic function to fetch data from an API with retry logic, specifically for POST."""
    params = {"key": api_key} # Pass API key as parameter
    last_error = None
    for attempt in range(retries):
        try:
            async with session.post(url, headers=headers, json=payload, params=params, timeout=60) as response:
                if response.status == 200:
                    return await response.json() # Success
                elif response.status == 429 or response.status >= 500: # Retry on rate limit or server error
                    print(f"API request to {url} failed with status {response.status}. Attempt {attempt + 1}/{retries}. Retrying in {delay} seconds...")
                    last_error = {"error": f"API Error: Status {response.status}", "details": await response.text()}
                    await asyncio.sleep(delay)
                else: # Handle other client errors (4xx) immediately without retry
                    print(f"API request to {url} failed with status {response.status}. Not retrying.")
                    error_details = await response.text()
                    print(f"Error details: {error_details}")
                    return {"error": f"API request failed with status {response.status}", "details": error_details}
        except asyncio.TimeoutError:
            print(f"API request to {url} timed out. Attempt {attempt + 1}/{retries}. Retrying in {delay} seconds...")
            last_error = {"error": "Request Timeout"}
            await asyncio.sleep(delay)
        except aiohttp.ClientError as e:
            print(f"Network/Client error during request to {url}: {e}. Attempt {attempt + 1}/{retries}. Retrying in {delay} seconds...")
            last_error = {"error": f"Network error: {e}"}
            await asyncio.sleep(delay)

    print(f"Maximum retries reached for {url}. Returning last known error.")
    return last_error if last_error else {"error": "Maximum retries reached. The API is currently unavailable."}


async def fetch_url_get(session, url, params):
    """Generic function to fetch data using GET."""
    try:
        async with session.get(url, params=params, timeout=30) as response:
            if response.status == 200:
                return await response.json()
            else:
                print(f"GET request to {url} failed with status {response.status}")
                error_details = await response.text()
                print(f"Error details: {error_details}")
                return {"error": f"API request failed with status {response.status}", "details": error_details}
    except asyncio.TimeoutError:
        print(f"GET request to {url} timed out.")
        return {"error": "Request Timeout"}
    except aiohttp.ClientError as e:
        print(f"Network/Client error during GET request to {url}: {e}")
        return {"error": f"Network error: {e}"}


async def fetch_youtube_links(topic, youtube_api_key, max_results=3):
    """Fetches YouTube video links and details for a given topic."""
    if not youtube_api_key:
        return {"error": "YouTube API Key is not configured."}

    search_url = "https://www.googleapis.com/youtube/v3/search"
    search_params = {
        "part": "snippet",
        "q": topic,
        "maxResults": max_results,
        "type": "video",
        "key": youtube_api_key
    }
    async with aiohttp.ClientSession() as session:
        search_data = await fetch_url_get(session, search_url, search_params)
        if "error" in search_data:
            return search_data # Return the error dictionary directly

        video_ids = [item["id"]["videoId"] for item in search_data.get("items", []) if "videoId" in item.get("id", {})]
        if not video_ids:
            return [] # Return empty list if no videos found

        stats_url = "https://www.googleapis.com/youtube/v3/videos"
        stats_params = {
            "part": "snippet,statistics,contentDetails",
            "id": ",".join(video_ids),
            "key": youtube_api_key
        }
        stats_data = await fetch_url_get(session, stats_url, stats_params)
        if "error" in stats_data:
            return stats_data # Return the error dictionary

        video_items = []
        for item in stats_data.get("items", []):
            snippet = item.get("snippet", {})
            statistics = item.get("statistics", {})
            content_details = item.get("contentDetails", {})
            video_id = item.get("id")

            if not video_id: continue # Skip if item has no ID somehow

            video_items.append({
                # Correct YouTube URL format
                "video_url": f"https://www.youtube.com/watch?v={video_id}",
                "thumbnail_url": snippet.get("thumbnails", {}).get("high", {}).get("url") or snippet.get("thumbnails", {}).get("default", {}).get("url", ""),
                "title": snippet.get("title", "No Title Provided"),
                "description": shorten_description(snippet.get("description", ""), 4), # Limit description lines
                "channel_name": snippet.get("channelTitle", "Unknown Channel"),
                # Safely convert stats to int, default to 0 if missing/invalid
                "views": f"{int(statistics.get('viewCount', 0)):,} views",
                "likes": f"{int(statistics.get('likeCount', 0)):,} likes",
                "duration": convert_youtube_duration(content_details.get("duration", ""))
            })
        return video_items


async def generate_summary_with_gemini(topic, gemini_api_key):
    """Generates a summary using the Gemini API with retry."""
    if not gemini_api_key:
        return {"error": "Gemini API Key is not configured."}

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_SUMMARY_MODEL}:generateContent"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": f"Provide a concise bullet-point explanation of '{topic}' suitable for a college student. Focus on key concepts and definitions."}]}],
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 500},
         # Add safety settings if needed
        # "safetySettings": [
        #     { "category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE" },
        #     # Add other categories as needed
        # ]
    }

    async with aiohttp.ClientSession() as session:
        response_data = await fetch_with_retry(session, url, gemini_api_key, headers, payload)

    if "error" in response_data:
        # Return the detailed error if fetching failed
        return response_data

    # Safely extract text content
    try:
        text = response_data["candidates"][0]["content"]["parts"][0]["text"]
        return text
    except (KeyError, IndexError, TypeError) as e:
        print(f"Error parsing Gemini summary response: {e}")
        print(f"Full Gemini response data: {response_data}")
        return {"error": "Failed to parse summary response from Gemini API."}


async def generate_references_with_gemini(topic, gemini_api_key):
    """Generates references using the Gemini API with retry."""
    if not gemini_api_key:
        return {"error": "Gemini API Key is not configured."}

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_REFERENCE_MODEL}:generateContent"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": f"Provide exactly 3 relevant book recommendations (Title and Author) and 3 relevant website recommendations (Name and URL) for learning more about '{topic}'. Format clearly."}]}],
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 500},
         # Add safety settings if needed
    }

    async with aiohttp.ClientSession() as session:
        response_data = await fetch_with_retry(session, url, gemini_api_key, headers, payload)

    if "error" in response_data:
         # Return the detailed error if fetching failed
        return response_data

    # Safely extract text content
    try:
        text = response_data["candidates"][0]["content"]["parts"][0]["text"]
        return text
    except (KeyError, IndexError, TypeError) as e:
        print(f"Error parsing Gemini references response: {e}")
        print(f"Full Gemini response data: {response_data}")
        return {"error": "Failed to parse references response from Gemini API."}


# --- Flask Routes ---

@app.route('/')
def index():
    """Renders the main input page."""
    return render_template('index.html')

@app.route('/results', methods=['POST'])
async def results():
    """Handles form submission, fetches data asynchronously, and renders results."""
    # Check if API keys are loaded
    if not YOUTUBE_API_KEY or not GEMINI_API_KEY:
        missing_keys = []
        if not YOUTUBE_API_KEY: missing_keys.append("YOUTUBE_API_KEY")
        if not GEMINI_API_KEY: missing_keys.append("GEMINI_API_KEY")
        return f"Error: Missing API Key(s) in .env file: {', '.join(missing_keys)}", 500

    user_topics = request.form.get('topics', '')
    if not user_topics:
        return "Error: No topics provided", 400

    resource_types = request.form.getlist('resources')
    topics = [t.strip() for t in user_topics.split(',') if t.strip()]

    if not topics:
        return "Error: No valid topics provided", 400
    if not resource_types:
        return "Error: No resource types selected", 400

    tasks = []
    task_map = {} # Keep track of which task corresponds to which topic/type

    for topic in topics:
        task_map[topic] = {}
        if 'youtube' in resource_types:
            task = asyncio.create_task(fetch_youtube_links(topic, YOUTUBE_API_KEY))
            tasks.append(task)
            task_map[topic]['youtube_task'] = task
        if 'summaries' in resource_types:
            task = asyncio.create_task(generate_summary_with_gemini(topic, GEMINI_API_KEY))
            tasks.append(task)
            task_map[topic]['summary_task'] = task
        if 'references' in resource_types:
            task = asyncio.create_task(generate_references_with_gemini(topic, GEMINI_API_KEY))
            tasks.append(task)
            task_map[topic]['references_task'] = task

    # Wait for all tasks to complete
    await asyncio.gather(*tasks, return_exceptions=True) # Use return_exceptions=True

    # Process results using the task map
    results_data = {}
    for topic in topics:
        results_data[topic] = {}
        if 'youtube' in resource_types:
            task = task_map[topic]['youtube_task']
            try:
                results_data[topic]['youtube'] = task.result()
            except Exception as e:
                 print(f"Error getting result for YouTube task ({topic}): {e}")
                 results_data[topic]['youtube'] = {"error": f"Task failed: {e}"} # Store exception
        if 'summaries' in resource_types:
            task = task_map[topic]['summary_task']
            try:
                results_data[topic]['summary'] = task.result()
            except Exception as e:
                print(f"Error getting result for Summary task ({topic}): {e}")
                results_data[topic]['summary'] = {"error": f"Task failed: {e}"} # Store exception
        if 'references' in resource_types:
            task = task_map[topic]['references_task']
            try:
                results_data[topic]['references'] = task.result()
            except Exception as e:
                print(f"Error getting result for References task ({topic}): {e}")
                results_data[topic]['references'] = {"error": f"Task failed: {e}"} # Store exception

        # Process results that might be error dictionaries themselves
        for key in ['youtube', 'summary', 'references']:
            if key in results_data[topic]:
                res = results_data[topic][key]
                # Check if the result itself is an error dictionary from the fetch functions
                if isinstance(res, dict) and 'error' in res:
                     print(f"API Error for {topic} - {key}: {res['error']}")
                     # Optionally pass the error details to the template if needed
                     results_data[topic][key] = f"Error: {res['error']}" # Simplify error for display


    # Render results page with the processed data
    return render_template('results.html', results=results_data)

# --- Main Execution Guard ---
if __name__ == "__main__":
    # Check for missing API keys on startup
    if not YOUTUBE_API_KEY:
        print("CRITICAL ERROR: YOUTUBE_API_KEY not found in environment variables. Create .env file.")
    if not GEMINI_API_KEY:
        print("CRITICAL ERROR: GEMINI_API_KEY not found in environment variables. Create .env file.")

    # Only run if keys are present (optional, prevents running without keys)
    if YOUTUBE_API_KEY and GEMINI_API_KEY:
         print("API Keys loaded successfully.")
         app.run(debug=True, host="127.0.0.1", port=5000)
    else:
         print("Application will not start due to missing API keys.")
