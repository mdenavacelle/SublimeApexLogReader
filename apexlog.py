# coding=UTF-8

import unittest, time, re

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

	def CSVScoreLine(self, index):
		scores = list()
		for j in self.cumulatives(index).split('\n'):
			if j[:1] == ' ':
				amountStart = j.find(':')+2
				amountEnd = j[amountStart:].find(' ') + amountStart
				amount = j[amountStart:amountEnd]
				total  = j[amountEnd+8:]
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

# Testing !
class test_log_parser_test(unittest.TestCase):
	MOCK_LOG = './mock.apexlog'
	VALID_HEADER = '28.0 APEX_PROFILING,INFO'
	MOCK_BLOCK='''10:05:55.417 (10417361000)|EXECUTION_STARTED
10:05:45.411 (411557000)|CODE_UNIT_STARTED|[EXTERNAL]|01p200000005MDn|TESTAP04Account.testBetweenDateObtention
10:05:45.412 (412186000)|LIMIT_USAGE|[297]|SCRIPT_STATEMENTS|1|200000
10:05:45.412 (412263000)|LIMIT_USAGE|[298]|SCRIPT_STATEMENTS|2|200000
10:05:45.412 (412275000)|LIMIT_USAGE|[299]|SCRIPT_STATEMENTS|3|200000
10:05:45.417 (417718000)|LIMIT_USAGE|[59]|SCRIPT_STATEMENTS|4|200000
10:05:45.425 (425311000)|LIMIT_USAGE|[174]|SCRIPT_STATEMENTS|5|200000
10:05:45.425 (425338000)|LIMIT_USAGE|[175]|SCRIPT_STATEMENTS|6|200000
10:05:45.425 (425352000)|LIMIT_USAGE|[176]|SCRIPT_STATEMENTS|7|200000
10:05:45.425 (425364000)|LIMIT_USAGE|[177]|SCRIPT_STATEMENTS|8|200000
10:05:45.425 (425380000)|LIMIT_USAGE|[178]|SCRIPT_STATEMENTS|9|200000
10:05:45.425 (425392000)|LIMIT_USAGE|[179]|SCRIPT_STATEMENTS|10|200000
10:05:45.425 (425404000)|LIMIT_USAGE|[180]|SCRIPT_STATEMENTS|11|200000
10:05:45.425 (425416000)|LIMIT_USAGE|[181]|SCRIPT_STATEMENTS|12|200000
10:05:45.425 (425428000)|LIMIT_USAGE|[182]|SCRIPT_STATEMENTS|13|200000
10:05:45.425 (425442000)|LIMIT_USAGE|[183]|SCRIPT_STATEMENTS|14|200000
10:05:45.425 (425454000)|LIMIT_USAGE|[184]|SCRIPT_STATEMENTS|15|200000
10:05:45.425 (425466000)|LIMIT_USAGE|[185]|SCRIPT_STATEMENTS|16|200000
10:05:45.425 (425475000)|LIMIT_USAGE|[193]|SCRIPT_STATEMENTS|17|200000
10:05:45.458 (458682000)|LIMIT_USAGE|[12]|SCRIPT_STATEMENTS|18|200000
10:05:45.458 (458720000)|LIMIT_USAGE|[13]|SCRIPT_STATEMENTS|19|200000
10:05:45.458 (458732000)|LIMIT_USAGE|[14]|SCRIPT_STATEMENTS|20|200000
10:05:45.458 (458742000)|LIMIT_USAGE|[15]|SCRIPT_STATEMENTS|21|200000
10:05:45.458 (458752000)|LIMIT_USAGE|[16]|SCRIPT_STATEMENTS|22|200000
10:05:45.458 (458763000)|LIMIT_USAGE|[17]|SCRIPT_STATEMENTS|23|200000
10:05:45.458 (458774000)|LIMIT_USAGE|[22]|SCRIPT_STATEMENTS|24|200000
10:05:45.459 (459117000)|LIMIT_USAGE|[23]|SCRIPT_STATEMENTS|25|200000
10:05:45.459 (459435000)|LIMIT_USAGE|[23]|SOQL|1|100
10:05:45.459 (459442000)|LIMIT_USAGE|[23]|AGGS|0|300
10:05:45.495 (495514000)|LIMIT_USAGE|[23]|SOQL_ROWS|1|50000
10:05:45.495 (495785000)|LIMIT_USAGE|[24]|SCRIPT_STATEMENTS|26|200000
10:05:45.495 (495833000)|LIMIT_USAGE|[25]|SCRIPT_STATEMENTS|27|200000
10:05:45.495 (495882000)|LIMIT_USAGE|[68]|SCRIPT_STATEMENTS|28|200000
10:05:45.496 (496092000)|LIMIT_USAGE|[195]|SCRIPT_STATEMENTS|29|200000
10:05:45.514 (514597000)|LIMIT_USAGE|[200]|SCRIPT_STATEMENTS|30|200000
10:05:45.514 (514612000)|LIMIT_USAGE|[221]|SCRIPT_STATEMENTS|31|200000
10:05:45.514 (514801000)|LIMIT_USAGE|[237]|SCRIPT_STATEMENTS|32|200000
10:05:45.514 (514901000)|LIMIT_USAGE|[245]|SCRIPT_STATEMENTS|33|200000
10:05:45.514 (514978000)|LIMIT_USAGE|[288]|SCRIPT_STATEMENTS|34|200000
10:05:45.515 (515111000)|LIMIT_USAGE|[327]|SCRIPT_STATEMENTS|35|200000
10:05:45.515 (515142000)|LIMIT_USAGE|[444]|SCRIPT_STATEMENTS|36|200000
10:05:45.515 (515306000)|LIMIT_USAGE|[456]|SCRIPT_STATEMENTS|37|200000
10:05:45.515 (515514000)|LIMIT_USAGE|[472]|SCRIPT_STATEMENTS|38|200000
10:05:45.516 (516357000)|LIMIT_USAGE|[554]|SCRIPT_STATEMENTS|39|200000
10:05:45.516 (516513000)|LIMIT_USAGE|[64]|SCRIPT_STATEMENTS|40|200000
10:05:45.516 (516534000)|LIMIT_USAGE|[69]|SCRIPT_STATEMENTS|41|200000
10:05:45.516 (516616000)|METHOD_ENTRY|[299]|01p200000002YJY|AP04Account.betweenDateObtention(Date)
10:05:45.516 (516723000)|SYSTEM_METHOD_ENTRY|[250]|Date.today()
10:05:45.516 (516775000)|SYSTEM_METHOD_EXIT|[250]|Date.today()
10:05:45.516 (516808000)|SYSTEM_METHOD_ENTRY|[250]|Date.daysBetween(Date)
10:05:45.516 (516825000)|SYSTEM_METHOD_EXIT|[250]|Date.daysBetween(Date)
10:05:45.516 (516847000)|METHOD_EXIT|[299]|01p200000002YJY|AP04Account.betweenDateObtention(Date)
10:05:45.516 (516860000)|LIMIT_USAGE|[302]|SCRIPT_STATEMENTS|45|200000
10:05:45.516 (516868000)|LIMIT_USAGE|[303]|SCRIPT_STATEMENTS|46|200000
10:05:45.516 (516879000)|METHOD_ENTRY|[303]|01p200000002YJY|AP04Account.betweenDateObtention(Date)
10:05:45.516 (516914000)|METHOD_EXIT|[303]|01p200000002YJY|AP04Account.betweenDateObtention(Date)
10:05:45.516 (516925000)|LIMIT_USAGE|[304]|SCRIPT_STATEMENTS|50|200000
10:05:45.563 (516991000)|CUMULATIVE_LIMIT_USAGE
10:05:45.563|LIMIT_USAGE_FOR_NS|(default)|
  Number of SOQL queries: 1 out of 100
  Number of query rows: 1 out of 50000
  Number of SOSL queries: 0 out of 20
  Number of DML statements: 0 out of 150
  Number of DML rows: 0 out of 10000
  Number of code statements: 50 out of 200000
  Maximum CPU time: 0 out of 10000
  Maximum heap size: 0 out of 6000000
  Number of callouts: 0 out of 10
  Number of Email Invocations: 0 out of 10
  Number of fields describes: 0 out of 100
  Number of record type describes: 0 out of 100
  Number of child relationships describes: 0 out of 100
  Number of picklist describes: 0 out of 100
  Number of future calls: 0 out of 10

10:05:45.563|CUMULATIVE_LIMIT_USAGE_END

10:05:45.517 (517029000)|CODE_UNIT_FINISHED|TESTAP04Account.testBetweenDateObtention
10:05:54.908 (9908917000)|EXECUTION_FINISHED'''
	
	MOCK_TRANSACTION='''10:05:55.417 (10417361000)|EXECUTION_STARTED
10:05:45.411 (411557000)|CODE_UNIT_STARTED|[EXTERNAL]|01p200000005MDn|TESTAP05Account.testBetweenDateObtention
10:05:45.516 (516534000)|LIMIT_USAGE|[69]|SCRIPT_STATEMENTS|41|200000
10:05:45.516 (516616000)|METHOD_ENTRY|[299]|01p200000002YJY|AP04Account.betweenDateObtention(Date)
10:05:45.516 (516723000)|SYSTEM_METHOD_ENTRY|[250]|Date.today()
10:05:45.516 (516775000)|SYSTEM_METHOD_EXIT|[250]|Date.today()
10:05:45.516 (516808000)|SYSTEM_METHOD_ENTRY|[250]|Date.daysBetween(Date)
10:05:45.516 (516825000)|SYSTEM_METHOD_EXIT|[250]|Date.daysBetween(Date)
10:05:45.516 (516847000)|METHOD_EXIT|[299]|01p200000002YJY|AP04Account.betweenDateObtention(Date)
10:05:45.516 (516860000)|LIMIT_USAGE|[302]|SCRIPT_STATEMENTS|45|200000
10:05:45.516 (516868000)|LIMIT_USAGE|[303]|SCRIPT_STATEMENTS|46|200000
10:05:45.516 (516879000)|METHOD_ENTRY|[303]|01p200000002YJY|AP04Account.betweenDateObtention(Date)
10:05:45.516 (516914000)|METHOD_EXIT|[303]|01p200000002YJY|AP04Account.betweenDateObtention(Date)
10:05:45.516 (516925000)|LIMIT_USAGE|[304]|SCRIPT_STATEMENTS|50|200000
10:05:45.563 (516991000)|CUMULATIVE_LIMIT_USAGE
10:05:45.563|LIMIT_USAGE_FOR_NS|(default)|
  Number of SOQL queries: 1 out of 100
  Number of query rows: 1 out of 50000
  Number of SOSL queries: 0 out of 20
  Number of DML statements: 0 out of 150
  Number of DML rows: 0 out of 10000
  Number of code statements: 50 out of 200000
  Maximum CPU time: 0 out of 10000
  Maximum heap size: 0 out of 6000000
  Number of callouts: 0 out of 10
  Number of Email Invocations: 0 out of 10
  Number of fields describes: 0 out of 100
  Number of record type describes: 0 out of 100
  Number of child relationships describes: 0 out of 100
  Number of picklist describes: 0 out of 100
  Number of future calls: 0 out of 10

10:05:45.563|CUMULATIVE_LIMIT_USAGE_END

10:05:45.517 (517029000)|CODE_UNIT_FINISHED|TESTAP05Account.testBetweenDateObtention
10:05:54.908 (9908917000)|EXECUTION_FINISHED'''

	MOCK_CODEBLOCK='''10:05:45.411 (411557000)|CODE_UNIT_STARTED|[EXTERNAL]|01p200000005MDn|TESTAP06Account.testBetweenDateObtention
10:05:45.516 (516534000)|LIMIT_USAGE|[69]|SCRIPT_STATEMENTS|41|200000
10:05:45.516 (516616000)|METHOD_ENTRY|[299]|01p200000002YJY|AP04Account.betweenDateObtention(Date)
10:05:45.516 (516723000)|SYSTEM_METHOD_ENTRY|[250]|Date.today()
10:05:45.516 (516775000)|SYSTEM_METHOD_EXIT|[250]|Date.today()
10:05:45.516 (516808000)|SYSTEM_METHOD_ENTRY|[250]|Date.daysBetween(Date)
10:05:45.516 (516825000)|SYSTEM_METHOD_EXIT|[250]|Date.daysBetween(Date)
10:05:45.516 (516847000)|METHOD_EXIT|[299]|01p200000002YJY|AP04Account.betweenDateObtention(Date)
10:05:45.516 (516860000)|LIMIT_USAGE|[302]|SCRIPT_STATEMENTS|45|200000
10:05:45.516 (516868000)|LIMIT_USAGE|[303]|SCRIPT_STATEMENTS|46|200000
10:05:45.516 (516879000)|METHOD_ENTRY|[303]|01p200000002YJY|AP04Account.betweenDateObtention(Date)
10:05:45.516 (516914000)|METHOD_EXIT|[303]|01p200000002YJY|AP04Account.betweenDateObtention(Date)
10:05:45.516 (516925000)|LIMIT_USAGE|[304]|SCRIPT_STATEMENTS|50|200000
10:05:45.563 (516991000)|CUMULATIVE_LIMIT_USAGE
10:05:45.563|LIMIT_USAGE_FOR_NS|(default)|
  Number of SOQL queries: 1 out of 100
  Number of query rows: 1 out of 50000
  Number of SOSL queries: 0 out of 20
  Number of DML statements: 0 out of 150
  Number of DML rows: 0 out of 10000
  Number of code statements: 50 out of 200000
  Maximum CPU time: 0 out of 10000
  Maximum heap size: 0 out of 6000000
  Number of callouts: 0 out of 10
  Number of Email Invocations: 0 out of 10
  Number of fields describes: 0 out of 100
  Number of record type describes: 0 out of 100
  Number of child relationships describes: 0 out of 100
  Number of picklist describes: 0 out of 100
  Number of future calls: 0 out of 10

10:05:45.563|CUMULATIVE_LIMIT_USAGE_END

10:05:45.517 (517029000)|CODE_UNIT_FINISHED|TESTAP06Account.testBetweenDateObtention'''

	MOCK_CODEBLOCK_2='''10:05:45.411 (411557000)|CODE_UNIT_STARTED|[EXTERNAL]|01p200000005MDn|TESTAP07Account.testBetweenDateObtention
10:05:45.516 (516534000)|LIMIT_USAGE|[69]|SCRIPT_STATEMENTS|41|200000
10:05:45.516 (516616000)|METHOD_ENTRY|[299]|01p200000002YJY|AP04Account.betweenDateObtention(Date)
10:05:45.516 (516723000)|SYSTEM_METHOD_ENTRY|[250]|Date.today()
10:05:45.516 (516775000)|SYSTEM_METHOD_EXIT|[250]|Date.today()
10:05:45.516 (516808000)|SYSTEM_METHOD_ENTRY|[250]|Date.daysBetween(Date)
10:05:45.516 (516825000)|SYSTEM_METHOD_EXIT|[250]|Date.daysBetween(Date)
10:05:45.516 (516847000)|METHOD_EXIT|[299]|01p200000002YJY|AP04Account.betweenDateObtention(Date)
10:05:45.516 (516860000)|LIMIT_USAGE|[302]|SCRIPT_STATEMENTS|45|200000
10:05:45.516 (516868000)|LIMIT_USAGE|[303]|SCRIPT_STATEMENTS|46|200000
10:05:45.516 (516879000)|METHOD_ENTRY|[303]|01p200000002YJY|AP04Account.betweenDateObtention(Date)
10:05:45.516 (516914000)|METHOD_EXIT|[303]|01p200000002YJY|AP04Account.betweenDateObtention(Date)
10:05:45.516 (516925000)|LIMIT_USAGE|[304]|SCRIPT_STATEMENTS|50|200000
10:05:45.563 (516991000)|CUMULATIVE_LIMIT_USAGE
10:05:45.563|LIMIT_USAGE_FOR_NS|(default)|
  Number of SOQL queries: 1 out of 100
  Number of query rows: 1 out of 50000
  Number of SOSL queries: 0 out of 20
  Number of DML statements: 0 out of 150
  Number of DML rows: 0 out of 10000
  Number of code statements: 50 out of 200000
  Maximum CPU time: 0 out of 10000
  Maximum heap size: 0 out of 6000000
  Number of callouts: 0 out of 10
  Number of Email Invocations: 0 out of 10
  Number of fields describes: 0 out of 100
  Number of record type describes: 0 out of 100
  Number of child relationships describes: 0 out of 100
  Number of picklist describes: 0 out of 100
  Number of future calls: 0 out of 10

10:05:45.563|CUMULATIVE_LIMIT_USAGE_END

10:05:45.517 (517029000)|CODE_UNIT_FINISHED|TESTAP07Account.testBetweenDateObtention'''

	MOCK_CUMULATIVE_BLOCK='''10:05:45.563 (516991000)|CUMULATIVE_LIMIT_USAGE
10:05:45.563|LIMIT_USAGE_FOR_NS|(default)|
  Number of SOQL queries: 1 out of 100
  Number of query rows: 1 out of 50000
  Number of SOSL queries: 0 out of 20
  Number of DML statements: 0 out of 150
  Number of DML rows: 0 out of 10000
  Number of code statements: 50 out of 200000
  Maximum CPU time: 0 out of 10000
  Maximum heap size: 0 out of 6000000
  Number of callouts: 0 out of 10
  Number of Email Invocations: 0 out of 10
  Number of fields describes: 0 out of 100
  Number of record type describes: 0 out of 100
  Number of child relationships describes: 0 out of 100
  Number of picklist describes: 0 out of 100
  Number of future calls: 0 out of 10
'''

	MOCK_BLOCK_AS_CSV_LINE='TESTAP04Account.testBetweenDateObtention	=1/100	=1/50000	=0/20	=0/150	=0/10000	=50/200000	=0/10000	=0/6000000	=0/10	=0/10	=0/100	=0/100	=0/100	=0/100	=0/10'

	'''
	Tests whether log has correct filters setup
	'''
	def validLogFiltersForScoring(self):
		log = ApexScoreLog()
		log.populate(open(self.MOCK_LOG).read(), self.MOCK_LOG)

		self.assertEquals(log.header, self.VALID_HEADER)

	def test_detectBlocksAndKeepsLineNumbers(self):
		log = ApexScoreLog()
		log.populate(self.MOCK_BLOCK, 'test_detectBlocksAndKeepsLineNumbers')

		self.assertEquals(len(log.transactionsIndexes), 1)
		self.assertEquals(log.transactionsIndexes[0], [0,78])

	def test_detectSeveralBlocksAndKeepsLineNumbers(self):
		log = ApexScoreLog()
		log.populate(self.MOCK_BLOCK + '\n' + self.MOCK_BLOCK, 'test_detectSeveralBlocksAndKeepsLineNumbers')

		self.assertEquals(len(log.transactionsIndexes), 2)
		self.assertEquals(log.transactionsIndexes[0], [0,78])
		self.assertEquals(log.transactionsIndexes[1], [79+0,79+78])

	def test_detectSeveralInternalBlocksAndKeepsLineNumbers(self):
		log = ApexScoreLog()
		log.populate(open(self.MOCK_LOG).read(), 'test_detectSeveralInternalBlocksAndKeepsLineNumbers')

		self.assertEquals(len(log.transactionsIndexes), 1)
		self.assertEquals(log.transactionsIndexes[0], [2,73])
		self.assertEquals(log.codeblocksIndexes[0], [4,5])
		self.assertEquals(log.codeblocksIndexes[1], [6,27])
		self.assertEquals(log.codeblocksIndexes[2], [29,50])
		self.assertEquals(log.codeblocksIndexes[3], [28,51])

	def test_getSpecificBlock(self):
		log = ApexScoreLog()
		log.populate(self.MOCK_BLOCK, 'test_getSpecificBlock')

		self.assertEquals(log.transactions(0), '\n'.join(self.MOCK_BLOCK.split('\n')[:len(self.MOCK_BLOCK.split('\n'))-1])) # just pop the last line

	def test_codeBlocksToCodeName(self):
		log = ApexScoreLog()
		log.populate(open(self.MOCK_LOG).read(), 'test_codeBlocksToCodeName')
		self.assertEquals(log.blockName(0), 'Validation:Opportunity:new')
		self.assertEquals(log.blockName(1), 'OpportunityAfterInsert on Opportunity trigger event AfterInsert for [006g0000003LETO]')
		self.assertEquals(log.blockName(2), 'Workflow:Opportunity')
		self.assertEquals(log.blockName(3), 'OpportunityBeforeUpdate on Opportunity trigger event BeforeUpdate for [006g0000003LETO]')
		self.assertEquals(log.transactionName(0), 'execute_anonymous_apex')
		try: # could not use self.assertRaises
			log.transactionName(1)
			self.assertTrue(False)
		except:
			self.assertTrue(True)

	def test_codeblockNameFromTransaction(self):
		log = ApexScoreLog()
		log.populate(open(self.MOCK_LOG).read(), 'test_codeblockNameFromTransaction')

		self.assertEquals(log.transactionName(0), 'execute_anonymous_apex')

	def test_cumulativeToCSVLine(self):
		log = ApexScoreLog()
		log.populate(self.MOCK_BLOCK, 'cumulativeToCSVLine')
		self.assertEquals(log.CSVScoreLine(0), self.MOCK_BLOCK_AS_CSV_LINE)

	def test_wholeApexLogfileExtraction(self):
		log = ApexScoreLog()
		log.populate(open(self.MOCK_LOG).read(), 'test_wholeApexLogfileExtraction')

		self.assertEquals(len(log.transactionsIndexes), 1)
		self.assertEquals(len(log.codeblocksIndexes), 4)
		self.assertEquals(len(log.cumulativesIndexes), 3)

	def test_getScoreAsCSV(self):
		log = ApexScoreLog()
		log.populate(open('mock.apexLog').read(), 'test_getScoreAsCSV')

		expected = '''OpportunityAfterInsert on Opportunity trigger event AfterInsert for [006g0000003LETO]\t=2/100\t=1/50000\t=0/20\t=1/150\t=1/10000\t=21/200000\t=0/10000\t=0/6000000\t=0/10\t=0/10\t=0/100\t=0/100\t=0/100\t=0/100\t=0/10
OpportunityBeforeUpdate on Opportunity trigger event BeforeUpdate for [006g0000003LETO]\t=2/100\t=1/50000\t=0/20\t=1/150\t=1/10000\t=28/200000\t=0/10000\t=0/6000000\t=0/10\t=0/10\t=0/100\t=0/100\t=0/100\t=0/100\t=0/10
execute_anonymous_apex\t=2/100\t=1/50000\t=0/20\t=1/150\t=1/10000\t=28/200000\t=0/10000\t=0/6000000\t=0/10\t=0/10\t=0/100\t=0/100\t=0/100\t=0/100\t=0/10'''

		self.assertEquals(log.scoreAsCSV(), expected)


if __name__ == '__main__':
	unittest.main()
