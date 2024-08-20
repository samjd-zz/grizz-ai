import tweepy
import requests
from config import load_config
from logger import app_logger

config = load_config()

# X_TWITTER: Authenticate with v1.1 API for media upload
auth = tweepy.OAuthHandler(config.X_CONSUMER_KEY, config.X_CONSUMER_SECRET)
auth.set_access_token(config.X_ACCESS_TOKEN, config.X_ACCESS_TOKEN_SECRET)
api = tweepy.API(auth)

# X_TWITTER: Authenticate with v2 API for posting tweet
x_tweet_client = tweepy.Client(
    consumer_key=config.X_CONSUMER_KEY,
    consumer_secret=config.X_CONSUMER_SECRET,
    access_token=config.X_ACCESS_TOKEN,
    access_token_secret=config.X_ACCESS_TOKEN_SECRET
)

def post_to_twitter(photo_path, message, link):
    media = api.media_upload(photo_path)
    media_id = media.media_id_string
    tweet = x_tweet_client.create_tweet(text=f'{message} {link}', media_ids=[media_id])
    app_logger.debug(f'X_Tweet posted: {tweet}')

def post_to_facebook(photo_path, message, link):
    url = f'https://graph.facebook.com/{config.FB_PAGE_ID}/photos'
    payload = {
        'caption': f'{message}\n{link}',
        'access_token': config.FB_ACCESS_TOKEN
    }
    files = {
        'source': open(photo_path, 'rb')
    }
    response = requests.post(url, data=payload, files=files)
    app_logger.debug(f'Facebook Response: {response.text}')