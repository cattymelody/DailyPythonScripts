'''
Created on 9 Dec 2012

@author: kreczko
'''
from optparse import OptionParser
import os
from ROOT import gSystem, gROOT, cout, TH1F, gStyle
gROOT.SetBatch(True)
from rootpy.io import File
from rootpy.plotting import Hist, Canvas
from array import array
from tools.Unfolding import Unfolding
from config import RooUnfold
from tools.hist_utilities import hist_to_value_error_tuplelist
from tools.file_utilities import write_data_to_JSON
# from unfolding import saveUnfolding
from tools.hist_utilities import value_error_tuplelist_to_hist

def check_one_data_multiple_unfolding(input_file, method, channel):
    global use_N_toy, nbins, output_folder
    gStyle.SetOptFit(0111)
    # same data different unfolding input
    get_folder = input_file.Get
    h_data = get_folder(channel + '/toy_1').measured
    pulls = []
    add_pull = pulls.append
    for nth_toy in range(2, use_N_toy + 1):
        folder = get_folder(channel + '/toy_%d' % nth_toy)
        h_truth, h_measured, h_response = get_histograms(folder)
        unfolding_obj = Unfolding(h_truth, h_measured, h_response, method=method)
        unfolding_obj.unfold(h_data)
        pull = unfolding_obj.pull()
        add_pull(pull)
    analyse_pulls(pulls, test='one_data_multiple_unfolding', method=method, channel=channel)
 
def check_multiple_data_one_unfolding(input_file, method, channel):
    global nbins, use_N_toy, output_folder
    gStyle.SetOptFit(0111)
    # same unfolding input, different data
    get_folder = input_file.Get
    h_truth, h_measured, h_response = get_histograms(get_folder(channel + '/toy_1'))
    unfolding_obj = Unfolding(h_truth, h_measured, h_response, method=method)
    pulls = []
    # cache functions
    unfold, get_pull, add_pull, reset = unfolding_obj.unfold, unfolding_obj.pull, pulls.append, unfolding_obj.Reset

    for nth_toy in range(2, use_N_toy + 1):
        folder = get_folder(channel + '/toy_%d' % nth_toy)
        h_data = folder.measured
        unfold(h_data)
        pull = get_pull()
        add_pull(pull)
        reset()
    analyse_pulls(pulls, test='multiple_data_one_unfolding', method=method, channel=channel)
    
def check_multiple_data_multiple_unfolding(input_file, method, channel):
    global nbins, use_N_toy, skip_N_toy, output_folder
    gStyle.SetOptFit(0111)
    # same unfolding input, different data
    get_folder = input_file.Get
    pulls = []
    add_pull = pulls.append
    histograms = []
    add_histograms = histograms.append
    
    for nth_toy_mc in range(skip_N_toy + 1, skip_N_toy + use_N_toy + 1):
        folder_mc = get_folder(channel + '/toy_%d' % nth_toy_mc)
        add_histograms(get_histograms(folder_mc))
           
    for nth_toy_mc in range(skip_N_toy + 1, skip_N_toy + use_N_toy + 1):
        print 'Doing MC no', nth_toy_mc
        h_truth, h_measured, h_response = histograms[nth_toy_mc - 1 - skip_N_toy]
        unfolding_obj = Unfolding(h_truth, h_measured, h_response, method=method)
        unfold, get_pull, reset = unfolding_obj.unfold, unfolding_obj.pull, unfolding_obj.Reset
        
        for nth_toy_data in range(skip_N_toy + 1, skip_N_toy + use_N_toy + 1):
            if nth_toy_data == nth_toy_mc:
                continue
            h_data = histograms[nth_toy_data - 1 - skip_N_toy][1]
            unfold(h_data)
            pull = get_pull()
            add_pull(pull)
            reset()
    save_pulls(pulls, test='multiple_data_multiple_unfolding', method=method, channel=channel)

def save_pulls(pulls, test, method, channel):    
    global use_N_toy, skip_N_toy
    file_template = 'Pulls_%s_%s_%s_toy_MC_%d_to_%d.txt'
    output_file = output_folder + file_template % (test, method, channel, skip_N_toy + 1, use_N_toy + skip_N_toy)
    write_data_to_JSON(pulls, output_file)
    
def analyse_pulls(pulls, test, method, channel):   
    allpulls = []

    for pull in pulls:
        allpulls.extend(pull)
    min_x, max_x = min(allpulls), max(allpulls)
    n_x_bins = int(max_x + abs(min_x)) * 10  # bin width = 0.1
    h_allpulls = Hist(n_x_bins, min_x, max_x)
    filling = h_allpulls.Fill
    for entry in allpulls:
        filling(entry)
    fit = h_allpulls.Fit('gaus', 'WWSQ')
    output_file = output_folder + 'Pull_%s_allBins_withFit_%s_%s.png' % (test, method, channel)
    plot_hist(h_allpulls, output_file, fit)
    write_data_to_JSON(hist_to_value_error_tuplelist(h_allpulls), output_file.replace('png', 'txt'))
    # individual bins
    mean_and_sigma = []
    fit_means = []
    fit_sigmas = []
    add_mean = fit_means.append
    add_sigma = fit_sigmas.append
    add_mean_and_sigma = mean_and_sigma.append
    for bin_i in range(nbins):
        h_pull = Hist(n_x_bins, min_x, max_x)
        for pull in pulls:
            h_pull.Fill(pull[bin_i])
        fit = h_pull.Fit('gaus', 'WWSQ')
        # get mean and sigma of fit, type(fit) = TFitResult
        fit_mean = fit.Parameter(1)
        fit_mean_error = fit.ParError(1)
        fit_sigma = fit.Parameter(2)
        fit_sigma_error = fit.ParError(2)
        add_mean_and_sigma((fit_mean, fit_sigma))
        add_mean((fit_mean, fit_mean_error))
        add_sigma((fit_sigma, fit_sigma_error))
        output_file = output_folder + 'Pull_%s_bin%d_withFit_%s_%s.png' % (test, bin_i, method, channel)
        plot_hist(h_pull, output_file, fit)
        write_data_to_JSON(hist_to_value_error_tuplelist(h_pull), output_file.replace('png', 'txt'))

    h_mean_and_sigma = value_error_tuplelist_to_hist(mean_and_sigma, list(bins))
    output_file = output_folder + 'Pull_%s_means_and_sigma_allbins_%s_%s.png' % (test, method, channel)
    plot_hist(h_mean_and_sigma, output_file)
    write_data_to_JSON(mean_and_sigma, output_file.replace('png', 'txt'))
    
    h_fit_means = value_error_tuplelist_to_hist(fit_means, list(bins))
    output_file = output_folder + 'Pull_%s_means_allbins_%s_%s.png' % (test, method, channel)
    plot_hist(h_fit_means, output_file)
    write_data_to_JSON(fit_means, output_file.replace('png', 'txt'))
    
    h_fit_sigmas = value_error_tuplelist_to_hist(fit_sigmas, list(bins))
    output_file = output_folder + 'Pull_%s_sigmas_allbins_%s_%s.png' % (test, method, channel)
    plot_hist(h_fit_sigmas, output_file)
    write_data_to_JSON(fit_sigmas, output_file.replace('png', 'txt'))
    
def get_histograms(folder):
    h_truth = folder.truth.Clone()
    h_measured = folder.measured.Clone()
    h_response = folder.response_withoutFakes_AsymBins.Clone()
    
    return h_truth, h_measured, h_response

def plot_hist(hist, output_file, fit=None):
    canvas = Canvas(width=1600, height=1000)
    canvas.SetLeftMargin(0.15)
    canvas.SetBottomMargin(0.15)
    canvas.SetTopMargin(0.10)
    canvas.SetRightMargin(0.05)
    hist.Draw()
    if fit:
        fit.Draw('same')
    canvas.SaveAs(output_file)
    canvas.SaveAs(output_file.replace('.png', '.pdf'))
    
if __name__ == "__main__":
    from ROOT import gROOT
    gROOT.SetBatch(True)
    gROOT.ProcessLine("gErrorIgnoreLevel = 3001;");
    bins = array('d', [0, 25, 45, 70, 100, 1000])
    nbins = len(bins) - 1
    parser = OptionParser()
    parser.add_option("-n", "--n_input_mc", type='int',
                      dest="n_input_mc", default=100,
                      help="number of toy MC used for the tests")
    parser.add_option("-s", "--skip_mc", type='int',
                      dest="skip_mc", default=0,
                      help="skip first n toy MC used for the tests")
    parser.add_option("-e", "--error_toy_MC", type='int',
                      dest="error_toy_MC", default=1000,
                      help="number of toy MC used for the error calculation in SVD unfolding")
    parser.add_option("-k", "--k_value", type='int',
                      dest="k_value", default=6,
                      help="k-value for SVD unfolding")
    parser.add_option("-m", "--method", type='string',
                      dest="method", default='RooUnfoldSvd',
                      help="unfolding method")
    parser.add_option("-f", "--file", type='string',
                      dest="file", default='../data/unfolding_toy_mc.root',
                      help="file with toy MC")
    parser.add_option("-c", "--channel", type='string',
                      dest="channel", default='both',
                      help="channel to be analysed: electron|muon|both")
    (options, args) = parser.parse_args()
    
    # set the number of toy MC for error calculation
    RooUnfold.SVD_n_toy = options.error_toy_MC
    RooUnfold.SVD_k_value = options.k_value
    use_N_toy = options.n_input_mc
    skip_N_toy = options.skip_mc
    method = options.method
    
    output_folder = 'plots/%d_input_toy_mc/k_value_%d/%d_error_toy_MC/' % (use_N_toy, RooUnfold.SVD_k_value, RooUnfold.SVD_n_toy)
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        
    input_file = input_file = File(options.file, 'read')
    
#    check_one_data_multiple_unfolding(input_file, method, 'electron')
#    check_multiple_data_one_unfolding(input_file, method, 'electron')
#    check_one_data_multiple_unfolding(input_file, method, 'muon')
#    check_multiple_data_one_unfolding(input_file, method, 'muon')
    
    from time import clock, time
    start1, start2 = clock(), time()
    if options.channel == 'electron':
        check_multiple_data_multiple_unfolding(input_file, method, 'electron')
    elif options.channel == 'muon':
        check_multiple_data_multiple_unfolding(input_file, method, 'muon')
    else:
        check_multiple_data_multiple_unfolding(input_file, method, 'electron')
        check_multiple_data_multiple_unfolding(input_file, method, 'muon')
    end1, end2 = clock(), time()
    
    print 'Runtime', end1 - start1
    print 'Runtime', end2 - start2
    