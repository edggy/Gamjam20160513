import json
import time
import random
import socket
import threading
import datetime

from filelock import FileLock

class Player:
	def __init__(self, connection, client_address):
		self.connection = connection
		self.client_address = client_address
		
		self.tickets = 100.0
		
		#self.name = self.get('What is your name?')
		self.name = '%s:%s' % self.client_address
		
		self.data = ''
		
	def depositTicket(self, bucket):
		if self.tickets >= 1:
			bucket += Ticket(self)
			self.tickets -= 1
			return True
		return False
	
	def __hash__(self):
		return hash(self.client_address)
	
	def get(self, info):
		while True:
			self.connection.sendall('req:%s' % info)
			result = self.connection.recv(1024).split(':')
			if result[0] == 'req':
				return result[1]
			
	
	def serve(self):
		self.data += self.connection.recv(1024)
		data, self.data = self.data.split('\0', 1)
		return data
	
	def send(self, data):
		self.connection.sendall(data)

class Ticket:
	def __init__(self, player):
		self.owner = player
		self.number = random.random()
		
	def __hash__(self):
		return int(self.number * 2**32)

class Bucket:
	def __init__(self):
		self.tickets = set([])
		self.available = True
	
	def addTicket(self, ticket):
		if not self.available or ticket in self.tickets:
			return False
		
		self.tickets.add(ticket)
		return True
	
	def __iadd__(self, ticket):
		self.addTicket(ticket)
	
	def __len__(self):
		return self.numTickets()
	
	def numTickets(self):
		return len(self.tickets)
	
	def empty(self):
		self.tickets.clear()

class GameServer:
	def __init__(self, settingFile):
		with open(settingFile) as f:
			self._settings = json.load(f)
		self.alive = threading.Event()
		self.threads = []
		self.players = []
		self.startTime = 0
		self.now = time.time
		self.roundNumber = 0
		self.buckets = [Bucket() for n in range(self._settings['num_buckets'])]
		self.house = 0
		
		
	def startRound(self):
		for b in self.buckets:
			b.empty()
			b.available = True
		self.startTime = self.now()
		self.roundNumber += 1
	
	def endRound(self):
		for b in self.buckets:
			b.available = False
			
		minBuckets = None
		minVal = None
		
		for b in self.buckets:
			tix = b.numTickets()
			if minVal is None or tix < minVal:
				minBuckets = [b]
				minVal = tix
			elif tix == minVal:
				minBuckets.append(b)
		
		# The prize is equal to the number of buckets but is divided among all smallest buckets
		prize = float(len(self.buckets)) / len(minBuckets)
		
		for b in minBuckets:
			for t in b.tickets:
				t.owner.tickets += prize
				self.house -= prize
				
		self.log('House:\t%s tickets' % (self.house), 5)
		for p in self.players:
			try:
				p.send('tickets:%s\0' % p.tickets)
				self.log('%s:\t%s tickets' % (p.name, p.tickets), 5)
			except socket.error:
				pass
		
	
	def doRound(self):
		while self.alive.isSet():
			self.startRound()
			time.sleep(int(self._settings['round_time']))
			self.endRound()
			
	def doPlayer(self, player):
		try:
			while self.alive.isSet():
				try:
					request = player.serve().split(':')
					if request[0] == 'time':
						player.send('time:%s\0' % (int(self._settings['round_time']) - self.now() + self.startTime))
						self.log('%s:\trequested time' % player.name, 10)
					elif request[0] == 'buckets':
						player.send('buckets:%s\0' % len(self.buckets))
						self.log('%s:\trequested buckets' % player.name, 10)
					elif request[0] == 'tickets':
						player.send('tickets:%s\0' % player.tickets)
						self.log('%s:\trequested tickets:\t%s' % (player.name, player.tickets), 10)
					elif request[0] == 'bucket':
						num = int(request[1])
						player.send('bucket:%s:%s\0' % (num, self.buckets[num].numTickets()))
						self.log('%s:\trequested bucket:\t%s' % (player.name, num), 10)
					elif request[0] == 'allbucket':
						ret = 'allbucket:%s' % len(self.buckets)
						for b in self.buckets:
							ret += ':%s' % b.numTickets()
						player.send(ret + '\0')
						self.log('%s:\trequested all buckets' % player.name, 10)
							
					elif request[0] == 'add':
						num = int(request[1])	
						self.log('%s:\trequested add:\t%s' % (player.name, num), 10)
						if self.buckets[num].addTicket(Ticket(player)):
							player.tickets -= 1
							self.house += 1
							player.send('add:%s\0' % num)
							player.send('tickets:%s\0' % player.tickets)
							self.log('%s:\tnow has:\t%s tickets' % (player.name, player.tickets), 10)
						else:
							player.send('add:error\0')
				except socket.error:
					player.send('Error\0')
				
		except socket.error:
			pass
		
		try:
			player.connection.shutdown(SHUT_RDWR)
		except:
			pass
		try:
			player.connection.close()
		except:
			pass			
	
	def run(self):
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		server_address = (self._settings['address'], int(self._settings['port']))
		self.sock.bind(server_address)
		self.sock.listen(5)
		self.log('Server is listening on %s:%d' % server_address,1)

		# Start looking for connections
		# self._sock.listen(self._settings['listen_queue_length'])
		
		self.alive.set()
		
		roundThread = threading.Thread(target=self.doRound ,args=())
		roundThread.start()
		self.threads.append(roundThread)
		#try:
		while self.alive.isSet():
			connection, client_address = self.sock.accept()
			new_player = Player(connection, client_address)
			self.players.append(new_player)
			playerThread = threading.Thread(target=self.doPlayer ,args=(new_player,))
			playerThread.start()
			self.threads.append(playerThread)
				
		#except Exception as e:
		#	self.log('error: %s' % e)
		self.cleanup()	
	
	def report(self, msg):
		# This function is too complicated to properly comment
		sys.stdout.flush()

		now = str(datetime.datetime.now())
		
		# Grab the lock
		log_file = self._settings['log_file']
		try:
			with FileLock(log_file), open(log_file, 'a') as f:
				f.write('%s:\t' % self.now())
				f.write(msg + '\n')
		except OSError:
			pass

		return msg	
	
	def log(self, msg, log_level=0):
		if log_level <= self._settings['verbose']:
			print msg
			return self.report(msg)
		else:
			return msg # This is pythonic	
	
	def cleanup(self):
		# Clean up threads
		self.log("Attempting to close threads...", 10)
		self.alive.clear() # Unset alive, this informs the class that no more server actions should take place
		for thread in self.threads:
			thread.join()
		threads = []
		self.log("Threads successfully closed", 10)

		# Clean up sockets
		self.log("Terminating active connections...", 10)
		for player in self.players:
			try:
				player.connection.shutdown(SHUT_RDWR)
			except:
				pass
			try:
				player.connection.close()
			except:
				pass			
		self.log("Active connections terminated", 10)	
		
		
if __name__ == "__main__":
	import sys
	server = GameServer(sys.argv[1])
	server.run()