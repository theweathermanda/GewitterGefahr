"""Unit tests for sounding_stats.py"""

import copy
import unittest
import numpy
import pandas
from gewittergefahr.gg_utils import sounding_stats
from gewittergefahr.gg_utils import moisture_conversions
from gewittergefahr.gg_utils import temperature_conversions
from gewittergefahr.gg_utils import nwp_model_utils

TOLERANCE = 1e-6
MB_TO_PASCALS = 100

# The following constants are used to test _remove_bad_pressure_levels and
# _fill_missing_humidity.
THESE_HEIGHTS_M_ASL = numpy.array(
    [100, 500, 1000, 1500, 2000, 2500, numpy.nan, 3500, 4000, 4500, 5000, 5500,
     6000, 6500, 7000, 7500, 8000, 8500, 10000])
THESE_PRESSURES_MB = numpy.array(
    [1000, 950, 900, 850, numpy.nan, 750, 700, 650, 600, 550, 500, 475, 450,
     425, 400, 375, 350, 325, 250])
THESE_TEMPERATURES_KELVINS = numpy.array(
    [300, 297.5, 295, 292.5, 290, 287.5, 285, 282.5, 280, 275, numpy.nan, 265,
     260, 255, 250, 245, 240, 235, 230])
THESE_SPECIFIC_HUMIDITIES = numpy.array(
    [0.0198, 0.019, 0.018, 0.017, 0.016, 0.015, 0.014, 0.013, 0.012,
     0.011, 0.01, 0.009, 0.008, 0.007, 0.006, 0.005, 0.004, 0.003, 0])
THESE_SPFH_SOME_MISSING = numpy.array(
    [numpy.nan, numpy.nan, 0.018, 0.017, numpy.nan, 0.015, 0.014, 0.013, 0.012,
     0.011, numpy.nan, 0.009, 0.008, numpy.nan, numpy.nan, 0.005, 0.004, 0.003,
     numpy.nan])

THESE_BAD_ROWS = numpy.concatenate((
    numpy.where(numpy.isnan(THESE_HEIGHTS_M_ASL))[0],
    numpy.where(numpy.isnan(THESE_PRESSURES_MB))[0],
    numpy.where(numpy.isnan(THESE_TEMPERATURES_KELVINS))[0]
))

THESE_DEWPOINTS_KELVINS = moisture_conversions.specific_humidity_to_dewpoint(
    THESE_SPECIFIC_HUMIDITIES, THESE_PRESSURES_MB * MB_TO_PASCALS)
THESE_RH_PERCENT = 100 * moisture_conversions.dewpoint_to_relative_humidity(
    THESE_DEWPOINTS_KELVINS, THESE_TEMPERATURES_KELVINS,
    THESE_PRESSURES_MB * MB_TO_PASCALS)

THESE_SPFH_MISSING_ROWS = numpy.where(numpy.isnan(THESE_SPFH_SOME_MISSING))[0]
THESE_RH_SOME_MISSING_PERCENT = copy.deepcopy(THESE_RH_PERCENT)
THESE_RH_SOME_MISSING_PERCENT[THESE_SPFH_MISSING_ROWS] = numpy.nan

THIS_DICT = {
    nwp_model_utils.HEIGHT_COLUMN_FOR_SOUNDING_TABLES: THESE_HEIGHTS_M_ASL,
    sounding_stats.PRESSURE_COLUMN_IN_SHARPPY_SOUNDING: THESE_PRESSURES_MB,
    nwp_model_utils.TEMPERATURE_COLUMN_FOR_SOUNDING_TABLES:
        THESE_TEMPERATURES_KELVINS
}
THIS_GENERIC_SOUNDING_TABLE = pandas.DataFrame.from_dict(THIS_DICT)

SOUNDING_TABLE_SPFH_MISSING_BAD_ROWS = THIS_GENERIC_SOUNDING_TABLE.assign(
    **{nwp_model_utils.SPFH_COLUMN_FOR_SOUNDING_TABLES:
           THESE_SPFH_SOME_MISSING})
SOUNDING_TABLE_SPFH_MISSING = SOUNDING_TABLE_SPFH_MISSING_BAD_ROWS.drop(
    SOUNDING_TABLE_SPFH_MISSING_BAD_ROWS.index[THESE_BAD_ROWS], axis=0,
    inplace=False)

SOUNDING_TABLE_SPFH_FILLED_BAD_ROWS = THIS_GENERIC_SOUNDING_TABLE.assign(
    **{nwp_model_utils.SPFH_COLUMN_FOR_SOUNDING_TABLES:
           THESE_SPECIFIC_HUMIDITIES})
SOUNDING_TABLE_SPFH_FILLED = SOUNDING_TABLE_SPFH_FILLED_BAD_ROWS.drop(
    SOUNDING_TABLE_SPFH_FILLED_BAD_ROWS.index[THESE_BAD_ROWS], axis=0,
    inplace=False)

SOUNDING_TABLE_RH_MISSING_BAD_ROWS = THIS_GENERIC_SOUNDING_TABLE.assign(
    **{nwp_model_utils.RH_COLUMN_FOR_SOUNDING_TABLES:
           THESE_RH_SOME_MISSING_PERCENT})
SOUNDING_TABLE_RH_MISSING = SOUNDING_TABLE_RH_MISSING_BAD_ROWS.drop(
    SOUNDING_TABLE_RH_MISSING_BAD_ROWS.index[THESE_BAD_ROWS], axis=0,
    inplace=False)

SOUNDING_TABLE_RH_FILLED_BAD_ROWS = THIS_GENERIC_SOUNDING_TABLE.assign(
    **{nwp_model_utils.RH_COLUMN_FOR_SOUNDING_TABLES: THESE_RH_PERCENT})
SOUNDING_TABLE_RH_FILLED = SOUNDING_TABLE_RH_FILLED_BAD_ROWS.drop(
    SOUNDING_TABLE_RH_FILLED_BAD_ROWS.index[THESE_BAD_ROWS], axis=0,
    inplace=False)

# The following constants are used to test check_statistic_name,
# remove_vector_suffix_from_stat_name, and add_vector_suffix_to_stat_name.
STORM_VELOCITY_X_NAME = 'storm_velocity_m_s01_x'
STORM_VELOCITY_Y_NAME = 'storm_velocity_m_s01_y'
STORM_VELOCITY_COS_NAME = 'storm_velocity_m_s01_cos'
STORM_VELOCITY_SIN_NAME = 'storm_velocity_m_s01_sin'
STORM_VELOCITY_MAGNITUDE_NAME = 'storm_velocity_m_s01_magnitude'
STORM_VELOCITY_NAME = 'storm_velocity_m_s01'
FAKE_SOUNDING_STAT_NAME = 'poop'

# The following constants are used to test _get_nwp_fields_for_sounding.
MINIMUM_PRESSURE_MB = 950.

THIS_LOWEST_TEMPERATURE_NAME, THIS_LOWEST_TEMPERATURE_NAME_GRIB1 = (
    nwp_model_utils.get_lowest_temperature_name(nwp_model_utils.RAP_MODEL_NAME))
THIS_LOWEST_HUMIDITY_NAME, THIS_LOWEST_HUMIDITY_NAME_GRIB1 = (
    nwp_model_utils.get_lowest_humidity_name(nwp_model_utils.RAP_MODEL_NAME))
THIS_LOWEST_HEIGHT_NAME, THIS_LOWEST_HEIGHT_NAME_GRIB1 = (
    nwp_model_utils.get_lowest_height_name(nwp_model_utils.RAP_MODEL_NAME))
THIS_LOWEST_U_WIND_NAME, THIS_LOWEST_U_WIND_NAME_GRIB1 = (
    nwp_model_utils.get_lowest_u_wind_name(nwp_model_utils.RAP_MODEL_NAME))
THIS_LOWEST_V_WIND_NAME, THIS_LOWEST_V_WIND_NAME_GRIB1 = (
    nwp_model_utils.get_lowest_v_wind_name(nwp_model_utils.RAP_MODEL_NAME))
THIS_LOWEST_PRESSURE_NAME, THIS_LOWEST_PRESSURE_NAME_GRIB1 = (
    nwp_model_utils.get_lowest_pressure_name(nwp_model_utils.RAP_MODEL_NAME))

SOUNDING_FIELD_NAMES_RAP = [
    'temperature_kelvins_950mb', 'temperature_kelvins_975mb',
    'temperature_kelvins_1000mb', THIS_LOWEST_TEMPERATURE_NAME,
    'relative_humidity_percent_950mb', 'relative_humidity_percent_975mb',
    'relative_humidity_percent_1000mb', THIS_LOWEST_HUMIDITY_NAME,
    'geopotential_height_metres_950mb', 'geopotential_height_metres_975mb',
    'geopotential_height_metres_1000mb', THIS_LOWEST_HEIGHT_NAME,
    'u_wind_m_s01_950mb', 'u_wind_m_s01_975mb', 'u_wind_m_s01_1000mb',
    THIS_LOWEST_U_WIND_NAME,
    'v_wind_m_s01_950mb', 'v_wind_m_s01_975mb', 'v_wind_m_s01_1000mb',
    THIS_LOWEST_V_WIND_NAME, THIS_LOWEST_PRESSURE_NAME]

SOUNDING_FIELD_NAMES_GRIB1_RAP = [
    'TMP:950 mb', 'TMP:975 mb', 'TMP:1000 mb',
    THIS_LOWEST_TEMPERATURE_NAME_GRIB1,
    'RH:950 mb', 'RH:975 mb', 'RH:1000 mb', THIS_LOWEST_HUMIDITY_NAME_GRIB1,
    'HGT:950 mb', 'HGT:975 mb', 'HGT:1000 mb', THIS_LOWEST_HEIGHT_NAME_GRIB1,
    'UGRD:950 mb', 'UGRD:975 mb', 'UGRD:1000 mb', THIS_LOWEST_U_WIND_NAME_GRIB1,
    'VGRD:950 mb', 'VGRD:975 mb', 'VGRD:1000 mb', THIS_LOWEST_V_WIND_NAME_GRIB1,
    THIS_LOWEST_PRESSURE_NAME_GRIB1]

TEMPERATURE_FIELD_NAMES_RAP = [
    'temperature_kelvins_950mb', 'temperature_kelvins_975mb',
    'temperature_kelvins_1000mb', THIS_LOWEST_TEMPERATURE_NAME]
RH_FIELD_NAMES_RAP = [
    'relative_humidity_percent_950mb', 'relative_humidity_percent_975mb',
    'relative_humidity_percent_1000mb', THIS_LOWEST_HUMIDITY_NAME]
HEIGHT_FIELD_NAMES_RAP = [
    'geopotential_height_metres_950mb', 'geopotential_height_metres_975mb',
    'geopotential_height_metres_1000mb', THIS_LOWEST_HEIGHT_NAME]
U_WIND_FIELD_NAMES_RAP = [
    'u_wind_m_s01_950mb', 'u_wind_m_s01_975mb', 'u_wind_m_s01_1000mb',
    THIS_LOWEST_U_WIND_NAME]
V_WIND_FIELD_NAMES_RAP = [
    'v_wind_m_s01_950mb', 'v_wind_m_s01_975mb', 'v_wind_m_s01_1000mb',
    THIS_LOWEST_V_WIND_NAME]
SOUNDING_FIELD_DICT_RAP = {
    nwp_model_utils.TEMPERATURE_COLUMN_FOR_SOUNDING_TABLES:
        TEMPERATURE_FIELD_NAMES_RAP,
    nwp_model_utils.RH_COLUMN_FOR_SOUNDING_TABLES: RH_FIELD_NAMES_RAP,
    nwp_model_utils.HEIGHT_COLUMN_FOR_SOUNDING_TABLES: HEIGHT_FIELD_NAMES_RAP,
    nwp_model_utils.U_WIND_COLUMN_FOR_SOUNDING_TABLES: U_WIND_FIELD_NAMES_RAP,
    nwp_model_utils.V_WIND_COLUMN_FOR_SOUNDING_TABLES: V_WIND_FIELD_NAMES_RAP
}

THIS_LOWEST_TEMPERATURE_NAME, THIS_LOWEST_TEMPERATURE_NAME_GRIB1 = (
    nwp_model_utils.get_lowest_temperature_name(
        nwp_model_utils.NARR_MODEL_NAME))
THIS_LOWEST_HUMIDITY_NAME, THIS_LOWEST_HUMIDITY_NAME_GRIB1 = (
    nwp_model_utils.get_lowest_humidity_name(nwp_model_utils.NARR_MODEL_NAME))
THIS_LOWEST_HEIGHT_NAME, THIS_LOWEST_HEIGHT_NAME_GRIB1 = (
    nwp_model_utils.get_lowest_height_name(nwp_model_utils.NARR_MODEL_NAME))
THIS_LOWEST_U_WIND_NAME, THIS_LOWEST_U_WIND_NAME_GRIB1 = (
    nwp_model_utils.get_lowest_u_wind_name(nwp_model_utils.NARR_MODEL_NAME))
THIS_LOWEST_V_WIND_NAME, THIS_LOWEST_V_WIND_NAME_GRIB1 = (
    nwp_model_utils.get_lowest_v_wind_name(nwp_model_utils.NARR_MODEL_NAME))
THIS_LOWEST_PRESSURE_NAME, THIS_LOWEST_PRESSURE_NAME_GRIB1 = (
    nwp_model_utils.get_lowest_pressure_name(nwp_model_utils.NARR_MODEL_NAME))

SOUNDING_FIELD_NAMES_NARR = [
    'temperature_kelvins_950mb', 'temperature_kelvins_975mb',
    'temperature_kelvins_1000mb', THIS_LOWEST_TEMPERATURE_NAME,
    'specific_humidity_950mb', 'specific_humidity_975mb',
    'specific_humidity_1000mb', THIS_LOWEST_HUMIDITY_NAME,
    'geopotential_height_metres_950mb', 'geopotential_height_metres_975mb',
    'geopotential_height_metres_1000mb', THIS_LOWEST_HEIGHT_NAME,
    'u_wind_m_s01_950mb', 'u_wind_m_s01_975mb', 'u_wind_m_s01_1000mb',
    THIS_LOWEST_U_WIND_NAME,
    'v_wind_m_s01_950mb', 'v_wind_m_s01_975mb', 'v_wind_m_s01_1000mb',
    THIS_LOWEST_V_WIND_NAME, THIS_LOWEST_PRESSURE_NAME]

SOUNDING_FIELD_NAMES_GRIB1_NARR = [
    'TMP:950 mb', 'TMP:975 mb', 'TMP:1000 mb',
    THIS_LOWEST_TEMPERATURE_NAME_GRIB1,
    'SPFH:950 mb', 'SPFH:975 mb', 'SPFH:1000 mb',
    THIS_LOWEST_HUMIDITY_NAME_GRIB1,
    'HGT:950 mb', 'HGT:975 mb', 'HGT:1000 mb', THIS_LOWEST_HEIGHT_NAME_GRIB1,
    'UGRD:950 mb', 'UGRD:975 mb', 'UGRD:1000 mb', THIS_LOWEST_U_WIND_NAME_GRIB1,
    'VGRD:950 mb', 'VGRD:975 mb', 'VGRD:1000 mb', THIS_LOWEST_V_WIND_NAME_GRIB1,
    THIS_LOWEST_PRESSURE_NAME_GRIB1]

TEMPERATURE_FIELD_NAMES_NARR = [
    'temperature_kelvins_950mb', 'temperature_kelvins_975mb',
    'temperature_kelvins_1000mb', THIS_LOWEST_TEMPERATURE_NAME]
SPFH_FIELD_NAMES_NARR = [
    'specific_humidity_950mb', 'specific_humidity_975mb',
    'specific_humidity_1000mb', THIS_LOWEST_HUMIDITY_NAME]
HEIGHT_FIELD_NAMES_NARR = [
    'geopotential_height_metres_950mb', 'geopotential_height_metres_975mb',
    'geopotential_height_metres_1000mb', THIS_LOWEST_HEIGHT_NAME]
U_WIND_FIELD_NAMES_NARR = [
    'u_wind_m_s01_950mb', 'u_wind_m_s01_975mb', 'u_wind_m_s01_1000mb',
    THIS_LOWEST_U_WIND_NAME]
V_WIND_FIELD_NAMES_NARR = [
    'v_wind_m_s01_950mb', 'v_wind_m_s01_975mb', 'v_wind_m_s01_1000mb',
    THIS_LOWEST_V_WIND_NAME]
SOUNDING_FIELD_DICT_NARR = {
    nwp_model_utils.TEMPERATURE_COLUMN_FOR_SOUNDING_TABLES:
        TEMPERATURE_FIELD_NAMES_NARR,
    nwp_model_utils.SPFH_COLUMN_FOR_SOUNDING_TABLES: SPFH_FIELD_NAMES_NARR,
    nwp_model_utils.HEIGHT_COLUMN_FOR_SOUNDING_TABLES: HEIGHT_FIELD_NAMES_NARR,
    nwp_model_utils.U_WIND_COLUMN_FOR_SOUNDING_TABLES: U_WIND_FIELD_NAMES_NARR,
    nwp_model_utils.V_WIND_COLUMN_FOR_SOUNDING_TABLES: V_WIND_FIELD_NAMES_NARR
}

# The following constants are used to test _remove_subsurface_pressure_levels.
THESE_PRESSURES_MB = numpy.array([1013.15, 1000, 975, 974.9999, 950, 900, 925])
THESE_HEIGHTS_M_ASL = numpy.array(
    [1.675, 112.933, 335.369, 335.3691, 561.523, 1029.52, 792.945])
THESE_TEMPERATURES_DEG_C = numpy.array(
    [23.123, 22.269, 21.569, 21.569, 20.968, 18.640, 19.975])
THESE_DEWPOINTS_DEG_C = numpy.array(
    [23.001, 22.104, 21.404, 21.404, 20.741, 17.956, 19.356])
THESE_U_WINDS_KT = numpy.array(
    [-3.896, -7.263, -5.232, -5.232, 2.946, 14.759, 10.421])
THESE_V_WINDS_KT = numpy.array(
    [6.579, 13.145, 22.208, 22.208, 26.798, 27.226, 27.819])
THESE_SURFACE_FLAGS = numpy.array(
    [False, False, True, False, False, False, False], dtype=bool)

THIS_DICT = {
    sounding_stats.PRESSURE_COLUMN_IN_SHARPPY_SOUNDING: THESE_PRESSURES_MB,
    sounding_stats.HEIGHT_COLUMN_IN_SHARPPY_SOUNDING: THESE_HEIGHTS_M_ASL,
    sounding_stats.TEMPERATURE_COLUMN_IN_SHARPPY_SOUNDING: THESE_TEMPERATURES_DEG_C,
    sounding_stats.DEWPOINT_COLUMN_IN_SHARPPY_SOUNDING: THESE_DEWPOINTS_DEG_C,
    sounding_stats.U_WIND_COLUMN_IN_SHARPPY_SOUNDING: THESE_U_WINDS_KT,
    sounding_stats.V_WIND_COLUMN_IN_SHARPPY_SOUNDING: THESE_V_WINDS_KT,
    sounding_stats.SURFACE_COLUMN_IN_SHARPPY_SOUNDING: THESE_SURFACE_FLAGS
}
SOUNDING_TABLE_SHARPPY_ORIG = pandas.DataFrame.from_dict(THIS_DICT)

# The following constants are used to test _sounding_to_sharppy_units.
MB_TO_PASCALS = 100
UNITLESS_TO_PERCENT = 100
KT_TO_METRES_PER_SECOND = 1.852 / 3.6

THESE_TEMPERATURES_KELVINS = temperature_conversions.celsius_to_kelvins(
    THESE_TEMPERATURES_DEG_C)
THESE_DEWPOINTS_KELVINS = temperature_conversions.celsius_to_kelvins(
    THESE_DEWPOINTS_DEG_C)
THESE_SPECIFIC_HUMIDITIES = moisture_conversions.dewpoint_to_specific_humidity(
    THESE_DEWPOINTS_KELVINS, THESE_PRESSURES_MB * MB_TO_PASCALS)
THESE_RH_PERCENT = moisture_conversions.dewpoint_to_relative_humidity(
    THESE_DEWPOINTS_KELVINS, THESE_TEMPERATURES_KELVINS,
    THESE_PRESSURES_MB * MB_TO_PASCALS) * UNITLESS_TO_PERCENT
THESE_U_WINDS_M_S01 = KT_TO_METRES_PER_SECOND * THESE_U_WINDS_KT
THESE_V_WINDS_M_S01 = KT_TO_METRES_PER_SECOND * THESE_V_WINDS_KT

THIS_DICT = {
    sounding_stats.PRESSURE_COLUMN_IN_SHARPPY_SOUNDING: THESE_PRESSURES_MB,
    nwp_model_utils.HEIGHT_COLUMN_FOR_SOUNDING_TABLES: THESE_HEIGHTS_M_ASL,
    nwp_model_utils.TEMPERATURE_COLUMN_FOR_SOUNDING_TABLES:
        THESE_TEMPERATURES_KELVINS,
    nwp_model_utils.SPFH_COLUMN_FOR_SOUNDING_TABLES: THESE_SPECIFIC_HUMIDITIES,
    nwp_model_utils.U_WIND_COLUMN_FOR_SOUNDING_TABLES: THESE_U_WINDS_M_S01,
    nwp_model_utils.V_WIND_COLUMN_FOR_SOUNDING_TABLES: THESE_V_WINDS_M_S01,
    sounding_stats.SURFACE_COLUMN_IN_SHARPPY_SOUNDING: THESE_SURFACE_FLAGS
}
SOUNDING_TABLE_RAP_UNITS = pandas.DataFrame.from_dict(THIS_DICT)

THIS_DICT = {
    sounding_stats.PRESSURE_COLUMN_IN_SHARPPY_SOUNDING: THESE_PRESSURES_MB,
    nwp_model_utils.HEIGHT_COLUMN_FOR_SOUNDING_TABLES: THESE_HEIGHTS_M_ASL,
    nwp_model_utils.TEMPERATURE_COLUMN_FOR_SOUNDING_TABLES:
        THESE_TEMPERATURES_KELVINS,
    nwp_model_utils.RH_COLUMN_FOR_SOUNDING_TABLES: THESE_RH_PERCENT,
    nwp_model_utils.U_WIND_COLUMN_FOR_SOUNDING_TABLES: THESE_U_WINDS_M_S01,
    nwp_model_utils.V_WIND_COLUMN_FOR_SOUNDING_TABLES: THESE_V_WINDS_M_S01,
    sounding_stats.SURFACE_COLUMN_IN_SHARPPY_SOUNDING: THESE_SURFACE_FLAGS
}
SOUNDING_TABLE_NARR_UNITS = pandas.DataFrame.from_dict(THIS_DICT)

SENTINEL_VALUE = sounding_stats.SENTINEL_VALUE_FOR_SHARPPY
THESE_TEMPERATURES_DEG_C[0:2] = SENTINEL_VALUE
THESE_DEWPOINTS_DEG_C[0:2] = SENTINEL_VALUE
THESE_U_WINDS_KT[0:2] = SENTINEL_VALUE
THESE_V_WINDS_KT[0:2] = SENTINEL_VALUE

THIS_DICT = {
    sounding_stats.PRESSURE_COLUMN_IN_SHARPPY_SOUNDING: THESE_PRESSURES_MB,
    sounding_stats.HEIGHT_COLUMN_IN_SHARPPY_SOUNDING: THESE_HEIGHTS_M_ASL,
    sounding_stats.TEMPERATURE_COLUMN_IN_SHARPPY_SOUNDING: THESE_TEMPERATURES_DEG_C,
    sounding_stats.DEWPOINT_COLUMN_IN_SHARPPY_SOUNDING: THESE_DEWPOINTS_DEG_C,
    sounding_stats.U_WIND_COLUMN_IN_SHARPPY_SOUNDING: THESE_U_WINDS_KT,
    sounding_stats.V_WIND_COLUMN_IN_SHARPPY_SOUNDING: THESE_V_WINDS_KT,
    sounding_stats.SURFACE_COLUMN_IN_SHARPPY_SOUNDING: THESE_SURFACE_FLAGS
}
SOUNDING_TABLE_WITH_SENTINELS = pandas.DataFrame.from_dict(THIS_DICT)

# The following constants are used to test _sort_sounding_by_height.
THESE_PRESSURES_MB = numpy.array([1013.15, 1000, 975, 974.9999, 950, 925, 900])
THESE_HEIGHTS_M_ASL = numpy.array(
    [1.675, 112.933, 335.369, 335.3691, 561.523, 792.945, 1029.52])
THESE_TEMPERATURES_DEG_C = numpy.array(
    [SENTINEL_VALUE, SENTINEL_VALUE, 21.569, 21.569, 20.968, 19.975, 18.640])
THESE_DEWPOINTS_DEG_C = numpy.array(
    [SENTINEL_VALUE, SENTINEL_VALUE, 21.404, 21.404, 20.741, 19.356, 17.956])
THESE_U_WINDS_KT = numpy.array(
    [SENTINEL_VALUE, SENTINEL_VALUE, -5.232, -5.232, 2.946, 10.421, 14.759])
THESE_V_WINDS_KT = numpy.array(
    [SENTINEL_VALUE, SENTINEL_VALUE, 22.208, 22.208, 26.798, 27.819, 27.226])

THIS_DICT = {
    sounding_stats.PRESSURE_COLUMN_IN_SHARPPY_SOUNDING: THESE_PRESSURES_MB,
    sounding_stats.HEIGHT_COLUMN_IN_SHARPPY_SOUNDING: THESE_HEIGHTS_M_ASL,
    sounding_stats.TEMPERATURE_COLUMN_IN_SHARPPY_SOUNDING: THESE_TEMPERATURES_DEG_C,
    sounding_stats.DEWPOINT_COLUMN_IN_SHARPPY_SOUNDING: THESE_DEWPOINTS_DEG_C,
    sounding_stats.U_WIND_COLUMN_IN_SHARPPY_SOUNDING: THESE_U_WINDS_KT,
    sounding_stats.V_WIND_COLUMN_IN_SHARPPY_SOUNDING: THESE_V_WINDS_KT,
    sounding_stats.SURFACE_COLUMN_IN_SHARPPY_SOUNDING: THESE_SURFACE_FLAGS
}
SOUNDING_TABLE_WITH_SENTINELS_SORTED = pandas.DataFrame.from_dict(THIS_DICT)

# The following constants are used to test _remove_redundant_pressure_levels.
SOUNDING_TABLE_NO_REDUNDANT = SOUNDING_TABLE_WITH_SENTINELS_SORTED.drop(
    SOUNDING_TABLE_WITH_SENTINELS_SORTED.index[[3]], axis=0,
    inplace=False).reset_index(drop=True)

# The following constants are used to test _remove_subsurface_pressure_levels.
SOUNDING_TABLE_NO_SUBSURFACE = SOUNDING_TABLE_NO_REDUNDANT.drop(
    SOUNDING_TABLE_NO_REDUNDANT.index[[0]], axis=0,
    inplace=False).reset_index(drop=True)

# The following constants are used to test _split_vector_column.
VECTOR_COLUMN = 'vector'
VECTOR_COLUMN_AS_TABLE = pandas.DataFrame.from_dict(
    {VECTOR_COLUMN: numpy.full(8, numpy.nan)})

THIS_NESTED_ARRAY = VECTOR_COLUMN_AS_TABLE[[
    VECTOR_COLUMN, VECTOR_COLUMN]].values.tolist()
VECTOR_COLUMN_AS_TABLE = VECTOR_COLUMN_AS_TABLE.assign(
    **{VECTOR_COLUMN: THIS_NESTED_ARRAY})

VECTOR_COLUMN_AS_TABLE[VECTOR_COLUMN].values[0] = numpy.array(
    [1, 0], dtype=float)
VECTOR_COLUMN_AS_TABLE[VECTOR_COLUMN].values[1] = numpy.array(
    [1, 1], dtype=float)
VECTOR_COLUMN_AS_TABLE[VECTOR_COLUMN].values[2] = numpy.array(
    [0, 1], dtype=float)
VECTOR_COLUMN_AS_TABLE[VECTOR_COLUMN].values[3] = numpy.array(
    [-1, 1], dtype=float)
VECTOR_COLUMN_AS_TABLE[VECTOR_COLUMN].values[4] = numpy.array(
    [-1, 0], dtype=float)
VECTOR_COLUMN_AS_TABLE[VECTOR_COLUMN].values[5] = numpy.array(
    [-1, -1], dtype=float)
VECTOR_COLUMN_AS_TABLE[VECTOR_COLUMN].values[6] = numpy.array(
    [0, -1], dtype=float)
VECTOR_COLUMN_AS_TABLE[VECTOR_COLUMN].values[7] = numpy.array(
    [1, -1], dtype=float)

ROOT2 = numpy.sqrt(2.)
HALF_ROOT2 = ROOT2 / 2

THESE_X_COMPONENTS = numpy.array([1, 1, 0, -1, -1, -1, 0, 1], dtype=float)
THESE_Y_COMPONENTS = numpy.array([0, 1, 1, 1, 0, -1, -1, -1], dtype=float)
THESE_MAGNITUDES = numpy.array([1, ROOT2, 1, ROOT2, 1, ROOT2, 1, ROOT2])
THESE_COSINES = numpy.array(
    [1, HALF_ROOT2, 0, -HALF_ROOT2, -1, -HALF_ROOT2, 0, HALF_ROOT2])
THESE_SINES = numpy.array(
    [0, HALF_ROOT2, 1, HALF_ROOT2, 0, -HALF_ROOT2, -1, -HALF_ROOT2])

X_COMPONENT_COLUMN = 'vector_x'
Y_COMPONENT_COLUMN = 'vector_y'
MAGNITUDE_COLUMN = 'vector_magnitude'
COSINE_COLUMN = 'vector_cos'
SINE_COLUMN = 'vector_sin'

THIS_VECTOR_COMPONENT_DICT = {
    X_COMPONENT_COLUMN: THESE_X_COMPONENTS,
    Y_COMPONENT_COLUMN: THESE_Y_COMPONENTS, MAGNITUDE_COLUMN: THESE_MAGNITUDES,
    COSINE_COLUMN: THESE_COSINES, SINE_COLUMN: THESE_SINES}
VECTOR_COMPONENT_TABLE_CONV_FACTOR1 = pandas.DataFrame.from_dict(
    THIS_VECTOR_COMPONENT_DICT)

THIS_VECTOR_COMPONENT_DICT = {
    X_COMPONENT_COLUMN: THESE_X_COMPONENTS * 10,
    Y_COMPONENT_COLUMN: THESE_Y_COMPONENTS * 10,
    MAGNITUDE_COLUMN: THESE_MAGNITUDES * 10,
    COSINE_COLUMN: THESE_COSINES, SINE_COLUMN: THESE_SINES}
VECTOR_COMPONENT_TABLE_CONV_FACTOR10 = pandas.DataFrame.from_dict(
    THIS_VECTOR_COMPONENT_DICT)

# The following constants are used to test _sentinels_to_nan.
CONVECTIVE_TEMPERATURE_NAME = 'convective_temperature_kelvins'
MEAN_WIND_0TO1KM_NAME = 'wind_mean_0to1km_agl_m_s01'
SURFACE_RH_NAME = 'relative_humidity_surface'
DERECHO_COMPOSITE_NAME = 'derecho_composite_param'

METADATA_TABLE = sounding_stats.read_metadata_for_statistics()
VALID_SOUNDING_STAT_NAMES = METADATA_TABLE[
    sounding_stats.STATISTIC_NAME_COLUMN].values

SOUNDING_STAT_NAMES = list(
    METADATA_TABLE[sounding_stats.STATISTIC_NAME_COLUMN].values)
SOUNDING_STAT_NAMES_SHARPPY = list(
    METADATA_TABLE[sounding_stats.SHARPPY_STATISTIC_NAME_COLUMN].values)

CONVECTIVE_TEMPERATURE_NAME_SHARPPY = SOUNDING_STAT_NAMES_SHARPPY[
    SOUNDING_STAT_NAMES.index(CONVECTIVE_TEMPERATURE_NAME)]
MEAN_WIND_0TO1KM_NAME_SHARPPY = SOUNDING_STAT_NAMES_SHARPPY[
    SOUNDING_STAT_NAMES.index(MEAN_WIND_0TO1KM_NAME)]
SURFACE_RH_NAME_SHARPPY = SOUNDING_STAT_NAMES_SHARPPY[
    SOUNDING_STAT_NAMES.index(SURFACE_RH_NAME)]
DERECHO_COMPOSITE_NAME_SHARPPY = SOUNDING_STAT_NAMES_SHARPPY[
    SOUNDING_STAT_NAMES.index(DERECHO_COMPOSITE_NAME)]

CONVECTIVE_TEMPS_DEG_F = numpy.array(
    [-130, -76, -40, -4, 32, 50, 68], dtype=float)
U_WINDS_0TO1KM_AGL_KT = numpy.array([10, 10, 0, -10, -10, -10, 0], dtype=float)
V_WINDS_0TO1KM_AGL_KT = numpy.array([0, 10, 10, 10, 0, -10, -10], dtype=float)
SURFACE_RH_PERCENTAGES = numpy.array([40, 50, 60, 70, 80, 90, 100], dtype=float)
DERECHO_COMPOSITE_PARAMS = numpy.array([0, 5, 10, 15, 20, 25, 30], dtype=float)

THIS_DICT = {
    CONVECTIVE_TEMPERATURE_NAME_SHARPPY: CONVECTIVE_TEMPS_DEG_F,
    SURFACE_RH_NAME_SHARPPY: SURFACE_RH_PERCENTAGES,
    DERECHO_COMPOSITE_NAME_SHARPPY: DERECHO_COMPOSITE_PARAMS
}
STATISTIC_TABLE_SHARPPY = pandas.DataFrame.from_dict(THIS_DICT)
STATISTIC_TABLE_SHARPPY_WITH_SENTINELS = pandas.DataFrame.from_dict(THIS_DICT)
STATISTIC_TABLE_SHARPPY_WITH_NANS = pandas.DataFrame.from_dict(THIS_DICT)

THIS_NESTED_ARRAY = STATISTIC_TABLE_SHARPPY[[
    SURFACE_RH_NAME_SHARPPY, SURFACE_RH_NAME_SHARPPY]].values.tolist()
STATISTIC_TABLE_SHARPPY = STATISTIC_TABLE_SHARPPY.assign(
    **{MEAN_WIND_0TO1KM_NAME_SHARPPY: THIS_NESTED_ARRAY})
STATISTIC_TABLE_SHARPPY_WITH_SENTINELS = (
    STATISTIC_TABLE_SHARPPY_WITH_SENTINELS.assign(
        **{MEAN_WIND_0TO1KM_NAME_SHARPPY: THIS_NESTED_ARRAY}))
STATISTIC_TABLE_SHARPPY_WITH_NANS = (
    STATISTIC_TABLE_SHARPPY_WITH_NANS.assign(
        **{MEAN_WIND_0TO1KM_NAME_SHARPPY: THIS_NESTED_ARRAY}))

for k in range(len(U_WINDS_0TO1KM_AGL_KT)):
    this_wind_vector = numpy.array(
        [U_WINDS_0TO1KM_AGL_KT[k], V_WINDS_0TO1KM_AGL_KT[k]])

    STATISTIC_TABLE_SHARPPY[MEAN_WIND_0TO1KM_NAME_SHARPPY].values[
        k] = copy.deepcopy(this_wind_vector)
    STATISTIC_TABLE_SHARPPY_WITH_SENTINELS[
        MEAN_WIND_0TO1KM_NAME_SHARPPY
    ].values[k] = copy.deepcopy(this_wind_vector)
    STATISTIC_TABLE_SHARPPY_WITH_NANS[MEAN_WIND_0TO1KM_NAME_SHARPPY].values[
        k] = copy.deepcopy(this_wind_vector)

STATISTIC_TABLE_SHARPPY_WITH_SENTINELS[
    CONVECTIVE_TEMPERATURE_NAME_SHARPPY
].values[0] = sounding_stats.SENTINEL_VALUE_FOR_SHARPPY
STATISTIC_TABLE_SHARPPY_WITH_SENTINELS[
    SURFACE_RH_NAME_SHARPPY
].values[1] = sounding_stats.SENTINEL_VALUE_FOR_SHARPPY
STATISTIC_TABLE_SHARPPY_WITH_SENTINELS[
    DERECHO_COMPOSITE_NAME_SHARPPY
].values[2] = sounding_stats.SENTINEL_VALUE_FOR_SHARPPY
STATISTIC_TABLE_SHARPPY_WITH_SENTINELS[
    MEAN_WIND_0TO1KM_NAME_SHARPPY
].values[3][0] = sounding_stats.SENTINEL_VALUE_FOR_SHARPPY
STATISTIC_TABLE_SHARPPY_WITH_SENTINELS[
    MEAN_WIND_0TO1KM_NAME_SHARPPY
].values[4][1] = sounding_stats.SENTINEL_VALUE_FOR_SHARPPY
STATISTIC_TABLE_SHARPPY_WITH_SENTINELS[
    MEAN_WIND_0TO1KM_NAME_SHARPPY
].values[5][0] = sounding_stats.SENTINEL_VALUE_FOR_SHARPPY
STATISTIC_TABLE_SHARPPY_WITH_SENTINELS[
    MEAN_WIND_0TO1KM_NAME_SHARPPY
].values[5][1] = sounding_stats.SENTINEL_VALUE_FOR_SHARPPY

STATISTIC_TABLE_SHARPPY_WITH_NANS[
    CONVECTIVE_TEMPERATURE_NAME_SHARPPY].values[0] = numpy.nan
STATISTIC_TABLE_SHARPPY_WITH_NANS[
    SURFACE_RH_NAME_SHARPPY].values[1] = numpy.nan
STATISTIC_TABLE_SHARPPY_WITH_NANS[
    DERECHO_COMPOSITE_NAME_SHARPPY].values[2] = numpy.nan
STATISTIC_TABLE_SHARPPY_WITH_NANS[
    MEAN_WIND_0TO1KM_NAME_SHARPPY].values[3] = numpy.full(2, numpy.nan)
STATISTIC_TABLE_SHARPPY_WITH_NANS[
    MEAN_WIND_0TO1KM_NAME_SHARPPY].values[4] = numpy.full(2, numpy.nan)
STATISTIC_TABLE_SHARPPY_WITH_NANS[
    MEAN_WIND_0TO1KM_NAME_SHARPPY].values[5] = numpy.full(2, numpy.nan)

# The following constants are used to test _convert_sounding_statistics.
TEN_KT_IN_MPS = 5.144444
ROOT200_KT_IN_MPS = 7.275343
U_WIND_0TO1KM_NAME = 'wind_mean_0to1km_agl_m_s01_x'
V_WIND_0TO1KM_NAME = 'wind_mean_0to1km_agl_m_s01_y'
WIND_SPEED_0TO1KM_NAME = 'wind_mean_0to1km_agl_m_s01_magnitude'
WIND_COS_0TO1KM_NAME = 'wind_mean_0to1km_agl_m_s01_cos'
WIND_SIN_0TO1KM_NAME = 'wind_mean_0to1km_agl_m_s01_sin'

CONVECTIVE_TEMPS_KELVINS = temperature_conversions.fahrenheit_to_kelvins(
    CONVECTIVE_TEMPS_DEG_F)
U_WINDS_M_S01 = numpy.array(
    [TEN_KT_IN_MPS, TEN_KT_IN_MPS, 0, -TEN_KT_IN_MPS, -TEN_KT_IN_MPS,
     -TEN_KT_IN_MPS, 0])
V_WINDS_M_S01 = numpy.array(
    [0, TEN_KT_IN_MPS, TEN_KT_IN_MPS, TEN_KT_IN_MPS, 0, -TEN_KT_IN_MPS,
     -TEN_KT_IN_MPS])
WIND_SPEEDS_M_S01 = numpy.array(
    [TEN_KT_IN_MPS, ROOT200_KT_IN_MPS, TEN_KT_IN_MPS, ROOT200_KT_IN_MPS,
     TEN_KT_IN_MPS, ROOT200_KT_IN_MPS, TEN_KT_IN_MPS])
WIND_COSINES = numpy.array(
    [1, HALF_ROOT2, 0, -HALF_ROOT2, -1, -HALF_ROOT2, 0])
WIND_SINES = numpy.array([0, HALF_ROOT2, 1, HALF_ROOT2, 0, -HALF_ROOT2, -1])
SURFACE_RH_UNITLESS = numpy.array([0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1])

THIS_DICT = {
    CONVECTIVE_TEMPERATURE_NAME: CONVECTIVE_TEMPS_KELVINS,
    U_WIND_0TO1KM_NAME: U_WINDS_M_S01, V_WIND_0TO1KM_NAME: V_WINDS_M_S01,
    WIND_SPEED_0TO1KM_NAME: WIND_SPEEDS_M_S01,
    WIND_COS_0TO1KM_NAME: WIND_COSINES, WIND_SIN_0TO1KM_NAME: WIND_SINES,
    SURFACE_RH_NAME: SURFACE_RH_UNITLESS,
    DERECHO_COMPOSITE_NAME: DERECHO_COMPOSITE_PARAMS
}
SOUNDING_STATISTIC_TABLE = pandas.DataFrame.from_dict(THIS_DICT)

# The following constants are used to test _get_unique_storm_sounding_stats.
THIS_SOUNDING_DICT1 = {
    sounding_stats.PRESSURE_COLUMN_IN_SHARPPY_SOUNDING:
        numpy.array([1, 2, 3], dtype=float),
    sounding_stats.HEIGHT_COLUMN_IN_SHARPPY_SOUNDING:
        numpy.array([4, 5, 6], dtype=float),
    sounding_stats.TEMPERATURE_COLUMN_IN_SHARPPY_SOUNDING:
        numpy.array([7, 8, 9], dtype=float),
    sounding_stats.DEWPOINT_COLUMN_IN_SHARPPY_SOUNDING:
        numpy.array([10, 11, 12], dtype=float),
    sounding_stats.U_WIND_COLUMN_IN_SHARPPY_SOUNDING:
        numpy.array([13, 14, 15], dtype=float),
    sounding_stats.V_WIND_COLUMN_IN_SHARPPY_SOUNDING:
        numpy.array([16, 17, 18], dtype=float),
    sounding_stats.SURFACE_COLUMN_IN_SHARPPY_SOUNDING:
        numpy.array([19, 20, 21], dtype=float)
}
THIS_SOUNDING_TABLE1 = pandas.DataFrame.from_dict(THIS_SOUNDING_DICT1)

THIS_SOUNDING_DICT2 = {
    sounding_stats.PRESSURE_COLUMN_IN_SHARPPY_SOUNDING:
        numpy.array([3, 2, 1], dtype=float),
    sounding_stats.HEIGHT_COLUMN_IN_SHARPPY_SOUNDING:
        numpy.array([4, 5, 6], dtype=float),
    sounding_stats.TEMPERATURE_COLUMN_IN_SHARPPY_SOUNDING:
        numpy.array([7, 8, 9], dtype=float),
    sounding_stats.DEWPOINT_COLUMN_IN_SHARPPY_SOUNDING:
        numpy.array([10, 11, 12], dtype=float),
    sounding_stats.U_WIND_COLUMN_IN_SHARPPY_SOUNDING:
        numpy.array([13, 14, 15], dtype=float),
    sounding_stats.V_WIND_COLUMN_IN_SHARPPY_SOUNDING:
        numpy.array([16, 17, 18], dtype=float),
    sounding_stats.SURFACE_COLUMN_IN_SHARPPY_SOUNDING:
        numpy.array([19, 20, 21], dtype=float)
}
THIS_SOUNDING_TABLE2 = pandas.DataFrame.from_dict(THIS_SOUNDING_DICT2)

THIS_SOUNDING_DICT3 = {
    sounding_stats.PRESSURE_COLUMN_IN_SHARPPY_SOUNDING:
        numpy.array([3, 2, 1], dtype=float),
    sounding_stats.HEIGHT_COLUMN_IN_SHARPPY_SOUNDING:
        numpy.array([6, 5, 4], dtype=float),
    sounding_stats.TEMPERATURE_COLUMN_IN_SHARPPY_SOUNDING:
        numpy.array([7, 8, 9], dtype=float),
    sounding_stats.DEWPOINT_COLUMN_IN_SHARPPY_SOUNDING:
        numpy.array([10, 11, 12], dtype=float),
    sounding_stats.U_WIND_COLUMN_IN_SHARPPY_SOUNDING:
        numpy.array([13, 14, 15], dtype=float),
    sounding_stats.V_WIND_COLUMN_IN_SHARPPY_SOUNDING:
        numpy.array([16, 17, 18], dtype=float),
    sounding_stats.SURFACE_COLUMN_IN_SHARPPY_SOUNDING:
        numpy.array([19, 20, 21], dtype=float)
}
THIS_SOUNDING_TABLE3 = pandas.DataFrame.from_dict(THIS_SOUNDING_DICT3)

LIST_OF_SOUNDING_TABLES = [
    None, THIS_SOUNDING_TABLE1, None, THIS_SOUNDING_TABLE2, None,
    THIS_SOUNDING_TABLE3, None, THIS_SOUNDING_TABLE3, None,
    THIS_SOUNDING_TABLE2, None, THIS_SOUNDING_TABLE1
]

U_MOTIONS_M_S01 = numpy.array([0, 5, 10, 15, 20, 25, 30, 27.5, 20, 15, 10, 5])
V_MOTIONS_M_S01 = numpy.full(len(U_MOTIONS_M_S01), 0.)

UNIQUE_INDICES = numpy.array([3, 5, 7, 1, 0], dtype=int)
ORIG_TO_UNIQUE_INDICES = numpy.array(
    [4, 3, 4, 0, 4, 1, 4, 2, 4, 0, 4, 3], dtype=int)

# The following constants are used to test find_sounding_statistic_file.
TOP_DIRECTORY_NAME = 'poop'
INIT_TIME_UNIX_SEC = 1526335354  # 220234 UTC 14 May 2018
LEAD_TIME_SEC = 3600
SPC_DATE_STRING = '20180514'
SOUNDING_STATISTIC_FILE_NAME = (
    'poop/2018/20180514/sounding_statistics_2018-05-14-220234_'
    'lead-time-3600sec.nc')


class SoundingsTests(unittest.TestCase):
    """Each method is a unit test for sounding_stats.py."""

    def test_remove_bad_pressure_levels_spfh_large_table(self):
        """Ensures correct output from _remove_bad_pressure_levels.

        In this case, sounding table is large and moisture variable is specific
        humidity.
        """

        this_sounding_table = copy.deepcopy(
            SOUNDING_TABLE_SPFH_MISSING_BAD_ROWS)
        this_sounding_table = sounding_stats._remove_bad_pressure_levels(
            this_sounding_table)

        these_columns = list(this_sounding_table)
        expected_columns = list(SOUNDING_TABLE_SPFH_MISSING)
        self.assertTrue(set(these_columns) == set(expected_columns))

        for this_column in these_columns:
            self.assertTrue(numpy.allclose(
                this_sounding_table[this_column].values,
                SOUNDING_TABLE_SPFH_MISSING[this_column].values,
                equal_nan=True))

    def test_remove_bad_pressure_levels_spfh_small_table(self):
        """Ensures correct output from _remove_bad_pressure_levels.

        In this case, sounding table is small and moisture variable is specific
        humidity.
        """

        these_rows = numpy.linspace(
            0, sounding_stats.MIN_PRESSURE_LEVELS_IN_SOUNDING - 1,
            num=sounding_stats.MIN_PRESSURE_LEVELS_IN_SOUNDING, dtype=int)

        this_sounding_table = copy.deepcopy(
            SOUNDING_TABLE_SPFH_MISSING_BAD_ROWS.iloc[these_rows])
        this_sounding_table = sounding_stats._remove_bad_pressure_levels(
            this_sounding_table)

        self.assertTrue(this_sounding_table is None)

    def test_remove_bad_pressure_levels_rh_large_table(self):
        """Ensures correct output from _remove_bad_pressure_levels.

        In this case, sounding table is large and moisture variable is relative
        humidity.
        """

        this_sounding_table = copy.deepcopy(SOUNDING_TABLE_RH_MISSING_BAD_ROWS)
        this_sounding_table = sounding_stats._remove_bad_pressure_levels(
            this_sounding_table)

        these_columns = list(this_sounding_table)
        expected_columns = list(SOUNDING_TABLE_RH_MISSING)
        self.assertTrue(set(these_columns) == set(expected_columns))

        for this_column in these_columns:
            self.assertTrue(numpy.allclose(
                this_sounding_table[this_column].values,
                SOUNDING_TABLE_RH_MISSING[this_column].values, equal_nan=True))

    def test_remove_bad_pressure_levels_rh_small_table(self):
        """Ensures correct output from _remove_bad_pressure_levels.

        In this case, sounding table is small and moisture variable is relative
        humidity.
        """

        these_rows = numpy.linspace(
            0, sounding_stats.MIN_PRESSURE_LEVELS_IN_SOUNDING - 1,
            num=sounding_stats.MIN_PRESSURE_LEVELS_IN_SOUNDING, dtype=int)

        this_sounding_table = copy.deepcopy(
            SOUNDING_TABLE_RH_MISSING_BAD_ROWS.iloc[these_rows])
        this_sounding_table = sounding_stats._remove_bad_pressure_levels(
            this_sounding_table)

        self.assertTrue(this_sounding_table is None)

    def test_fill_missing_humidity_spfh(self):
        """Ensures correct output from _fill_missing_humidity.

        In this case, moisture variable is specific humidity.
        """

        this_sounding_table = copy.deepcopy(SOUNDING_TABLE_SPFH_MISSING)
        this_sounding_table = sounding_stats._fill_missing_humidity(
            this_sounding_table)

        these_columns = list(this_sounding_table)
        expected_columns = list(SOUNDING_TABLE_SPFH_FILLED)
        self.assertTrue(set(these_columns) == set(expected_columns))

        for this_column in these_columns:
            self.assertTrue(numpy.allclose(
                this_sounding_table[this_column].values,
                SOUNDING_TABLE_SPFH_FILLED[this_column].values, equal_nan=True))

    def test_fill_missing_humidity_rh(self):
        """Ensures correct output from _fill_missing_humidity.

        In this case, moisture variable is relative humidity.
        """

        this_sounding_table = copy.deepcopy(SOUNDING_TABLE_RH_MISSING)
        this_sounding_table = sounding_stats._fill_missing_humidity(
            this_sounding_table)

        these_columns = list(this_sounding_table)
        expected_columns = list(SOUNDING_TABLE_RH_FILLED)
        self.assertTrue(set(these_columns) == set(expected_columns))

        for this_column in these_columns:
            self.assertTrue(numpy.allclose(
                this_sounding_table[this_column].values,
                SOUNDING_TABLE_RH_FILLED[this_column].values, equal_nan=True))

    def test_check_statistic_name_x(self):
        """Ensures correct output from check_statistic_name.

        In this case, statistic is the x-component of a vector.
        """

        sounding_stats.check_statistic_name(
            statistic_name=STORM_VELOCITY_X_NAME, metadata_table=METADATA_TABLE)

    def test_check_statistic_name_y(self):
        """Ensures correct output from check_statistic_name.

        In this case, statistic is the y-component of a vector.
        """

        sounding_stats.check_statistic_name(
            statistic_name=STORM_VELOCITY_Y_NAME, metadata_table=METADATA_TABLE)

    def test_check_statistic_name_magnitude(self):
        """Ensures correct output from check_statistic_name.

        In this case, statistic is the magnitude of a vector.
        """

        sounding_stats.check_statistic_name(
            statistic_name=STORM_VELOCITY_MAGNITUDE_NAME,
            metadata_table=METADATA_TABLE)

    def test_check_statistic_name_sin(self):
        """Ensures correct output from check_statistic_name.

        In this case, statistic is the sine of a vector.
        """

        sounding_stats.check_statistic_name(
            statistic_name=STORM_VELOCITY_SIN_NAME,
            metadata_table=METADATA_TABLE)

    def test_check_statistic_name_cos(self):
        """Ensures correct output from check_statistic_name.

        In this case, statistic is the cosine of a vector.
        """

        sounding_stats.check_statistic_name(
            statistic_name=STORM_VELOCITY_COS_NAME,
            metadata_table=METADATA_TABLE)

    def test_check_statistic_name_scalar(self):
        """Ensures correct output from check_statistic_name.

        In this case, statistic is not a vector component.
        """

        sounding_stats.check_statistic_name(
            statistic_name=STORM_VELOCITY_NAME, metadata_table=METADATA_TABLE)

    def test_check_statistic_name_fake(self):
        """Ensures correct output from check_statistic_name.

        In this case, statistic name is invalid.
        """

        with self.assertRaises(ValueError):
            sounding_stats.check_statistic_name(
                statistic_name=FAKE_SOUNDING_STAT_NAME,
                metadata_table=METADATA_TABLE)

    def test_remove_vector_suffix_from_stat_name_x(self):
        """Ensures correct output from remove_vector_suffix_from_stat_name.

        In this case, statistic is the x-component of a vector.
        """

        this_basic_stat_name, this_vector_suffix = (
            sounding_stats.remove_vector_suffix_from_stat_name(
                statistic_name=STORM_VELOCITY_X_NAME,
                metadata_table=METADATA_TABLE))

        self.assertTrue(this_basic_stat_name == STORM_VELOCITY_NAME)
        self.assertTrue(this_vector_suffix == sounding_stats.X_COMPONENT_SUFFIX)

    def test_remove_vector_suffix_from_stat_name_scalar(self):
        """Ensures correct output from remove_vector_suffix_from_stat_name.

        In this case, statistic is not a vector component.
        """

        this_basic_stat_name, this_vector_suffix = (
            sounding_stats.remove_vector_suffix_from_stat_name(
                statistic_name=STORM_VELOCITY_NAME,
                metadata_table=METADATA_TABLE))

        self.assertTrue(this_basic_stat_name == STORM_VELOCITY_NAME)
        self.assertTrue(this_vector_suffix is None)

    def test_remove_vector_suffix_from_stat_name_fake(self):
        """Ensures correct output from remove_vector_suffix_from_stat_name.

        In this case, statistic name is invalid.
        """

        with self.assertRaises(ValueError):
            sounding_stats.remove_vector_suffix_from_stat_name(
                statistic_name=FAKE_SOUNDING_STAT_NAME,
                metadata_table=METADATA_TABLE)

    def test_add_vector_suffix_to_stat_name(self):
        """Ensures correct output from add_vector_suffix_to_stat_name."""

        this_stat_name = sounding_stats.add_vector_suffix_to_stat_name(
            basic_statistic_name=STORM_VELOCITY_NAME,
            vector_suffix=sounding_stats.X_COMPONENT_SUFFIX)
        self.assertTrue(this_stat_name == STORM_VELOCITY_X_NAME)

    def test_get_nwp_fields_for_sounding_rap_no_dict(self):
        """Ensures correct output from _get_nwp_fields_for_sounding.

        In this case, model_name = "rap" and return_dict = False.
        """

        these_sounding_field_names, these_sounding_field_names_grib1 = (
            sounding_stats._get_nwp_fields_for_sounding(
                nwp_model_utils.RAP_MODEL_NAME,
                minimum_pressure_mb=MINIMUM_PRESSURE_MB, return_dict=False))

        self.assertTrue(set(these_sounding_field_names) ==
                        set(SOUNDING_FIELD_NAMES_RAP))
        self.assertTrue(set(these_sounding_field_names_grib1) ==
                        set(SOUNDING_FIELD_NAMES_GRIB1_RAP))

    def test_get_nwp_fields_for_sounding_narr_no_dict(self):
        """Ensures correct output from _get_nwp_fields_for_sounding.

        In this case, model_name = "narr" and return_dict = False.
        """

        these_sounding_field_names, these_sounding_field_names_grib1 = (
            sounding_stats._get_nwp_fields_for_sounding(
                nwp_model_utils.NARR_MODEL_NAME,
                minimum_pressure_mb=MINIMUM_PRESSURE_MB, return_dict=False))

        self.assertTrue(set(these_sounding_field_names) ==
                        set(SOUNDING_FIELD_NAMES_NARR))
        self.assertTrue(set(these_sounding_field_names_grib1) ==
                        set(SOUNDING_FIELD_NAMES_GRIB1_NARR))

    def test_get_nwp_fields_for_sounding_rap_dict(self):
        """Ensures correct output from _get_nwp_fields_for_sounding.

        In this case, model_name = "rap" and return_dict = True.
        """

        this_sounding_table_to_fields_dict, _ = (
            sounding_stats._get_nwp_fields_for_sounding(
                nwp_model_utils.RAP_MODEL_NAME,
                minimum_pressure_mb=MINIMUM_PRESSURE_MB, return_dict=True))

        self.assertTrue(this_sounding_table_to_fields_dict ==
                        SOUNDING_FIELD_DICT_RAP)

    def test_get_nwp_fields_for_sounding_narr_dict(self):
        """Ensures correct output from _get_nwp_fields_for_sounding.

        In this case, model_name = "narr" and return_dict = True.
        """

        this_sounding_table_to_fields_dict, _ = (
            sounding_stats._get_nwp_fields_for_sounding(
                nwp_model_utils.NARR_MODEL_NAME,
                minimum_pressure_mb=MINIMUM_PRESSURE_MB, return_dict=True))

        self.assertTrue(this_sounding_table_to_fields_dict ==
                        SOUNDING_FIELD_DICT_NARR)

    def test_remove_subsurface_pressure_levels_keep_rows(self):
        """Ensures correct output from _remove_subsurface_pressure_levels.

        In this case, delete_rows = False.
        """

        this_sounding_table = copy.deepcopy(SOUNDING_TABLE_SHARPPY_ORIG)
        this_sounding_table = sounding_stats._remove_subsurface_pressure_levels(
            this_sounding_table, delete_rows=False)
        self.assertTrue(
            this_sounding_table.equals(SOUNDING_TABLE_WITH_SENTINELS))

    def test_sort_sounding_by_height(self):
        """Ensures correct output from _sort_sounding_by_height."""

        this_input_table = copy.deepcopy(SOUNDING_TABLE_WITH_SENTINELS)
        this_sounding_table = sounding_stats._sort_sounding_by_height(
            this_input_table)
        this_sounding_table.reset_index(drop=True, inplace=True)

        self.assertTrue(
            this_sounding_table.equals(SOUNDING_TABLE_WITH_SENTINELS_SORTED))

    def test_remove_redundant_pressure_levels(self):
        """Ensures correct output from _remove_redundant_pressure_levels."""

        this_input_table = copy.deepcopy(SOUNDING_TABLE_WITH_SENTINELS_SORTED)
        this_sounding_table = sounding_stats._remove_redundant_pressure_levels(
            this_input_table)

        self.assertTrue(
            this_sounding_table.equals(SOUNDING_TABLE_NO_REDUNDANT))

    def test_remove_subsurface_pressure_levels_delete_rows(self):
        """Ensures correct output from _remove_subsurface_pressure_levels.

        In this case, delete_rows = True.
        """

        this_sounding_table = sounding_stats._remove_subsurface_pressure_levels(
            SOUNDING_TABLE_NO_REDUNDANT, delete_rows=True)
        self.assertTrue(
            this_sounding_table.equals(SOUNDING_TABLE_NO_SUBSURFACE))

    def test_split_vector_column_conversion_factor1(self):
        """Ensures correct output from _split_vector_column.

        In this case, conversion_factor = 1.
        """

        this_vector_component_dict = sounding_stats._split_vector_column(
            VECTOR_COLUMN_AS_TABLE, conversion_factor=1.)
        this_vector_component_table = pandas.DataFrame.from_dict(
            this_vector_component_dict)

        self.assertTrue(set(list(this_vector_component_table)) ==
                        set(list(VECTOR_COMPONENT_TABLE_CONV_FACTOR1)))

        for this_column in list(this_vector_component_table):
            self.assertTrue(numpy.allclose(
                this_vector_component_table[this_column].values,
                VECTOR_COMPONENT_TABLE_CONV_FACTOR1[this_column].values,
                atol=TOLERANCE))

    def test_split_vector_column_conversion_factor10(self):
        """Ensures correct output from _split_vector_column.

        In this case, conversion_factor = 10.
        """

        this_vector_component_dict = sounding_stats._split_vector_column(
            VECTOR_COLUMN_AS_TABLE, conversion_factor=10.)
        this_vector_component_table = pandas.DataFrame.from_dict(
            this_vector_component_dict)

        self.assertTrue(set(list(this_vector_component_table)) ==
                        set(list(VECTOR_COMPONENT_TABLE_CONV_FACTOR10)))

        for this_column in list(this_vector_component_table):
            self.assertTrue(numpy.allclose(
                this_vector_component_table[this_column].values,
                VECTOR_COMPONENT_TABLE_CONV_FACTOR10[this_column].values,
                atol=TOLERANCE))

    def test_sounding_to_sharppy_units_rap(self):
        """Ensures correct output from _sounding_to_sharppy_units.

        In this case, converting from RAP units to SHARPpy units.
        """

        this_sounding_table = sounding_stats._sounding_to_sharppy_units(
            SOUNDING_TABLE_RAP_UNITS)

        self.assertTrue(set(list(this_sounding_table)) ==
                        set(list(SOUNDING_TABLE_SHARPPY_ORIG)))

        for this_column in list(this_sounding_table):
            self.assertTrue(numpy.allclose(
                this_sounding_table[this_column].values,
                SOUNDING_TABLE_SHARPPY_ORIG[this_column].values,
                atol=TOLERANCE))

    def test_sounding_to_sharppy_units_narr(self):
        """Ensures correct output from _sounding_to_sharppy_units.

        In this case, converting from NARR units to SHARPpy units.
        """

        this_sounding_table = sounding_stats._sounding_to_sharppy_units(
            SOUNDING_TABLE_NARR_UNITS)

        self.assertTrue(set(list(this_sounding_table)) ==
                        set(list(SOUNDING_TABLE_SHARPPY_ORIG)))

        for this_column in list(this_sounding_table):
            self.assertTrue(numpy.allclose(
                this_sounding_table[this_column].values,
                SOUNDING_TABLE_SHARPPY_ORIG[this_column].values,
                atol=TOLERANCE))

    def test_sentinels_to_nan(self):
        """Ensures correct output from _sentinels_to_nan."""

        this_table = copy.deepcopy(STATISTIC_TABLE_SHARPPY_WITH_SENTINELS)
        this_table = sounding_stats._sentinels_to_nan(
            statistic_table_sharppy=this_table, metadata_table=METADATA_TABLE)
        this_num_soundings = len(this_table.index)

        expected_column_names = list(STATISTIC_TABLE_SHARPPY_WITH_NANS)
        actual_column_names = list(this_table)
        self.assertTrue(set(expected_column_names) == set(actual_column_names))

        for this_column in actual_column_names:
            if this_column == MEAN_WIND_0TO1KM_NAME_SHARPPY:
                for i in range(this_num_soundings):
                    self.assertTrue(numpy.allclose(
                        this_table[this_column].values[i],
                        STATISTIC_TABLE_SHARPPY_WITH_NANS[
                            this_column].values[i],
                        atol=TOLERANCE, equal_nan=True))

            else:
                self.assertTrue(numpy.allclose(
                    this_table[this_column].values,
                    STATISTIC_TABLE_SHARPPY_WITH_NANS[this_column].values,
                    atol=TOLERANCE, equal_nan=True))

    def test_convert_sounding_statistics(self):
        """Ensures correct output from _convert_sounding_statistics."""

        this_sounding_stat_table = (
            sounding_stats._convert_sounding_statistics(
                STATISTIC_TABLE_SHARPPY, METADATA_TABLE))

        self.assertTrue(set(list(this_sounding_stat_table)) ==
                        set(list(SOUNDING_STATISTIC_TABLE)))

        for this_column in list(this_sounding_stat_table):
            self.assertTrue(numpy.allclose(
                this_sounding_stat_table[this_column].values,
                SOUNDING_STATISTIC_TABLE[this_column].values, atol=TOLERANCE,
                equal_nan=True))

    def test_get_unique_storm_soundings(self):
        """Ensures correct output from _get_unique_storm_sounding_stats."""

        these_unique_indices, these_indices_orig_to_unique = (
            sounding_stats._get_unique_storm_soundings(
                LIST_OF_SOUNDING_TABLES, u_motions_m_s01=U_MOTIONS_M_S01,
                v_motions_m_s01=V_MOTIONS_M_S01))

        self.assertTrue(numpy.array_equal(these_unique_indices, UNIQUE_INDICES))
        self.assertTrue(numpy.array_equal(
            these_indices_orig_to_unique, ORIG_TO_UNIQUE_INDICES))

    def test_find_sounding_statistic_file(self):
        """Ensures correct output from find_sounding_statistic_file."""

        this_file_name = sounding_stats.find_sounding_statistic_file(
            top_directory_name=TOP_DIRECTORY_NAME,
            init_time_unix_sec=INIT_TIME_UNIX_SEC, lead_time_sec=LEAD_TIME_SEC,
            spc_date_string=SPC_DATE_STRING, raise_error_if_missing=False)
        self.assertTrue(this_file_name == SOUNDING_STATISTIC_FILE_NAME)


if __name__ == '__main__':
    unittest.main()
