#!/usr/bin/env python2
"""
* File: MaskScorer.py
* Date: 08/30/2016
* Translated by Daniel Zhou
* Original implemented by Yooyoung Lee
* Status: Complete

* Description: This calculates performance scores for localizing mainpulated area
                between reference mask and system output mask

* Requirements: This code requires the following packages:

    - opencv
    - pandas

  The rest are available on your system

* Disclaimer:
This software was developed at the National Institute of Standards
and Technology (NIST) by employees of the Federal Government in the
course of their official duties. Pursuant to Title 17 Section 105
of the United States Code, this software is not subject to copyright
protection and is in the public domain. NIST assumes no responsibility
whatsoever for use by other parties of its source code or open source
server, and makes no guarantees, expressed or implied, about its quality,
reliability, or any other characteristic."
"""

########### packages ########################################################
import sys
import argparse
import os
import shutil
import cv2
import pandas as pd
import argparse
import numpy as np
#import maskreport as mr
#import pdb #debug purposes
#from abc import ABCMeta, abstractmethod
import configparser

# loading scoring and reporting libraries
#lib_path = "../../lib"
lib_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../lib")
sys.path.append(lib_path)
from metricRunner import maskMetricRunner
import Partition_mask as pt
from myround import myround
#import masks
#execfile(os.path.join(lib_path,"masks.py"))
#execfile('maskreport.py')

########### Temporary Variable ############################################################
mfc18_oo_name = "ProbeStatus"
nc17_oo_name = "IsOptOut"

########### Command line interface ########################################################

#data_path = "../../data"
refFname = "reference/manipulation/NC2016-manipulation-ref.csv"
indexFname = "indexes/NC2016-manipulation-index.csv"
#sysFname = data_path + "/SystemOutputs/dct0608/dct02.csv"

#################################################
## command-line arguments for "file"
#################################################

parser = argparse.ArgumentParser(description='Compute scores for the masks and generate a report.')
parser.add_argument('-t','--task',type=str,default='manipulation',
help='Two different types of tasks: [manipulation] and [splice]',metavar='character')
parser.add_argument('--refDir',type=str,
help='NC2016_Test directory path: [e.g., ../../data/NC2016_Test]',metavar='character')
parser.add_argument('--sysDir',type=str,default='.',
help='System output directory path: [e.g., ../../data/NC2016_Test]',metavar='character')
parser.add_argument('-r','--inRef',type=str,
help='Reference csv file name: [e.g., reference/manipulation/NC2016-manipulation-ref.csv]',metavar='character')
parser.add_argument('-s','--inSys',type=str,
help='System output csv file name: [e.g., ~/expid/system_output.csv]',metavar='character')
parser.add_argument('-x','--inIndex',type=str,default=indexFname,
help='Task Index csv file name: [e.g., indexes/NC2016-manipulation-index.csv]',metavar='character')
parser.add_argument('-oR','--outRoot',type=str,
help="Directory root plus prefix to save outputs.",metavar='character')
parser.add_argument('--outMeta',action='store_true',help='Save the CSV file with the system scores with minimal metadata')
parser.add_argument('--outAllmeta',action='store_true',help='Save the CSV file with the system scores with all metadata')

#added from DetectionScorer.py
factor_group = parser.add_mutually_exclusive_group()
factor_group.add_argument('-q', '--query', nargs='*',
help="Evaluate algorithm performance by given queries.", metavar='character')
factor_group.add_argument('-qp', '--queryPartition',
help="Evaluate algorithm performance with partitions given by one query (syntax : '==[]','<','<=','>','>=')", metavar='character')
factor_group.add_argument('-qm', '--queryManipulation', nargs='*',
help="Filter the data by given queries before evaluation. Each query will result in a separate evaluation run.", metavar='character')

parser.add_argument('--eks',type=int,default=15,
help="Erosion kernel size number must be odd, [default=15]",metavar='integer')
parser.add_argument('--dks',type=int,default=11,
help="Dilation kernel size number must be odd, [default=11]",metavar='integer')
parser.add_argument('--ntdks',type=int,default=15,
help="Non-target dilation kernel for distraction no-score regions. Size number must be odd, [default=15]",metavar='integer')
parser.add_argument('-k','--kernel',type=str,default='box',
help="Convolution kernel type for erosion and dilation. Choose from [box],[disc],[diamond],[gaussian], or [line]. The default is 'box'.",metavar='character')
parser.add_argument('--rbin',type=int,default=-1,
help="Binarize the reference mask in the relevant mask file to black and white with a numeric threshold in the interval [0,255]. Pick -1 to evaluate the relevant regions based on the other arguments. [default=-1]",metavar='integer')
parser.add_argument('--sbin',type=int,default=-10,
help="Binarize the system output mask to black and white with a numeric threshold in the interval [-1,255]. -1 can be chosen to binarize the entire mask to white. -10 indicates that the threshold for the mask will be chosen at the maximal absolute MCC value. [default=-10]",metavar='integer')
parser.add_argument('--jpeg2000',action='store_true',help="Evaluate JPEG2000 reference masks. Individual regions in the JPEG2000 masks may interserct; each pixel may contain multiple manipulations.")
parser.add_argument('--nspx',type=int,default=-1,
help="Set a pixel value for all system output masks to serve as a no-score region [0,255]. -1 indicates that no particular pixel value will be chosen to be the no-score zone. [default=-1]",metavar='integer')
parser.add_argument('-pppns','--perProbePixelNoScore',action='store_true',
help="Use the pixel values in the ProbeOptOutPixelValue column (DonorOptOutPixelValue as well for the splice task) of the system output to designate no-score zones.")

#parser.add_argument('--avgOver',type=str,default='',
#help="A collection of features to average reports over, separated by commas.", metavar="character")
parser.add_argument('-v','--verbose',type=int,default=None,
help="Control print output. Select 1 to print all non-error print output and 0 to suppress all print output (bar argument-parsing errors).",metavar='0 or 1')
parser.add_argument('-p','--processors',type=int,default=1,
help="The number of processors to use in the computation. Choosing too many processors will cause the program to forcibly default to a smaller number. [default=1].",metavar='positive integer')
parser.add_argument('--precision',type=int,default=16,
help="The number of digits to round computed scores. Note that rounding is not absolute, but is by significant digits (e.g. a score of 0.003333333333333... will round to 0.0033333 for a precision of 5). (default = 16).",metavar='positive integer')
parser.add_argument('--truncate',action='store_true',
help="Truncate rather than round the figures to the specified precision. If no number is specified for precision, the default 16 will be used.")
parser.add_argument('-html',help="Output data to HTML files.",action="store_true")
parser.add_argument('--optOut',action='store_true',help="Evaluate algorithm performance on a select number of trials determined by the performer via values in the ProbeStatus column.")
parser.add_argument('--displayScoredOnly',action='store_true',help="Display only the data for which a localized score could be generated.")
parser.add_argument('-xF','--indexFilter',action='store_true',help="Filter scoring to only files that are present in the index file. This option permits scoring to select smaller index files for the purpose of testing.")
parser.add_argument('--speedup',action='store_true',help="Run mask evaluation with a sped-up evaluator.")
parser.add_argument('--debug_off',action='store_false',help="Continue running localization scorer on the next probe even when encountering errors. This can be used to skip unwanted .")
parser.add_argument('--cache_dir',type=str,default=None,
help="The directory to cache reference mask data for future use. Subdirectories will be created according to specific details related to the task.",metavar='valid file directory')
parser.add_argument('--cache_flush',action='store_true',help="Flush the cache directory before starting computation. This is especially crucial when the queryManipulation options are used in conjunction with --cache_dir.")

args = parser.parse_args()

if len(sys.argv) < 2:
    parser.print_help()
    exit(0)

verbose=args.verbose

#wrapper print function for print message suppression
if verbose:
    def printq(string):
        print(string)
else:
    printq = lambda *a:None

#wrapper print function when encountering an error. Will also cause script to exit after message is printed.

#if verbose==0:
#    def printerr(string,exitcode=1):
#        exit(exitcode)
#else:
def printerr(string,exitcode=1):
    if verbose != 0:
        parser.print_help()
        print(string)
    exit(exitcode)

args.task = args.task.lower()

if args.task not in ['manipulation','splice']:
    printerr("ERROR: Localization task type must be 'manipulation' or 'splice'.")
if args.refDir is None:
    printerr("ERROR: Test directory path must be supplied.")

mySysDir = os.path.join(args.sysDir,os.path.dirname(args.inSys))
myRefDir = args.refDir

if args.inRef is None:
    printerr("ERROR: Input file name for reference must be supplied.")

if args.inSys is None:
    printerr("ERROR: Input file name for system output must be supplied.")

if args.inIndex is None:
    printerr("ERROR: Input file name for index files must be supplied.")

#create the folder and save the mask outputs
#set.seed(1)

#generate plotjson options
#detpath = os.path.join(os.path.dirname(os.path.abspath(__file__)),'../DetectionScorer/plotJsonFiles')
#detpath = os.path.join(os.path.dirname(os.path.abspath(__file__)),'plotJsonFiles')
#if not os.path.isdir(detpath):
#    os.system(' '.join(['mkdir',detpath]))

#assume outRoot exists
if args.outRoot in [None,'']:
    printerr("ERROR: the folder name and prefix for outputs must be supplied.")

outdir=os.path.dirname(args.outRoot)
outpfx=os.path.basename(args.outRoot)

def mkdir(dirname):
    if not os.path.isdir(dirname):
        os.system('mkdir {}'.format(dirname))

mkdir(outdir)

if args.task == 'manipulation':
    index_dtype = {'TaskID':str,
             'ProbeFileID':str,
             'ProbeFileName':str,
             'ProbeWidth':np.int64,
             'ProbeHeight':np.int64}
    sys_dtype = {'ProbeFileID':str,
             'ConfidenceScore':str, #this should be "string" due to the "nan" value, otherwise "nan"s will have different unique numbers
             'OutputProbeMaskFileName':str}

elif args.task == 'splice':
    index_dtype = {'TaskID':str,
             'ProbeFileID':str,
             'ProbeFileName':str,
             'ProbeWidth':np.int64,
             'ProbeHeight':np.int64,
             'DonorFileID':str,
             'DonorFileName':str,
             'DonorWidth':np.int64,
             'DonorHeight':np.int64}
    sys_dtype = {'ProbeFileID':str,
             'DonorFileID':str,
             'ConfidenceScore':str, #this should be "string" due to the "nan" value, otherwise "nan"s will have different unique numbers
             'OutputProbeMaskFileName':str,
             'OutputDonorMaskFileName':str}

printq("Beginning the mask scoring report...")

mySysFile = os.path.join(args.sysDir,args.inSys)
mySys = pd.read_csv(mySysFile,sep="|",header=0,dtype=sys_dtype,na_filter=False)

ref_dtype = {}
myRefFile = os.path.join(myRefDir,args.inRef)
with open(myRefFile,'r') as ref:
    ref_dtype = {h:str for h in ref.readline().rstrip().split('|')} #treat it as string

myRef = pd.read_csv(myRefFile,sep="|",header=0,dtype=ref_dtype,na_filter=False)
#sub_ref = myRef[myRef['IsTarget']=="Y"].copy()
sub_ref = myRef
myIndex = pd.read_csv(os.path.join(myRefDir,args.inIndex),sep="|",header=0,dtype=index_dtype,na_filter=False)

param_pfx = ['Probe']
if args.task == 'splice':
    param_pfx = ['Probe','Donor']
param_ids = [''.join([e,'FileID']) for e in param_pfx]

m_df = pd.merge(sub_ref, mySys, how='left', on=param_ids)
# get rid of inf values from the merge and entries for which there is nothing to work with.
m_df = m_df.replace([np.inf,-np.inf],np.nan).dropna(subset=[''.join([e,'MaskFileName']) for e in param_pfx])

#for all columns unique to mySys except ConfidenceScore, replace np.nan with empty string
sysCols = list(mySys)
refCols = list(sub_ref)

if args.optOut and (not (mfc18_oo_name in sysCols) and not (nc17_oo_name in sysCols)):
    print("ERROR: No {} or {} column detected. Filtration is meaningless.".format(mfc18_oo_name,nc17_oo_name))
    exit(1)

sysCols = [c for c in sysCols if c not in refCols]
sysCols.remove('ConfidenceScore')

for c in sysCols:
    m_df.loc[pd.isnull(m_df[c]),c] = ''
if args.indexFilter:
    printq("Filtering the reference and system output by index file...")
    m_df = pd.merge(myIndex[param_ids + ['ProbeWidth']],m_df,how='left',on=param_ids).drop('ProbeWidth',1)

pd.options.mode.chained_assignment = None #NOTE: disable this when debugging

if len(m_df) == 0:
    print("ERROR: the system output data does not match with the index. Either one may be empty. Please validate again.")
    exit(1)

#apply to post-index filtering
totalTrials = len(m_df)
#NOTE: IsOptOut values can be any one of "Y", "N", "Detection", or "Localization"
#NOTE: ProbeStatus values can be any one of "Processed", "NonProcessed", "OptOutAll", "OptOutDetection", "OptOutLocalization"
optOutCol = mfc18_oo_name
if mfc18_oo_name in sysCols:
    undesirables = str(['OptOutAll','OptOutLocalization'])
    all_statuses = {'Processed','NonProcessed','OptOutAll','OptOutDetection','OptOutLocalization','FailedValidation'}
elif nc17_oo_name in sysCols:
    optOutCol = nc17_oo_name
    undesirables = str(['Y','Localization'])
    all_statuses = {'Y','N','Detection','Localization','FailedValidation'}
#check to see if there are any values not one of these
probeStatuses = set(list(m_df[optOutCol].unique()))
if '' in probeStatuses:
    probeStatuses.remove('') #NOTE: wrt index filtering
if probeStatuses - all_statuses > set():
    print("ERROR: Status {} is not recognized.".format(probeStatuses - all_statuses))
    exit(1)

if (args.task == 'splice') and (mfc18_oo_name in sysCols):
    donorStatuses = set(list(m_df['DonorStatus'].unique()))
    all_donor_statuses = {'Processed','NonProcessed','OptOutLocalization','FailedValidation'}
    if donorStatuses - all_donor_statuses > set():
        print("ERROR: Status {} is not recognized for column DonorStatus.".format(donorStatuses - all_donor_statuses))
        exit(1)

#optout filter here for faster processing
if nc17_oo_name in sysCols:
    oo_df = m_df.query("IsOptOut!={}".format(undesirables))
elif mfc18_oo_name in sysCols:
    if args.task == 'manipulation':
        oo_df = m_df.query("ProbeStatus!={}".format(undesirables))
    elif args.task == 'splice':
        oo_df = m_df.query("not ((ProbeStatus=={}) & (DonorStatus=={}))".format(undesirables,undesirables))

if args.optOut:
    m_df = oo_df

totalOptIn = len(oo_df)
totalOptOut = totalTrials - totalOptIn
TRR = float(totalOptIn)/totalTrials
m_df = m_df.query("IsTarget=='Y'") 

if args.perProbePixelNoScore and (('ProbeOptOutPixelValue' not in sysCols) or ((args.task == 'splice') and ('DonorOptOutPixelValue' not in sysCols))):
    if args.task == 'manipulation':
        print("ERROR: 'ProbeOptOutPixelValue' is not found in the columns of the system output.")
    elif args.task == 'splice':
        print("ERROR: 'ProbeOptOutPixelValue' or 'DonorOptOutPixelValue' is not found in the columns of the system output.")
    exit(1)

#TODO: move this into the localization scorer and optout at the very end
#opting out at the beginning
#if args.optOut:
#    m_df = m_df.query(" ".join(['not',optOutQuery]))

#rounding modes
round_modes = ['sd']
if args.truncate:
    round_modes.append('t')

#cache directory features
task_sffx = args.task[0]

#if cache_dir exists, notify accordingly.
if args.cache_dir:
    if os.path.isdir(args.cache_dir) and not args.cache_flush:
        print("{} exists. Content in the directory can be used for efficient scoring.".format(args.cache_dir))
    mkdir(args.cache_dir)

cache_sub_dir = []
#cache_sub_dir = ['ref_{}_e{}_d{}_nt{}'.format(task_sffx,args.eks,args.dks,args.ntdks)]
#if args.jpeg2000:
#    cache_sub_dir.append('jp2')

#TODO: change this to a dictionary, since this is all it does.
#class loc_scoring_params:
#    def __init__(self,
#                 mode,
#                 eks,
#                 dks,
#                 ntdks,
#                 nspx,
#                 pppns,
#                 kernel,
#                 verbose,
#                 html,
#                 precision,
#                 truncate,
#                 processors,
#                 debug_mode,
#                 cache_dir=args.cache_dir):
#        self.mode = mode
#        self.eks = eks
#        self.dks = dks
#        self.ntdks = ntdks
#        self.nspx = nspx
#        self.pppns = pppns
#        self.kernel = kernel
#        self.verbose = verbose
#        self.html = html
#        self.precision = precision
#        self.truncate = truncate
#        self.processors = processors
#        self.debug_mode = debug_mode
#        self.cache_dir = cache_dir

class loc_scoring_params:
    def __init__(self,**kwds):
        self.__dict__.update(kwds)

def round_df(my_df,metlist):
    df_cols = list(my_df)
    final_metlist = [met for met in metlist if met in df_cols]
    my_df[final_metlist] = my_df[final_metlist].applymap(lambda n: myround(n,args.precision,round_modes))
    return my_df

#define HTML functions here
#TODO: move these to separate files and import from those files
df2html = lambda *a:None
if args.task == 'manipulation':
    def createReport(m_df, journalData, probeJournalJoin, index, refDir, sysDir, rbin, sbin,erodeKernSize, dilateKernSize,distractionKernSize, kern,outputRoot,html,color,verbose,precision,cache_dir=None):
        # if the confidence score are 'nan', replace the values with the mininum score
        #m_df[pd.isnull(m_df['ConfidenceScore'])] = m_df['ConfidenceScore'].min()
        # convert to the str type to the float type for computations
        #m_df['ConfidenceScore'] = m_df['ConfidenceScore'].astype(np.float)
    
        metricRunner = maskMetricRunner(m_df,args.refDir,sysDir,args.rbin,args.sbin,journalData,probeJournalJoin,index,speedup=args.speedup,color=args.jpeg2000)

        #revise this to outputRoot and loc_scoring_params
#        params = loc_scoring_params(0,args.eks,args.dks,args.ntdks,args.nspx,args.perProbePixelNoScore,args.kernel,args.verbose,args.html,precision,args.truncate,args.processors,args.debug_off,cache_dir=cache_dir)
        params = loc_scoring_params(mode = 0,
                                    optOut = args.optOut,
                                    eks = args.eks,
                                    dks = args.dks,
                                    ntdks = args.ntdks,
                                    nspx = args.nspx,
                                    pppns = args.perProbePixelNoScore,
                                    kernel = args.kernel,
                                    verbose = args.verbose,
                                    html = args.html,
                                    precision = precision,
                                    truncate = args.truncate,
                                    processors = args.processors,
                                    debug_off = args.debug_off,
                                    cache_dir = cache_dir
                                   )

        df = metricRunner.getMetricList(outputRoot,params)
#        df = metricRunner.getMetricList(args.eks,args.dks,args.ntdks,args.nspx,args.kernel,outputRoot,args.verbose,args.html,precision=args.precision,processors=args.processors)
        merged_df = pd.merge(m_df.drop('Scored',1),df,how='left',on='ProbeFileID')

        nonscore_df = merged_df.query("OptimumMCC == -2")
#        merged_df['Scored'] = pd.Series(['Y']*len(merged_df))
#        merged_df.loc[merged_df.query('MCC == -2').index,'Scored'] = 'N'
        midx = nonscore_df.index
        relevant_met_cols=['OptimumThreshold','OptimumNMM','OptimumBWL1','GWL1','AUC','EER','OptimumPixelTP','OptimumPixelTN','OptimumPixelFP','OptimumPixelFN','PixelN','PixelBNS','PixelSNS','PixelPNS']
        if len(midx) > 0:
            merged_df.loc[midx,relevant_met_cols] = np.nan
        #remove the rows that were not scored due to no region being present. We set those rows to have MCC == -2.
        if args.displayScoredOnly:
            #get the list of non-scored and delete them
            nonscore_df['ProbeFileID'].apply(lambda x: os.system('rm -rf {}'.format(os.path.join(outputRoot,x))))
#            nonscore_df['ProbeFileID'].apply(lambda x: os.system('echo {}'.format(os.path.join(outputRoot,x))))
            merged_df = merged_df.query('OptimumMCC > -2')
    
        #reorder merged_df's columns. Names first, then scores, then other metadata
        rcols = merged_df.columns.tolist()
        firstcols = ['TaskID','ProbeFileID','ProbeFileName','ProbeMaskFileName','IsTarget','OutputProbeMaskFileName','ConfidenceScore','OptimumThreshold','OptimumNMM','OptimumMCC','OptimumBWL1','GWL1','AUC','EER','Scored','PixelN','OptimumPixelTP','OptimumPixelTN','OptimumPixelFP','OptimumPixelFN','PixelBNS','PixelSNS','PixelPNS']
#        if args.sbin >= -1:
        firstcols.extend(['MaximumThreshold','MaximumNMM','MaximumMCC','MaximumBWL1',
                          'MaximumPixelTP','MaximumPixelTN','MaximumPixelFP','MaximumPixelFN',
                          'ActualThreshold','ActualNMM','ActualMCC','ActualBWL1',
                          'ActualPixelTP','ActualPixelTN','ActualPixelFP','ActualPixelFN'])

        metadata = [t for t in rcols if t not in firstcols]
        firstcols.extend(metadata)
        merged_df = merged_df[firstcols]
        #filter for optout here
        all_cols = merged_df.columns.values.tolist()
        if "IsOptOut" in all_cols:
            merged_df.loc[merged_df.query("IsOptOut==['FailedValidation']").index,'OutputProbeMaskFileName'] = ''
            if params.optOut:
                merged_df = merged_df.query("IsOptOut==['N','Detection','FailedValidation']")
        elif "ProbeStatus" in all_cols:
            merged_df.loc[merged_df.query("ProbeStatus==['FailedValidation']").index,'OutputProbeMaskFileName'] = ''
            if params.optOut:
                merged_df = merged_df.query("ProbeStatus==['Processed','NonProcessed','OptOutDetection','FailedValidation']")
    
        return merged_df

    def journalUpdate(probeJournalJoin,journalData,r_df):
        #get the manipulations that were not scored and set the same columns in journalData to 'N'
        pjoins = probeJournalJoin.query("ProbeFileID=={}".format(r_df.query('OptimumMCC == -2')['ProbeFileID'].tolist()))[['JournalName','StartNodeID','EndNodeID','ProbeFileID']]
        pjoins['Foo'] = 0 #dummy variable to be deleted later
#        p_idx = pjoins.reset_index().merge(journalData,how='left',on=['ProbeFileID','JournalName','StartNodeID','EndNodeID']).set_index('index').dropna().drop('Color',1).index
        p_idx = journalData.reset_index().merge(pjoins,how='left',on=['ProbeFileID','JournalName','StartNodeID','EndNodeID']).set_index('index').dropna().drop('Foo',1).index

        #set where the rows are the same in the join
        journalData.loc[p_idx,'Evaluated'] = 'N'
        journalcols_else = list(journalData)
        journalcols_else.remove('ProbeFileID')
#        journalcols = ['ProbeFileID','JournalName','StartNodeID','EndNodeID']
        #journalcols.extend(list(journalData))
        #journalData = pd.merge(journalData,probeJournalJoin[['ProbeFileID','JournalName','StartNodeID','EndNodeID']],how='right',on=['JournalName','StartNodeID','EndNodeID'])
        journalcols = ['ProbeFileID']
        journalcols.extend(journalcols_else)
        journalData = journalData[journalcols]
        journalData.to_csv(path_or_buf=os.path.join(outRootQuery,'_'.join([prefix,'journalResults.csv'])),sep="|",index=False)
        return 0

    #averaging procedure starts here.
    def averageByFactors(r_df,metrics,constant_mets,factor_mode,query): #TODO: next time pass in object of parameters instead of tacking on new ones every time
        if 'OptimumMCC' not in metrics:
            print("ERROR: OptimumMCC is not in the metrics provided.")
            return 1
        #filter nan out of the below
        metrics_to_be_scored = ['OptimumThreshold','OptimumMCC','OptimumNMM','OptimumBWL1','GWL1','AUC','EER']
        if args.sbin >= -1:
            metrics_to_be_scored.extend(['MaximumThreshold','MaximumMCC','MaximumNMM','MaximumBWL1',
                                         'ActualThreshold','ActualMCC','ActualNMM','ActualBWL1'])
        if r_df.query("Scored=='Y'")[metrics_to_be_scored].dropna().shape[0] == 0:
            #if nothing was scored, print a message and return
            print("None of the masks that we attempted to score for query {} had regions to be scored. Further factor analysis is futile.".format(query))
            return 0
        r_dfc = r_df.copy()
        r_idx = r_dfc.query('OptimumMCC == -2').index
        r_dfc.loc[r_idx,'Scored'] = 'N'
        r_dfc.loc[r_idx,'OptimumMCC'] = np.nan
        r_df_scored = r_dfc.query("Scored=='Y'")
        ScoreableTrials = len(r_df_scored)
        my_partition = pt.Partition(args.task,r_df_scored,query,factor_mode,metrics) #average over queries
        df_list = my_partition.render_table(metrics)
        if len(df_list) == 0:
            return 0
        
        constant_metrics = {}
        for m in constant_mets:
            constant_metrics[m] = myround(r_df[m].iloc[0],args.precision,round_modes)

#        totalTrials = len(r_df)
#        totalOptOut = len(r_df.query("IsOptOut=='Y'"))
#        totalOptIn = totalTrials - totalOptOut
#        TRR = float(totalOptIn)/totalTrials
        optOutStats = ['TRR']

        a_df = 0
        if factor_mode == 'q': #don't print anything if there's nothing to print
            #use Partition for OOP niceness and to identify file to be written.
            #a_df get the headers of temp_df and tack entries on one after the other
            a_df = pd.DataFrame(columns=df_list[0].columns)
            for i,temp_df in enumerate(df_list):
                heads = list(temp_df)
                temp_df['TRR'] = TRR
                temp_df['totalTrials'] = totalTrials
                temp_df['ScoreableTrials'] = ScoreableTrials
                temp_df['totalOptIn'] = totalOptIn
                temp_df['totalOptOut'] = totalOptOut
                temp_df['optOutScoring'] = 'N'
                if args.optOut:
                    temp_df['optOutScoring'] = 'Y'

                temp_df['OptimumThreshold'] = temp_df['OptimumThreshold'].dropna().astype(int).astype(str)
#                if args.sbin >= -1:
#                    temp_df['MaximumThreshold'] = temp_df['MaximumThreshold'].dropna().astype(int).astype(str)
#                    temp_df['ActualThreshold'] = temp_df['ActualThreshold'].dropna().astype(int).astype(str)

                for m in constant_mets:
                    temp_df[m] = constant_metrics[m]

                heads.extend(constant_mets)
                heads.extend(['TRR','totalTrials','ScoreableTrials','totalOptIn','totalOptOut','optOutScoring'])
                temp_df = temp_df[heads]
                if temp_df is not 0: #TODO: reconsider the placement of this piece of code
                    temp_df.loc[:,'OptimumThreshold'] = temp_df['OptimumThreshold'].dropna().astype(int).astype(str)
                    if args.sbin >= -1:
                        temp_df.loc[:,'MaximumThreshold'] = temp_df['MaximumThreshold'].dropna().astype(int).astype(str)
                        temp_df.loc[:,'ActualThreshold'] = temp_df['ActualThreshold'].dropna().astype(int).astype(str)
                    else:
                        temp_df.loc[:,'MaximumThreshold'] = ''
                        temp_df.loc[:,'ActualThreshold'] = ''
                stdev_mets = [met for met in list(temp_df) if 'stddev' in met]
                my_metrics_to_be_scored = metrics_to_be_scored + stdev_mets + optOutStats
                float_mets = [met for met in my_metrics_to_be_scored if ('Threshold' not in met) or ('stddev' in met)]
                temp_df = round_df(temp_df,float_mets)
                temp_df.to_csv(path_or_buf="{}_{}.csv".format(os.path.join(outRootQuery,'_'.join([prefix,'mask_scores'])),i),sep="|",index=False)
                a_df = a_df.append(temp_df,ignore_index=True)
                
            #at the same time do an optOut filter where relevant and save that
#            if args.optOut:
#                my_partition_o = pt.Partition(r_dfc.query("Scored=='Y'"),["({}) & (IsOptOut!='Y')".format(q) for q in query],factor_mode,metrics,verbose) #average over queries
#                df_list_o = my_partition_o.render_table(metrics)
#                if len(df_list_o) > 0:
#                    for i,temp_df_o in enumerate(df_list_o):
#                        heads = list(temp_df_o)
#                        temp_df_o['TRR'] = TRR
#                        temp_df_o['totalTrials'] = totalTrials
#                        temp_df_o['totalOptIn'] = totalOptIn
#                        temp_df_o['totalOptOut'] = totalOptOut
#                        heads.extend(['TRR','totalTrials','totalOptIn','totalOptOut'])
#                        temp_df_o = temp_df_o[heads]
#                        temp_df_o.to_csv(path_or_buf="{}_{}.csv".format(os.path.join(outRootQuery,prefix + '-mask_scores_optout'),i),sep="|",index=False)
#                        a_df = a_df.append(temp_df_o,ignore_index=True)
        elif (factor_mode == 'qp') or (factor_mode == '') or (factor_mode == 'qm'):
            a_df = df_list[0]
            if len(a_df) == 0:
                return 0
            #add optOut scoring in addition to (not replacing) the averaging procedure
#            if args.optOut:
#                if query == '':
#                    my_partition_o = pt.Partition(r_dfc.query("Scored=='Y'"),"IsOptOut!='Y'",factor_mode,metrics,verbose) #average over queries
#                else:
#                    my_partition_o = pt.Partition(r_dfc.query("(Scored=='Y') & (IsOptOut!='Y')"),"({}) & (IsOptOut!='Y')".format(query),factor_mode,metrics,verbose) #average over queries
#                df_list_o = my_partition_o.render_table(metrics)
#                if len(df_list_o) > 0:
#                    a_df = a_df.append(df_list_o[0],ignore_index=True)
            heads = list(a_df)
            a_df['TRR'] = TRR
            a_df['totalTrials'] = totalTrials
            a_df['ScoreableTrials'] = ScoreableTrials
            a_df['totalOptIn'] = totalOptIn
            a_df['totalOptOut'] = totalOptOut
            a_df['optOutScoring'] = 'N'
            if args.optOut:
                a_df['optOutScoring'] = 'Y'
            a_df['OptimumThreshold'] = a_df['OptimumThreshold'].dropna().astype(int).astype(str)
            for m in constant_mets:
                a_df[m] = constant_metrics[m]
            heads.extend(constant_mets)
            if args.sbin >= -1:
                a_df['MaximumThreshold'] = a_df['MaximumThreshold'].dropna().astype(int).astype(str)
                a_df['ActualThreshold'] = a_df['ActualThreshold'].dropna().astype(int).astype(str)
            else:
                a_df['MaximumThreshold'] = ''
                a_df['ActualThreshold'] = ''

            heads.extend(['TRR','totalTrials','ScoreableTrials','totalOptIn','totalOptOut','optOutScoring'])
            a_df = a_df[heads]
            stdev_mets = [met for met in list(a_df) if 'stddev' in met]
            my_metrics_to_be_scored = metrics_to_be_scored + stdev_mets + optOutStats
            float_mets = [met for met in my_metrics_to_be_scored if ('Threshold' not in met) or ('stddev' in met)]
            a_df = round_df(a_df,float_mets)
            a_df.to_csv(path_or_buf=os.path.join(outRootQuery,"_".join([prefix,"mask_score.csv"])),sep="|",index=False)

        return a_df

    def df2html(df,average_df,outputRoot,queryManipulation,query):
        html_out = df.copy()

        #os.path.join doesn't seem to work with Pandas Series so just do a manual string addition
        if outputRoot[-1] == '/':
            outputRoot = outputRoot[:-1]

        #set links around the system output data frame files for images that are not NaN
        #html_out.ix[~pd.isnull(html_out['OutputProbeMaskFileName']),'ProbeFileName'] = '<a href="' + outputRoot + '/' + html_out.ix[~pd.isnull(html_out['OutputProbeMaskFileName']),'ProbeFileName'].str.split('/').str.get(-1).str.split('.').str.get(0) + '.html">' + html_out['ProbeFileName'] + '</a>'
        pd.set_option('display.max_colwidth',-1)
#            html_out.loc[~pd.isnull(html_out['OutputProbeMaskFileName']) & (html_out['Scored'] == 'Y'),'ProbeFileName'] = '<a href="' + html_out.ix[~pd.isnull(html_out['OutputProbeMaskFileName']),'ProbeFileID'] + '/' + html_out.ix[~pd.isnull(html_out['OutputProbeMaskFileName']),'ProbeFileName'].str.split('/').str.get(-1).str.split('.').str.get(0) + '.html">' + html_out.ix[~pd.isnull(html_out['OutputProbeMaskFileName']),'ProbeFileName'].str.split('/').str.get(-1) + '</a>'
        html_out.loc[html_out['Scored'] == 'Y','ProbeFileName'] = '<a href="' + html_out.ix[html_out['Scored'] == 'Y','ProbeFileID'] + '/' + html_out.ix[html_out['Scored'] == 'Y','ProbeFileName'].str.split('/').str.get(-1).str.split('.').str.get(0) + '.html">' + html_out.ix[html_out['Scored'] == 'Y','ProbeFileName'].str.split('/').str.get(-1) + '</a>'

        html_out = html_out.round({'OptimumNMM':3,'OptimumMCC':3,'OptimumBWL1':3,'GWL1':3})

        #final filtering
        html_out.loc[html_out.query("OptimumMCC == -2").index,'OptimumMCC'] = ''
        html_out.loc[html_out.query("(OptimumMCC == 0) & (Scored == 'N')").index,'Scored'] = 'Y'

        #write to index.html
        fname = os.path.join(outputRoot,'index.html')
        myf = open(fname,'w')

        #add other metrics where relevant
        if average_df is not 0:
            #write title and then average_df
            metriclist = {}
            for met in ['NMM','MCC','BWL1']:
                metriclist['Optimum%s' % met] = 3
                if args.sbin >= -1:
                    metriclist['Maximum%s' % met] = 3
                    metriclist['Actual%s' % met] = 3
            for met in ['GWL1','AUC','EER']:
                metriclist[met] = 3
            
            a_df_copy = average_df.copy().round(metriclist)
            myf.write('<h3>Average Scores</h3>\n')
            myf.write(a_df_copy.to_html().replace("text-align: right;","text-align: center;"))

        #insert graphs here
        myf.write("<br/><table><tbody><tr><td><embed src=\"mask_average_roc.pdf\" alt=\"mask_average_roc\" width=\"540\" height=\"540\" type='application/pdf'></td><td><embed src=\"pixel_average_roc.pdf\" alt=\"pixel_average_roc\" width=\"540\" height=\"540\"></td></tr><tr><th>Mask Average ROC</th><th>Pixel Average ROC</th></tr></tbody></table><br/>\n")

        myf.write('<h3>Per Scored Trial Scores</h3>\n')
        myf.write(html_out.to_html(escape=False,na_rep='').replace("text-align: right;","text-align: center;").encode('utf-8'))
        myf.write('\n')
        #write the query if manipulated
        if queryManipulation:
            myf.write("\nFiltered by query: {}\n".format(query))

        myf.close()

elif args.task == 'splice':
    def createReport(m_df, journalData, probeJournalJoin, index, refDir, sysDir, rbin, sbin,erodeKernSize, dilateKernSize,distractionKernSize, kern,outputRoot,html,color,verbose,precision,cache_dir=None):
        #finds rows in index and sys which correspond to target reference
        #sub_index = index[sub_ref['ProbeFileID'].isin(index['ProbeFileID']) & sub_ref['DonorFileID'].isin(index['DonorFileID'])]
        #sub_sys = sys[sub_ref['ProbeFileID'].isin(sys['ProbeFileID']) & sub_ref['DonorFileID'].isin(sys['DonorFileID'])]
    
#        # if the confidence score are 'nan', replace the values with the mininum score
        #m_df[pd.isnull(m_df['ConfidenceScore'])] = m_df['ConfidenceScore'].min()
        # convert to the str type to the float type for computations
        #m_df['ConfidenceScore'] = m_df['ConfidenceScore'].astype(np.float)
#        maskMetricRunner = mm.maskMetricList(m_df,refDir,sysDir,rbin,sbin,journalData,probeJournalJoin,index,mode=1)
        metricRunner = maskMetricRunner(m_df,refDir,sysDir,rbin,args.sbin,journalData,probeJournalJoin,index,speedup=args.speedup,color=False)
#        probe_df = maskMetricRunner.getMetricList(erodeKernSize,dilateKernSize,0,kern,outputRoot,verbose,html,precision=precision)
        #TODO: temporary until we can evaluate color for the splice task
        cache_dir_new=None
        if cache_dir:
            if args.cache_flush:
                os.system('rm -rf {}/*'.format(cache_dir))
            cache_dir_new = os.path.join(cache_dir,'probe')
            mkdir(cache_dir_new)

            config_meta = configparser.ConfigParser()
#        params = loc_scoring_params(1,args.eks,args.dks,0,args.nspx,args.perProbePixelNoScore,args.kernel,args.verbose,args.html,precision,args.truncate,args.processors,args.debug_off,cache_dir=cache_dir_new)
        params = loc_scoring_params(mode = 1,
                                    optOut = args.optOut,
                                    eks = args.eks,
                                    dks = args.dks,
                                    ntdks = 0,
                                    nspx = args.nspx,
                                    pppns = args.perProbePixelNoScore,
                                    kernel = args.kernel,
                                    verbose = args.verbose,
                                    html = args.html,
                                    precision = precision,
                                    truncate = args.truncate,
                                    processors = args.processors,
                                    debug_off = args.debug_off,
                                    cache_dir = cache_dir_new
                                   )
        probe_df = metricRunner.getMetricList(outputRoot,params)
#        probe_df = metricRunner.getMetricList(args.eks,args.dks,0,args.nspx,args.kernel,outputRoot,args.verbose,args.html,precision=args.precision,processors=args.processors)
    
#        maskMetricRunner = mm.maskMetricList(m_df,refDir,sysDir,rbin,sbin,journalData,probeJournalJoin,index,mode=2) #donor images
#        metricRunner = maskMetricRunner(m_df,args.refDir,mySysDir,args.rbin,args.sbin,journalData,probeJournalJoin,index,mode=2,speedup=args.speedup,color=args.color)
#        donor_df = maskMetricRunner.getMetricList(erodeKernSize,dilateKernSize,0,kern,outputRoot,verbose,html,precision=precision)
        if cache_dir:
            cache_dir_new = os.path.join(cache_dir,'donor')
            mkdir(cache_dir_new)

#        params = loc_scoring_params(2,args.eks,args.dks,0,args.nspx,args.perProbePixelNoScore,args.kernel,args.verbose,args.html,precision,args.truncate,args.processors,args.debug_off,cache_dir=cache_dir_new)
        params = loc_scoring_params(mode = 2,
                                    optOut = args.optOut,
                                    eks = args.eks,
                                    dks = args.dks,
                                    ntdks = 0,
                                    nspx = args.nspx,
                                    pppns = args.perProbePixelNoScore,
                                    kernel = args.kernel,
                                    verbose = args.verbose,
                                    html = args.html,
                                    precision = precision,
                                    truncate = args.truncate,
                                    processors = args.processors,
                                    debug_off = args.debug_off,
                                    cache_dir = cache_dir_new
                                   )
        donor_df = metricRunner.getMetricList(outputRoot,params)
#        donor_df = metricRunner.getMetricList(args.eks,args.dks,0,args.nspx,args.kernel,outputRoot,args.verbose,args.html,precision=args.precision,processors=args.processors)

        #make another dataframe here that's formatted distinctly from the first.
        stackp = probe_df.copy()
        stackd = donor_df.copy()
        stackp['DonorFileID'] = stackd['DonorFileID']
        stackd['ProbeFileID'] = stackp['ProbeFileID']
        stackp['ScoredMask'] = 'Probe'
        stackd['ScoredMask'] = 'Donor'
 
        stackdf = pd.concat([stackp,stackd],axis=0)
        stackmerge = pd.merge(stackdf,m_df.drop('Scored',1),how='left',on=['ProbeFileID','DonorFileID'])
        firstcols = ['TaskID','ProbeFileID','ProbeFileName','ProbeMaskFileName','DonorFileID','DonorFileName','DonorMaskFileName','IsTarget','OutputProbeMaskFileName','OutputDonorMaskFileName','ConfidenceScore','ScoredMask','OptimumThreshold','OptimumNMM','OptimumMCC','OptimumBWL1','GWL1','AUC','EER']
#        if args.sbin >= -1:
        firstcols.extend(['MaximumThreshold','MaximumNMM','MaximumMCC','MaximumBWL1',
                          'ActualThreshold','ActualNMM','ActualMCC','ActualBWL1'])
        rcols = stackmerge.columns.tolist()
        metadata = [t for t in rcols if t not in firstcols]
        firstcols.extend(metadata)
        stackmerge = stackmerge[firstcols]

        sidx = stackmerge.query('OptimumMCC==-2').index
        stackmerge.loc[sidx,'Scored'] = 'N'
        nan_met_cols = ['OptimumThreshold','OptimumNMM','OptimumBWL1','GWL1','AUC','EER']
        stackmerge.loc[sidx,nan_met_cols] = np.nan
        stackmerge.loc[sidx,'OptimumMCC'] = np.nan
        
        #add other scores for case sbin >= 0
        probe_df.rename(index=str,columns={"OptimumNMM":"pOptimumNMM",
                                           "OptimumMCC":"pOptimumMCC",
                                           "OptimumBWL1":"pOptimumBWL1",
                                           "GWL1":"pGWL1",
                                           "AUC":"pAUC",
                                           "EER":"pEER",
                                           'OptimumThreshold':'pOptimumThreshold',
                                           'OptimumPixelTP':'pOptimumPixelTP',
                                           'OptimumPixelTN':'pOptimumPixelTN',
                                           'OptimumPixelFP':'pOptimumPixelFP',
                                           'OptimumPixelFN':'pOptimumPixelFN',
                                           "MaximumNMM":"pMaximumNMM",
                                           "MaximumMCC":"pMaximumMCC",
                                           "MaximumBWL1":"pMaximumBWL1",
                                           'MaximumThreshold':'pMaximumThreshold',
                                           'MaximumPixelTP':'pMaximumPixelTP',
                                           'MaximumPixelTN':'pMaximumPixelTN',
                                           'MaximumPixelFP':'pMaximumPixelFP',
                                           'MaximumPixelFN':'pMaximumPixelFN',
                                           "ActualNMM":"pActualNMM",
                                           "ActualMCC":"pActualMCC",
                                           "ActualBWL1":"pActualBWL1",
                                           'ActualThreshold':'pActualThreshold',
                                           'ActualPixelTP':'pActualPixelTP',
                                           'ActualPixelTN':'pActualPixelTN',
                                           'ActualPixelFP':'pActualPixelFP',
                                           'ActualPixelFN':'pActualPixelFN',
                                           'PixelAverageAUC':'pPixelAverageAUC',
                                           'MaskAverageAUC':'pMaskAverageAUC',
                                           'PixelN':'pPixelN',
                                           'PixelBNS':'pPixelBNS',
                                           'PixelSNS':'pPixelSNS',
                                           'PixelPNS':'pPixelPNS',
                                           "ColMaskFileName":"ProbeColMaskFileName",
                                           "AggMaskFileName":"ProbeAggMaskFileName",
                                           "Scored":"ProbeScored"},inplace=True)
    
        donor_df.rename(index=str,columns={"OptimumNMM":"dOptimumNMM",
                                           "OptimumMCC":"dOptimumMCC",
                                           "OptimumBWL1":"dOptimumBWL1",
                                           "GWL1":"dGWL1",
                                           "AUC":"dAUC",
                                           "EER":"dEER",
                                           'OptimumThreshold':'dOptimumThreshold',
                                           'OptimumPixelTP':'dOptimumPixelTP',
                                           'OptimumPixelTN':'dOptimumPixelTN',
                                           'OptimumPixelFP':'dOptimumPixelFP',
                                           'OptimumPixelFN':'dOptimumPixelFN',
                                           "MaximumNMM":"dMaximumNMM",
                                           "MaximumMCC":"dMaximumMCC",
                                           "MaximumBWL1":"dMaximumBWL1",
                                           'MaximumThreshold':'dMaximumThreshold',
                                           'MaximumPixelTP':'dMaximumPixelTP',
                                           'MaximumPixelTN':'dMaximumPixelTN',
                                           'MaximumPixelFP':'dMaximumPixelFP',
                                           'MaximumPixelFN':'dMaximumPixelFN',
                                           "ActualNMM":"dActualNMM",
                                           "ActualMCC":"dActualMCC",
                                           "ActualBWL1":"dActualBWL1",
                                           'ActualThreshold':'dActualThreshold',
                                           'ActualPixelTP':'dActualPixelTP',
                                           'ActualPixelTN':'dActualPixelTN',
                                           'ActualPixelFP':'dActualPixelFP',
                                           'ActualPixelFN':'dActualPixelFN',
                                           'PixelAverageAUC':'dPixelAverageAUC',
                                           'MaskAverageAUC':'dMaskAverageAUC',
                                           'PixelN':'dPixelN',
                                           'PixelBNS':'dPixelBNS',
                                           'PixelSNS':'dPixelSNS',
                                           'PixelPNS':'dPixelPNS',
                                           "ColMaskFileName":"DonorColMaskFileName",
                                           "AggMaskFileName":"DonorAggMaskFileName",
                                           "Scored":"DonorScored"},inplace=True)
    
        pd_df = pd.concat([probe_df,donor_df],axis=1)
        merged_df = pd.merge(m_df,pd_df,how='left',on=['ProbeFileID','DonorFileID']).drop('Scored',1)
        nonscore_df = merged_df.query('(pOptimumMCC == -2) and (dOptimumMCC == -2)')

        #reorder merged_df's columns. Names first, then scores, then other metadata
        p_idx = merged_df.query('pOptimumMCC == -2').index
        d_idx = merged_df.query('dOptimumMCC == -2').index
        rcols = merged_df.columns.tolist()
        firstcols = ['TaskID','ProbeFileID','ProbeFileName','ProbeMaskFileName','DonorFileID','DonorFileName','DonorMaskFileName','IsTarget','OutputProbeMaskFileName','OutputDonorMaskFileName','ConfidenceScore','pOptimumThreshold','pOptimumNMM','pOptimumMCC','pOptimumBWL1','pGWL1','pAUC','pEER','dOptimumThreshold','dOptimumNMM','dOptimumMCC','dOptimumBWL1','dGWL1','dAUC','dEER']
#        if args.sbin >= -1:
        firstcols.extend(['pMaximumThreshold','pMaximumNMM','pMaximumMCC','pMaximumBWL1',
                          'pMaximumPixelTP','pMaximumPixelTN','pMaximumPixelFP','pMaximumPixelFN',
                          'dMaximumThreshold','dMaximumNMM','dMaximumMCC','dMaximumBWL1',
                          'dMaximumPixelTP','dMaximumPixelTN','dMaximumPixelFP','dMaximumPixelFN',
                          'pActualThreshold','pActualNMM','pActualMCC','pActualBWL1',
                          'pActualPixelTP','pActualPixelTN','pActualPixelFP','pActualPixelFN',
                          'dActualThreshold','dActualNMM','dActualMCC','dActualBWL1',
                          'dActualPixelTP','dActualPixelTN','dActualPixelFP','dActualPixelFN'])
        metadata = [t for t in rcols if t not in firstcols]
        firstcols.extend(metadata)
        merged_df = merged_df[firstcols]
  
        #account for other metrics
        if (len(p_idx) > 0) or (len(d_idx) > 0):
            metriclist = ['OptimumThreshold','OptimumNMM','OptimumMCC','OptimumBWL1','GWL1',
                          'OptimumPixelTP','OptimumPixelTN','OptimumPixelFP','OptimumPixelFN',
                          'PixelN','PixelBNS','PixelSNS','PixelPNS']
#            if args.sbin >= -1:
            metriclist.extend(['MaximumThreshold','MaximumNMM','MaximumMCC','MaximumBWL1',
                                       'MaximumPixelTP','MaximumPixelTN','MaximumPixelFP','MaximumPixelFN',
                                       'ActualThreshold','ActualNMM','ActualMCC','ActualBWL1',
                                       'ActualPixelTP','ActualPixelTN','ActualPixelFP','ActualPixelFN'])
            
            for met in metriclist:
                merged_df.loc[p_idx,''.join(['p',met])] = np.nan
                merged_df.loc[d_idx,''.join(['d',met])] = np.nan

        #filter for optout here where both are opted out
        all_cols = merged_df.columns.values.tolist()
        if "IsOptOut" in all_cols:
            failidx = merged_df.query("IsOptOut==['FailedValidation']").index
            merged_df.loc[failidx,'OutputProbeMaskFileName'] = ''
            merged_df.loc[failidx,'OutputDonorMaskFileName'] = ''
            if params.optOut:
                merged_df = merged_df.query("IsOptOut==['N','Detection','FailedValidation']")
        elif "ProbeStatus" in all_cols and 'DonorStatus' in all_cols:
            merged_df.loc[merged_df.query("ProbeStatus==['FailedValidation']").index,'OutputProbeMaskFileName'] = ''
            merged_df.loc[merged_df.query("DonorStatus==['FailedValidation']").index,'OutputDonorMaskFileName'] = ''
            if params.optOut:
                merged_df = merged_df.query("(ProbeStatus==['Processed','NonProcessed','OptOutDetection','FailedValidation']) | (DonorStatus==['Processed','NonProcessed','FailedValidation'])")

        if args.displayScoredOnly:
            #get the list of non-scored and delete them
            nonscore_df.apply(lambda x: os.system('rm -rf {}'.format(os.path.join(outputRoot,'_'.join(x['ProbeFileID'],x['DonorFileID'])))))
#            nonscore_df.apply(lambda x: os.system('echo {}'.format(os.path.join(outputRoot,'_'.join(x['ProbeFileID'],x['DonorFileID'])))))
            merged_df = merged_df.query('(pOptimumMCC > -2) and (dOptimumMCC > -2)')
        return merged_df,stackmerge

    def journalUpdate(probeJournalJoin,journalData,r_df):
        #set where the rows are the same in the join
        pjoins = probeJournalJoin.query("ProbeFileID=={}".format(r_df.query('pOptimumMCC == -2')['ProbeFileID'].tolist()))[['JournalName','StartNodeID','EndNodeID','ProbeFileID']]
        pjoins['Foo'] = 0 #dummy variable to be deleted later
        p_idx = journalData.reset_index().merge(pjoins,how='left',on=['ProbeFileID','JournalName','StartNodeID','EndNodeID']).set_index('index').dropna().drop('Foo',1).index
#        p_idx = pjoins.reset_index().merge(journalData,how='left',on=['ProbeFileID','JournalName','StartNodeID','EndNodeID']).set_index('index').dropna().drop('Color',1).index
        djoins = probeJournalJoin.query("DonorFileID=={}".format(r_df.query('dOptimumMCC == -2')['DonorFileID'].tolist()))[['JournalName','StartNodeID','EndNodeID','DonorFileID']]
        djoins['Foo'] = 0 #dummy variable to be deleted later
        d_idx = journalData.reset_index().merge(djoins,how='left',on=['DonorFileID','JournalName','StartNodeID','EndNodeID']).set_index('index').dropna().drop('Foo',1).index
#        d_idx = djoins.reset_index().merge(journalData,how='left',on=['DonorFileID','JournalName','StartNodeID','EndNodeID']).set_index('index').dropna().drop('Color',1).index

        journalData.loc[p_idx,'ProbeEvaluated'] = 'N'
        journalData.loc[d_idx,'DonorEvaluated'] = 'N'
        journalcols = ['ProbeFileID','DonorFileID']
        journalcols_else = list(journalData)
        journalcols_else.remove('ProbeFileID')
        journalcols_else.remove('DonorFileID')
        journalcols.extend(journalcols_else)

#        journalData = pd.merge(journalData,probeJournalJoin[['ProbeFileID','DonorFileID','JournalName','StartNodeID','EndNodeID']],how='right',on=['JournalName','StartNodeID','EndNodeID'])
        journalData = journalData[journalcols]
        journalData.to_csv(path_or_buf=os.path.join(outRootQuery,'_'.join([prefix,'journalResults.csv'])),sep="|",index=False)
        return 0

    def averageByFactors(r_df,metrics,constant_mets,factor_mode,query):
        if ('pOptimumMCC' not in metrics) or ('dOptimumMCC' not in metrics):
            print("ERROR: pOptimumMCC or dOptimumMCC are not in the metrics.")
            return 1
        #filter nan out of the below
        metrics_to_be_scored = []
        for pfx in ['p','d']:
            metrics_to_be_scored.append(''.join([pfx,'OptimumThreshold']))
            for met in ['MCC','NMM','BWL1']:
                metrics_to_be_scored.append(''.join([pfx,'Optimum',met]))
                if args.sbin >= -1:
                    metrics_to_be_scored.append(''.join([pfx,'Maximum',met]))
                    metrics_to_be_scored.append(''.join([pfx,'Actual',met]))
            for met in ['GWL1','AUC','EER']:
                 metrics_to_be_scored.append(''.join([pfx,met]))
        
        if r_df.query("(ProbeScored == 'Y') | (DonorScored == 'Y')")[metrics_to_be_scored].dropna().shape[0] == 0:
            #if nothing was scored, print a message and return
            print("None of the masks that we attempted to score for query {} had regions to be scored. Further factor analysis is futile.".format(query))
            return 0
        p_idx = r_df.query('pOptimumMCC == -2').index
        d_idx = r_df.query('dOptimumMCC == -2').index
        r_dfc = r_df.copy()
        r_dfc.loc[p_idx,'ProbeScored'] = 'N'
        r_dfc.loc[d_idx,'DonorScored'] = 'N'

        constant_metrics = {}
        for m in constant_mets:
            constant_metrics[m] = myround(r_df[m].iloc[0],args.precision,round_modes)

        #substitute for other values that won't get counted in the average
        r_dfc.loc[p_idx,'pOptimumMCC'] = np.nan
        r_dfc.loc[d_idx,'dOptimumMCC'] = np.nan
        my_partition = pt.Partition(args.task,r_dfc.query("ProbeScored=='Y' | DonorScored=='Y'"),query,factor_mode,metrics) #average over queries
#            my_partition = pt.Partition(r_dfc,q,factor_mode,metrics,verbose) #average over queries
        df_list = my_partition.render_table(metrics)
        if len(df_list) == 0:
            return 0

#        totalTrials = len(r_df)
#        totalOptOut = len(r_df.query("IsOptOut=='Y'"))
#        totalOptIn = totalTrials - totalOptOut
#        TRR = float(totalOptIn)/totalTrials
        optOutStats = ['TRR']

        a_df = 0
        if factor_mode == 'q': #don't print anything if there's nothing to print
            #use Partition for OOP niceness and to identify file to be written. 
            #a_df get the headers of temp_df and tack entries on one after the other
            a_df = pd.DataFrame(columns=df_list[0].columns) 
            for i,temp_df in enumerate(df_list):
                heads = list(temp_df)
                temp_df['TRR'] = TRR
                temp_df['totalTrials'] = totalTrials
                temp_df['ScoreableProbeTrials'] = totalTrials - len(p_idx)
                temp_df['ScoreableDonorTrials'] = totalTrials - len(d_idx)
                temp_df['totalOptIn'] = totalOptIn
                temp_df['totalOptOut'] = totalOptOut
                temp_df['optOutScoring'] = 'N'
                if args.optOut:
                    temp_df['optOutScoring'] = 'Y'

                temp_df.loc[:,['pOptimumThreshold','dOptimumThreshold']].fillna(value=-10,axis=1,inplace=True)
                temp_df.loc[:,['pOptimumThreshold','dOptimumThreshold']] = temp_df[['pOptimumThreshold','dOptimumThreshold']].astype(int).astype(str)
                temp_df.loc[:,['pOptimumThreshold','dOptimumThreshold']].replace(to_replace='-10',value='',inplace=True)
                bincols = ['pMaximumThreshold','pActualThreshold','dMaximumThreshold','dActualThreshold']
                if args.sbin >= -1:
                    temp_df.loc[:,bincols].fillna(value=-10,axis=1,inplace=True)
                    temp_df.loc[:,bincols] = temp_df[bincols].astype(int).astype(str)
                    temp_df.loc[:,bincols].replace(to_replace='-10',value='',inplace=True)
                else:
                    for col in bincols:
                        temp_df.loc[:,col] = ''

                for m in constant_mets:
                    temp_df[m] = constant_metrics[m]
                stdev_mets = [met for met in list(temp_df) if 'stddev' in met]
                my_metrics_to_be_scored = metrics_to_be_scored + stdev_mets + optOutStats
                float_mets = [met for met in my_metrics_to_be_scored if ('Threshold' not in met) or ('stddev' in met)]
                temp_df = round_df(temp_df,float_mets)
                heads.extend(constant_mets)
                heads.extend(['TRR','totalTrials','ScoreableProbeTrials','ScoreableDonorTrials','totalOptIn','totalOptOut','optOutScoring'])
                temp_df = temp_df[heads]
                temp_df.to_csv(path_or_buf="{}_{}.csv".format(os.path.join(outRootQuery,'_'.join([prefix,'mask_scores'])),i),sep="|",index=False)
                a_df = a_df.append(temp_df,ignore_index=True)
            #at the same time do an optOut filter where relevant and save that
#            if args.optOut:
#                my_partition_o = pt.Partition(r_dfc.query("ProbeScored=='Y' | DonorScored=='Y'"),["({}) & (IsOptOut!='Y')".format(q) for q in query],factor_mode,metrics,verbose) #average over queries
#                df_list_o = my_partition_o.render_table(metrics)
#                if len(df_list_o) > 0:
#                    for i,temp_df_o in enumerate(df_list_o):
#                        heads = list(temp_df_o)
#                        temp_df_o['TRR'] = TRR
#                        temp_df_o['totalTrials'] = totalTrials
#                        temp_df_o['totalOptIn'] = totalOptIn
#                        temp_df_o['totalOptOut'] = totalOptOut
#                        heads.extend(['TRR','totalTrials','totalOptIn','totalOptOut'])
#                        temp_df_o = temp_df_o[heads]
#                        temp_df_o.to_csv(path_or_buf="{}_{}.csv".format(os.path.join(outRootQuery,prefix + '-mask_scores_optout'),i),sep="|",index=False)
#                        a_df = a_df.append(temp_df_o,ignore_index=True)
                
        elif (factor_mode == 'qp') or (factor_mode == '') or (factor_mode == 'qm'):
            a_df = df_list[0]
            if len(a_df) == 0:
                return 0
            #add optOut scoring in addition to (not replacing) the averaging procedure
#            if args.optOut:
#                if query == '':
#                    my_partition_o = pt.Partition(r_dfc.query("ProbeScored=='Y' | DonorScored=='Y'"),"IsOptOut!='Y'",factor_mode,metrics,verbose) #average over queries
#                else:
#                    my_partition_o = pt.Partition(r_dfc.query("(ProbeScored=='Y' | DonorScored=='Y') & (IsOptOut!='Y')"),"({}) & (IsOptOut!='Y')".format(query),factor_mode,metrics,verbose) #average over queries
#                df_list_o = my_partition_o.render_table(metrics)
#                if len(df_list_o) > 0:
#                    a_df = a_df.append(df_list_o[0],ignore_index=True)
            heads = list(a_df)
            a_df['TRR'] = TRR
            a_df['totalTrials'] = totalTrials
            a_df['ScoreableProbeTrials'] = totalTrials - len(p_idx)
            a_df['ScoreableDonorTrials'] = totalTrials - len(d_idx)
            a_df['totalOptIn'] = totalOptIn
            a_df['totalOptOut'] = totalOptOut
            a_df['optOutScoring'] = 'N'
            if args.optOut:
                a_df['optOutScoring'] = 'Y'

            for m in constant_mets:
                a_df[m] = constant_metrics[m]
            heads.extend(constant_mets)
            heads.extend(['TRR','totalTrials','ScoreableProbeTrials','ScoreableDonorTrials','totalOptIn','totalOptOut','optOutScoring'])
            a_df = a_df[heads]
            #fillna with '' and then turn everything into a string
            if a_df is not 0:
#                def vals2intstr(row):
#                    keys = row.keys()
#                    for k in keys:
#                        n = row[k]
#                        if n in [np.nan,None]:
#                            row.set_value(k,'')
#                        else:
#                            row.set_value(k,str(int(n)))#"{:.0f}".format(n)
#                    return row

                #integer-ize everything to get rid of trailing decimak okaces#
                a_df.loc[:,['pOptimumThreshold','dOptimumThreshold']].fillna(value=-10,axis=1,inplace=True)
                a_df.loc[:,['pOptimumThreshold','dOptimumThreshold']] = a_df[['pOptimumThreshold','dOptimumThreshold']].astype(int).astype(str)
                a_df.loc[:,['pOptimumThreshold','dOptimumThreshold']].replace(to_replace='-10',value='',inplace=True)

                bincols = ['pMaximumThreshold','pActualThreshold','dMaximumThreshold','dActualThreshold']
                if args.sbin >= -1:
                    a_df.loc[:,bincols].fillna(value=-10,axis=1,inplace=True)
                    a_df.loc[:,bincols] = a_df[bincols].astype(int).astype(str)
                    a_df.loc[:,bincols].replace(to_replace='-10',value='',inplace=True)
                else:
                    for col in bincols:
                        a_df.loc[:,col] = ''
                    
            stdev_mets = [met for met in list(a_df) if 'stddev' in met]
            my_metrics_to_be_scored = metrics_to_be_scored + stdev_mets + optOutStats
            float_mets = [met for met in my_metrics_to_be_scored if ('Threshold' not in met) or ('stddev' in met)]
            a_df = round_df(a_df,float_mets)
            a_df.to_csv(path_or_buf=os.path.join(outRootQuery,'_'.join([prefix,"mask_score.csv"])),sep="|",index=False)

        return a_df

    def df2html(df,average_df,outputRoot,queryManipulation,query):
        html_out = df.copy()

        #os.path.join doesn't seem to work with Pandas Series so just do a manual string addition
        if outputRoot[-1] == '/':
            outputRoot = outputRoot[:-1]

        #set links around the system output data frame files for images that are not NaN
        #html_out.ix[~pd.isnull(html_out['OutputProbeMaskFileName']),'ProbeFileName'] = '<a href="' + outputRoot + '/' + html_out.ix[~pd.isnull(html_out['OutputProbeMaskFileName']),'ProbeFileName'].str.split('/').str.get(-1).str.split('.').str.get(0) + '.html">' + html_out['ProbeFileName'] + '</a>'
        #html_out.ix[~pd.isnull(html_out['OutputDonorMaskFileName']),'DonorFileName'] = '<a href="' + outputRoot + '/' + html_out.ix[~pd.isnull(html_out['OutputDonorMaskFileName']),'DonorFileName'].str.split('/').str.get(-1).str.split('.').str.get(0) + '.html">' + html_out['DonorFileName'] + '</a>'
        pd.set_option('display.max_colwidth',-1)
#            html_out.loc[~pd.isnull(html_out['OutputProbeMaskFileName']),'ProbeFileName'] = '<a href="' + html_out.ix[~pd.isnull(html_out['OutputProbeMaskFileName']),'ProbeFileID'] + '_' + html_out.ix[~pd.isnull(html_out['OutputProbeMaskFileName']),'DonorFileID'] + '/probe/' + html_out.ix[~pd.isnull(html_out['OutputProbeMaskFileName']),'ProbeFileName'].str.split('/').str.get(-1).str.split('.').str.get(0) + '.html">' + html_out.ix[~pd.isnull(html_out['OutputProbeMaskFileName']),'ProbeFileName'].str.split('/').str.get(-1) + '</a>'
#            html_out.loc[~pd.isnull(html_out['OutputDonorMaskFileName']),'DonorFileName'] = '<a href="' + html_out.ix[~pd.isnull(html_out['OutputProbeMaskFileName']),'ProbeFileID'] + '_' + html_out.ix[~pd.isnull(html_out['OutputProbeMaskFileName']),'DonorFileID'] + '/donor/' + html_out.ix[~pd.isnull(html_out['OutputDonorMaskFileName']),'DonorFileName'].str.split('/').str.get(-1).str.split('.').str.get(0) + '.html">' + html_out.ix[~pd.isnull(html_out['OutputDonorMaskFileName']),'DonorFileName'].str.split('/').str.get(-1) + '</a>'

        html_out.at[html_out['ProbeScored'] == 'Y','ProbeFileName'] = '<a href="' + html_out.ix[html_out['ProbeScored'] == 'Y','ProbeFileID'] + '_' + html_out.ix[html_out['ProbeScored'] == 'Y','DonorFileID'] + '/probe/' + html_out.ix[html_out['ProbeScored'] == 'Y','ProbeFileName'].str.split('/').str.get(-1).str.split('.').str.get(0) + '.html">' + html_out.ix[html_out['ProbeScored'] == 'Y','ProbeFileName'].str.split('/').str.get(-1) + '</a>'
        html_out.at[html_out['DonorScored'] == 'Y','DonorFileName'] = '<a href="' + html_out.ix[html_out['DonorScored'] == 'Y','ProbeFileID'] + '_' + html_out.ix[html_out['DonorScored'] == 'Y','DonorFileID'] + '/donor/' + html_out.ix[html_out['DonorScored'] == 'Y','DonorFileName'].str.split('/').str.get(-1).str.split('.').str.get(0) + '.html">' + html_out.ix[html_out['DonorScored'] == 'Y','DonorFileName'].str.split('/').str.get(-1) + '</a>'

        html_out = html_out.round({'pOptimumNMM':3,'pOptimumMCC':3,'pOptimumBWL1':3,'pGWL1':3,'dOptimumNMM':3,'dOptimumMCC':3,'dOptimumBWL1':3,'dGWL1':3})

        html_out.at[html_out.query("pOptimumMCC == -2").index,'pOptimumMCC'] = ''
        html_out.at[html_out.query("dOptimumMCC == -2").index,'dOptimumMCC'] = ''
        html_out.at[html_out.query("pOptimumMCC == 0 & ProbeScored == 'N'").index,'ProbeScored'] = 'Y'
        html_out.at[html_out.query("dOptimumMCC == 0 & DonorScored == 'N'").index,'DonorScored'] = 'Y'
        #write to index.html
        fname = os.path.join(outputRoot,'index.html')
        myf = open(fname,'w')

        if average_df is not 0:
            #write title and then average_df
            metriclist = {}
            for pfx in ['p','d']:
                for met in ['NMM','MCC','BWL1']:
                    metriclist[''.join([pfx,'Optimum',met])] = 3
                    if args.sbin >= -1:
                        metriclist[''.join([pfx,'Maximum',met])] = 3
                        metriclist[''.join([pfx,'Actual',met])] = 3
                for met in ['GWL1','AUC','EER']:
                    metriclist[''.join([pfx,met])] = 3

            a_df_copy = average_df.copy().round(metriclist)
            myf.write('<h3>Average Scores</h3>\n')
            myf.write(a_df_copy.to_html().replace("text-align: right;","text-align: center;"))

        #insert graphs here
        myf.write("<br/><table><tbody><tr><td><embed src=\"mask_average_roc_probe.pdf\" alt=\"mask_average_roc_probe\" width=\"540\" height=\"540\" type='application/pdf'></td><td><embed src=\"pixel_average_roc_probe.pdf\" alt=\"pixel_average_roc_probe\" width=\"540\" height=\"540\" type='application/pdf'></td></tr><tr><th>Probe Average ROC</th><th>Probe Pixel Average ROC</th></tr><tr><td><embed src=\"mask_average_roc_donor.pdf\" alt=\"mask_average_roc_donor\" width=\"540\" height=\"540\" type='application/pdf'</td><td><embed src=\"pixel_average_roc_donor.pdf\" alt=\"pixel_average_roc_donor\" width=\"540\" height=\"540\" type='application/pdf'></td></tr><tr><th>Donor Average ROC</th><th>Donor Pixel Average ROC</th></tr></tbody></table><br/>\n")

        myf.write('<h3>Per Scored Trial Scores</h3>\n')
        myf.write(html_out.to_html(escape=False,na_rep='').encode('utf-8'))
        myf.write('\n')
        #write the query if manipulated
        if queryManipulation:
            myf.write("\nFiltered by query: {}\n".format(query))

        myf.close()

#TODO: basic data init-ing starts here
factor_mode = ''
query = '' #in a similar format to queryManipulation elements, since partition treats them similarly
n_query = 1
if args.query:
    factor_mode = 'q'
    query = args.query #is a list of items
elif args.queryPartition:
    factor_mode = 'qp'
    query = args.queryPartition #is a singleton, so keep it as such
elif args.queryManipulation:
    factor_mode = 'qm'
    query = args.queryManipulation #is a list of items
    n_query = len(args.queryManipulation)

## if the confidence score are 'nan', replace the values with the mininum score
#mySys[pd.isnull(mySys['ConfidenceScore'])] = mySys['ConfidenceScore'].min()
## convert to the str type to the float type for computations
#mySys['ConfidenceScore'] = mySys['ConfidenceScore'].astype(np.float)

outRoot = outdir
prefix = outpfx#os.path.basename(args.inSys).split('.')[0]

reportq = 0
if args.verbose:
    reportq = 1

if args.precision < 1:
    printq("Precision should not be less than 1 for scores to be meaningful. Defaulting to 16 digits.")
    args.precision=16

#update accordingly along with ProbeJournalJoin and JournalMask csv's in refDir
refpfx = os.path.join(myRefDir,args.inRef.split('.')[0])
#try/catch this
try:
    probeJournalJoin = pd.read_csv('-'.join([refpfx,'probejournaljoin.csv']),sep="|",header=0,na_filter=False)
except IOError:
    print("No probeJournalJoin file is present. This run will terminate.")
    exit(1)

try:
    journalMask = pd.read_csv('-'.join([refpfx,'journalmask.csv']),sep="|",header=0,na_filter=False)
except IOError:
    print("No journalMask file is present. This run will terminate.")
    exit(1)
    
#TODO: basic data init-ing ends here

def cache_init(cache_dir,output_dir,query=''):
    if args.cache_flush:
        os.system('rm -rf {}/*'.format(cache_dir))
    mkdir(cache_dir)
    #save all metadata in a file in this directory.
    config_meta = configparser.ConfigParser()
    refpfx = args.inRef[:-4]
    pjj_name = '%s-probejournaljoin.csv' % refpfx
    jm_name = '%s-journalmask.csv' % refpfx

    config_meta['eval_task'] = {'task':args.task}
    config_meta['reference'] = {'directory':args.refDir,
                                'reference':args.inRef,
                                'probejournaljoin':pjj_name,
                                'journalmask':jm_name}
    config_meta['index'] = {'indexfile':args.inIndex}
    config_meta['query'] = {'query':query}
    config_meta['no_score_parameters'] = {'kernel':args.kernel,
                                          'erode_size':args.eks,
                                          'dilate_size':args.dks,
                                          'non_target_size':args.ntdks,
                                          'global_pixel_ns':args.nspx,
                                          'per_probe_pixel_ns':args.perProbePixelNoScore}
    config_meta['JPEG2000_scoring'] = {'implemented':args.jpeg2000}

    config_name = os.path.join(cache_dir,'config.ini')
   
    tmp_path = os.path.join(output_dir,'config_tmp.ini')
    with open(tmp_path,'w') as configfile:
        config_meta.write(configfile)
    #if exists, check the two to ensure they are equal
    if os.path.isfile(config_name):
        existing_config = configparser.ConfigParser()
        existing_config.read(config_name)
        #if not equal, print a warning
        if existing_config != config_meta:
            print("Warning: a config file exists, but is not identical to the parameters generated.")
            os.system('diff {} {}'.format(tmp_path,config_name))
            #if reference files are not identical, terminate and ask for a new reference directory
            score_status = 0
            config_check_fields = ['eval_task:task:evaluation tasks',
                                  'reference:reference:reference files',
                                  'query:query:queries',
                                  'JPEG2000_scoring:implemented:JPEG2000 scoring options',
                                  'no_score_parameters:kernel:kernel types',
                                  'no_score_parameters:erode_size:erode kernel sizes',
                                  'no_score_parameters:dilate_size:dilate kernel sizes',
                                  'no_score_parameters:non_target_size:non-target kernel sizes']
            for fields in config_check_fields:
                f1,f2,ferr = fields.split(':')
                if (f1 == 'no_score_parameters') and (score_status == 0) and (existing_config[f1][f2] != config_meta[f1][f2]):
                    print("The {} are not equal between the configuration files. Preparing to reset the no-score masks.".format(ferr))
                    #remove all bns.png and sns.png.
                    if args.task == 'manipulation':
                        os.system('rm -f {}'.format(os.path.join(cache_dir,'*_bns.png')))
                        os.system('rm -f {}'.format(os.path.join(cache_dir,'*_sns.png')))
                    elif args.task == 'splice':
                        #append probe and donor dirs if splice
                        for sub_dir in ['probe','donor']:
                            cache_sub_dir = os.path.join(cache_dir,sub_dir)
                            os.system('rm -f {}'.format(os.path.join(cache_sub_dir,'*_bns.png')))
                            os.system('rm -f {}'.format(os.path.join(cache_sub_dir,'*_sns.png')))
                    continue
                if existing_config[f1][f2] != config_meta[f1][f2]:
                    print("Error: the {} are not equal between the configuration files.".format(ferr))
                    score_status = 1
            if score_status == 1:
                print("Pick a different directory to cache the reference data or rerun with --cache_flush to remove existing data.")
                exit(1)
#            else:
#                os.rename(tmp_path,config_name)
#    else:
#        os.rename(tmp_path,config_name)

# Merge the reference and system output
if args.task == 'manipulation':
    #TODO: basic data cleanup
    # if the confidence score are 'nan', replace the values with the mininum score
    m_df.loc[pd.isnull(m_df['ConfidenceScore']),'ConfidenceScore'] = mySys['ConfidenceScore'].min()
    # convert to the str type to the float type for computations
    m_df['ConfidenceScore'] = m_df['ConfidenceScore'].astype(np.float)
    journaljoinfields = ['JournalName','StartNodeID','EndNodeID']
#    if 'BitPlane' in list(probeJournalJoin):
#        journaljoinfields.append('BitPlane')

    journalData0 = pd.merge(probeJournalJoin,journalMask,how='left',on=journaljoinfields)
    if args.indexFilter:
        printq("Filtering the journal data by index file...")
        myIndex = myIndex.query("ProbeFileID == {}".format(probeJournalJoin['ProbeFileID'].unique().tolist())) #filter index first.
        journalData0 = pd.merge(myIndex[['ProbeFileID','ProbeWidth']],journalData0,how='left',on='ProbeFileID').drop('ProbeWidth',1)
    n_journals = len(journalData0)
    journalData0.index = range(n_journals)
    #TODO: basic data cleanup ends here

    if factor_mode == 'qm':
        queryM = query
    else:
        queryM = ['']

    for qnum,q in enumerate(queryM):
        #journalData0 = journalMask.copy() #pd.merge(probeJournalJoin,journalMask,how='left',on=['JournalName','StartNodeID','EndNodeID'])
        journalData_df = pd.merge(probeJournalJoin,journalMask,how='left',on=journaljoinfields)

        m_dfc = m_df.copy()
        if factor_mode == 'qm':
            journalData0['Evaluated'] = pd.Series(['N']*n_journals)
        else:
            journalData0['Evaluated'] = pd.Series(['Y']*n_journals) #add column for Evaluated: 'Y'/'N'

        #journalData = journalData0.copy()
        #use big_df to filter from the list as a temporary thing
        if q is not '':
            #exit if query does not match
            printq("Merging main data and journal data and querying the result...")
            try:
                big_df = pd.merge(m_df,journalData_df,how='left',on=['ProbeFileID','JournalName']).query(q) #TODO: test on sample with a print?
            except pd.computation.ops.UndefinedVariableError:
                print("The query '{}' doesn't seem to refer to a valid key. Please correct the query and try again.".format(q))
                exit(1)

            m_dfc = m_dfc.query("ProbeFileID=={}".format(np.unique(big_df.ProbeFileID).tolist()))
            #journalData = journalData.query("ProbeFileID=={}".format(list(big_df.ProbeFileID)))
            journalData_df = journalData_df.query("ProbeFileID=={}".format(list(big_df.ProbeFileID)))
#            journalData_df = journalData_df.merge(big_df[['ProbeFileID','JournalName','StartNodeID','EndNodeID']],how='left',on=['ProbeFileID','JournalName','StartNodeID','EndNodeID'])
            journalData0.loc[journalData0.reset_index().merge(big_df[['ProbeFileID','ProbeMaskFileName'] + journaljoinfields],\
                             how='left',on=journaljoinfields).set_index('index').dropna().drop('ProbeMaskFileName',1).index,'Evaluated'] = 'Y'
        m_dfc.index = range(len(m_dfc))
            #journalData.index = range(0,len(journalData))

        #if get empty journalData or if no ProbeFileID's match between the two, there is nothing to be scored.
        if (len(journalData_df) == 0) or not (True in journalData_df['ProbeFileID'].isin(m_df['ProbeFileID']).unique()):
            print("The query '{}' yielded no journal data over which computation may take place.".format(q))
            continue

        outRootQuery = outRoot
        if len(queryM) > 1:
            outRootQuery = os.path.join(outRoot,'index_{}'.format(qnum)) #affix outRoot with qnum suffix for some length
            mkdir(outRootQuery)
        m_dfc['Scored'] = ['Y']*len(m_dfc)

        cache_sub_dir_new = cache_sub_dir[:]
        if (q is not '') and n_query > 1:
            cache_sub_dir_new.append('q{}'.format(qnum))
        cache_full_dir=None
        if args.cache_dir:
            cache_full_dir=os.path.join(args.cache_dir,'_'.join(cache_sub_dir_new))
            cache_init(cache_full_dir,outRootQuery,q)

        printq("Beginning mask scoring...")
        r_df = createReport(m_dfc,journalData0, probeJournalJoin, myIndex, myRefDir, mySysDir,args.rbin,args.sbin,args.eks, args.dks, args.ntdks, args.kernel, outRootQuery, html=args.html,color=args.jpeg2000,verbose=reportq,precision=16,cache_dir=cache_full_dir)

        #get the manipulations that were not scored and set the same columns in journalData0 to 'N'
        journalUpdate(probeJournalJoin,journalData0,r_df)
        
        metrics = ['OptimumThreshold','OptimumNMM','OptimumMCC','OptimumBWL1','GWL1','AUC','EER']
#        if args.sbin >= -1:
        metrics.extend(['MaximumNMM','MaximumMCC','MaximumBWL1',
                        'ActualNMM','ActualMCC','ActualBWL1'])
        constant_mets = ['PixelAverageAUC','MaskAverageAUC']
#        if args.sbin >= -1:
        constant_mets.extend(['MaximumThreshold','ActualThreshold'])

        a_df = 0
        if factor_mode == 'qm':
            a_df = averageByFactors(r_df,metrics,constant_mets,factor_mode,q)
        else:
            a_df = averageByFactors(r_df,metrics,constant_mets,factor_mode,query)

        # tack on PixelAverageAUC and MaskAverageAUC to a_df and remove from r_df
        r_df = r_df.drop(['PixelAverageAUC','MaskAverageAUC'],1)
#        if args.sbin >= -1:
        r_df = r_df.drop(['MaximumThreshold','ActualThreshold'],1)

#        if a_df is not 0:
#            a_df['OptimumThreshold'] = a_df['OptimumThreshold'].dropna().apply(lambda x: str(int(x)))
#            if args.sbin >= 0:
#                a_df['MaximumThreshold'] = a_df['MaximumThreshold'].dropna().apply(lambda x: str(int(x)))
#                a_df['ActualThreshold'] = a_df['ActualThreshold'].dropna().apply(lambda x: str(int(x)))

        r_idx = r_df.query('OptimumMCC == -2').index
        if len(r_idx) > 0:
            r_df.loc[r_idx,'Scored'] = 'N'
            r_df.loc[r_idx,'OptimumNMM'] = ''
            r_df.loc[r_idx,'OptimumBWL1'] = ''
            r_df.loc[r_idx,'GWL1'] = ''

        #convert all pixel values to decimal-less strings
        pix2ints = ['OptimumThreshold','OptimumPixelTP','OptimumPixelFP','OptimumPixelTN','OptimumPixelFN',
                    'PixelN','PixelBNS','PixelSNS','PixelPNS']

        if args.sbin >= -1:
            pix2ints.extend(['MaximumPixelTP','MaximumPixelFP','MaximumPixelTN','MaximumPixelFN',
                             'ActualPixelTP','ActualPixelFP','ActualPixelTN','ActualPixelFN'])

        for pix in pix2ints:
            r_df[pix] = r_df[pix].dropna().apply(lambda x: str(int(x)))

        #generate HTML table report
        if args.html:
            df2html(r_df,a_df,outRootQuery,args.queryManipulation,q)

        r_df.loc[r_idx,'OptimumMCC'] = ''
        prefix = outpfx#os.path.basename(args.inSys).split('.')[0]

        #control precision here
        float_mets = [met for met in metrics if 'Threshold' not in met]
        r_df[float_mets] = r_df[float_mets].applymap(lambda n: myround(n,args.precision,round_modes))

        if args.outMeta:
            roM_df = r_df[['TaskID','ProbeFileID','ProbeFileName','OutputProbeMaskFileName','IsTarget','ConfidenceScore',optOutCol,
                           'OptimumThreshold','OptimumNMM','OptimumMCC','OptimumBWL1','GWL1','AUC','EER',
                           'OptimumPixelTP','OptimumPixelTN','OptimumPixelFP','OptimumPixelFN',
                           'MaximumNMM','MaximumMCC','MaximumBWL1',
                           'MaximumPixelTP','MaximumPixelTN','MaximumPixelFP','MaximumPixelFN',
                           'ActualNMM','ActualMCC','ActualBWL1',
                           'ActualPixelTP','ActualPixelTN','ActualPixelFP','ActualPixelFN',
                           'PixelN','PixelBNS','PixelSNS','PixelPNS'
                          ]]
            roM_df.to_csv(path_or_buf=os.path.join(outRootQuery,'_'.join([prefix,'perimage-outMeta.csv'])),sep="|",index=False)
        if args.outAllmeta:
            #left join with index file and journal data
            rAM_df = pd.merge(r_df,myIndex,how='left',on=['TaskID','ProbeFileID','ProbeFileName'])
            rAM_df = pd.merge(rAM_df,journalData0,how='left',on=['ProbeFileID','JournalName'])
            rAM_df.to_csv(path_or_buf=os.path.join(outRootQuery,'_'.join([prefix,'perimage-allMeta.csv'])),sep="|",index=False)

        r_df.to_csv(path_or_buf=os.path.join(outRootQuery,'_'.join([prefix,'mask_scores_perimage.csv'])),sep="|",index=False)
    
elif args.task == 'splice':
    #TODO: basic data cleanup
    # if the confidence score are 'nan', replace the values with the mininum score
    m_df.loc[pd.isnull(m_df['ConfidenceScore']),'ConfidenceScore'] = mySys['ConfidenceScore'].min()
    # convert to the str type to the float type for computations
    m_df['ConfidenceScore'] = m_df['ConfidenceScore'].astype(np.float)

    journaljoinfields = ['JournalName','StartNodeID','EndNodeID']
#    journaljoinfields = ['JournalName']
#    if 'BitPlane' in list(probeJournalJoin):
#        journaljoinfields.append('BitPlane')

    joinfields = param_ids+journaljoinfields
    journalData0 = pd.merge(probeJournalJoin[joinfields].drop_duplicates(),journalMask,how='left',on=journaljoinfields).drop_duplicates()
    if args.indexFilter:
        printq("Filtering the journal data by index file...")
#        myIndex['ProbeDonorID'] = ":".join([myIndex['ProbeFileID'],myIndex['DonorFileID']])
#        journalData0['ProbeDonorID'] = ":".join([journalData0['ProbeFileID'],journalData0['DonorFileID']])
        myIndex['ProbeDonorID'] = myIndex[['ProbeFileID','DonorFileID']].apply(lambda x: ':'.join(x),axis=1)
        journalData0['ProbeDonorID'] = journalData0[['ProbeFileID','DonorFileID']].apply(lambda x: ':'.join(x),axis=1)
        myIndex = myIndex.query("ProbeDonorID=={}".format(journalData0.ProbeDonorID.unique().tolist())) #first filter by Probe-Donor pairs
        journalData0 = pd.merge(myIndex[['ProbeDonorID']],journalData0,how='left',on=['ProbeDonorID']).drop('ProbeDonorID',1)
    
    n_journals = len(journalData0)
    journalData0.index = range(n_journals)
    #TODO: basic data cleanup ends here

    if factor_mode == 'qm':
        queryM = query
    else:
        queryM = ['']

    eval_pfx = param_pfx[:]
    for qnum,q in enumerate(queryM):
        m_dfc = m_df.copy()

        for param in eval_pfx:
            if factor_mode == 'qm':
                journalData0[param+'Evaluated'] = pd.Series(['N']*n_journals)
            else:
                journalData0[param+'Evaluated'] = pd.Series(['Y']*n_journals)

        #use big_df to filter from the list as a temporary thing
        journalData_df = pd.merge(probeJournalJoin,journalMask,how='left',on=journaljoinfields)
        #journalData = journalData0.copy()

        if q is not '':
            #exit if query does not match
            printq("Merging main data and journal data and querying the result...")
            try:
                bigdf_join_fields = param_ids
                if 'JournalName' in m_df.columns.values.tolist():
                    bigdf_join_fields = param_ids + ['JournalName']
                big_df = pd.merge(m_df,journalData_df,how='left',on=bigdf_join_fields).query(q)
            except pd.computation.ops.UndefinedVariableError:
                print("The query '{}' doesn't seem to refer to a valid key. Please correct the query and try again.".format(q))
                exit(1)

            #do a join with the big dataframe and filter out the stuff that doesn't show up by pairs
            m_dfc = pd.merge(m_dfc,big_df[bigdf_join_fields + ['Operation']],how='left',on=bigdf_join_fields).dropna().drop('Operation',1)
            #journalData = pd.merge(journalData0,big_df[['ProbeFileID','DonorFileID','JournalName']],how='left',on=['ProbeFileID','DonorFileID','JournalName'])
            journalData0.loc[journalData0.reset_index().merge(big_df[journaljoinfields + ['ProbeFileID','DonorFileID','ProbeMaskFileName']],\
                             how='left',on=journaljoinfields).set_index('index').dropna().drop('ProbeMaskFileName',1).index,'ProbeEvaluated'] = 'Y'
            journalData0.loc[journalData0.reset_index().merge(big_df[journaljoinfields + ['ProbeFileID','DonorFileID','DonorMaskFileName']],\
                             how='left',on=journaljoinfields).set_index('index').dropna().drop('DonorMaskFileName',1).index,'DonorEvaluated'] = 'Y'

        m_dfc.index = range(m_dfc.shape[0])
            #journalData.index = range(0,len(journalData))

        #if no (ProbeFileID,DonorFileID) pairs match between the two, there is nothing to be scored.
        if len(pd.merge(m_df,journalData_df,how='left',on=param_ids)) == 0:
            print("The query '{}' yielded no journal data over which computation may take place.".format(q))
            continue

        outRootQuery = outRoot
        if len(queryM) > 1:
            outRootQuery = os.path.join(outRoot,'index_{}'.format(qnum)) #affix outRoot with qnum suffix for some length
            mkdir(outRootQuery)
   
        m_dfc['Scored'] = ['Y']*m_dfc.shape[0]

        cache_sub_dir_new = cache_sub_dir[:]
        if q is not '':
            cache_sub_dir_new.append('q{}'.format(qnum))
        cache_full_dir=None
        if args.cache_dir:
            cache_full_dir=os.path.join(args.cache_dir,'_'.join(cache_sub_dir_new))
            cache_init(cache_full_dir,outRootQuery,q)
        printq("Beginning mask scoring...")
        r_df,stackdf = createReport(m_dfc,journalData0, probeJournalJoin, myIndex, myRefDir, mySysDir,args.rbin,args.sbin,args.eks, args.dks, args.ntdks, args.kernel, outRootQuery, html=args.html,color=args.jpeg2000,verbose=reportq,precision=16,cache_dir=cache_full_dir)
        journalUpdate(probeJournalJoin,journalData0,r_df)

        #filter here
        metrics = ['pOptimumThreshold','pOptimumNMM','pOptimumMCC','pOptimumBWL1','pGWL1','pAUC','pEER',
                   'dOptimumThreshold','dOptimumNMM','dOptimumMCC','dOptimumBWL1','dGWL1','dAUC','dEER']
#        if args.sbin >= -1:
        metrics.extend(['pMaximumNMM','pMaximumMCC','pMaximumBWL1',
                        'dMaximumNMM','dMaximumMCC','dMaximumBWL1',
                        'pActualNMM','pActualMCC','pActualBWL1',
                        'dActualNMM','dActualMCC','dActualBWL1'])
        constant_mets = ['pPixelAverageAUC','dPixelAverageAUC','pMaskAverageAUC','dMaskAverageAUC']
#        if args.sbin >= -1:
        constant_mets.extend(['pMaximumThreshold','dMaximumThreshold','pActualThreshold','dActualThreshold'])

        a_df = 0
        if factor_mode == 'qm':
            a_df = averageByFactors(r_df,metrics,constant_mets,factor_mode,q)
        else:
            a_df = averageByFactors(r_df,metrics,constant_mets,factor_mode,query)

        r_df = r_df.drop(['pPixelAverageAUC','pMaskAverageAUC','dPixelAverageAUC','dMaskAverageAUC'],1)
#        if args.sbin >= -1:
        r_df = r_df.drop(['pMaximumThreshold','pActualThreshold','dMaximumThreshold','dActualThreshold'],1)

        #convert all to ints.
#        if a_df is not 0:
#            a_df['pOptimumThreshold'] = a_df['pOptimumThreshold'].dropna().apply(lambda x: str(int(x)))
#            a_df['dOptimumThreshold'] = a_df['dOptimumThreshold'].dropna().apply(lambda x: str(int(x)))
#            if args.sbin >= 0:
#                a_df['pMaximumThreshold'] = a_df['pMaximumThreshold'].dropna().apply(lambda x: str(int(x)))
#                a_df['pActualThreshold'] = a_df['pActualThreshold'].dropna().apply(lambda x: str(int(x)))
#                a_df['dMaximumThreshold'] = a_df['dMaximumThreshold'].dropna().apply(lambda x: str(int(x)))
#                a_df['dActualThreshold'] = a_df['dActualThreshold'].dropna().apply(lambda x: str(int(x)))

        p_mcc_idx = r_df.query('pOptimumMCC == -2').index
        d_mcc_idx = r_df.query('dOptimumMCC == -2').index
        r_df.loc[p_mcc_idx,'ProbeScored'] = 'N'
        r_df.loc[p_mcc_idx,'pOptimumNMM'] = ''
        r_df.loc[p_mcc_idx,'pOptimumBWL1'] = ''
        r_df.loc[p_mcc_idx,'pGWL1'] = ''
        r_df.loc[d_mcc_idx,'DonorScored'] = 'N'
        r_df.loc[d_mcc_idx,'dOptimumNMM'] = ''
        r_df.loc[d_mcc_idx,'dOptimumBWL1'] = ''
        r_df.loc[d_mcc_idx,'dGWL1'] = ''

        #convert all pixel values to decimal-less strings
        pix2ints = ['pOptimumThreshold','pOptimumPixelTP','pOptimumPixelFP','pOptimumPixelTN','pOptimumPixelFN',
                    'pPixelN','pPixelBNS','pPixelSNS','pPixelPNS',
                    'dOptimumThreshold','dOptimumPixelTP','dOptimumPixelFP','dOptimumPixelTN','dOptimumPixelFN',
                    'dPixelN','dPixelBNS','dPixelSNS','dPixelPNS']

        if args.sbin >= -1:
            pix2ints.extend(['pMaximumPixelTP','pMaximumPixelFP','pMaximumPixelTN','pMaximumPixelFN',
                             'pActualPixelTP','pActualPixelFP','pActualPixelTN','pActualPixelFN',
                             'dMaximumPixelTP','dMaximumPixelFP','dMaximumPixelTN','dMaximumPixelFN',
                             'dActualPixelTP','dActualPixelFP','dActualPixelTN','dActualPixelFN'])

        for pix in pix2ints:
            r_df[pix] = r_df[pix].dropna().apply(lambda x: str(int(x)))

        #generate HTML table report
        if args.html:
            df2html(r_df,a_df,outRootQuery,args.queryManipulation,q)
    
        r_df.loc[p_mcc_idx,'pOptimumMCC'] = ''
        r_df.loc[d_mcc_idx,'dOptimumMCC'] = ''

        prefix = outpfx#os.path.basename(args.inSys).split('.')[0]
        #control precision here
        float_mets = [met for met in metrics if 'Threshold' not in met]
        r_df[float_mets] = r_df[float_mets].applymap(lambda n: myround(n,args.precision,round_modes))

        #other reports of varying
        if args.outMeta:
            roM_df = stackdf[['TaskID','ProbeFileID','ProbeFileName','DonorFileID','DonorFileName','OutputProbeMaskFileName','OutputDonorMaskFileName','ScoredMask','IsTarget','ConfidenceScore',optOutCol,
                              'OptimumThreshold','OptimumNMM','OptimumMCC','OptimumBWL1','GWL1','AUC','EER',
                              'OptimumPixelTP','OptimumPixelTN','OptimumPixelFP','OptimumPixelFN',
                              'MaximumNMM','MaximumMCC','MaximumBWL1',
                              'MaximumPixelTP','MaximumPixelTN','MaximumPixelFP','MaximumPixelFN',
                              'ActualNMM','ActualMCC','ActualBWL1',
                              'ActualPixelTP','ActualPixelTN','ActualPixelFP','ActualPixelFN',
                              'PixelN','PixelBNS','PixelSNS','PixelPNS'
                              ]]
            roM_df.to_csv(path_or_buf=os.path.join(outRootQuery,'_'.join([prefix,'perimage-outMeta.csv'])),sep="|",index=False)
        if args.outAllmeta:
            #left join with index file and journal data
            rAM_df = pd.merge(stackdf.copy(),myIndex,how='left',on=['TaskID','ProbeFileID','ProbeFileName','DonorFileID','DonorFileName'])
            rAM_df = pd.merge(rAM_df,journalData0,how='left',on=['ProbeFileID','DonorFileID','JournalName'])
            rAM_df.to_csv(path_or_buf=os.path.join(outRootQuery,'_'.join([prefix,'perimage-allMeta.csv'])),sep="|",index=False)

        r_df.to_csv(path_or_buf=os.path.join(outRootQuery,'_'.join([prefix,'mask_scores_perimage.csv'])),sep="|",index=False)

printq("Ending the mask scoring report.")
exit(0)

