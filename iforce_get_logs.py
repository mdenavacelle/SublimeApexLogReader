# coding=UTF-8

import os, platform
import urllib, urllib2, json, logging, time, shutil
import sublime, sublime_plugin
import unittest
import apexlog

# coding=UTF-8

# testing
'''
TODO: 
* for loops sans copie ( par référence )
'''
class LogBroker():
	# Configuration
	org    = None
	logdir = None
	logs   = list()

	# Données
	distant = None
	local   = None

	def __init__(self, org, logdir = './logs'):
		self.org = org
		self.logdir = logdir

	def getLocalLogsList(self):
		liste = os.listdir(self.logdir)
		return liste

	def getLocalLogsIdAsList(self):
		liste = self.getLocalLogsList()
		out = set()
		for i in liste:
			out.add(i.split('.apexlog')[0])
		return out

	def getDistantLogsIdList(self):
		self.org.connect()
		query = 'SELECT Id, SystemModStamp from ApexLog WHERE LogUserId = \''+self.org.user_id+'\''
		data = self.org.query( query)
		asJson = json.loads( data)
		out = set()
		for i in asJson['records']:
			out.add( i['Id'])
		self.distant = out
		return self.distant

	def obtain(self):
		logging.error('Recuperation des logs distants')
		self.getDistantLogsIdList()
		for i in self.distant:
			self.logs.append( self.getDistantLog( i))
		return self.logs

	'''
	Factory
	'''
	def getDistantLog(self, id):
		apiURL = '/tooling/sobjects/ApexLog/'+id+'/Body'
		logBody = self.org.get( apiURL)
		logName = id
		log = ApexLog()
		log.populate( logBody, logName)
		return log

	def persist(self):
		logging.error('Ecriture des logs')
		for l in self.logs:
			f = open( self.logdir+'/'+l.filename,'w')
			f.write( l.dump())
			f.close()


'''
Représente une connection à Salesforce
Basé sur iForce et son fichier de connection
'''
class SFDC():
	# Self
	conf = None
	instance = 'https://test.salesforce.com'
	api = '/services/data/v28.0'

	# OAuth2 Authorize
	authurl = instance+'/services/oauth2/token'
	grant_type = 'password'
	access_token = None
	instance_url = None
	user_id = None

	'''
	Constructeur
	'''
	def __init__(self, configObject):
		self.conf = configObject

	'''
	Effectue la connection
	'''
	def connect(self): 
		self.access_token = self.getAccessToken()
		self.user_id = self.getUserId()

	'''
	Etablit la connection OAuth2 et stocke le résultat
	TODO: unit testable
	'''
	def getAuthorization(self):
		hdr = {'Accept': 'application/json'}
		params = {
			'grant_type'    : 'password',
			'client_id'     : self.conf.client_id,
			'client_secret' : self.conf.client_secret,
			'username'      : self.conf.username,
			'password'      : self.conf.password
			}
		req = urllib2.Request( self.authurl, urllib.urlencode( params), headers=hdr)
		opener = urllib2.build_opener()
		try:
			res = opener.open( req)
			res_json = json.loads(res.read())
			# Saves response
			self.access_token = res_json['access_token']
			self.instance_url = res_json['instance_url']
			self.issued_at = res_json['issued_at']
			self.signature = res_json['signature']
			self.id = res_json['id']
		except Exception, e:
			raise Exception( 'Connection impossible')
		# persist
		self.saveToken()

	def getAccessToken(self):
		if self.access_token is None:
			self.getAuthorization()
		return self.access_token

	def getAuthHeader(self):
		return 'Authorization', 'Bearer '+self.access_token

	def saveToken(self):
		f = open('access_token','w')
		f.write(self.access_token)
		f.close()

	def getUserId(self):
		return self.id.split('/id/')[1].split('/')[1]


	'''
	Effectue une requete GET en REST yo
	'''
	def get(self, query):
		url = self.instance_url+self.api+query
		req = urllib2.Request( url)
		req.add_header('Authorization','Bearer '+self.getAccessToken())
		res = urllib2.urlopen( req)
		return res.read()

	'''
	REST SOQL Query
	'''
	def query( self, query):
		encodedQuery = urllib.urlencode({'q' : query})
		apiURL = '/query/?'+encodedQuery
		data = self.get( apiURL )
		if len(data) <= 1:
			raise Exception('Reponse vide')
		return data

'''
Représente le contenu d'un fichier de configuration au format INI
'''
class iForceConfig():
	# business
	username  = None
	password  = None
	serverurl = None
	client_id = None
	client_secret = None

	# self awareness
	filePath  = None

	'''
	TODO: cleaner self control
	'''
	def __init__(self, filePath = './iForce_build.properties'):
		self.filePath = filePath
		confile = open( self.filePath)
		for i in confile.readlines():
			if "username=" in i:
				self.username = i.split('=')[1].strip()
			elif 'password=' in i:
				self.password = i.split('=')[1].strip()
			elif 'serverurl=' in i:
				self.serverurl = i.split('=')[1].strip()
			elif 'client_id=' in i:
				self.client_id = i.split('=')[1].strip()
			elif 'client_secret=' in i:
				self.client_secret = i.split('=')[1].strip()
		if (self.username is None ) or ( self.password is None ) or ( self.serverurl is None ) or ( self.client_id is None ) or ( self.client_secret is None ):
			raise Exception( 'Configuration incomplete !')


# Testing !
# a bit of TDD
class SFDCTests(unittest.TestCase):
	# Data for iForceConfig assertions
	DEV_CREDENTIALS = './sandbox_MNE.properties'
	MOCK_FILENAME   = './mockc_sfdc_config.properties'
	MOCK_USERNAME   = 'test@test.com'
	MOCK_PASSWORD   = 'correcthorsebatterystaple'
	MOCK_SERVERURL  = 'http://server.com'
	MOCK_CLIENT_ID  = 'mockid'
	MOCK_CLIENT_SECRET   = 'mocksecret'
	# ApexLog object and LogBroker
	MOCK_LOG = './mockid_mocktime.apexlog'
	MOCK_LOGS = './logs'
	MOCK_LOGLIST = ['1_mocktime.apexlog', '2_mocktime.apexlog', '3_mocktime.apexlog']
	MOCK_SF_QUERY_RESPONSE = './mock_sf_query_response.json'

	conf = None
	org  = None

	def setUp(self):
		# Mock config file
		confile = open( self.MOCK_FILENAME,'w')
		confile.write( 'username='+ self.MOCK_USERNAME +'\n')
		confile.write( 'password='+ self.MOCK_PASSWORD +'\n')
		confile.write( 'serverurl='+self.MOCK_SERVERURL+'\n')
		confile.write( 'client_id='+self.MOCK_CLIENT_ID+'\n')
		confile.write( 'client_secret='+self.MOCK_CLIENT_SECRET+'\n')
		confile.close()

	'''
	Test wether iForceConfig reads a file and sets its required properties
	'''
	def test_iForceConfig(self):
		conf = iForceConfig( self.MOCK_FILENAME)
		self.assertEquals(conf.username,  self.MOCK_USERNAME )
		self.assertEquals(conf.password,  self.MOCK_PASSWORD )
		self.assertEquals(conf.serverurl, self.MOCK_SERVERURL )
		self.assertEquals(conf.client_id, self.MOCK_CLIENT_ID )
		self.assertEquals(conf.client_secret, self.MOCK_CLIENT_SECRET )
		os.remove( self.MOCK_FILENAME)

	def test_SFDC_getAuth(self):
		conf = iForceConfig( self.DEV_CREDENTIALS)
		sfdc = SFDC( conf)
		res = sfdc.getAuthorization()
		self.assertIsNot( sfdc.access_token, None, 'Auth fail: no access_token')
		self.assertIsNot( sfdc.instance_url, None, 'Auth fail: no instance_url')
		self.assertIsNot( sfdc.issued_at, None, 'Auth fail: no issued_at')
		self.assertIsNot( sfdc.signature, None, 'Auth fail: no signature')
		self.assertIsNot( sfdc.id, None, 'Auth fail: no user id')
		self.assertIsNot( sfdc.getAccessToken(), None, 'No stored access token !')

	def test_SFDC_saves_token(self):
		conf = iForceConfig( self.DEV_CREDENTIALS)
		sfdc = SFDC( conf)
		res = sfdc.getAuthorization()
		self.assertEquals( sfdc.access_token, open('access_token').readlines()[0])

	def test_SFDC_connect(self):
		conf = iForceConfig( self.DEV_CREDENTIALS)
		sfdc = SFDC( conf)
		sfdc.connect()
		self.assertIsNot( sfdc.access_token, None)
		self.assertIsNot( sfdc.user_id, None)

	def init_org(self):
		conf = iForceConfig( self.DEV_CREDENTIALS)
		self.org = SFDC( conf)
		return self.org

	def test_ApexLogBroker(self):
		logBroker = LogBroker( self.init_org())
		self.assertEquals( logBroker.org, self.org)

	def setup_mock_logs_dir(self):
		try:
			os.mkdir( self.MOCK_LOGS)
		except OSError, e:
			# directory exists
			None
		for i in self.MOCK_LOGLIST:
			file( self.MOCK_LOGS+'/'+i,'a').close()

	def teardown_mock_logs_dir(self):
		shutil.rmtree(self.MOCK_LOGS)

	def test_LogBroker_lists_local_logs(self):
		self.setup_mock_logs_dir()
		logBroker = LogBroker( self.init_org())
		res = logBroker.getLocalLogsList()
		self.assertEquals( res, self.MOCK_LOGLIST)
		self.teardown_mock_logs_dir()

	def test_LogBroker_lists_distant_logs(self):
		logBroker = LogBroker( self.init_org())
		self.assertIsNot( len( logBroker.getDistantLogsIdList()), 0 )
		logBroker.obtain()
		logBroker.persist()



if __name__ == '__main__':
	unittest.main()



class iforce_get_logsCommand(sublime_plugin.WindowCommand):
	currentProjectFolder = None
	antBin = None

	def run(self, *args, **kwargs):
		logging.error('GetLogs')
		self.currentProjectFolder = self.window.folders()[0]
		# Connection automatique en environnement iForce
		org = SFDC( iForceConfig( self.currentProjectFolder+'/iForce_build.properties'))
		logBroker = LogBroker( org, self.currentProjectFolder+'/logs')

		# Intégration Sublime Text
		logsList = None
		org.connect()

		query = 'SELECT Id, LogUserId, Request, Operation, Application, Status, SystemModstamp FROM ApexLog'
		#localIds = logBroker.getLocalLogsIdAsList()
		#query += ' WHERE Id not in ('+localIds.join(',')+')'
		logs = logBroker.org.query( query)
		
		# Données de logs
		try:
			apexLogs = logBroker.obtain( )
		except Exception, e:
			logging.exception('Erreur lors de la recupération des logs')

		# Stockage
		try:
			logBroker.persist( )
		except Exception, e:
			logging.exception('Erreur lors de l\'ecriture des logs')
