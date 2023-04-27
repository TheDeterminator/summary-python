from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from youtube_transcript_api import YouTubeTranscriptApi
import json
import requests
from bs4 import BeautifulSoup
import os
from dotenv import load_dotenv

load_dotenv()


app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Create a VideoData model
class VideoData(db.Model):
    video_id = db.Column(db.String, primary_key=True)
    title = db.Column(db.JSON)
    transcript = db.Column(db.Text)

    def __init__(self, video_id, title, transcript):
        self.video_id = video_id
        self.title = title
        self.transcript = transcript


# def import_data_from_json():
#     # Check if there are any records in the VideoData table
#     if VideoData.query.first() is None:
#         try:
#             with open('video_data_cache.json', 'r') as file:
#                 video_data_cache = json.load(file)
#         except FileNotFoundError:
#             video_data_cache = {}

#         for video_id, video_data in video_data_cache.items():
#             video = VideoData.query.get(video_id)
#             if not video:
#                 new_video = VideoData(
#                     video_id=video_id,
#                     title=video_data['title'],
#                     transcript=json.dumps(video_data['transcript'])  # Change this line
#                 )
#                 db.session.add(new_video)
#                 db.session.commit()

#         print('Imported data from video_data_cache.json')
#     else:
#         print('Data already exists in the database, skipping import.')


# Add these lines to read the transcript cache from a file
# try:
#     with open('video_data_cache.json', 'r') as file:
#         video_data_cache = json.load(file)
# except FileNotFoundError:
#     video_data_cache = {}


def get_video_data(video_id):
    try:
        video_data = VideoData.query.get(video_id)
        if video_data:
            return {'title': video_data.title, 'transcript': json.loads(video_data.transcript)}
        else:
            # Build the YouTube video URL
            video_url = f'https://www.youtube.com/watch?v={video_id}'

            # Use requests and BeautifulSoup to extract the video title
            response = requests.get(video_url)
            soup = BeautifulSoup(response.content, 'html.parser')
            video_title = soup.find('title').text.strip().split(' - YouTube')[0]

            # Use the YouTubeTranscriptApi to get the transcript
            transcript = YouTubeTranscriptApi.get_transcript(video_id)

            # Cache the video data in the database
            video_data = VideoData(id=video_id, title=video_title, transcript=transcript)
            db.session.add(video_data)
            db.session.commit()

            return {'title': video_data.title, 'transcript': video_data.transcript}
    except:
        error = 'Error: Invalid URL or no captions available.'
        return {'error': error}

@app.route('/')
def home():
    return render_template('index.html')


@app.route('/get_transcript', methods=['POST'])
def get_transcript():
    youtube_url = request.form['youtube-url']
    video_id_index = youtube_url.find('v=') + 2
    if video_id_index == -1:
        return jsonify({'error': 'Invalid URL or no video ID found.'})
    video_id = youtube_url[video_id_index:]
    if '&' in video_id:
        video_id = video_id[:video_id.index('&')]

    video_data = get_video_data(video_id)
    if 'error' in video_data:
        return jsonify(video_data)

    # Concatenate the transcript text into a single string
    transcript_text = ''
    for item in video_data['transcript']:
        transcript_text += item['text'] + ' '

    # Return a JSON response with the video data and transcript text
    response = {
        'title': video_data['title'],
        'transcript': transcript_text,
        'video_url': youtube_url
    }
    return jsonify(response)


@app.route('/get_video_title/<video_id>')
def get_video_title(video_id):
    try:
        # Build the YouTube video URL
        video_url = f'https://www.youtube.com/watch?v={video_id}'

        # Use requests and BeautifulSoup to extract the video title
        response = requests.get(video_url)
        soup = BeautifulSoup(response.content, 'html.parser')
        video_title = soup.find('title').text.strip().split(' - YouTube')[0]

        return jsonify({'title': video_title, 'video_url': video_url})
    except:
        error = 'Error: Invalid URL or no captions available.'
        return jsonify({'error': error})


if __name__ == "__main__":
    # with app.app_context():
        # import_data_from_json()
    app.run(debug=True)
