import requests

BOT_TOKEN = '7875785978:AAEpBaaWco33dvQZ2ipQvmqKSivXvvf3cyI'

response = requests.get(f'https://api.telegram.org/bot{BOT_TOKEN}/getUpdates')
print(response.json())
