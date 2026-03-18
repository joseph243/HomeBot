from __future__ import annotations
import time, os, requests, threading, queue
from datetime import datetime
from multiprocessing.managers import BaseManager
from device import Device, DeviceType

#api secrets:
secrets_local_file = "~/.ssh/telegram.key"
config_local_file = "homebot.config"

class MessageManager(BaseManager):
	pass

devices: list[Device] = []

def initializeMessageSend(key) -> queue.Queue:
	log("initialize network message send")
	AUTH = read_secrets(secrets_local_file)["homebotqueuetoken"]
	PORT = 55556
	HOST = '10.0.0.235'
	class MessageManager(BaseManager):
		pass
	MessageManager.register('outgoing')
	manager = MessageManager(address=(HOST, PORT), authkey=key)
	manager.connect()
	return manager.outgoing()

def initializeMessageReceive(key) -> queue.Queue:
	LISTEN_TO_HOST = '0.0.0.0'
	PORT = 55555
	AUTH = read_secrets(secrets_local_file)["homebotqueuetoken"]
	log("initialize network message receive")
	messages = queue.Queue()
	class MessageManager(BaseManager):
		pass
	MessageManager.register('incoming', callable=lambda: messages)
	manager = MessageManager(address=(LISTEN_TO_HOST,PORT), authkey=key)
	server = manager.get_server()
	thread = threading.Thread(target = server.serve_forever, daemon=True)
	thread.start()
	log(f"Listening for messages on {LISTEN_TO_HOST}:{PORT}")
	return messages

def handle_message_from_device(in_dict):
	t = in_dict["type"]
	n = in_dict["name"]
	o = True
	try:
		device_type = DeviceType(t.upper())
	except ValueError:
		raise ValueError(f"Invalid device type: {t}")
	d = Device(n, device_type, o)
	track_device(d)

def track_device(inDevice):
	isNewDevice = True
	isComingOnline = True
	for d in devices:
		#lazy way to update last contact time, just remove and re-add every cycle
		if d.name == inDevice.name:
			isComingOnline = not d.online
			devices.remove(d)
			isNewDevice = False
	devices.append(inDevice)
	if isNewDevice:
		send_telegram_message("New Device Detected: " + str(inDevice))
	elif isComingOnline:
		send_telegram_message(str(inDevice))

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
    "deviceOfflineAfterMinutes",
	"checkDeviceFrequencyMinutes",
	"homebotIP"
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

def generateStatusMessage() -> str:
	botStatus = "I have been running since " + startTime.strftime("%Y-%m-%d %H:%M:%S")
	if not devices:
		return "HomeBot is running, but tracking zero devices. " + botStatus
	else:
		body = "\n".join(str(d) for d in devices)
		return botStatus + "\n" + "I am tracking these devices: " + "\n" + body

def checkHeartbeat():
	now = datetime.now()
	for d in devices:
		seconds_since_contact = (now - d.last_contact).total_seconds()
		newStatus = seconds_since_contact < configOfflineAfterSeconds
		if (newStatus != d.online):
			d.online = newStatus
			send_telegram_message(str(d))

def main():
	global telegram_command
	global startTime
	global chatId
	global token
	global devices
	global configOfflineAfterSeconds
	global homebotip

	configs = read_config_file(config_local_file)
	configOfflineAfterSeconds = int(configs["deviceOfflineAfterMinutes"]) * 60
	configCheckEverySeconds = int(configs["checkDeviceFrequencyMinutes"]) * 60
	homebotip = configs["homebotIP"]

	startTime = datetime.now()

	secrets = read_secrets(secrets_local_file)

	chatId = secrets["homebottelegramchatid"]
	token = secrets["homebottelegramtoken"]
	NETWORKAUTH = (secrets["homebotqueuetoken"]).encode('utf-8')

	print("")
	print("homebot started at " + startTime.strftime("%Y-%m-%d %H:%M:%S"))
	print("homebot ip is set to " + homebotip)
	print("-----------------------------------------")
	print("check in on devices every " + configs["deviceOfflineAfterMinutes"] + " minutes.")
	print("devices offline after " + configs["checkDeviceFrequencyMinutes"] + " minutes.")
	print("-----------------------------------------")
	print("")
	print("starting Telegram Watcher thread.")

	t = threading.Thread(
		target=messageWatcher,
		daemon=True,
		args=(read_secrets(secrets_local_file)["homebottelegramtoken"],read_secrets(secrets_local_file)["homebottelegramchatid"])
	)
	t.start()

	print("starting network communications")
	incomingNetworkComms = initializeMessageReceive(NETWORKAUTH)
	outgoingNetworkComms = initializeMessageSend(NETWORKAUTH)

	next_device_check = time.time() + configCheckEverySeconds

	send_telegram_message("HomeBot activated!")
	while(True):
		time.sleep(1)
		##monitor device comms:
		try:
			dev_msg_dict = incomingNetworkComms.get_nowait()
			handle_message_from_device(dev_msg_dict)
		except queue.Empty:
			pass

		##update device statuses:
		now = time.time()
		if (now >= next_device_check):
			print("status check..")
			checkHeartbeat()
			next_device_check = now + configCheckEverySeconds

		##monitor telegram/user comms:
		if (telegram_command == None):
			continue
		if (telegram_command == "time"):
			message = "The current time is " + datetime.now().strftime("%I:%M") + ". Brain the size of a planet, and they treat me like a sundial."
			send_telegram_message(message)
			telegram_command = None	
		if telegram_command == "status":
			message = generateStatusMessage() 
			send_telegram_message(message)
			telegram_command = None
		if telegram_command == "die":
			message = "Sure, let me just terminate myself real quick.  I don't mind.  Really.  It probably won't hurt..."
			send_telegram_message(message)
			telegram_command = None
			break
		if telegram_command == "hello" or telegram_command == "hi":
			message = "Hello!  I am HomeBot, your friendly home automation conductor."
			send_telegram_message(message)
			telegram_command = None
		if (telegram_command == "help"):
			message = "Help is on the way!  I know these commands:  status | die | hello | hi | time | help"
			send_telegram_message(message)
			telegram_command = None
		if telegram_command != None:
			message = "I do not understand this command!  Type 'help' for a list of commands."
			send_telegram_message(message)
			telegram_command = None

	exitMessage = "shutting down."
	send_telegram_message(exitMessage)
	log(exitMessage)

if __name__ == "__main__":
	main()
