# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""
Tests for the core module.
"""

import astropy.units as u
import numpy as np
import pytest
from astropy.modeling.models import Gaussian1D, Gaussian2D
from astropy.utils.exceptions import AstropyUserWarning
from numpy.testing import assert_allclose, assert_equal

from photutils.aperture import CircularAnnulus, CircularAperture
from photutils.profiles import EdgeRadialProfile, RadialProfile
from photutils.utils._optional_deps import HAS_SCIPY


@pytest.fixture(name='profile_data')
def fixture_profile_data():
    xsize = 101
    ysize = 80
    xcen = (xsize - 1) / 2
    ycen = (ysize - 1) / 2
    xycen = (xcen, ycen)

    sig = 10.0
    model = Gaussian2D(21., xcen, ycen, sig, sig)
    y, x = np.mgrid[0:ysize, 0:xsize]
    data = model(x, y)

    error = 10.0 * np.sqrt(data)
    mask = np.zeros(data.shape, dtype=bool)
    mask[:int(ycen), :int(xcen)] = True

    return xycen, data, error, mask


def test_radial_profile(profile_data):
    xycen, data, _, _ = profile_data

    min_radius = 0.0
    max_radius = 35.0
    radius_step = 1.0
    rp1 = RadialProfile(data, xycen, min_radius, max_radius, radius_step,
                        error=None, mask=None)

    assert_equal(rp1.radius, np.arange(36))
    assert rp1.area.shape == (36,)
    assert rp1.profile.shape == (36,)
    assert rp1.profile_error.shape == (0,)
    assert rp1.area[0] > 0.0

    assert len(rp1.apertures) == 36
    assert isinstance(rp1.apertures[0], CircularAperture)
    assert isinstance(rp1.apertures[1], CircularAnnulus)

    min_radius = 0.7
    max_radius = 35.0
    radius_step = 1.0
    rp2 = RadialProfile(data, xycen, min_radius, max_radius, radius_step,
                        error=None, mask=None)
    assert isinstance(rp2.apertures[0], CircularAnnulus)


def test_edge_radial_profile(profile_data):
    xycen, data, _, _ = profile_data

    edge_radii = np.arange(37)
    rp1 = EdgeRadialProfile(data, xycen, edge_radii, error=None, mask=None)

    assert_equal(rp1.radius, np.arange(36) + 0.5)
    assert rp1.area.shape == (36,)
    assert rp1.profile.shape == (36,)
    assert rp1.profile_error.shape == (0,)
    assert_allclose(rp1.area[0], np.pi)

    assert len(rp1.apertures) == 36
    assert isinstance(rp1.apertures[0], CircularAperture)
    assert isinstance(rp1.apertures[1], CircularAnnulus)

    edge_radii = np.arange(1, 36)
    rp2 = EdgeRadialProfile(data, xycen, edge_radii, error=None, mask=None)
    assert isinstance(rp2.apertures[0], CircularAnnulus)


def test_edge_radial_profile_inputs(profile_data):
    xycen, data, _, _ = profile_data

    msg = 'minimum edge_radii must be >= 0'
    with pytest.raises(ValueError, match=msg):
        edge_radii = np.arange(-1, 10)
        EdgeRadialProfile(data, xycen, edge_radii, error=None, mask=None)

    msg = 'edge_radii must be a 1D array and have at least two values'
    with pytest.raises(ValueError, match=msg):
        edge_radii = [1]
        EdgeRadialProfile(data, xycen, edge_radii, error=None, mask=None)
    with pytest.raises(ValueError, match=msg):
        edge_radii = np.arange(6).reshape(2, 3)
        EdgeRadialProfile(data, xycen, edge_radii, error=None, mask=None)

    msg = 'edge_radii must be strictly increasing'
    with pytest.raises(ValueError, match=msg):
        edge_radii = np.arange(10)[::-1]
        EdgeRadialProfile(data, xycen, edge_radii, error=None, mask=None)


@pytest.mark.skipif(not HAS_SCIPY, reason='scipy is required')
def test_radial_profile_gaussian(profile_data):
    xycen, data, _, _ = profile_data

    min_radius = 0.0
    max_radius = 35.0
    radius_step = 1.0
    rp1 = RadialProfile(data, xycen, min_radius, max_radius, radius_step,
                        error=None, mask=None)

    assert isinstance(rp1.gaussian_fit, Gaussian1D)
    assert rp1.gaussian_profile.shape == (36,)
    assert rp1.gaussian_fwhm < 23.6

    max_radius = 200
    rp2 = RadialProfile(data, xycen, min_radius, max_radius, radius_step,
                        error=None, mask=None)
    assert isinstance(rp2.gaussian_fit, Gaussian1D)
    assert rp2.gaussian_profile.shape == (201,)
    assert rp2.gaussian_fwhm < 23.6


def test_radial_profile_unit(profile_data):
    xycen, data, error, _ = profile_data

    min_radius = 0.0
    max_radius = 35.0
    radius_step = 1.0
    unit = u.Jy
    rp1 = RadialProfile(data << unit, xycen, min_radius, max_radius,
                        radius_step, error=error << unit, mask=None)
    assert rp1.profile.unit == unit
    assert rp1.profile_error.unit == unit

    with pytest.raises(ValueError):
        RadialProfile(data << unit, xycen, min_radius, max_radius, radius_step,
                      error=error, mask=None)


def test_radial_profile_error(profile_data):
    xycen, data, error, _ = profile_data

    min_radius = 0.0
    max_radius = 35.0
    radius_step = 1.0
    rp1 = RadialProfile(data, xycen, min_radius, max_radius, radius_step,
                        error=error, mask=None)

    assert_equal(rp1.radius, np.arange(36))
    assert rp1.area.shape == (36,)
    assert rp1.profile.shape == (36,)
    assert rp1.profile_error.shape == (36,)

    assert len(rp1.apertures) == 36
    assert isinstance(rp1.apertures[0], CircularAperture)
    assert isinstance(rp1.apertures[1], CircularAnnulus)


def test_radial_profile_normalize_nan(profile_data):
    """
    If the profile has NaNs (e.g., aperture outside of the image),
    make sure the normalization ignores them.
    """
    xycen, data, _, _ = profile_data

    min_radius = 0.0
    max_radius = 100.0
    radius_step = 1.0

    rp1 = RadialProfile(data, xycen, min_radius, max_radius, radius_step)
    rp1.normalize()
    assert not np.isnan(rp1.profile[0])


def test_radial_profile_nonfinite(profile_data):
    xycen, data, error, _ = profile_data
    data2 = data.copy()
    data2[40, 40] = np.nan
    mask = ~np.isfinite(data2)

    min_radius = 0.0
    max_radius = 35.0
    radius_step = 1.0

    rp1 = RadialProfile(data, xycen, min_radius, max_radius, radius_step,
                        error=None, mask=mask)

    rp2 = RadialProfile(data2, xycen, min_radius, max_radius, radius_step,
                        error=error, mask=mask)
    assert_allclose(rp1.profile, rp2.profile)

    msg = 'Input data contains non-finite values'
    with pytest.warns(AstropyUserWarning, match=msg):
        rp3 = RadialProfile(data2, xycen, min_radius, max_radius, radius_step,
                            error=error, mask=None)
        assert_allclose(rp1.profile, rp3.profile)

    error2 = error.copy()
    error2[40, 40] = np.inf
    with pytest.warns(AstropyUserWarning, match=msg):
        rp4 = RadialProfile(data, xycen, min_radius, max_radius, radius_step,
                            error=error2, mask=None)
        assert_allclose(rp1.profile, rp4.profile)
