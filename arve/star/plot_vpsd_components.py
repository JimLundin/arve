"""
plot vpsd components
"""

import matplotlib.pyplot as plt
import numpy as np


def plot_vpsd_components(star):

    # figure
    fig = plt.figure()

    # read VPSD and units
    freq, vpsd, freq_avg, vpsd_avg = [star.vpsd[var] for var in ["freq", "vpsd", "freq_avg", "vpsd_avg"]]
    time_unit, vrad_unit = [star.arve.data.vrad[var] for var in ["time_unit", "vrad_unit"]]

    # plot VPSD and average VPSD
    plt.loglog(freq, vpsd, ls="-", c="k", alpha=0.5)
    plt.loglog(freq_avg, vpsd_avg, ls="None", marker="o", mec="k", mfc="None")

    # empty array for sum of components
    vpsd_tot = np.zeros(len(freq))

    # loop components
    for comp in star.vpsd_components.keys():

        # component dictionary
        comp_dict = star.vpsd_components[comp]

        # type and coefficients
        type     = comp_dict["type"]
        coef_val = comp_dict["coef_val"]

        # component Constant
        if type == "Constant":

            # unpack coefficients
            c0 = coef_val[0]

            # compute component
            vpsd_comp = c0

            # plot component
            plt.axhline(vpsd_comp, ls="--", label=comp)

        # component Lorentz
        if type == "Lorentz":
            
            # unpack coefficients
            c0 = coef_val[0]
            c1 = coef_val[1]
            c2 = coef_val[2]

            # compute component
            vpsd_comp = c0*c1**2/(c1**2+(freq-c2)**2)

            # plot component
            plt.loglog(freq, vpsd_comp, ls="--", label=comp)

        # component Harvey
        if type == "Harvey":

            # unpack coefficients
            c0 = coef_val[0]
            c1 = coef_val[1]
            c2 = coef_val[2]

            # compute component
            vpsd_comp = c0/(1+(c1*freq)**c2)

            # plot component
            plt.loglog(freq, vpsd_comp, ls="--", label=comp)

        # add component to sum
        vpsd_tot += vpsd_comp

    # plot component sum
    plt.loglog(freq, vpsd_tot, ls="-", c="k", label="Total")

    # plot limits
    plt.xlim(freq[0], freq[-1])

    # plot labels
    plt.xlabel("$f$" + " " + f"[{time_unit}" + "$^{-1}$]")
    plt.ylabel("VPSD" + " " + f"[({vrad_unit})" + "$^{2}$" + " / " + f"{time_unit}" + "$^{-1}$]")

    # plot legend
    leg = plt.legend(loc="lower left")
    leg.set_zorder(101)

    # plot layout
    plt.tight_layout()

    # return figure
    return fig