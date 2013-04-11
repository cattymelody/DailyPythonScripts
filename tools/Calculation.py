'''
Created on 20 Nov 2012

@author: kreczko
'''
from uncertainties import ufloat
import numpy
from math import sqrt
from config.met_systematics import metsystematics_sources

def calculate_xsection(inputs, luminosity, efficiency=1.):
    '''
    BUG: this doesn't work unless the inputs are unfolded!
    inputs = list of value-error pairs
    luminosity = integrated luminosity of the measurement
    '''
    result = []
    add_result = result.append
    for value, error in inputs:
        xsection = value / luminosity / efficiency
        xsection_error = error / luminosity / efficiency
        add_result((xsection, xsection_error))        
    return result

def calculate_normalised_xsection(inputs, bin_widths, normalise_to_one=False):
    '''
    Calculates normalised average x-section for each bin: 1/N *1/bin_width sigma_i
    There are two ways to calculate this
    1) N = sum(sigma_i)
    2) N = sum(sigma_i/bin_width)
    The latter one will normalise the total distribution to 1
    inputs = list of value-error pairs
    bin_widths = bin widths of the inputs
    '''
    result = []
    add_result = result.append
    
    normalisation = 0
    for measurement, bin_width in zip(inputs, bin_widths):
        value = ufloat(measurement)
        
        if normalise_to_one:
            normalisation += value / bin_width
        else:
            normalisation += value
    for measurement, bin_width in zip(inputs, bin_widths):
        value = ufloat(measurement)
        xsection = value / normalisation / bin_width
        add_result((xsection.nominal_value, xsection.std_dev()))   
    return result

def decombine_result(combined_result, original_ratio):
    '''
    Use to extract the individual results from a combined result
    i.e. 
    combined_result = (sample_1_value + sample_2_value, combined_error)
    original_ratio = sample_1_value/sample_2_value
    This method will return the decombined values for the two samples:
    return (sample_1_value, sample_1_error), (sample_2_value, sample_2_error)
    with the proper errors
    '''
    combined_result = ufloat(combined_result)
    sample_1 = combined_result * original_ratio / (1 + original_ratio)
    sample_2 = combined_result - sample_1
    return (sample_1.nominal_value, sample_1.std_dev()), (sample_2.nominal_value, sample_2.std_dev())

def combine_results(result1, result2):
    '''
    Combines results of the form {measurement: (value, error)
    '''
    samples = result1.keys()
    if not samples == result2.keys():
        print 'Error - combine_results: results have a different set of keys!'
        return None
    combined_result = {}
    for sample in result1.keys():
        value1, error1 = result1[sample]
        value2, error2 = result2[sample]
        combined_result[sample] = (value1 + value2, error1 + error2)
    return combined_result

def combine_complex_results(result1, result2):
    '''
    Combines results of the form {measurement: [(value, error), ....]
    '''
    
    samples = result1.keys()
    if not samples == result2.keys():
        print 'Error - combine_results: results have a different set of keys!'
        return None
    
    combined_result = {}
    
    for sample in samples:
        results = []
        for entry1, entry2 in zip(result1[sample], result2[sample]):
            value1, error1 = entry1
            value2, error2 = entry2
            results.append((value1 + value2, error1 + error2))
        combined_result[sample] = results
    return combined_result

def calculate_lower_and_upper_PDFuncertainty(central_measurement, pdf_uncertainty_values={}):
    '''
    Calculates the appropriate lower and upper PDF uncertainty
    @param central_measurement: measurement from central PDF weight
    @param pdf_uncertainty_values: dictionary of measurements with different PDF weights; 
                                    format {PDFWeights_%d: measurement}
    '''
    negative = []
    positive = []
    
    # split PDF uncertainties into downwards (negative) and upwards (positive) components
    for index in range(1, 45):
        pdf_weight = 'PDFWeights_%d' % index
        pdf_uncertainty = pdf_uncertainty_values[pdf_weight]
        if index % 2 == 0:  # even == negative
            negative.append(pdf_uncertainty)
        else:
            positive.append(pdf_uncertainty)
            
    pdf_max = numpy.sqrt(sum(max(x - central_measurement, y - central_measurement, 0) ** 2 for x, y in zip(negative, positive)))
    pdf_min = numpy.sqrt(sum(max(central_measurement - x, central_measurement - y, 0) ** 2 for x, y in zip(negative, positive)))
    
    return pdf_min, pdf_max   

def calculate_lower_and_upper_systematics(central_measurement, lower_systematics, upper_systematics, 
                                          group = {}):
    pass
    
def getRelativeError(value, error):
    relativeError = 0
    if not value == 0:
        relativeError = error / value
    return relativeError

def symmetriseErrors(error1, error2):
    error1, error2 = abs(error1), abs(error2)
    if error1 > error2:
        return error1, error1
    return error2, error2

def calculateTotalUncertainty(results, bin_i, omitTTJetsSystematics=False):
    #pdf_min, pdf_max = calculate_lower_and_upper_PDFuncertainty(results['central'][bin_i])
    pdf_min, pdf_max = 0, 0
    centralResult = results['central'][bin_i]
    centralvalue, centralerror = centralResult[0], centralResult[1]
    totalMinus, totalPlus = pdf_min ** 2 , pdf_max ** 2
    totalMinus_err, totalPlus_err = 0, 0
    totalMETMinus, totalMETPlus = 0, 0
    totalMETMinus_err, totalMETPlus_err = 0, 0
    uncertainty = {}
    for source in results.keys():
        if source == 'central' or 'PDFWeights_' in source:
            continue
        if omitTTJetsSystematics and source in ['TTJet scale-', 'TTJet scale+', 'TTJet matching-', 'TTJet matching+']:
            continue
        result = results[source][bin_i]
        value, error = result[0], result[1]
        diff = abs(value) - abs(centralvalue)
        diff_error = sqrt((centralerror / centralvalue) ** 2 + (error / value) ** 2) * abs(diff)
        uncertainty[source] = [diff, diff_error]
        if diff > 0:
            totalPlus += diff ** 2
            totalPlus_err += diff_error ** 2
        else:
            totalMinus += diff ** 2
            totalMinus_err += diff_error ** 2
            
        if source in metsystematics_sources:
            if diff > 0:
                totalMETPlus += diff ** 2
                totalMETPlus_err += diff_error ** 2
            else:
                totalMETMinus += diff ** 2
                totalMETMinus_err += diff_error ** 2
        
    total = sqrt(totalPlus + totalMinus)
    total_error = sqrt(totalPlus_err + totalMinus_err)
    totalPlus, totalMinus, totalPlus_err, totalMinus_err = (sqrt(totalPlus), sqrt(totalMinus),
                                                             sqrt(totalPlus_err), sqrt(totalMinus_err))
    
    totalMETPlus, totalMETMinus, totalMETPlus_err, totalMETMinus_err = (sqrt(totalMETPlus), sqrt(totalMETMinus),
                                                             sqrt(totalMETPlus_err), sqrt(totalMETMinus_err))
    uncertainty['Total+'] = [totalPlus, totalPlus_err]
    uncertainty['Total-'] = [totalMinus, totalMinus_err]
    uncertainty['Total'] = [total, total_error]
    uncertainty['TotalMETUnc+'] = [totalMETPlus, totalMETPlus_err]
    uncertainty['TotalMETUnc-'] = [totalMETMinus, totalMETMinus_err]
    uncertainty['PDFWeights+'] = [pdf_max, 0]
    uncertainty['PDFWeights-'] = [pdf_min, 0]
    
    return uncertainty
