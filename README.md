# Learning Resource Generator

The **Learning Resource Generator** is a Flask-based web application designed to help students easily find relevant learning materials such as YouTube videos, book recommendations, and website references for various topics. 

---

## Features

- **YouTube Videos:** Provides top 3 educational videos with title, views, likes, duration, and description.
- **Summaries:** Generates concise and student-friendly topic summaries using Google Gemini AI.
- **Book & Website Recommendations:** Suggests books and websites for further study on the entered topics.
- **User-Friendly UI:** An intuitive interface for entering topics and selecting desired resource types.
- **Responsive Design:** Works well on both desktop and mobile devices.

---

## Technologies Used

- **Backend:** Flask (Python)
- **Frontend:** HTML, CSS (Bootstrap for styling)
- **APIs Used:**
  - [YouTube Data API](https://developers.google.com/youtube/v3)
  - [Google Custom Search API](https://developers.google.com/custom-search)
  - [Google Gemini AI API](https://ai.google.dev/)

---

## Installation

### Prerequisites
Ensure you have the following installed:

- Python 3.x
- Flask
- Required dependencies (install via `pip`)

### Steps to Run Locally

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/YOUR_USERNAME/LearningResourceGenerator.git
   cd LearningResourceGenerator

Create a Virtual Environment:

python3 -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate


Install Dependencies:
pip install -r requirements.txt


Set up API Keys:
Create a .env file in the root directory and add:

YOUTUBE_API_KEY=your_youtube_api_key
GOOGLE_API_KEY=your_google_api_key
CX_ID=your_google_custom_search_engine_id
GEMINI_API_KEY=your_gemini_api_key


Run the Flask App:
python app.py

Open in Browser:
http://127.0.0.1:5000
