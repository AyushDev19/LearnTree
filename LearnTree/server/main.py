from flask import Flask, send_file, request, jsonify
from flask_cors import CORS
import asyncio
import os
from google import genai
import edge_tts
from googleapiclient.discovery import build
import smtplib
from email.mime.text import MIMEText

app = Flask(__name__)
CORS(app)

GEMINI_API_KEY = "AIzaSyBc70X28NtqrbzEpkz6uKcbLfXgDZ1Sixs"
YOUTUBE_API_KEY = "AIzaSyAwoGu3XgUVmIPtl2ZGlR1ZoJR-veqEUD4"

client = genai.Client(api_key=GEMINI_API_KEY)
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_ADDRESS = "ayush25.dev@gmail.com"
EMAIL_PASSWORD = "sogb bsll ffaf qsfz"
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
AUDIO_FILE = os.path.join(UPLOAD_FOLDER, "latest.mp3")
@app.route("/send-email", methods=["POST"])
def send_email():
    data = request.get_json()
    name = data.get("name")
    from_email = data.get("email")
    message = data.get("message")

    if not name or not from_email or not message:
        return jsonify({"error": "Missing required fields"}), 400

    subject = f"Message from {name}"
    body = f"Sender Email: {from_email}\n\nMessage:\n{message}"

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = "ayush25.dev@gmail.com"

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.sendmail(EMAIL_ADDRESS, msg["To"], msg.as_string())

        return jsonify({"message": "Email sent successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def youtube_search(query):
    youtube_set = []
    youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
    request = youtube.search().list(q=query, part="snippet", maxResults=1, type="video")
    response = request.execute()
    for item in response["items"]:
        title = item["snippet"]["title"]
        video_id = item["id"]["videoId"]
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        youtube_set.append({"title": title, "url": video_url})
    return youtube_set
@app.route("/ytlink", methods=["GET"])
def ytlink():
    topic = request.args.get("topic")
    class_ = request.args.get("class")
    board = request.args.get("board")

    if not all([topic, class_, board]):
        return jsonify({"error": "Missing topic, class, or board parameter"}), 400
    query = f"{topic} Class {class_} {board} syllabus"
    youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
    request_api = youtube.search().list(
        q=query, part="snippet", maxResults=5, type="video"
    )
    response = request_api.execute()
    links = [
        f"https://www.youtube.com/watch?v={item['id']['videoId']}"
        for item in response["items"]
    ]
    return jsonify(links)


def generate_feynman(name, topic, class_, board):
    prompt = (
        f"Student Name: {name}\n"
        f"Topic: {topic}\n"
        f"Class: {class_}\n"
        f"Board: {board}\n\n"
        f"Explain {topic} to {name} in a short, clear, simple, and detailed but short way "
        f"for a Class {class_} student following the {board} board. "
        f"Use the Feynman Technique: break down the idea into basic terms, avoid jargon, "
        f"use analogies or examples, and relate it to everyday experiences. "
        f"Make sure it's easy to understand for their level."
    )
    response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
    return response.text.strip()


def generate_explanation(name, class_, topic, board):
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=(
            f"Explain the topic {topic} of class {class_} to a student named {name} "
            f"as per syllabus of {board} elaborately. "
            f"When giving your output wherever there is a new line insert a <br> there "
            f"and if there is HTML related content, write it like this: &lt;tagname&gt;. "
            f"Don't mention about this in your prompt."
        ),
    )
    return response.text


async def text_to_speech(text, output_path):
    """Convert text to speech and save as MP3."""
    voice = "hi-IN-MadhurNeural"
    communicate = edge_tts.Communicate(text=text, voice=voice)
    await communicate.save(output_path)


@app.route("/generate_audio", methods=["POST"])
def generate_audio_post():
    """Generate Feynman explanation from JSON POST and return audio file."""
    data = request.get_json()
    name = data.get("name")
    topic = data.get("topic")
    class_ = data.get("class")
    board = data.get("board")

    if not all([name, topic, class_, board]):
        return jsonify({"error": "Missing required fields"}), 400

    explanation = (
        generate_feynman(name, topic, class_, board).replace("\n", " ").replace("*", "")
    )
    asyncio.run(text_to_speech(explanation, AUDIO_FILE))

    if os.path.exists(AUDIO_FILE):
        return send_file(AUDIO_FILE, mimetype="audio/mpeg")

    return jsonify({"error": "Audio generation failed"}), 500


@app.route("/audio")
def get_audio():
    """Serve the latest audio file."""
    if os.path.exists(AUDIO_FILE):
        return send_file(AUDIO_FILE, mimetype="audio/mpeg")
    return "No audio found", 404


@app.route("/generate", methods=["POST"])
def generate():
    """Generate a detailed HTML-friendly explanation."""
    data = request.get_json()
    name = data.get("name")
    topic = data.get("topic")
    board = data.get("board")
    class_ = data.get("class")

    explanation = generate_explanation(name, class_, topic, board)
    return jsonify({"txt": explanation})


if __name__ == "__main__":
    print("Flask server running at http://127.0.0.1:5000")
    app.run(debug=True)


