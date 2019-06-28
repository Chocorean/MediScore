# -*- coding: utf-8 -*-
"""
Date: 03/07/2017
Authors: Yooyoung Lee and Timothee Kheyrkhah

Description: this script loads DM files and renders plots.
In addition, the user can customize the plots through the command line interface or via 
json files.

"""

import os 
import sys
import json
import argparse
from ast import literal_eval

lib_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../lib")
sys.path.append(lib_path)

import Render as p
import detMetrics as dm

def create_parser():
    """Command line interface creation with arguments definitions.

    Returns:
        argparse.ArgumentParser

    """
    parser = argparse.ArgumentParser(description='NIST detection scorer.', formatter_class=argparse.RawTextHelpFormatter)

    input_help = ("Supports the following inputs:\n- .txt file containing one file path per line\n- .dm file\n",
                  "- a list of pair [{'path':'path/to/dm_file','label':str,'show_label':bool}, **{any matplotlib.lines.Line2D properties}].\n",
                  "Example:\n  [[{'path':'path/to/file_1.dm','label':'sys_1','show_label':True}, {'color':'red','linestyle':'solid'}],\n",
                  "             [{'path':'path/to/file_2.dm','label':'sys_2','show_label':False}, {}]",
                  "Note: Use an empty dict for default behavior.")

    parser.add_argument('-i', '--input', required=True,metavar = "str",
                        help=''.join(input_help))

    parser.add_argument("--outputFolder", default='.',
                        help="Path to the output folder. (default: %(default)s)",metavar='')

    parser.add_argument("--outputFileNameSuffix", default='plot',
                        help="Output file name suffix. (default: '%(default)s')",metavar='')

    # Plot Options
    parser.add_argument("--plotOptionJsonFile", help="Path to a json file containing plot options", metavar='path')

    parser.add_argument("--curveOptionJsonFile", help="Path to a json file containing a list of matplotlib.lines.Line2D dictionnaries properties (One per curve)", metavar='path')

    parser.add_argument("--plotType", default="ROC", choices=["ROC", "DET"],
                        help="Plot type (default: %(default)s)", metavar='')

    parser.add_argument("--plotTitle",default="Performance",
                        help="Define the plot title (default: '%(default)s')", metavar='')

    parser.add_argument("--plotSubtitle",default='',
                        help="Define the plot subtitle (default: '%(default)s')", metavar='')

    parser.add_argument("--display", action="store_true",
                        help="Display plots")

    parser.add_argument("--multiFigs", action="store_true",
                        help="Generate plots (with only one curve) per a partition")

    parser.add_argument('--noNum', action="store_true",
                        help="Do not print the number of target trials and non-target trials on the legend of the plot")

    parser.add_argument('-v', "--verbose", action="store_true",
                        help="Increase output verbosity")

    parser.add_argument('--dumpPlotParams', action="store_true",
                        help="Dump the parameters used for the plot and the curves as Jsons in the output directory")

    return parser

def validate_plot_options(plot_options):
    """Validation of the custom dictionnary of general options for matplotlib's plot.
    This function raises a custom exception in case of invalid or missing plot options
    and catches in order to quit with a specific error message.

    Args:
        plot_options (dict): The dictionnary containing the general plot options

    Note: The dictionnary should contain at most the following keys
            'title', 'subtitle', 'plot_type', 
            'title_fontsize', 'subtitle_fontsize', 
            'xticks_size', 'yticks_size', 
            'xlabel', 'xlabel_fontsize', 
            'ylabel', 'ylabel_fontsize'
        See the matplotlib documentation for a description of those parameters 
        (except for the plot_type (choose from 'ROC', 'DET'))
    """

    class PlotOptionValidationError(Exception):
        """Custom Exception raised for errors in the global plot option json file
        Attributes:
            msg (str): explanation message of the error
        """
        def __init__(self,msg):
            self.msg = msg

    v_print("Validating global plot options...")
    try:
        #1 check plot type
        plot_type = plot_options["plot_type"]
        if plot_type not in ["ROC", "DET"]:
            raise PlotOptionValidationError("invalid plot type '{}' (choose from 'ROC', 'DET')".format(plot_type))

    except PlotOptionValidationError as e:
        print("PlotOptionValidationError: {}".format(e.msg))
        sys.exit(1)

    except KeyError as e:
        print("PlotOptionValidationError: no '{}' provided".format(e.args[0]))
        sys.exit(1)

def evaluate_input(args):
    """This function parse and evaluate the argument from command line interface,
    it returns the list of DM files loaded with also potential custom plot and curves options provided.
    The functions parse the input argument and the potential custom options arguments (plot and curves).

    It first infers the type of input provided. The following 3 input type are supported:
        - type 1: A .txt file containing a pass of .dm file per lines
        - type 2: A single .dm path
        - type 3: A custom list of pairs of dictionnaries (see the input help from the command line parser)

    Then it loads custom (or defaults if not provided) plot and curves options per DM file.

    Args:
        args (argparse.Namespace): the result of the call of parse_args() on the ArgumentParser object

    Returns:
        Result (tuple): A tuple containing
            - DM_list (list): list of DM objects
            - opts_list (list): list of dictionnaries for the curves options
            - plot_opts (dict): dictionnary of plot options  
    """

    DM_list = list()
    opts_list = list()
    # Case 1: text file containing one path per line
    if args.input.endswith('.txt'):
        input_type = 1
        with open(args.input) as f:
            fp_list = f.read().splitlines()

        for dm_file_path in fp_list:
            label = None
            # We handle a potential label provided
            if ':' in dm_file_path:
                dm_file_path, label = dm_file_path.rsplit(':', 1)

            dm_obj = dm.load_dm_file(dm_file_path)
            dm_obj.path = dm_file_path
            dm_obj.label = label
            dm_obj.show_label = True
            DM_list.append(dm_obj)

    # Case 2: One dm pickled file
    elif args.input.endswith('.dm'):
        input_type = 2
        dm_obj = dm.load_dm_file(args.input)
        dm_obj.path = args.input
        dm_obj.label = None
        dm_obj.show_label = None
        DM_list = [dm_obj]

    # Case 3: String containing a list of input with their metadata
    elif args.input.startswith('[[') and args.input.endswith(']]'):
        input_type = 3
        
        try:
            input_list = literal_eval(args.input)
            for dm_data, dm_opts in input_list:
                dm_file_path = dm_data['path']
                dm_obj = dm.load_dm_file(dm_file_path)
                dm_obj.path = dm_file_path
                dm_obj.label = dm_data['label']
                dm_obj.show_label = dm_data['show_label']
                DM_list.append(dm_obj)
                opts_list.append(dm_opts)

        except ValueError as e:
            if not all([len(x) == 2 for x in input_list]):
                print("ValueError: Invalid input format. All sub-lists must be a pair of two dictionnaries.\n-> {}".format(str(e)))
            else:
                print("ValueError: {}".format(str(e)))
            sys.exit(1)

        except SyntaxError as e:
            print("SyntaxError: The input provided is invalid.\n-> {}".format(str(e)))
            sys.exit(1)

    #*-* Options Processing *-*

    # General plot options
    if not args.plotOptionJsonFile:
        v_print("Generating the default plot options...")
        plot_opts = p.gen_default_plot_options(plot_title = args.plotTitle, plot_subtitle = args.plotSubtitle, plot_type = args.plotType)
        
    else:
        try:
            v_print("Loading of the plot options from the json config file...")
            plot_opts = p.load_plot_options(args.plotOptionJsonFile)
            validate_plot_options(plot_opts)
        except FileNotFoundError as e:
            print("FileNotFoundError: No such file or directory: '{}'".format(args.plotOptionJsonFile))
            sys.exit(1)
    
    # Curve options
    if not args.curveOptionJsonFile:
        v_print("Generating the default curves options...")
        opts_list = p.gen_default_curve_options(len(DM_list))
        
    elif input_type != 3:
        try:
            v_print("Loading of the curves options from the json config file...")
            opts_list = p.load_plot_options(args.curveOptionJsonFile)
            if len(opts_list) < len(DM_list):
                print("ERROR: the number of the curve options is different with the number of the DM objects: ({} < {})".format(len(opts_list), len(DM_list)))
                sys.exit(1)
        except FileNotFoundError as e:
            print("FileNotFoundError: No such file or directory: '{}'".format(args.curveOptionJsonFile))
            sys.exit(1)

    return DM_list, opts_list, plot_opts

def outputFigure(figure, outputFolder, outputFileNameSuffix, plotType):
    """Generate the plot file(s) as pdf at the provided destination
    The filename created as the following format:
        * for a single figure: {file_suffix}_{plot_type}_all.pdf
        * for a list of figures: {file_suffix}_{plot_type}_{figure_number}.pdf

    Args:
        figure (matplotlib.pyplot.figure or a list of matplotlib.pyplot.figure): the figure to plot
        outputFolder (str): path to the destination folder 
        outputFileNameSuffix (str): string suffix that will be inserted at the beginning of the filename
        plotType (str): the type of plot (ROC or DET)

    """
    if outputFolder != '.' and not os.path.exists(outputFolder):
        os.makedirs(outputFolder)

    # Figure Output
    fig_filename_tmplt = "{file_suffix}_{plot_type}_{plot_id}.pdf".format(file_suffix=outputFileNameSuffix,
                                                                          plot_type=plotType,
                                                                          plot_id="{plot_id}")
    
    fig_path = os.path.normpath(os.path.join(outputFolder, fig_filename_tmplt))

    # This will save multiple figures if multi_fig == True
    if isinstance(figure,list):
        for i,fig in enumerate(figure):
            fig.savefig(fig_path.format(plot_id=str(i)), bbox_inches='tight')
    else:
        figure.savefig(fig_path.format(plot_id='all'), bbox_inches='tight')

def dumpPlotOptions(outputFolder, opts_list, plot_opts):
    """This function dumps the options used for the plot and curves as json files.
    at the provided outputFolder. The two file have following names:
        - Global options plot: "plot_options.json"
        - curves options:  "curve_options.json"

    Args: 
        outputFolder (str): path to the output folder
        opts_list (list): list of dictionnaries for the curves options
        plot_opts (dict): dictionnary of plot options  

    """
    output_json_path = os.path.normpath(os.path.join(outputFolder, "plotJsonFiles"))
    if not os.path.exists(output_json_path):
        os.makedirs(output_json_path)

    for json_data, json_filename in zip([opts_list, plot_opts], ["curve_options.json", "plot_options.json"]):
        with open(os.path.join(output_json_path, json_filename), 'w') as f:
            f.write(json.dumps(json_data, indent=2, separators=(',', ':')))


if __name__ == '__main__':

    print("Starting DMRender...\n")
    parser = create_parser()
    args = parser.parse_args()

    # Verbosity option
    if args.verbose:
        def v_print(*args):
            for arg in args:
               print (arg),
            print
    else:
        v_print = lambda *a: None  # do-nothing function

    # Backend option
    if not args.display: # If no plot displayed, we set the matplotlib backend
        import matplotlib
        matplotlib.use('Agg')

    v_print("Evaluating parameters...")
    DM_list, opts_list, plot_opts = evaluate_input(args)

    #*-* Label processing *-*
    #TODO: Move this code to a function once it as been cleaned 
    
    optout = False
    for curve_opts, dm_obj in zip(opts_list, DM_list):
        measures_list = []
        if plot_opts['plot_type'] == 'ROC':
            met_str = "AUC: {}".format(round(dm_obj.auc,2))
        elif plot_opts['plot_type'] == 'DET':
            met_str = "EER: {}".format(round(dm_obj.eer,2))

        trr_str = ""
        optout = False # ?
        if dm_obj.sys_res == 'tr':
            optout = True
            trr_str = "TRR: {}".format(dm_obj.trr)
            
            if plot_opts['plot_type'] == 'ROC':
                #plot_opts['title'] = "trROC"
                met_str = "trAUC: {}".format(round(dm_obj.auc,2))
            elif plot_opts['plot_type'] == 'DET':
                #plot_opts['title'] = "trDET"
                met_str = "trEER: {}".format(round(dm_obj.eer,2))
        
        measures_list.append(met_str)
        if trr_str: measures_list.append(trr_str)

        curve_opts["label"] = None
        if dm_obj.show_label:
            curve_label = dm_obj.label if dm_obj.label else dm_obj.path
            
            if args.noNum:
                curve_opts["label"] = "{label} ({measures})".format(label=curve_label, measures=', '.join(measures_list))
            else:
                curve_opts["label"] = "{label} ({measures}, T#: {nb_target}, NT#: {nb_nontarget})".format(label=curve_label, 
                                                                                                          measures=', '.join(measures_list),
                                                                                                          nb_target=dm_obj.t_num, 
                                                                                                          nb_nontarget=dm_obj.nt_num)

    #*-* Plotting *-*

    # Creation of the object setRender (~DetMetricSet)
    configRender = p.setRender(DM_list, opts_list, plot_opts)
    # Creation of the Renderer
    myRender = p.Render(configRender)
    # Plotting
    myfigure = myRender.plot_curve(args.display, multi_fig=args.multiFigs, isOptOut = optout, isNoNumber = args.noNum)

    # Output process
    outputFigure(myfigure, args.outputFolder, args.outputFileNameSuffix, args.plotType)
    
    # If we need to dump the used plotting options
    if args.dumpPlotParams:
        dumpPlotOptions(args.outputFolder, opts_list, plot_opts)





