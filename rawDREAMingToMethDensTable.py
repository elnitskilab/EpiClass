#!/usr/bin/env	python

import sys
import pandas as pd
import numpy as np
import re
import datetime
import ntpath

import argparse
from argparse import RawTextHelpFormatter


#--------------------------------------------------------------------------
#--------------------------------------------------------------------------

# Command line variables:


parser = argparse.ArgumentParser(formatter_class=RawTextHelpFormatter,
	description=
	'''
	Convert Raw DREAMing datafile to either 'plasmaMeltPeakCounts.csv' or 'methylationDensityTable.csv'

	note: 'plasmaMeltPeakCounts.csv' is a deprecated file type. Originally used in MDBC beta version.

	'methylationDensityTable.csv' is used for MDBCanalysisAndPlots.py and other scripts in the MDBC analysis pipeline.

	IMPORTANT:
	Converting the data into 'methylationDensityTable.csv' requires a "temp_to_density" table, and "numCpGs" parameters
	that have already been determined for the DREAMing locus in question.
	''',

	epilog=
	'''
	usage:
	./convertRawDREAMingToMethDensTable.py -data raw_DREAMing_data_table.csv -temps meltTempsToMD.csv -cpgs numCpGs

	example:
	./convertRawDREAMingToMethDensTable.py -data 20190211-DREAMing_well_melt_temps_raw.csv -temps ZNF154DREAMingMeltTempsToMD.csv -cpgs 14 -bg -info Samples,copies_loaded,date
	'''
	)

parser.add_argument('-data', '--rawDREAMingFile', metavar='rawDREAMingFile.csv', required=True, action="store",
	help='''REQUIRED.
	CSV file containing raw DREAMing melting peak temperature data.

	Structure should be as follows:
	sample   	XXXX_L    XXXX_H 
	copies_loaded    6000    6000
	1		80.8
	2		80.8
	3		80.8	84.0
	4		80.8
	5		80.8
	6		80
	7		80.8	83.8
	8		80.8	82.6
	9		80.8
	10		80
	11		80
	12		80.8
	plate    	A    	A
	date    	9.12    9.12

	sample --> first row are the samples names. Each sample has two columns designated by '_L' and '_H'. L = lower melting peak temperature and H = temperature of second melting peak farthest to the right (if exists) (aka the highest on the melt trace).
	copies_loaded --> row containing number of genomic equivalents loaded into the DREAMing assay for the given sample on the given plate and date run. Because two columns are designated for a sample, value should be the same for each of those cells.
	1:12 --> wells 1-12 on a given row of a 96-well microtiter plate for which the DREAMing assay was run for the given sample. Note that the number of wells can vary depending on the passay or plate used.
	plate --> optional row assigning samples to the DREAMing assay for which they were run. Because two columns are designated for a sample, value should be the same for each of those cells.
	date --> optional row assigning samples to the date for which they were run in a given DREAMing assay. Because two columns are designated for a sample, value should be the same for each of those cells.
	Additional rows could be added.

	Note that a given sample can have several replicates, in which the column name will then be followed by a .1, .2, etc depending on the number of replicates. ex: XXXX_L.1, XXXX_H.1; XXXX_L.2, XXXX_H.2
	By default, replicates of a sample are combined to make the 'plasmaMeltPeakCounts.csv' or 'methylationDensityTable.csv' files.

	IMPORTANT:
	fractionless melting peak temperatures (80.0C, ex.) should be recorded as '80' in order to match 'meltTempsToMD.csv'
	'''
	)

parser.add_argument('-temps', '--methylationDensityConversion', metavar='meltTempsToMD.csv', required=True, action="store",
	help='''REQUIRED.
	Table with melting peak temperature to assigned methylation density value for the given DREAMing locus.
	Used to calibrate the melting peak temperature to methylation density.
	Generated by modeling the observed melting temperature and the actual number of meCpGs via amplicon sequencing.

	IMPORTANT: the temperatures in the raw DREAMing data file must fall within the range of melting temperatures in this file.

	ex:
	For ZNF154 DREAMing assay:
	'79.2':0.0,
	'79.4':0.0,
	'79.6':0.0,
	'79.8': 0.0,
	'80': 0.07,
	'80.2': 0.14,
	'80.4': 0.14,
	'80.6': 0.21,
	'80.8': 0.28,
	'81': 0.35,
	'81.2': 0.35,
	'81.4': 0.42,
	'81.6': 0.49,
	'81.8': 0.56,
	'82': 0.56,
	'82.2': 0.63,
	'82.4': 0.7,
	'82.6': 0.77,
	'82.8': 0.84,
	'83': 0.84,
	'83.2': 0.91,
	'83.4': 1.0,
	'83.6': 1.0,
	'83.8': 1.0,
	'84': 1.0
	'''
	)

parser.add_argument('-cpgs', '--numberLocusCpGs', metavar='numCpGs', required=True, action="store", type=int,
	help='''REQUIRED.
	Number of CpGs covered in DREAMing locus and previously used to calibrate the DREAMing melting peak temperature to methylation density.
	'''
	)

parser.add_argument('-bg', '--input2bg', action='store_true', default=False,
	help='''
	Include input genomic equivalents as background reads with a methylation density = 0.
	'''
	)

parser.add_argument('-pois', '--poisson', action='store_true', default=False,
	help='''
	Adjust the counts of melting peak temperatures for each sample in a given DREAMing assay based on a Poissonian distribution.
	'''
	)

parser.add_argument('-tm', '--meltingTempResolution', metavar='0.2', default=0.2, type=float,
	help='''
	Melting temperature resolution of the melting peaks. Typically 0.2C, but could change depending on the thermocycler used for the DREAMing assay.
	'''
	)

parser.add_argument('-info', '--Info', metavar='Sample,copies_loaded', default='Sample,copies_loaded', type=str,
	help='''
	Comma separated list of rows of interest for the analysis.
	'Sample', and 'copies_loaded' required. However, additional labels could be added to include other sample/assay information in the file output table, perhaps to select or filter samples later on.
	'''
	)

parser.add_argument('-countFile', '--meltPeakCounts', action='store_true', default=False,
	help='''
	Return the 'plasmaMeltPeakCounts.csv' table.

	example table:
		Sample  copies_loaded  79.2  79.4  79.6  79.8  80  80.2  80.4  80.6
	0       A         9565.0     	0     5     8     1   6     6     4     2   
	1       B        39267.0     	3     3     3    13   0     5    13     5   
	2       C         7236.0     	0     0     1     4   9     3     4     2  
	'''
	)

parser.add_argument('-out', '--outDir', action='store',
	help='''
	Directory path to store output files. Should end with '/'
	'''
	)

#--------------------------------------------------------------------------

# get file name from path no matter the operating system or file path
def path_leaf(path):
    head, tail = ntpath.split(path)
    return tail or ntpath.basename(head)

#-----------------------------------------------------------------------------------------

# Collect command line arguments
args = parser.parse_args()


#-----------------------------------------------------------------------------------------
#-----------------------------------------------------------------------------------------

# Set up global variables:


# raw DREAMing melting temperatures
df = pd.read_csv(args.rawDREAMingFile, index_col=[0])

# calibration melting peak temperatures
calibrationDF = pd.read_csv(args.methylationDensityConversion)
tempValues = [ str(int(i)) if str(i)[-1] == '0' else str(i) for i in calibrationDF['temp'] ]
MDvalues = [ float(i) for i in calibrationDF['MD'] ]
temp_to_density = dict(zip(tempValues, MDvalues))

# number of CpGs covered in DREAMing locus
numCpGs = vars(args)['numberLocusCpGs']
numM = np.arange(0,numCpGs+1)
numU = np.arange(0,numCpGs+1)[::-1]

# number of wells used for the DREAMing assays in the rawDREAMingFile.csv
wells = []
for i in df.index.values:
	try:
		wells.append(int(i))
	except: ValueError
numWells = len(wells)
wellIndices = [str(i) for i in np.arange(1, numWells+1)]

# resolution of melting peak recordings. 0.2C is standard for the given thermocycler.
meltRes = float(vars(args)['meltingTempResolution'])

# list of sample information to include in final output table. 'Sample' and 'copies_loaded' are required.
info = list(vars(args)['Info'].split(','))

# if counting input copies as part of background as fragments with MD = 0%:
input2bg = vars(args)['input2bg']
if input2bg == True:
	temp_to_density['copies_loaded'] = 0.0

# Poisson Adjustment
poisAdj = vars(args)['poisson']

# meltPeakCounts.csv table returned
meltPeakTable = vars(args)['meltPeakCounts']

# 20190211-DREAMing_well_melt_temps_raw.csv --> '20190211-DREAMing'
inputName = path_leaf( str(args.rawDREAMingFile) ).split('_')[0]


date = datetime.date.today()

if vars(args)['outDir'] != None:
	outdir = str(args.outDir)
	fileTag = outdir + 'convertRawDREAMingToMethDensTable.' + inputName + '.poisAdj=' + str(poisAdj).upper() + '.input2bg=' + str(input2bg).upper() + '.Created=' + str(date)
else:
	fileTag = 'convertRawDREAMingToMethDensTable.' + inputName + '.poisAdj=' + str(poisAdj).upper() + '.input2bg=' + str(input2bg).upper() + '.Created=' + str(date)


# print std.out 'print' statements to new file and to console:
class Logger(object):
    def __init__(self):
        self.terminal = sys.stdout
        self.log = open(fileTag + '.out', "w")

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)  

    def flush(self):
        #this flush method is needed for python 3 compatibility.
        #this handles the flush command by doing nothing.
        pass

sys.stdout = Logger()


print 'Date:' + str(date)
print '#--------------------------------------------------------------------------'
print 'Command:'
print sys.argv
print ' '
print args
print ' '
print '#--------------------------------------------------------------------------'
print "Building 'methylationDensityTable.csv' files from raw DREAMing data"
print 'Methylation Density Table: ' + str(inputName)
print 'Parameters:'
print '	number of CpGs = ' + str(numCpGs)
print '	input2bg = ' + str(input2bg)
print '	Poisson Adjustment = ' + str(poisAdj)
print '	Wells per DREAMing assay = ' + str(numWells)
print '	Included information:'
print '	' + str(info)
print ' '


# list of unique sample names (split on _H or _L headings to designate type of melt peak in raw DREAMing table)
samplesOfInterest = sorted(list(set([ re.split(r'_[HL]', i)[0] for i in df.columns ])))

# get lowest and highest melting temperatures recored in table to set range
minMelt = np.nanmin(df.loc[ wellIndices ].astype(float).values.ravel())
maxMelt = np.nanmax(df.loc[ wellIndices ].astype(float).values.ravel())

print '	Minumum recorded melting peak = ' + str(minMelt)
print '	Maximum recorded melting peak = ' + str(maxMelt)
print '	Melting degree C resolution = ' + str(meltRes)
print ' '

# range of recorded melting peak temperatures in raw DREAMing data to use as temporary column headings to store melting peak temperature counts for samples.
melt_cols = [str(round(t, 1)) if str(round(t, 1))[-1] != '0' else str(round(t, 1))[:2] for t in np.arange(minMelt, maxMelt+meltRes, meltRes)]

# standard columns of interest
columns = info + melt_cols

# index to append melting peak counts and other info for each sample to proper location in sampleRecord
recordIndex = dict(zip(columns, np.arange(len(columns))))

''' example recordIndex:
{
 'Sample': 0,
 'copies_loaded': 1
 '79.2': 2,
 '79.4': 3,
 '79.6': 4,
 '79.8': 5,
 '80': 6,
 '80.2': 7,
 '80.4': 8,
 '80.6': 9,
 '80.8': 10,
 '81': 11,
 '81.2': 12,
 '81.4': 13,
 '81.6': 14,
 '81.8': 15,
 '82': 16,
 '82.2': 17,
 '82.4': 18,
 '82.6': 19,
 '82.8': 20,
 '83': 21,
 '83.2': 22,
 '83.4': 23,
 '83.6': 24,
 '83.8': 25,
 '84': 26,
 }
'''


#-----------------------------------------------------------------------------------------
#-----------------------------------------------------------------------------------------

# Build the 'plasmaMeltPeakCounts.csv' file
# a depricated MDBC input file for DREAMing plasma data
# the methylationDensityTable.csv file is derived from this file

# STRATEGY:
# make list for each sample where each position corresponds to associated entry in the recordIndex.
# update this sample list with counts of melting peak temperatures or other sample information.
# append these sample lists as 'rows' to master dataframe:

master_array = []

print 'Extracting raw melt peak counts from samples of interest...'

for sample in samplesOfInterest:

	print '	' + str(sample)

	# make list to update for each sample
	sampleRecord = [0] * len(columns) 
	
	# dataframe slice where columns represent melting peak temperature records for instances of sample
	# could be multiple replicates (records) of a given sample
	# and each sample has at least two columns: one for L and one for H melt peak recordings
	temp = df[df.columns[df.columns.str.contains(sample)]]

	# for each instance of the sample, get rows with melt peak recordings
	# and get number of occurances of each melt peak
	for col in temp.columns:
		meltPeaks = temp.loc[ wellIndices, col ]
		meltPeaks.fillna(0, inplace=True) # replace empty cells with 0
		meltPeaksToStr = meltPeaks.astype(str) # convert melt peak values to strings
		types, counts = np.unique(meltPeaksToStr, return_counts=True)

		# for each melting peak temp record and count, check to make sure string (ex: '79.8' or '80') and not nan
		for j in np.arange( len(counts) ):
			if types[j] != '0': # ignore the cells that were empty

				# append counts to correct position in sampleRecord based on recordIndex

				# if all wells are that melt temp
				if int(counts[j]) == numWells:
					sampleRecord[ recordIndex[ types[j]] ] += numWells

				else:
					# if poisson adjustment:
					if poisAdj == True:
						sampleRecord[ recordIndex[types[j]] ] += round( (-np.log(1.0 - (counts[j]/float(numWells))) * float(numWells)), 0)
					# or just append number of counts of the given melt temp:
					else:
						sampleRecord[ recordIndex[types[j]] ] += counts[j]

	# append other info to sampleRecord:
	for i in info:

		if i == 'copies_loaded':
			# update list with total copies loaded for all DREAMing assays of the sample
			sampleCopies = [ float(val) for val in temp.loc[i, :].values if type(val) == str ]

			# sum together total copies for all DREAMing assay instances of sample
			sampleRecord[ recordIndex[i] ] = sum(sampleCopies)/2.0 # divide by 2 b/c L and H columns count the copies twice

		if i == 'Sample':
			# update list with sample name
			sampleRecord[ recordIndex[i] ] = sample


	# append sample row to the master array:
	master_array.append(sampleRecord)

# build master df of all sampleRecords
master_df = pd.DataFrame(master_array, columns=columns)
fileName = 'plasmaMeltPeakCounts.' + inputName + '.poisAdj=' + str(poisAdj).upper() + '.input2bg=' + str(input2bg).upper() + '_Created=' + str(date) + '.csv'

if meltPeakTable == True:
	master_df.to_csv(fileName)
	print ' '
	print "'plasmaMeltPeakCounts.csv' file created:"
	print fileName
	print ' '


#-----------------------------------------------------------------------------------------

# Continue to make Methylation Density Table
# convert 'plasmaMeltPeakCounts.csv' to 'methylation_density_table.csv' for use with MDBCanalysisAndPlots.py

print "Converting to 'methylation_density_table.csv'..."
print ' '


# set sample names as index
master_df.set_index('Sample', inplace=True)

master_df_peaks = master_df[temp_to_density.keys()] # columns can only be read methylation density counts

# convert melt temperature column names to MD values
master_df_peaks.rename(index=str, columns=temp_to_density, inplace=True)

# then transpose sample names to columns
methDensTable = master_df_peaks.copy().T

''' example of what methDensTable now looks like:
Sample  100250   100292  100296  100442  100626  100654  100662  101086  \
0.00*    9565.0  39267.0  7236.0   458.0  9840.0  1560.0   747.0  6240.0   
0.00       0.0      3.0     0.0     0.0     0.0     0.0     0.0     0.0   
0.00       5.0      3.0     0.0     0.0     0.0     0.0     0.0     0.0   
0.00       8.0      3.0     1.0     0.0     4.0     1.0     0.0    11.0   
0.00       1.0     13.0     4.0    10.0     5.0     3.0     0.0     4.0   
0.07       6.0      0.0     9.0     0.0     3.0     3.0    11.0     2.0   
0.14       6.0      5.0     3.0     0.0     6.0     1.0     0.0     2.0
...
...
* note that this was 'copies_loaded', but b/c part of temp_to_density {temp_to_density : 0.0}, was changed to MD value

'''

# combine the counts for replicate MDs
methDensTableCombined = methDensTable.groupby(methDensTable.index).sum()

# Add in numU, numM, and MD columns
methDensTableCombined['numU'] = numU
methDensTableCombined['numM'] = numM

MDs = methDensTableCombined.index.values.tolist()
methDensTableCombined['MD'] = MDs

methDensTableCombined.reset_index(inplace=True, drop=True)

print 'number of unmethylated CpGs:'
print numU
print 'number of methylated CpGs:'
print numM
print 'MDs:'
print MDs
print ' '

# reorder columns:
methDensTableCombined = methDensTableCombined[ ['numU', 'numM', 'MD'] + samplesOfInterest ]

''' example of what methDensTableCombined now looks like:
numU  numM    MD  100250   100292  100296  100442  100626  100654  \
14     0  	0.00  9579.0  39289.0  7241.0   468.0  9849.0  1564.0   
13     1  	0.07     6.0      0.0     9.0     0.0     3.0     3.0   
12     2  	0.14    10.0     18.0     7.0     0.0     9.0     1.0   
11     3  	0.21     2.0      5.0     2.0     0.0     4.0     1.0   
10     4  	0.28     2.0      3.0     3.0     0.0     2.0     0.0
...
...

'''

#methDensFileName = 'methylation_density_table.' + inputName + '.poisAdj=' + str(poisAdj).upper() + '.input2bg=' + str(input2bg).upper() + '.Created=' + str(date) + '.csv'
methDensTableCombined.to_csv(fileTag + '.csv', index=False)

print 'Created: ' + fileTag + '.csv'
print 'Done'








