# coding=UTF-8

import time, re

'''
Représente un log Salesforce
'''
class ApexLog():
	rawBody = None
	id = None
	time  = None
	body  = None
	version = None
	filename = None
	log_levels = None
	header = None

	def isIncomplete(self):
		return (self.id is None) or	(self.time is None) or	(self.version is None) or	(self.log_levels is None) or	(self.body is None)

	def populate(self, rawData, filename):
		if len(rawData) < 1:
			quit('Empty Data')
		self.rawBody = rawData

		self.filename = filename
		filename = filename.strip('./')
		self.id = filename.split('.apexlog')[0]
		self.time = str(time.time())
		self.filename = filename + '_' + self.time + '.apexlog'

		try:
			firstline = rawData.split('\n')[0]
			self.header = firstline
			self.version = firstline.split(' ')[0]
			self.log_levels = firstline.split(' ')[1]
			self.body = rawData.split(firstline)[1][1:]
		except:
			print('Erreur')
			None # No Header


	def dump(self):
		return self.version+' '+self.log_levels+'\n'+self.body

'''
Représente un ApexLog permettant de générer un score de performance.
'''
class ApexScoreLog(ApexLog):

	BOUNDARY_TRANSACTION_START = 'EXECUTION_STARTED'
	BOUNDARY_TRANSACTION_END   = 'EXECUTION_FINISHED'
	BOUNDARY_CODEBLOCK_START   = 'CODE_UNIT_START'
	BOUNDARY_CODEBLOCK_END     = 'CODE_UNIT_FINISHED'
	BOUNDARY_CUMULATIVE_START  = 'CUMULATIVE_LIMIT_USAGE'
	BOUNDARY_CUMULATIVE_END    = 'CUMULATIVE_LIMIT_USAGE_END'

	codeTypes = ['transactions', 'codeblocks', 'cumulatives']

	def __init__(self):
		self.transactionsIndexes = list()
		self.codeblocksIndexes   = list()
		self.cumulativesIndexes  = list()

		self.transactionsNames = list()
		self.codeblocksNames   = list()
		self.cumulativesNames  = list()

	def transactions(self, index):
		codeDataIndexes = self.transactionsIndexes
		return self.extractDataFromRaw(codeDataIndexes, index)

	def cumulatives(self, index):
		codeDataIndexes = self.cumulativesIndexes
		return self.extractDataFromRaw(codeDataIndexes, index)

	def codeblocks(self, index):
		codeDataIndexes = self.codeblocksIndexes
		data = self.extractDataFromRaw(codeDataIndexes, index)
		return data

	def extractDataFromRaw(self, codeDataIndexes, index):
		if index > len(codeDataIndexes) - 1 :
			raise Exception('No transaction with index ' + str(index))
		return '\n'.join(self.rawBody.split('\n')[codeDataIndexes[index][0]:codeDataIndexes[index][1]])


	def populate(self, rawData, filename):
		ApexLog.populate(self, rawData, filename)

		#Parse log Data
		l = 0
		buffer_transaction_start = None
		buffer_codeblock_start = None
		buffer_codeblock_stack = list()
		buffer_cumulative_start = None

		logLines = self.rawBody.split('\n')

		#Initial parsing and blocks detection
		for i in logLines:
			if self.BOUNDARY_TRANSACTION_START in i:
				buffer_codeblock_stack = list() #stack reset
				#print('BOUNDARY_TRANSACTION_START',l)
				buffer_transaction_start = l
				nextLineTable = logLines[l+1].split('|')
				transactionName = nextLineTable[len(nextLineTable)-1]
				self.transactionsNames.append(transactionName)
				l += 1
				continue
			if self.BOUNDARY_TRANSACTION_END in i:
				#print('BOUNDARY_TRANSACTION_END',l)
				if buffer_transaction_start == None:
					raise Exception('Transaction boundary problem')
				self.transactionsIndexes.append([buffer_transaction_start, l])
				buffer_transaction_start = None
				l += 1
				continue

			if (self.BOUNDARY_CODEBLOCK_START in i):
				if self.BOUNDARY_TRANSACTION_START in logLines[l-1]:
					l += 1
					continue
				lineTable = i.split('|')
				codeblockName = lineTable[len(lineTable)-1]
				self.codeblocksNames.append(codeblockName)
				#print('BOUNDARY_CODEBLOCK_START',l)
				buffer_codeblock_stack.append(l)
				l += 1
				continue
			if self.BOUNDARY_CODEBLOCK_END in i:
				if self.BOUNDARY_TRANSACTION_END in logLines[l+1]:
					l += 1
					continue
				#print('BOUNDARY_CODEBLOCK_END',l, i, logLines[l])
				lastindex = buffer_codeblock_stack[len(buffer_codeblock_stack) - 1]
				self.codeblocksIndexes.append([lastindex, l])
				buffer_codeblock_stack = buffer_codeblock_stack[:len(buffer_codeblock_stack) - 1]
				l += 1
				continue
			if (self.BOUNDARY_CUMULATIVE_START in i) and (self.BOUNDARY_CUMULATIVE_END not in i):
				#print('BOUNDARY_CUMULATIVE_START',l)
				buffer_cumulative_start = l
				l += 1
				continue
			if self.BOUNDARY_CUMULATIVE_END in i:
				#print('BOUNDARY_CUMULATIVE_END',l)
				if buffer_cumulative_start == None:
					raise Exception('Cumulative boundary problem')
				self.cumulativesIndexes.append([buffer_cumulative_start, l])
				buffer_cumulative_start = None

				lineTable = logLines[l+2].split('|')
				codeblockName = lineTable[len(lineTable)-1]
				self.cumulativesNames.append(codeblockName)

				l += 1
				continue
			l += 1

		# error control
		if len(self.cumulativesIndexes) == 0:
			raise Exception('Log format probably not valid: no cumulative limits found')


	def CSVScoreLine(self, index):
		scores = list()
		for j in self.cumulatives(index).split('\n'):
			if j[:1] == ' ':
				amountStart = j.find(':')+2
				amountEnd = j[amountStart:].find(' ') + amountStart
				amount = j[amountStart:amountEnd]
				total  = j[amountEnd+8:]
				if total.find('*') != -1: # **** CLOSE TO LIMIT
					total = total[:total.find('*')-1]
				score = '=' + str(amount) + '/' + str(total)
				scores.append(score)

		line = self.cumulativesNames[index] + '\t'
		line += '\t'.join(scores)
		return line

	def scoreAsCSV(self):
		scores = list()
		for i in range(len(self.cumulativesIndexes)):
			scores.append(self.CSVScoreLine(i))
		return '\n'.join(scores)

	def blockName(self, blockNumber):
		return self.codeblocksNames[blockNumber]

	def transactionName(self, blockNumber):
		return self.transactionsNames[blockNumber]

