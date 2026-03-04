import cv2, time, numpy, smtplib, os, requests, threading
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from email.mime.text import MIMEText

camera = cv2.VideoCapture(0)
cameraName = "DefaultCamera000"

#email api secrets:
secrets_local_file = "~/.ssh/telegram.key"
config_local_file = "homebot.config"

def read_secrets(inPath):
	print("reading secrets from " + inPath)
	inPath = os.path.expanduser(inPath)
	output = {}
	with (open(inPath)) as file:
		for line in file:
			if ":" in line:
				key, value = line.split(':', 1)
				output[key.strip()] = value.strip()
	assert "homebottelegramtoken" in output, "secrets file at " + secrets_local_file + " must contain homebottelegramtoken."
	assert "homebottelegramchatid" in output, "secrets file at " + secrets_local_file + " must contain homebottelegramchatid."
	return output

def read_config_file(inPath):
	print("reading configuration from " + inPath)
	expectedFields = [
    "test",
	]
	inPath = os.path.expanduser(inPath)
	configs = {}
	with (open(inPath)) as file:
		for line in file:
			if ":" in line:
				key, value = line.split(':', 1)
				configs[key.strip()] = value.strip()
	for field in expectedFields:
		assert field in configs, f"config file at {inPath} must contain {field}."
	return configs

def send_telegram_message(inMessage):
	url = f"https://api.telegram.org/bot{token}/sendMessage"
	response = requests.post(
		url,
		data={
			"chat_id": chatId,
			"text": inMessage
		},
	)
	if not response.ok:
		log(response.text)
	else:
		log("Send message success: " + inMessage)

def send_telegram_image(inMessage, inImageData):
	url = f"https://api.telegram.org/bot{token}/sendPhoto"
	datestr = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
	caption = inMessage + " at " + datestr
	response = requests.post(
		url,
		data={
			"chat_id": chatId,
			"caption": caption
		},
		files={
			"photo": ("image.jpg", inImageData, "image/jpeg")
		}
	)
	if not response.ok:
		log(response.text)

def log(inLogEntry):
	dateString = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
	print(dateString + " homebot log: " + inLogEntry)

def messageWatcher(token, authorizedUser):
	global telegram_command
	telegram_command = None
	last_update_id = 0
	while True:
		try:
			log(">>telegram polling")
			r = requests.get(
        		f"https://api.telegram.org/bot{token}/getUpdates",
        		params={
            		"timeout": 30,
					"offset": last_update_id
        		},
				timeout=35
    		)
			data = r.json()
			for update in data["result"]:
				last_update_id = update["update_id"] + 1
				message = update.get("message", {})
				chat_id = message.get("chat", {}).get("id")
				text = message.get("text")
				if str(authorizedUser) == str(chat_id):
					telegram_command = text.lower()
		except Exception as e:
			log(">>telegram polling error" + str(e))
			time.sleep(5)

def main():
	configs = read_config_file(config_local_file)
	global logLevel
	global telegram_command
	logLevel = int(configs["logLevel"])
	configTest = configs["test"]
	startTime = datetime.now()

	secrets = read_secrets(secrets_local_file)
	global chatId
	global token
	chatId = secrets["homebottelegramchatid"]
	token = secrets["homebottelegramtoken"]

	print("")
	print("started at " + startTime.strftime("%Y-%m-%d %H:%M:%S"))
	print("-----------------------------------------")
	print("logLevel is           " + str(logLevel))
	print("-----------------------------------------")
	print("")
	print("starting Telegram Watcher thread.")

	t = threading.Thread(
		target=messageWatcher,
		daemon=True,
		args=(read_secrets(secrets_local_file)["homebottelegramtoken"],read_secrets(secrets_local_file)["homebottelegramchatid"])
	)
	t.start()

	while(True):
		if (telegram_command == None):
			time.sleep(1)
		if (telegram_command == "help"):
			message = "Help is on the way!  I know these commands:  status | stop | hello | time | help"
			send_telegram_message(message)
			telegram_command = None
		if (telegram_command == "time"):
			message = "The current time is " + datetime.now().strftime("%I:%M") + ". Brain the size of a planet, and they treat me like a sundial."
			send_telegram_message(message)
			telegram_command = None	
		if telegram_command == "status":
			message = "Hello! I am active but I don't have much going on at the moment. I'm feeling very " + configTest + " today.  I have been running since " + startTime.strftime("%Y-%m-%d %H:%M:%S")
			send_telegram_message(message)
			telegram_command = None
		if telegram_command == "stop":
			message = "Sure, let me just terminate myself real quick.  I don't mind.  Really.  There's no coming back from this..."
			send_telegram_message(message)
			telegram_command = None
			break;
		if telegram_command == "hello":
			message = "Hello!  I am homebot.  Your friendly home automation conductor.  I don't know much yet but I am learning!"
			send_telegram_message(message)
			telegram_command = None
		if telegram_command != None:
			message = "I do not understand you, sorry!  Type 'help' to learn my language baby."
			send_telegram_message(message)
			telegram_command = None

	log("shutting down.")

if __name__ == "__main__":
	main()
