from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, VideoUnavailable, NoTranscriptFound
import json
import requests
# from requests import RequestException
from requests.exceptions import RequestException, Timeout, TooManyRedirects
from bs4 import BeautifulSoup
import os
from sqlalchemy.dialects.mysql import MEDIUMTEXT, LONGTEXT

app = Flask(__name__)

# app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://thedeterminator:testpassword@thedeterminator.mysql.pythonanywhere-services.com/thedeterminator$summarydb'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Create a VideoData model


class VideoData(db.Model):
    video_id = db.Column(db.String(255), primary_key=True)
    title = db.Column(db.JSON)
    transcript = db.Column(MEDIUMTEXT)

    def __init__(self, video_id, title, transcript):
        self.video_id = video_id
        self.title = title
        self.transcript = transcript

class History(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    # video_id = db.Column(db.String(255), db.ForeignKey('video_data.video_id'), nullable=False)

    def __init__(self, user_id, video_id):
        self.user_id = user_id
        self.video_id = video_id

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(255), nullable=False)

    def __init__(self, username):
        self.username = username



def get_video_data(video_id):
    try:
        video_data = VideoData.query.get(video_id)

        if video_data:
            return {'title': video_data.title, 'transcript': json.loads(video_data.transcript)}
        else:
            # Build the YouTube video URL
            video_url = f'https://www.youtube.com/watch?v={video_id}'

            try:
                # Use requests and BeautifulSoup to extract the video title
                response = requests.get(video_url)
                response.raise_for_status()
                soup = BeautifulSoup(response.content, 'html.parser')
                video_title_element = soup.find('title')
                if video_title_element:
                    video_title = video_title_element.text.strip().split(
                        ' - YouTube')[0]
                else:
                    return {'error': 'Error: Could not find the video title.'}
            except RequestException as e:
                return {'error': f'Error: Failed to fetch the video URL. {str(e)}'}
            except Timeout:
                return {'error': 'Error: The request timed out.'}
            except TooManyRedirects:
                return {'error': 'Error: Too many redirects.'}
            except Exception as e:
                return {'error': f'Error: An unexpected error occurred 1. {str(e)}'}

            try:
                # Use the YouTubeTranscriptApi to get the transcript
                transcript = YouTubeTranscriptApi.get_transcript(video_id)
            except (TranscriptsDisabled, NoTranscriptFound):
                return {'error': 'Error: No captions available for this video.'}
            except VideoUnavailable:
                return {'error': 'Error: The video is unavailable.'}

            # Cache the video data in the database
            video_data = VideoData(
                video_id=video_id, title=video_title, transcript=json.dumps(transcript))
            db.session.add(video_data)
            db.session.commit()

            # return {'title': video_data.title, 'transcript': video_data.transcript} may want to change back to this implemntation and wrap the transcript in json.loads() becasue I don't want the data to get out of step it shouldn't but just in case
            return {'title': video_title, 'transcript': transcript}
    except Exception as e:
        error = f'Error: An unexpected error occurred 2. {str(e)}'
        return {'error': error}


@app.route('/')
def home():
    return render_template('index.html')

def extract_youtube_video_id(youtube_url):
    # Follow redirects to get the final URL
    try:
        response = requests.get(youtube_url, allow_redirects=True)
        final_url = response.url
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Error: Failed to fetch the URL. {str(e)}'})

    # Check if the final URL is a valid YouTube URL
    if "www.youtube.com/watch?v=" not in final_url and "youtu.be/" not in final_url:
        return jsonify({'error': 'Invalid URL or no video ID found.'})

    # Extract the video ID
    if "www.youtube.com/watch?v=" in final_url:
        video_id = final_url.split("www.youtube.com/watch?v=")[-1]
    elif "youtu.be/" in final_url:
        video_id = final_url.split("youtu.be/")[-1]

    if '&' in video_id:
        video_id = video_id[:video_id.index('&')]

    return video_id, final_url


@app.route('/get_transcript', methods=['POST'])
def get_transcript():
    youtube_url = request.form['youtube-url']
    test_user_id = 1

    video_id, final_url = extract_youtube_video_id(youtube_url)

    video_data = get_video_data(video_id)
    if 'error' in video_data:
        return jsonify(video_data)

    # existing_history = History.query.filter_by(user_id=test_user_id, video_id=video_id).first()

    # if not existing_history:
    #         history = History(user_id=test_user_id, video_id=video_id)
    #         db.session.add(history)
    #         db.session.commit()


    # Concatenate the transcript text into a single string
    transcript_text = ''

    for item in video_data['transcript']:
        transcript_text += item['text'] + ' '

    # Return a JSON response with the video data and transcript text
    response = {
        'title': video_data['title'],
        'transcript': transcript_text,
        'video_url': final_url
    }
    return jsonify(response)


@app.route('/get_video_title/<video_id>')
def get_video_title(video_id):
    # Check if the video_id parameter is valid
    if len(video_id) != 11 or not video_id.isalnum():
        error = 'Error: Invalid video ID.'
        return jsonify({'error': error})

    try:
        # Build the YouTube video URL
        video_url = f'https://www.youtube.com/watch?v={video_id}'

        # Use requests and BeautifulSoup to extract the video title
        response = requests.get(video_url)
        response.raise_for_status()  # raise HTTPError if status is not 200
        soup = BeautifulSoup(response.content, 'html.parser')
        video_title = soup.find('title').text.strip().split(' - YouTube')[0]

        return jsonify({'title': video_title, 'video_url': video_url})
    except requests.exceptions.RequestException as e:
        error = f'Error: {e}'
        return jsonify({'error': error})
    except (AttributeError, IndexError):
        error = 'Error: Unable to extract video title.'
        return jsonify({'error': error})


if __name__ == "__main__":
    app.run(debug=True)
