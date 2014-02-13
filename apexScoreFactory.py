# coding=UTF-8

'''
apexScoreFactory

Version 1
Martin de Navacelle

'''
usage = '''

Creates a Score report based on a Salesforce's Apex debug log.

Make sure your log has the following filters only:
APEX_PROFILING,INFO

Outputs: chemin_du_log.nom_du_log.apexlog.csv

> Usage: python apexScoreFactory chemin_du_log.nom_du_log.apexlog
'''

from apexlog import *
import sys


def quitter(message):
	if message != None:
		print(message)
	print('\n',usage[185:])
	quit()



opts = sys.argv[1:2]

if len(opts) == 0:
	quitter()

opts = opts[0]

# verification de l'existence du fichier
try:
   with open(opts):
       print('Found file')
except IOError:
   quitter('/!\ File not found.')

print('Extracting Score...')
log = ApexScoreLog()

log.populate(open(opts).read(), opts)

#if log.version != '28.0':
#	raise Exception('Version non valide '+log.version)

csvScore = log.scoreAsCSV()

if len(csvScore) < 1:
	quitter('/!\ Empty result, quitting.')


print('Creating '+opts+'.csv')
outfile = open(opts+'.csv', 'w')
outfile.write(csvScore)
outfile.close()

print('Done :)')

