"""
compute vpsd
"""

import numpy as np


def compute_vpsd(star):

    # RV time series
    time, vrad_val, vrad_err, time_unit, vrad_unit = [star.arve.data.vrad[var] for var in ["time", "vrad_val", "vrad_err", "time_unit", "vrad_unit"]]

    # compute velocity power spectrum
    freq, vps, phi, win_freq, win_vps, win_area = star.arve.functions.gls_periodogram(time=time, y=vrad_val, sig=vrad_err, normalize=False, win_func=True)

    # compute log-average VPS
    freq_bin = 10 ** (np.linspace(np.log10(freq[0]), np.log10(freq[-1]), 51))
    freq_avg = (freq_bin[1:] + freq_bin[:-1]) / 2
    vps_avg  = np.empty(freq_avg.size)
    for i in range(freq_avg.size):
        vps_bin = vps[(freq > freq_bin[i]) & (freq < freq_bin[i + 1])]
        if len(vps_bin) == 0:
            vps_avg[i] = np.nan
        else:
            vps_avg[i] = np.mean(vps_bin)

    # delete NaN values
    i_delete = np.isnan(vps_avg)
    freq_avg = np.delete(freq_avg, np.where(i_delete))
    vps_avg  = np.delete(vps_avg , np.where(i_delete))

    # compute VPSD
    vpsd     = vps     / win_area
    vpsd_avg = vps_avg / win_area

    # save in ARVE structure
    star.vpsd = {"freq": freq, "vps": vps, "vpsd": vpsd, "phase": phi, "freq_avg": freq_avg, "vps_avg": vps_avg, "vpsd_avg": vpsd_avg}