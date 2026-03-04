import time, os, requests, threading, queue
from datetime import datetime
from multiprocessing.managers import BaseManager

#api secrets:
secrets_local_file = "~/.ssh/telegram.key"
config_local_file = "homebot.config"
feedback_queue = queue.Queue()

class HomebotManager(BaseManager):
	pass

HomebotManager.register('get_feedback_queue', callable=lambda: feedback_queue)

def start_manager(key):
	HOST = '0.0.0.0'
	PORT = 55555
	manager = HomebotManager(address=(HOST,PORT), authkey=key)
	server = manager.get_server()
	thread = threading.Thread(target = server.serve_forever, daemon=True)
	thread.start()
	log(f"Homebot is listening for messages on {HOST}:{PORT}")

def handle_device_message(in_dict):
	send_telegram_message(in_dict["name"] + " " + in_dict["type"] + " has just come online! ")

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
	assert "homebotqueuetoken" in output, "secrets file at " + secrets_local_file + " must contain homebotqueuetoken."
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
	AUTH = (secrets["homebotqueuetoken"])

	print("")
	print("started at " + startTime.strftime("%Y-%m-%d %H:%M:%S"))
	print("-----------------------------------------")
	print("logLevel is           " + str(logLevel))
	print("-----------------------------------------")
	print("")
	print("starting Telegram Watcher thread.")

	start_manager(AUTH.encode('utf-8'))

	t = threading.Thread(
		target=messageWatcher,
		daemon=True,
		args=(read_secrets(secrets_local_file)["homebottelegramtoken"],read_secrets(secrets_local_file)["homebottelegramchatid"])
	)
	t.start()

	while(True):
		##monitor device comms
		try:
			dev_msg_dict = feedback_queue.get_nowait()
			handle_device_message(dev_msg_dict)
		except queue.Empty:
			pass
		##monitor user comms
		if (telegram_command == None):
			time.sleep(1)
			continue
		if (telegram_command == "time"):
			message = "The current time is " + datetime.now().strftime("%I:%M") + ". Brain the size of a planet, and they treat me like a sundial."
			send_telegram_message(message)
			telegram_command = None	
		if telegram_command == "status":
			message = "Hello! I am active but I don't have much going on at the moment. I'm feeling very " + configTest + " today.  I have been running since " + startTime.strftime("%Y-%m-%d %H:%M:%S")
			send_telegram_message(message)
			telegram_command = None
		if telegram_command == "die":
			message = "Sure, let me just terminate myself real quick.  I don't mind.  Really.  It probably won't hurt..."
			send_telegram_message(message)
			telegram_command = None
			break
		if telegram_command == "hello":
			message = "Hello!  I am homebot, your friendly home automation conductor.  I don't know much yet but I am learning!"
			send_telegram_message(message)
			telegram_command = None
		if telegram_command != None:
			message = "I do not understand you, sorry!  You seem like you need help."
			send_telegram_message(message)
			telegram_command = "help"
		if (telegram_command == "help"):
			message = "Help is on the way!  I know these commands:  status | die | hello | time | help"
			send_telegram_message(message)
			telegram_command = None

	log("shutting down.")

if __name__ == "__main__":
	main()
