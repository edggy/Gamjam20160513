import json
import time
import threading

class BucketGame:
	def __init__(self, settingFile):
		with open(settingFile) as f:
			self._settings = json.load(f)        

		self.players = {}
		self.buckets = [Bucket() for n in range(self._settings['num_buckets'])]
		self.house = 0
		self.ticketLock = threading.Lock()
		self.alive = threading.Event()
		
		self.now = time.time

	def newPlayer(self, playerID):
		self.players[playerID] = Player(playerID, self._settings['starting_tickets'])

	def depositTickets(self, playerID, bucketNum, numTickets = 1):
		numTickets = int(numTickets)
		deposited = self.players[playerID].depositTickets(self.buckets[bucketNum], numTickets)
		with self.ticketLock:
			self.house += deposited
			
	def getTimeLeft(self):
		return float(self._settings['round_time']) - self.now() + self.startTime
	
	def getBuckets(self):
		return [len(b) for b in self.buckets]
	
	def getState(self, playerID = None):
		state = {}
		state['time'] = self.getTimeLeft()
		state['buckets'] = self.getBuckets()
		if playerID in self.players:
			player = self.players[playerID]
			state['tickets'] = player.getTickets()
		
	def startRound(self):
		for b in self.buckets:
			b.empty()
			b.available.set()
		self.startTime = self.now()
		self.roundNumber += 1
		
	def endRound(self):
		for b in self.buckets:
			b.available.unset()
			
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
		
		# Deliver prizes
		for b in minBuckets:
			for t in b.tickets:
				with t.owner.ticketLock:
					collected = t.collect(t, prize)
				with self.ticketLock:
					self.house -= collected
				
		self.log('House:\t%s tickets' % (self.house), 5)
		
	def doRounds(self):
		while self.alive.isSet():
			self.startRound()
			time.sleep(int(self._settings['round_time']))
			self.endRound()	
			
	def start(self):
		self.alive.set()
		self.roundThread = threading.Thread(target=self.doRound ,args=())
		self.roundThread.start()
		
	def stop(self):
		self.alive.clear()
		self.roundThread.join()
		
	def report(self, msg):
		# This function is too complicated to properly comment
		sys.stdout.flush()
	
		# Grab the lock
		log_file = self._settings['log_file']
		try:
			with FileLock(log_file), open(log_file, 'a') as f:
				f.write('%s:\t%s\n' % (self.now(), msg))
		except OSError:
			pass
	
		return msg	
	
	def log(self, msg, log_level=0):
		if log_level <= self._settings['verbose']:
			print msg
			return self.report(msg)
		else:
			return msg # This is pythonic	
		

class Player:
	def __init__(self, playerID, startTickets = 0):
		self.playerID = playerID
		self.tickets = startTickets
		self.depositedTickets = set([])
		
		self.ticketLock = threading.Lock()
		
	def getTickets(self):
		return int(self.tickets)
		
	def depositTickets(self, bucket, numTickets = 1):
		numTickets = int(numTickets)
		
		if self.tickets >= numTickets:
			newTicket = Ticket(self)
			if bucket.addTicket(newTicket) == newTicket:
				self.depositedTickets.add(newTicket)
				
			with self.ticketLock:
				self.tickets -= numTickets
			return numTickets
		return 0
	
	def collect(self, ticket, winnings):
		if ticket in self.depositedTickets:
			self.depositedTickets.remove(ticket)
			with self.ticketLock:
				self.tickets += winnings
			return winnings
		return 0
		
	def endRound(self):
		self.depositedTickets.clear()
		
	def __hash__(self):
		return hash(self.playerID)

class Ticket:
	def __init__(self, player):
		self.owner = player
		self.number = random.random()
		
	def collect(self, winnings):
		return self.owner.collect(self, winnings)
		
	def __eq__(self, other):
		try:
			return self.number == other.number
		except:
			return False
		
	def __hash__(self):
		return int(self.number * 2**32)

class Bucket:
	def __init__(self):
		self.tickets = set([])
		self.ticketLock = threading.Lock()
		self.available = threading.Event()
		
	def isOpen(self):
		return self.available.isSet()

	def addTicket(self, ticket):
		if not self.available or ticket in self.tickets:
			return None
		
		with self.ticketLock:
			self.tickets.add(ticket)
		return ticket

	def __iadd__(self, ticket):
		self.addTicket(ticket)

	def __len__(self):
		return self.numTickets()

	def numTickets(self):
		return len(self.tickets)

	def empty(self):
		with self.ticketLock:
			self.tickets.clear()    

