"""Class to work with TESS data PRF"""

from typing import Tuple, List
import numpy as np
from .utils import LKPRFWarning
from .data import get_tess_prf_file
import warnings
from scipy.interpolate import RectBivariateSpline

from .prfmodel import PRF


class TESSPRF(PRF):
    """A TESSPRF class. The TESS PRF measurements are supersampled by a factor of 9."""

    def __init__(self, camera: int, ccd: int):
        super().__init__()
        self.camera = camera
        self.ccd = ccd
        self.mission = "TESS"
        self._prepare_prf()

    def __repr__(self):
        return f"TESSPRF Object [Camera {self.camera}, CCD {self.ccd}]"

    def _get_prf_data(self):
        return get_tess_prf_file(camera=self.camera, ccd=self.ccd)

    def check_coordinates(self, targets: List[Tuple], shape: Tuple):
        row, column = self._unpack_targets(targets)
        """Check that coordinates are within bounds, raise warnings otherwise."""
        if (np.atleast_1d(column) < 45).any():
            warnings.warn(
                "`targets` contains collateral pixels: Column(s) < 45",
                LKPRFWarning,
            )

        if ((np.atleast_1d(column) + shape[1]) >= 2093).any():
            warnings.warn(
                "`targets` contains collateral pixels: Column(s) >= 2093 ",
                LKPRFWarning,
            )

        if ((np.atleast_1d(row) + shape[0]) > 2048).any():
            warnings.warn(
                "`targets` contains collateral pixels: Row(s) > 2048)",
                LKPRFWarning,
            )

        return
    

    def _prepare_supersamp_prf(self, targets: List[Tuple], shape: Tuple):
        row, column = self._unpack_targets(targets)
        # Set the row and column for the model. 

        # Create one supersampled PRF for each image, used for all targets in the image
        row, column = np.atleast_1d(row), np.atleast_1d(column)
        row = np.min([np.max([row, row**0 * 0], axis=0), row**0 * 2048], axis=0).mean()
        column = np.min(
            [np.max([column, column**0 * 45], axis=0), column**0 * 2092], axis=0
        ).mean()

        # interpolate the calibrated PRF shape to the target position
        min_prf_weight = 1e-6
        rowdim, coldim = shape[0], shape[1]
        ref_column = column + 0.5 * coldim
        ref_row = row + 0.5 * rowdim
        supersamp_prf = np.zeros(self.PRFdata.shape[1:], dtype="float32")

        # Find the 4 measured PRF models nearest the target location
        prf_weights = [
            np.sqrt(
                (ref_column - self.crval1p[i]) ** 2 + (ref_row - self.crval2p[i]) ** 2) 
                for i in range(self.PRFdata.shape[0])
                ]
        idx = np.argpartition(prf_weights, 4)[:4]

        for i in idx:
            if prf_weights[i] < min_prf_weight:
                prf_weights[i] = min_prf_weight
            supersamp_prf += self.PRFdata[i] / prf_weights[i]


        supersamp_prf /= np.nansum(supersamp_prf) * self.cdelt1p[0] * self.cdelt2p[0]
        
        # Set up the interpolation function
        self.interpolate = RectBivariateSpline(self.PRFrow, self.PRFcol, supersamp_prf)
        return
