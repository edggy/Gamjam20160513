import os
import sys
import time
import socket
import threading

class Player:
	def __init__(self):
		try:
			server_info = (socket.gethostbyname(sys.argv[1]), int(sys.argv[2]))
		except:
			server_info = (socket.gethostbyname(raw_input('Server: ')), int(raw_input('Port: ')))
			# How did you mess this up?
			#print "Usage:\n%s [ip] [port]" % sys.argv[0]
			#raw_input("Press the any key to finish.")
			#sys.exit(1)
			
		# Check if ip is in ipv4 format or ipv6 format
		ipv4 = False
		if '.' in server_info[0]: #this works, screw regex
			ipv4 = True

		# Connect to server
		if ipv4:
			self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		else:
			self.server = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)

		# Connect to the server
		connected = False

		# Attempt to connect 10 times. If it fails all 10, give up.
		for i in range(1, 11):
			try:
				self.server.connect(server_info)
				connected = True
				break
			except:
				print "Could not connect to the server (attempt #%d). Trying again." % i

		if not connected:
			print "Could not connect to the server, it might be down or super busy."
			raw_input("Press the any key to finish.")
			sys.exit(1)

		self.tickets = -1
		self.buckets = {}
		self.numBuckets = 0
		self.time = -1
		self.myBuckets = {}
		self.select = 0

		self.alive = threading.Event()
		self.change = False
		self.data = ''

	def recv(self):
		self.data += self.server.recv(1024)
		data, self.data = self.data.split('\0', 1)
		return data
	
	def send(self, data):
		self.server.send(str(data) + '\0')
	
	def __str__(self):
		ret = ''
		ret += 'Tickets:\t%d\t\tTime Left:\t%d\n' % (self.tickets, self.time)
		for n in range(self.numBuckets):
			ret += '%d\t' % n
		ret += '\n'
		for n in range(self.numBuckets):
			if n in self.buckets:
				ret += '%d\t' % self.buckets[n]
			#else:
				#self.server.send('bucket:%s' % n)
				#ret += '??\t'
		ret += '\n'
		for n in range(self.numBuckets):
			if n in self.myBuckets:
				ret += '%d\t' % self.myBuckets[n]
			else:
				ret += '0\t'   
		return ret

	def doListen(self):
		try:
			while self.alive.isSet():
				try:
					
					recv = self.recv().split(':')
					#if recv[0] == 'req':
						#self.server.send('req:%s' % raw_input(recv[1]))
					#print recv
					if recv[0] == 'tickets':
						newTickets = float(recv[1])
						if self.tickets != newTickets:
							self.tickets = newTickets
							self.change = True
					elif recv[0] == 'buckets':
						self.numBuckets = int(recv[1])                        
					elif recv[0] == 'time':
						self.time = float(recv[1])
						self.change = True
					elif recv[0] == 'bucket':
						self.buckets[int(recv[1])] = int(recv[2])  
						self.change = True
					elif recv[0] == 'allbucket':  
						self.numBuckets = int(recv[1])
						for n in range(self.numBuckets):
							self.buckets[n] = int(recv[n+2])
						self.change = True
					elif recv[0] == 'add':
						try:
							self.myBuckets[int(recv[1])] += 1
							self.change = True
						except:
							pass
				except socket.error:
					self.send('error')
		except socket.error:
			pass
		print 'ERROR'

	def updateWindow(self, window):
		maxY, maxX = window.getmaxyx()
		window.erase()
		window.addstr(0,0,'Tickets: %d' % self.tickets)
		timeStr = 'Time Left: %d' % self.time
		window.addstr(0, maxX - len(timeStr), timeStr)
				
		
		if self.numBuckets > 0:
			Yspace = maxY/8
			Xspace = maxX/(self.numBuckets+1)
			
			window.addstr(Yspace,0,'Bin Number:')
			window.addstr(Yspace*2,0, 'Ticket Count:')
			window.addstr(Yspace*3,0, 'My Tickets:')			
			
			for n in range(self.numBuckets):
				count = 0
				mycount = 0
				try:
					count = self.buckets[n]
					mycount = self.mybuckets[n]
				except:
					pass
				
				window.addstr(Yspace,(n+1)*Xspace + Xspace/2,str((n+1)))
				window.addstr(Yspace*2,(n+1)*Xspace + Xspace/2, str(count))
				window.addstr(Yspace*3,(n+1)*Xspace + Xspace/2, str(mycount))
				if self.select == n:
					window.addstr(Yspace*3+1,(n+1)*Xspace + Xspace/2, '^')
					window.addstr(Yspace*3+2,(n+1)*Xspace + Xspace/2 - 1, 'add')
		window.move(maxY-1, 0)
		
	def doAction(self, window = None):
		self.send('tickets')
		self.send('buckets')
		if window is not None:
			window.timeout(0)
		self.lastCheck = 0
		
		while self.alive.isSet():
			curTime = time.time() 
			if curTime - self.lastCheck > 1:
				self.send('time')
				self.send('allbucket')
				self.lastCheck = curTime
			if window is None:
				if self.change:
					os.system('cls')
					print self
					self.change = False
			else:
				self.updateWindow(window)
				
				c = window.getch()
				if c == curses.ERR:
					pass
				elif c == curses.KEY_LEFT:
					if self.select > 0:
						self.select -= 1
				elif c == curses.KEY_RIGHT:
					if self.select < self.numBuckets - 1:
						self.select += 1
				elif c == ord(' '):
					self.send('add:%s' % self.select)
				elif c == ord('q'):
					self.alive.clear()
			

	def run(self, window = None):
		self.alive.set()
		listenThread = threading.Thread(target=self.doListen ,args=())
		listenThread.start()
		actionThread = threading.Thread(target=self.doAction ,args=(window,))
		actionThread.start()
		listenThread.join()
		actionThread.join()

if __name__ == "__main__":
	client = Player()
	try:
		# requires curses, you can get it at http://www.lfd.uci.edu/~gohlke/pythonlibs/#curses
		import curses		
		curses.wrapper(client.run)
	except ImportError:
		client.run()