import os
from typing import Optional, TypeVar, Union

import numpy as np
import numpy.typing as npt
import pandas as pd
import pkg_resources
from scipy.optimize import curve_fit  # type: ignore
from tqdm import tqdm

from arve import ARVE

TData = TypeVar("TData", bound="Data")
RT = TypeVar("RT")


class Data:
    """ARVE Data base-class."""

    def __init__(self: TData, arve: ARVE) -> None:
        self.arve = arve
        self.spec: dict[str, Union[npt.NDArray[np.float64], str, None]] = {}
        self.vrad: dict[str, Union[npt.NDArray[np.float64], str, None]] = {}
        self.ccf: dict[str, Union[npt.NDArray[np.float64], str, None]] = {}

    def add_spec(
        self: TData,
        time: npt.NDArray[np.float64],
        wave: npt.NDArray[np.float64],
        flux_val: npt.NDArray[np.float64],
        flux_err: Optional[npt.NDArray[np.float64]] = None,
        time_unit: Optional[str] = None,
        wave_unit: Optional[str] = None,
        flux_unit: Optional[str] = None,
    ) -> None:
        """Add spectral data.

        :param time: time values
        :param wave: wavelength values
        :param flux_val: flux values
        :param flux_err: flux errors, defaults to None
        :param time_unit: time unit, defaults to None
        :param wave_unit: wavelength unit, defaults to None
        :param flux_unit: flux unit, defaults to None
        :return: None
        """
        # add dictionary with spectral data
        self.spec = {
            "time": time,
            "wave": wave,
            "flux_val": flux_val,
            "flux_err": flux_err,
            "time_unit": time_unit,
            "wave_unit": wave_unit,
            "flux_unit": flux_unit,
        }

    def add_vrad(
        self: TData,
        time: npt.NDArray[np.float64],
        vrad_val: npt.NDArray[np.float64],
        vrad_err: Optional[npt.NDArray[np.float64]] = None,
        time_unit: Optional[str] = None,
        vrad_unit: Optional[str] = None,
    ) -> None:
        """Add radial velocity data.

        :param time: time values
        :param vrad_val: radial velocity values
        :param vrad_err: radial velocity errors, defaults to None
        :param time_unit: time unit, defaults to None
        :param vrad_unit: radial velocity unit, defaults to None
        :return: None
        """
        # add dictionary with radial velocity data
        self.vrad = {
            "time": time,
            "vrad_val": vrad_val,
            "vrad_err": vrad_err,
            "time_unit": time_unit,
            "vrad_unit": vrad_unit,
        }

    def compute_vrad_ccf(
        self: TData,
        mask_path: Optional[str] = None,
        weight: Optional[str] = None,
        criteria: Optional[npt.NDArray[np.float64]] = None,
        vgrid: list[float] = [-20, 20, 0.25],
    ) -> None:
        """Compute radial velocities (RVs) from spectral data.

        :param mask_path: path to line mask (must be a CSV file where the wavelength column is "wave"), defaults to None
        :param weight: column name of weight, defaults to None
        :param criteria: criteria to apply (must be columns with prefix "crit_"), defaults to None
        :param vgrid: velocity grid, in the format [start,stop,step] and in units of km/s, on which to evaluate the CCF, defaults to [-20,20,0.25]
        :return: None
        """
        # read spectral data and units
        time, wave, flux_val, flux_err = (
            self.spec[key] for key in ["time", "wave", "flux_val", "flux_err"]
        )
        (time_unit,) = (self.spec[key] for key in ["time_unit"])

        if not (time and wave and flux_val and flux_err):
            msg = "Spectral data must be added first."
            raise ValueError(msg)
        if not isinstance(time, np.ndarray):
            msg = "Time must be a numpy array."
            raise TypeError(msg)
        if not isinstance(wave, np.ndarray):
            msg = "Wavelength must be a numpy array."
            raise TypeError(msg)
        if not isinstance(flux_val, np.ndarray):
            msg = "Flux values must be a numpy array."
            raise TypeError(msg)
        if not isinstance(flux_err, np.ndarray):
            msg = "Flux errors must be a numpy array."
            raise TypeError(msg)

        # mask from VALD
        if mask_path is None:
            # search masks
            path_aux_data = pkg_resources.resource_filename("arve", "aux_data/")
            masks = os.listdir(path_aux_data + "masks/")
            masks = [mask for mask in masks if mask.endswith(".csv")]
            sptype_masks = [mask.split("_")[0] for mask in masks]

            # convert spectral types to numbers
            sptype_num = self.arve.functions.sptype_to_num(
                sptype=self.arve.star.stellar_parameters["sptype"]
            )
            sptype_num_masks = np.array(
                [
                    self.arve.functions.sptype_to_num(sptype=sptype)
                    for sptype in sptype_masks
                ]
            )

            # read closest mask
            idx_mask = np.argmin(np.abs(sptype_num - sptype_num_masks))

            # mask path
            mask_path = path_aux_data + "masks/" + masks[idx_mask]

        # read mask
        mask = pd.read_csv(mask_path)

        # mask name
        mask_name = mask_path.split("/")[-1]

        # central wavelengths
        wc = np.array(mask["wave"])

        # weights
        w = np.ones_like(wc) if weight is None else np.array(mask[weight])

        # keep mask lines which satisfy criteria
        if criteria is not None:
            idx = np.ones_like(wc, dtype=bool)
            for i in range(len(criteria)):
                crit = np.array(mask["crit_" + criteria[i]])
                idx *= crit
            wc = wc[idx]
            w = w[idx]

        # RV shifts
        vrads = np.arange(vgrid[0], vgrid[1] + vgrid[2] / 2, vgrid[2])

        # keep mask lines within spectrum overlap
        idx = (self.arve.functions.doppler_shift(wave=wc, v=min(vrads)) > min(wave)) & (
            self.arve.functions.doppler_shift(wave=wc, v=max(vrads)) < max(wave)
        )
        wc = wc[idx]
        w = w[idx]

        # normalize weights
        w = w / np.sum(w)

        # nr. of ...
        Nspec = len(flux_val)  # spectra
        Nvrad = len(vrads)  # RV shifts

        # empty arrays for RV values and errors
        vrad_val = np.zeros(Nspec)
        vrad_err = np.zeros(Nspec)

        # empty arrays for FWHM values and errors
        fwhm_val = np.zeros(Nspec)

        # loop spectra
        print("Analyzed spectra:")
        for i in tqdm(range(Nspec)):
            # empty arrays for CCF values and errors
            ccf_val = np.zeros(Nvrad)
            ccf_err = np.zeros(Nvrad)

            # loop RV shifts
            for j in range(Nvrad):
                # shifted central wavelengths
                wc_shift = self.arve.functions.doppler_shift(wave=wc, v=vrads[j])

                # right and left indices
                i_r = np.searchsorted(wave, wc_shift, side="right")
                i_l = i_r - 1

                # right and left fractions
                f_r = (wc_shift - wave[i_l]) / (wave[i_r] - wave[i_l])
                f_l = 1 - f_r

                # CCF value and error
                ccf_val[j] = np.sum(
                    (flux_val[i][i_l] * f_l + flux_val[i][i_r] * f_r) * w
                )
                ccf_err[j] = np.sum(
                    (flux_err[i][i_l] ** 2 * f_l + flux_err[i][i_r] ** 2 * f_r) * w**2
                ) ** (1 / 2)

            # initial guess on Gaussian parameters
            C0 = np.max(ccf_val)
            a0 = C0 - np.min(ccf_val)
            b0 = vrads[np.argmin(ccf_val)]
            c0 = (b0 - vrads[np.where(ccf_val < (C0 - a0 / 2))[0][0]]) * 2
            p0 = (C0, a0, b0, c0)

            # CCF moments with fitted Gaussian
            ccf_mom, _ = curve_fit(
                self.arve.functions.inverted_gaussian,
                vrads,
                ccf_val,
                sigma=ccf_err,
                p0=p0,
            )

            # RV value and error
            vrad_val[i] = ccf_mom[2]
            vrad_err[i] = 1 / np.sqrt(
                np.sum(
                    1 / np.abs(ccf_err * np.gradient(vrads) / np.gradient(ccf_val)) ** 2
                )
            )

            # FWHM value and error
            fwhm_val[i] = ccf_mom[3]

        # save RV data
        self.vrad = {
            "time": time,
            "vrad_val": vrad_val,
            "vrad_err": vrad_err,
            "time_unit": time_unit,
            "vrad_unit": "km/s",
            "method": "CCF",
            "mask": mask_name,
        }
        self.ccf = {"time": time, "fwhm_val": fwhm_val}
