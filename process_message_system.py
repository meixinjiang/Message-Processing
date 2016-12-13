import os
import pickle
import sys
import threading
import time
from queue import Queue
import atexit

ANY='any'

"""
MessageProc class
"""
class MessageProc:

	"""
	Initiates the instance variables of the MessageProc class.
	"""
	def __init__(self):
		self.arrived_condition = threading.Condition()
		self.communication_queue = Queue()
		self.open_pipes_dict = {}
		self.received_message_list = []
		self.lock = threading.Lock()

	"""
	Removes the current process' named pipe if it exists.
	"""
	def clean_up(self):
		if os.path.exists('/tmp/pipe'+str(os.getpid())):
			os.remove('/tmp/pipe'+str(os.getpid()))

	"""
	Creates a named pipe for the current process given its ID.
	Starts a daemon thread targeting the extract_from_pipe method.
	"""
	def main(self, *args):
		pipe_name = '/tmp/pipe' + str(os.getpid())
		if not os.path.exists(pipe_name):
			os.mkfifo(pipe_name)	#creates the pipe with with a unique ID

		transfer_thread = threading.Thread(target=self.extract_from_pipe, daemon=True)
		transfer_thread.start()			

	"""
	Clones the current process resulting in the creation of a child process.
	Child process calls the main() method to create its pipe.

	returns - child's process ID
	"""
	def start(self, *args):
		pid = os.fork()

		#removes named pipes for the process once it has finished
		atexit.register(self.clean_up)	

		if pid == 0:
			self.main(*args)	#calls main() method of MessageProc
			sys.exit(0)
		else:
			return pid


	"""
	Sends a message consisting of a label and its values to the specified process.

	parameters - process ID, label, values
	"""
	def give(self, pid, label, *values):
		#makes sure the pipe being sent to has been created
		if not os.path.exists('/tmp/pipe' + str(pid)):
			time.sleep(0.01)

		pickleFile = open('/tmp/pipe' + str(pid), 'wb', buffering=0)

		pickle.dump((label, values), pickleFile)	

	"""
	Matches the received messages with the message types.

	parameters - varying message types
	returns - action associated with the message type
	"""
	def receive(self, *message_types):
		self.time_out = None

		#Finds the first TimeOut message (if it exists) and stores it
		for kind in message_types:
			if isinstance(kind, TimeOut) and self.time_out == None:
					self.time_out = kind

		while True:
			#Removes a message from the communication queue and appends it
			#to the received messages list, given the queue is not empty
			if self.communication_queue.qsize() > 0:
				self.lock.acquire()
				self.received_message_list.append(self.communication_queue.get())
				self.lock.release()

			#Matches messages with the message types
			elif self.received_message_list != []:

				#loops through all the received messages
				for i in range(len(self.received_message_list)):
					message = self.received_message_list[i]

					#loops through all the message types
					for types in message_types:
						if isinstance(types, Message):
							
							#matches the message type to any message label
							if types.getMessage() == ANY:
								if types.getGuard():
									if message[1] != ():	#message type action takes parameters
										self.lock.acquire()
										self.received_message_list.pop(i)
										self.lock.release()
										return types.getAction(message[1][0])
									else:	#action does not need parameters
										self.lock.acquire()
										self.received_message_list.pop(i)
										self.lock.release()
										return types.getAction()								

							#message label matches the message type
							elif types.getMessage() == message[0]:
								if types.getGuard():
									if message[1] != ():	#message type action takes parameters
										self.lock.acquire()
										self.received_message_list.pop(i)
										self.lock.release()
										return types.getAction(message[1][0])
									else:
										self.lock.acquire()
										self.received_message_list.pop(i)
										self.lock.release()
										return types.getAction()	
							else:	#message does not match any of the message types
								continue 	#continues to the next message

				#Times out if left-over messages do not match any message types
				#and a TimeOut has been provided
				if self.received_message_list != [] and self.time_out != None:
					with self.arrived_condition:
						#starts countdown, messages may arrive and interrupt 
						wait = self.arrived_condition.wait(self.time_out.getSeconds())
						if wait == False:	#countdown has not been interrupted
							return self.time_out.getAction()

			else:	#communication queue is empty
				if self.time_out != None:	#times out if a TimeOut has been provided
					with self.arrived_condition:
						#starts countdown, message may arrive and interrupt
						wait = self.arrived_condition.wait(self.time_out.getSeconds())
						if wait == False:	#countdown has not been interrupted
							return self.time_out.getAction()
				else:
					with self.arrived_condition:
						#waits until a new message arrives
						self.arrived_condition.wait()

	"""
	Extracts messages from the current process' named pipe and appends it to the
	communication queue.

	Credits to Robert Sheehan (taken from lecture 9)
	"""
	def extract_from_pipe(self):
		unpickleFile = open('/tmp/pipe' + str(os.getpid()), 'rb')
		while True:
			try:
				extractedMessage = pickle.load(unpickleFile)
				with self.arrived_condition:
					self.communication_queue.put(extractedMessage)
					self.arrived_condition.notify()
			except EOFError:
				time.sleep(0.01)

"""
Message class
"""
class Message:
	"""
	Initiates the instance variables of the Message class
	"""
	def __init__(self, message, action=lambda: None, guard=lambda: True):
		self.message = message
		self.action = action
		self.guard = guard

	"""
	Returns the message label
	"""
	def getMessage(self):
		return self.message

	"""
	Returns the action
	"""
	def getAction(self, *values):
		return self.action(*values)

	"""
	Returns the guard
	"""
	def getGuard(self):
		return self.guard()

"""
TimeOut class
"""
class TimeOut:
	"""
	Initiates the instance variables of the TimeOut class
	"""
	def __init__(self, seconds, action=lambda: None):
		self.seconds = seconds
		self.action = action

	"""
	Returns the number of seconds
	"""
	def getSeconds(self):
		return self.seconds

	"""
	Returns the action
	"""
	def getAction(self, *values):
		return self.action(*values)

