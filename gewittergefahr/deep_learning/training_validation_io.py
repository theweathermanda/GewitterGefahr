"""IO methods for training and on-the-fly validation.

--- NOTATION ---

The following letters will be used throughout this module.

E = number of examples (storm objects)
M = number of rows in each radar image
N = number of columns in each radar image
H_r = number of radar heights
F_r = number of radar fields (or "variables" or "channels")
H_s = number of sounding heights
F_s = number of sounding fields (or "variables" or "channels")
C = number of radar field/height pairs
"""

import numpy
import keras
from gewittergefahr.deep_learning import deep_learning_utils as dl_utils
from gewittergefahr.deep_learning import data_augmentation
from gewittergefahr.deep_learning import input_examples
from gewittergefahr.gg_utils import target_val_utils
from gewittergefahr.gg_utils import radar_utils
from gewittergefahr.gg_utils import error_checking

KM_TO_METRES = 1000

EXAMPLE_FILES_KEY = 'example_file_names'
NUM_EXAMPLES_PER_BATCH_KEY = 'num_examples_per_batch'

RADAR_FIELDS_KEY = 'radar_field_names'
RADAR_HEIGHTS_KEY = 'radar_heights_m_agl'
SOUNDING_FIELDS_KEY = 'sounding_field_names'
SOUNDING_HEIGHTS_KEY = 'sounding_heights_m_agl'
FIRST_STORM_TIME_KEY = 'first_storm_time_unix_sec'
LAST_STORM_TIME_KEY = 'last_storm_time_unix_sec'
NUM_ROWS_KEY = 'num_grid_rows'
NUM_COLUMNS_KEY = 'num_grid_columns'

NORMALIZATION_TYPE_KEY = 'normalization_type_string'
NORMALIZATION_FILE_KEY = 'normalization_param_file_name'
MIN_NORMALIZED_VALUE_KEY = 'min_normalized_value'
MAX_NORMALIZED_VALUE_KEY = 'max_normalized_value'

BINARIZE_TARGET_KEY = 'binarize_target'
LOOP_ONCE_KEY = 'loop_thru_files_once'
REFLECTIVITY_MASK_KEY = 'refl_masking_threshold_dbz'
SAMPLING_FRACTIONS_KEY = 'class_to_sampling_fraction_dict'

X_TRANSLATIONS_KEY = 'x_translations_pixels'
Y_TRANSLATIONS_KEY = 'y_translations_pixels'
ROTATION_ANGLES_KEY = 'ccw_rotation_angles_deg'
NOISE_STDEV_KEY = 'noise_standard_deviation'
NUM_NOISINGS_KEY = 'num_noisings'
FLIP_X_KEY = 'flip_in_x'
FLIP_Y_KEY = 'flip_in_y'

DEFAULT_OPTION_DICT = {
    NORMALIZATION_TYPE_KEY: dl_utils.Z_NORMALIZATION_TYPE_STRING,
    MIN_NORMALIZED_VALUE_KEY: dl_utils.DEFAULT_MIN_NORMALIZED_VALUE,
    MAX_NORMALIZED_VALUE_KEY: dl_utils.DEFAULT_MAX_NORMALIZED_VALUE,
    BINARIZE_TARGET_KEY: False,
    LOOP_ONCE_KEY: False,
    REFLECTIVITY_MASK_KEY: dl_utils.DEFAULT_REFL_MASK_THRESHOLD_DBZ,
    SAMPLING_FRACTIONS_KEY: None,
    X_TRANSLATIONS_KEY: None,
    Y_TRANSLATIONS_KEY: None,
    ROTATION_ANGLES_KEY: None,
    NOISE_STDEV_KEY: 0.05,
    NUM_NOISINGS_KEY: 0,
    FLIP_X_KEY: False,
    FLIP_Y_KEY: False
}


def _get_batch_size_by_class(
        num_examples_per_batch, target_name, class_to_sampling_fraction_dict):
    """Returns number of examples needed per batch for each class.

    :param num_examples_per_batch: Total number of examples per batch.
    :param target_name: Name of target variable.
    :param class_to_sampling_fraction_dict: See doc for `generator_2d_or_3d`.
    :return: class_to_batch_size_dict: Dictionary, where each key is the integer
        representing a class (-2 for "dead storm") and the corresponding value
        is the number of examples in each batch.
    """

    num_extended_classes = target_val_utils.target_name_to_num_classes(
        target_name=target_name, include_dead_storms=True)

    if class_to_sampling_fraction_dict is None:
        num_classes = target_val_utils.target_name_to_num_classes(
            target_name=target_name, include_dead_storms=False)

        include_dead_storms = num_extended_classes > num_classes

        if include_dead_storms:
            first_keys = numpy.array(
                [target_val_utils.DEAD_STORM_INTEGER], dtype=int)

            second_keys = numpy.linspace(
                0, num_classes - 1, num=num_classes, dtype=int)

            keys = numpy.concatenate((first_keys, second_keys))
        else:
            keys = numpy.linspace(
                0, num_extended_classes - 1, num=num_extended_classes,
                dtype=int)

        values = numpy.full(
            num_extended_classes, num_examples_per_batch, dtype=int)
        return dict(zip(keys, values))

    return dl_utils.class_fractions_to_num_examples(
        sampling_fraction_by_class_dict=class_to_sampling_fraction_dict,
        target_name=target_name, num_examples_total=num_examples_per_batch)


def _get_remaining_batch_size_by_class(
        class_to_batch_size_dict, target_values_in_memory):
    """Returns number of remaining examples needed for each class.

    :param class_to_batch_size_dict: Dictionary created by
        `_get_batch_size_by_class`.
    :param target_values_in_memory: 1-D numpy array of target values (integer
        class labels).
    :return: class_to_rem_batch_size_dict: Same as input
        `class_to_batch_size_dict` but with different values.
    """

    if target_values_in_memory is None:
        return class_to_batch_size_dict

    class_to_rem_batch_size_dict = {}

    for this_class in class_to_batch_size_dict.keys():
        this_num_examples = (
            class_to_batch_size_dict[this_class] -
            numpy.sum(target_values_in_memory == this_class)
        )

        this_num_examples = max([this_num_examples, 0])
        class_to_rem_batch_size_dict.update({this_class: this_num_examples})

    return class_to_rem_batch_size_dict


def _check_stopping_criterion(
        num_examples_per_batch, class_to_batch_size_dict,
        class_to_sampling_fraction_dict, target_values_in_memory):
    """Evaluates stopping criterion for generator.

    :param num_examples_per_batch: Total number of examples per batch.
    :param class_to_batch_size_dict: Dictionary created by
        `_get_batch_size_by_class`.
    :param class_to_sampling_fraction_dict: Dictionary created by
        `_get_remaining_batch_size_by_class`.
    :param target_values_in_memory: 1-D numpy array of target values (integer
        class labels).
    :return: stop_generator: Boolean flag.
    """

    class_to_num_read_dict = {}

    for this_key in class_to_batch_size_dict:
        this_value = numpy.sum(target_values_in_memory == this_key)
        class_to_num_read_dict.update({this_key: this_value})

    print 'Number of examples in memory for each class:\n{0:s}\n'.format(
        str(class_to_num_read_dict))

    num_examples_in_memory = len(target_values_in_memory)
    stop_generator = num_examples_in_memory >= num_examples_per_batch

    if stop_generator and class_to_sampling_fraction_dict is not None:
        for this_key in class_to_batch_size_dict.keys():
            stop_generator = (
                stop_generator and
                class_to_num_read_dict[this_key] >=
                class_to_batch_size_dict[this_key]
            )

    return stop_generator


def _select_batch(
        list_of_predictor_matrices, target_values, num_examples_per_batch,
        binarize_target, num_classes):
    """Randomly selects batch from examples in memory.

    E = number of examples in memory
    e = number of examples in batch

    :param list_of_predictor_matrices: 1-D list of predictor matrices.  Each
        item should be a numpy array where the first axis has length E.
    :param target_values: length-E numpy array of target values (integer class
        labels).
    :param num_examples_per_batch: Total number of examples per batch.
    :param binarize_target: Boolean flag.  If True, target variable will be
        binarized, where the highest class becomes 1 and all other classes
        become 0.  If False, the original classes will be kept, in which case
        the prediction task may be binary or multiclass.
    :param num_classes: Number of classes for target variable.
    :return: list_of_predictor_matrices: Same as input, except the first axis of
        each array has length e.
    :return: target_array: See output doc for `generator_2d_or_3d`.
    """

    num_examples_in_memory = len(target_values)
    example_indices = numpy.linspace(
        0, num_examples_in_memory - 1, num=num_examples_in_memory, dtype=int)

    if num_examples_in_memory > num_examples_per_batch:
        batch_indices = numpy.random.choice(
            example_indices, size=num_examples_per_batch, replace=False)
    else:
        batch_indices = example_indices + 0

    for i in range(len(list_of_predictor_matrices)):
        if list_of_predictor_matrices[i] is None:
            continue

        list_of_predictor_matrices[i] = list_of_predictor_matrices[
            i][batch_indices, ...].astype('float32')

    target_values[target_values == target_val_utils.DEAD_STORM_INTEGER] = 0

    if binarize_target:
        target_values = (target_values == num_classes - 1).astype(int)
        num_classes_to_predict = 2
    else:
        num_classes_to_predict = num_classes + 0

    if num_classes_to_predict == 2:
        print 'Fraction of examples in positive class: {0:.3f}'.format(
            numpy.mean(target_values))
        return list_of_predictor_matrices, target_values

    target_matrix = keras.utils.to_categorical(
        target_values[batch_indices], num_classes_to_predict)

    class_fractions = numpy.mean(target_matrix, axis=0)
    print 'Fraction of examples in each class: {0:s}\n'.format(
        str(class_fractions))

    return list_of_predictor_matrices, target_matrix


def _augment_radar_images(
        list_of_predictor_matrices, target_array, x_translations_pixels,
        y_translations_pixels, ccw_rotation_angles_deg,
        noise_standard_deviation, num_noisings, flip_in_x, flip_in_y):
    """Applies one or more data augmentations to each radar image.

    P = number of predictor matrices
    T = number of translations applied to each image
    Q = number of augmentations applied to each image
    e = original number of examples
    E = e * (1 + Q) = number of examples after augmentation

    This method applies each augmentation separately, so a given image can be
    translated *or* rotated *or* noised.

    :param list_of_predictor_matrices: length-P list, where each item is a numpy
        array with the first axis having length e.
    :param target_array: See output doc for `generator_2d_or_3d`.  May have
        length e or dimensions of e x K.
    :param x_translations_pixels: length-T numpy array of translations in
        x-direction.  If you do not want translation, make this None.
    :param y_translations_pixels: length-T numpy array of translations in
        y-direction.  If you do not want translation, make this None.
    :param ccw_rotation_angles_deg: 1-D numpy array of counterclockwise rotation
        angles.  If you do not want rotation, make this None.
    :param noise_standard_deviation: Standard deviation for Gaussian noise.  If
        you do not want noising, make this None.
    :param num_noisings: Number of times to replicate each example with noise.
        If you do not want noising, make this None.
    :param flip_in_x: Boolean flag.  If True, each radar image will be flipped
        in the x-direction.
    :param flip_in_y: Boolean flag.  If True, each radar image will be flipped
        in the y-direction.
    :return: list_of_predictor_matrices: Same as input, except the first axis of
        each array now has length E.
    :return: target_array: Same as input, except dimensions are now either
        length-E or E x K.
    """

    if x_translations_pixels is None and y_translations_pixels is None:
        num_translations = 0
    else:
        error_checking.assert_is_integer_numpy_array(x_translations_pixels)
        error_checking.assert_is_numpy_array(
            x_translations_pixels, num_dimensions=1)
        num_translations = len(x_translations_pixels)

        error_checking.assert_is_integer_numpy_array(y_translations_pixels)
        error_checking.assert_is_numpy_array(
            y_translations_pixels,
            exact_dimensions=numpy.array([num_translations])
        )

        error_checking.assert_is_greater_numpy_array(
            numpy.absolute(x_translations_pixels) +
            numpy.absolute(y_translations_pixels),
            0
        )

    if ccw_rotation_angles_deg is None:
        num_rotations = 0
    else:
        error_checking.assert_is_numpy_array_without_nan(
            ccw_rotation_angles_deg)
        error_checking.assert_is_numpy_array(
            ccw_rotation_angles_deg, num_dimensions=1)

        num_rotations = len(ccw_rotation_angles_deg)

    error_checking.assert_is_integer(num_noisings)
    error_checking.assert_is_geq(num_noisings, 0)
    error_checking.assert_is_boolean(flip_in_x)
    error_checking.assert_is_boolean(flip_in_y)

    last_num_dimensions = len(list_of_predictor_matrices[-1].shape)
    soundings_included = last_num_dimensions == 3
    num_radar_matrices = (
        len(list_of_predictor_matrices) - int(soundings_included)
    )

    print (
        'Augmenting radar images ({0:d} translations, {1:d} rotations, {2:d} '
        'noisings, {3:d} x-flips, and {4:d} y-flips each)...'
    ).format(
        num_translations, num_rotations, num_noisings, int(flip_in_x),
        int(flip_in_y)
    )

    orig_num_examples = list_of_predictor_matrices[0].shape[0]

    for i in range(num_translations):
        for j in range(num_radar_matrices):
            this_multiplier = j + 1  # Handles azimuthal shear.

            this_image_matrix = data_augmentation.shift_radar_images(
                radar_image_matrix=
                list_of_predictor_matrices[j][:orig_num_examples, ...],
                x_offset_pixels=this_multiplier * x_translations_pixels[i],
                y_offset_pixels=this_multiplier * y_translations_pixels[i])

            list_of_predictor_matrices[j] = numpy.concatenate(
                (list_of_predictor_matrices[j], this_image_matrix), axis=0)

        target_array = numpy.concatenate(
            (target_array, target_array[:orig_num_examples, ...]), axis=0)

        if soundings_included:
            list_of_predictor_matrices[-1] = numpy.concatenate(
                (list_of_predictor_matrices[-1],
                 list_of_predictor_matrices[-1][:orig_num_examples, ...]),
                axis=0)

    for i in range(num_rotations):
        for j in range(num_radar_matrices):
            this_image_matrix = data_augmentation.rotate_radar_images(
                radar_image_matrix=
                list_of_predictor_matrices[j][:orig_num_examples, ...],
                ccw_rotation_angle_deg=ccw_rotation_angles_deg[i])

            list_of_predictor_matrices[j] = numpy.concatenate(
                (list_of_predictor_matrices[j], this_image_matrix), axis=0)

        target_array = numpy.concatenate(
            (target_array, target_array[:orig_num_examples, ...]), axis=0)

        if soundings_included:
            list_of_predictor_matrices[-1] = numpy.concatenate(
                (list_of_predictor_matrices[-1],
                 list_of_predictor_matrices[-1][:orig_num_examples, ...]),
                axis=0)

    for i in range(num_noisings):
        for j in range(num_radar_matrices):
            this_image_matrix = data_augmentation.noise_radar_images(
                radar_image_matrix=
                list_of_predictor_matrices[j][:orig_num_examples, ...],
                standard_deviation=noise_standard_deviation)

            list_of_predictor_matrices[j] = numpy.concatenate(
                (list_of_predictor_matrices[j], this_image_matrix), axis=0)

        target_array = numpy.concatenate(
            (target_array, target_array[:orig_num_examples, ...]), axis=0)

        if soundings_included:
            list_of_predictor_matrices[-1] = numpy.concatenate(
                (list_of_predictor_matrices[-1],
                 list_of_predictor_matrices[-1][:orig_num_examples, ...]),
                axis=0)

    if flip_in_x:
        for j in range(num_radar_matrices):
            this_image_matrix = data_augmentation.flip_radar_images_x(
                list_of_predictor_matrices[j][:orig_num_examples, ...]
            )

            list_of_predictor_matrices[j] = numpy.concatenate(
                (list_of_predictor_matrices[j], this_image_matrix), axis=0)

        target_array = numpy.concatenate(
            (target_array, target_array[:orig_num_examples, ...]), axis=0)

        if soundings_included:
            list_of_predictor_matrices[-1] = numpy.concatenate(
                (list_of_predictor_matrices[-1],
                 list_of_predictor_matrices[-1][:orig_num_examples, ...]),
                axis=0)

    if flip_in_y:
        for j in range(num_radar_matrices):
            this_image_matrix = data_augmentation.flip_radar_images_y(
                list_of_predictor_matrices[j][:orig_num_examples, ...]
            )

            list_of_predictor_matrices[j] = numpy.concatenate(
                (list_of_predictor_matrices[j], this_image_matrix), axis=0)

        target_array = numpy.concatenate(
            (target_array, target_array[:orig_num_examples, ...]), axis=0)

        if soundings_included:
            list_of_predictor_matrices[-1] = numpy.concatenate(
                (list_of_predictor_matrices[-1],
                 list_of_predictor_matrices[-1][:orig_num_examples, ...]),
                axis=0)

    return list_of_predictor_matrices, target_array


def check_generator_args(option_dict):
    """Error-checks input arguments for generator.

    :param option_dict: See doc for any generator in this file.
    :return: option_dict: Same as input, except defaults may have been added.
    """

    orig_option_dict = option_dict.copy()
    option_dict = DEFAULT_OPTION_DICT.copy()
    option_dict.update(orig_option_dict)

    error_checking.assert_is_string_list(option_dict[EXAMPLE_FILES_KEY])
    error_checking.assert_is_numpy_array(
        numpy.array(option_dict[EXAMPLE_FILES_KEY]), num_dimensions=1)

    error_checking.assert_is_integer(option_dict[NUM_EXAMPLES_PER_BATCH_KEY])
    error_checking.assert_is_geq(option_dict[NUM_EXAMPLES_PER_BATCH_KEY], 32)
    error_checking.assert_is_boolean(option_dict[BINARIZE_TARGET_KEY])
    error_checking.assert_is_boolean(option_dict[LOOP_ONCE_KEY])

    return option_dict


def generator_2d_or_3d(option_dict):
    """Generates examples with either 2-D or 3-D radar images.

    Each example (storm object) consists of the following:

    - Storm-centered radar images (either one 2-D image for each field/height
      pair or one 3-D image for each field)
    - Storm-centered sounding (optional)
    - Target value (class)

    :param option_dict: Dictionary with the following keys.
    option_dict['example_file_names']: 1-D list of paths to input files (will be
        read by `input_examples.read_example_file`).
    option_dict['num_examples_per_batch']: Number of examples in each batch.
    option_dict['binarize_target']: Boolean flag.  If True, target variable will
        be binarized, where the highest class becomes 1 and all other classes
        become 0.  If False, the original classes will be kept, in which case
        the prediction task may be binary or multiclass.
    option_dict['loop_thru_files_once']: Boolean flag.  If True, this generator
        will read only once from each file.  If False, once this generator has
        reached the last file, it will start over at the first file.
    option_dict['radar_field_names']: 1-D list of radar fields.  See
        `input_examples.read_example_file` for details.
    option_dict['radar_heights_m_agl']: 1-D numpy array of radar heights (metres
        above ground level).  See `input_examples.read_example_file` for
        details.
    option_dict['sounding_field_names']: 1-D list of sounding fields.  See
        `input_examples.read_example_file` for details.  If you want do not want
        to use soundings, make this None.
    option_dict['sounding_heights_m_agl']: 1-D numpy array of sounding heights
        (metres above ground level).  See `input_examples.read_example_file` for
        details.
    option_dict['first_storm_time_unix_sec']: First storm time.  This generator
        will discard examples outside the period `first_storm_time_unix_sec`...
        `last_storm_time_unix_sec`.
    option_dict['last_storm_time_unix_sec']: See above.
    option_dict['num_grid_rows']: Number of rows in each radar image.
    option_dict['num_grid_columns']: Number of columns in each radar image.
    option_dict['normalization_type_string']: Normalization type (used for both
        radar images and soundings).  See
        `deep_learning_utils.normalize_radar_images` or
        `deep_learning_utils.normalize_soundings` for details.
    option_dict['normalization_param_file_name']: Path to file with
        normalization params.  See the above-mentioned methods for details.
    option_dict['min_normalized_value']: Minimum value for min-max
        normalization.  See the above-mentioned methods for details.
    option_dict['max_normalized_value']: Max value for min-max normalization.
        See the above-mentioned methods for details.
    option_dict['class_to_sampling_fraction_dict']: Used for downsampling.  See
        `deep_learning_utils.sample_by_class` for details.  If you do not want
        downsampling, make this None.
    option_dict['refl_masking_threshold_dbz']: Reflectivity mask, used only for
        3-D images.  Any grid cell (voxel) with reflectivity < threshold is
        masked out.
    option_dict['x_translations_pixels']: Used for data augmentation.  See doc
        for `_augment_radar_images`.
    option_dict['y_translations_pixels']: Same.
    option_dict['ccw_rotation_angles_deg']: Same.
    option_dict['noise_standard_deviation']: Same.
    option_dict['num_noisings']: Same.
    option_dict['flip_in_x']: Same.
    option_dict['flip_in_y']: Same.

    If `sounding_field_names is None`...

    :return: radar_image_matrix: numpy array (E x M x N x C or
        E x M x N x H_r x F_r) of storm-centered radar images.
    :return: target_array: If problem is multiclass and
        `binarize_target = False`, this is an E-by-K numpy array of zeros and
        ones.  If target_array[i, k] = 1, the [i]th example belongs to the [k]th
        class.

        If problem is binary or `binarize_target = True`, this is a length-E
        numpy array of zeros and ones.

    If `sounding_field_names is not None`...

    :return: predictor_list: List with the following items.
    predictor_list[0] = radar_image_matrix: See above.
    predictor_list[1] = sounding_matrix: numpy array (E x H_s x F_s) of storm-
        centered soundings.
    :return: target_array: See above.
    """

    option_dict = check_generator_args(option_dict)

    example_file_names = option_dict[EXAMPLE_FILES_KEY]
    num_examples_per_batch = option_dict[NUM_EXAMPLES_PER_BATCH_KEY]

    first_storm_time_unix_sec = option_dict[FIRST_STORM_TIME_KEY]
    last_storm_time_unix_sec = option_dict[LAST_STORM_TIME_KEY]
    num_grid_rows = option_dict[NUM_ROWS_KEY]
    num_grid_columns = option_dict[NUM_COLUMNS_KEY]
    radar_field_names = option_dict[RADAR_FIELDS_KEY]
    radar_heights_m_agl = option_dict[RADAR_HEIGHTS_KEY]
    sounding_field_names = option_dict[SOUNDING_FIELDS_KEY]
    sounding_heights_m_agl = option_dict[SOUNDING_HEIGHTS_KEY]

    normalization_type_string = option_dict[NORMALIZATION_TYPE_KEY]
    normalization_param_file_name = option_dict[NORMALIZATION_FILE_KEY]
    min_normalized_value = option_dict[MIN_NORMALIZED_VALUE_KEY]
    max_normalized_value = option_dict[MAX_NORMALIZED_VALUE_KEY]

    binarize_target = option_dict[BINARIZE_TARGET_KEY]
    loop_thru_files_once = option_dict[LOOP_ONCE_KEY]
    refl_masking_threshold_dbz = option_dict[REFLECTIVITY_MASK_KEY]
    class_to_sampling_fraction_dict = option_dict[SAMPLING_FRACTIONS_KEY]

    x_translations_pixels = option_dict[X_TRANSLATIONS_KEY]
    y_translations_pixels = option_dict[Y_TRANSLATIONS_KEY]
    ccw_rotation_angles_deg = option_dict[ROTATION_ANGLES_KEY]
    noise_standard_deviation = option_dict[NOISE_STDEV_KEY]
    num_noisings = option_dict[NUM_NOISINGS_KEY]
    flip_in_x = option_dict[FLIP_X_KEY]
    flip_in_y = option_dict[FLIP_Y_KEY]

    this_example_dict = input_examples.read_example_file(
        netcdf_file_name=example_file_names[0], metadata_only=True)
    target_name = this_example_dict[input_examples.TARGET_NAME_KEY]

    class_to_batch_size_dict = _get_batch_size_by_class(
        num_examples_per_batch=num_examples_per_batch, target_name=target_name,
        class_to_sampling_fraction_dict=class_to_sampling_fraction_dict)

    num_classes = target_val_utils.target_name_to_num_classes(
        target_name=target_name, include_dead_storms=False)

    radar_image_matrix = None
    sounding_matrix = None
    target_values = None

    file_index = 0
    include_soundings = False
    num_radar_dimensions = -1

    while True:
        if loop_thru_files_once and file_index >= len(example_file_names):
            raise StopIteration

        stop_generator = False
        while not stop_generator:
            if file_index == len(example_file_names):
                if loop_thru_files_once:
                    if target_values is None:
                        raise StopIteration
                    break

                file_index = 0

            class_to_rem_batch_size_dict = _get_remaining_batch_size_by_class(
                class_to_batch_size_dict=class_to_batch_size_dict,
                target_values_in_memory=target_values)

            print 'Reading data from: "{0:s}"...'.format(
                example_file_names[file_index])
            this_example_dict = input_examples.read_example_file(
                netcdf_file_name=example_file_names[file_index],
                include_soundings=sounding_field_names is not None,
                radar_field_names_to_keep=radar_field_names,
                radar_heights_to_keep_m_agl=radar_heights_m_agl,
                sounding_field_names_to_keep=sounding_field_names,
                sounding_heights_to_keep_m_agl=sounding_heights_m_agl,
                first_time_to_keep_unix_sec=first_storm_time_unix_sec,
                last_time_to_keep_unix_sec=last_storm_time_unix_sec,
                num_rows_to_keep=num_grid_rows,
                num_columns_to_keep=num_grid_columns,
                class_to_num_examples_dict=class_to_rem_batch_size_dict)

            file_index += 1
            if this_example_dict is None:
                continue

            include_soundings = (
                input_examples.SOUNDING_MATRIX_KEY in this_example_dict)
            num_radar_dimensions = len(
                this_example_dict[input_examples.RADAR_IMAGE_MATRIX_KEY].shape
            ) - 2

            if target_values is None:
                radar_image_matrix = (
                    this_example_dict[input_examples.RADAR_IMAGE_MATRIX_KEY]
                    + 0.
                )
                target_values = (
                    this_example_dict[input_examples.TARGET_VALUES_KEY] + 0)

                if include_soundings:
                    sounding_matrix = (
                        this_example_dict[input_examples.SOUNDING_MATRIX_KEY]
                        + 0.
                    )
            else:
                radar_image_matrix = numpy.concatenate(
                    (radar_image_matrix,
                     this_example_dict[input_examples.RADAR_IMAGE_MATRIX_KEY]),
                    axis=0)
                target_values = numpy.concatenate((
                    target_values,
                    this_example_dict[input_examples.TARGET_VALUES_KEY]
                ))

                if include_soundings:
                    sounding_matrix = numpy.concatenate(
                        (sounding_matrix,
                         this_example_dict[input_examples.SOUNDING_MATRIX_KEY]),
                        axis=0)

            stop_generator = _check_stopping_criterion(
                num_examples_per_batch=num_examples_per_batch,
                class_to_batch_size_dict=class_to_batch_size_dict,
                class_to_sampling_fraction_dict=class_to_sampling_fraction_dict,
                target_values_in_memory=target_values)

        if class_to_sampling_fraction_dict is not None:
            indices_to_keep = dl_utils.sample_by_class(
                sampling_fraction_by_class_dict=class_to_sampling_fraction_dict,
                target_name=target_name, target_values=target_values,
                num_examples_total=num_examples_per_batch)

            radar_image_matrix = radar_image_matrix[indices_to_keep, ...]
            target_values = target_values[indices_to_keep]
            if include_soundings:
                sounding_matrix = sounding_matrix[indices_to_keep, ...]

        if refl_masking_threshold_dbz is not None and num_radar_dimensions == 3:
            radar_image_matrix = dl_utils.mask_low_reflectivity_pixels(
                radar_image_matrix_3d=radar_image_matrix,
                field_names=radar_field_names,
                reflectivity_threshold_dbz=refl_masking_threshold_dbz)

        if normalization_type_string is not None:
            radar_image_matrix = dl_utils.normalize_radar_images(
                radar_image_matrix=radar_image_matrix,
                field_names=radar_field_names,
                normalization_type_string=normalization_type_string,
                normalization_param_file_name=normalization_param_file_name,
                min_normalized_value=min_normalized_value,
                max_normalized_value=max_normalized_value).astype('float32')

            if include_soundings:
                sounding_matrix = dl_utils.normalize_soundings(
                    sounding_matrix=sounding_matrix,
                    field_names=sounding_field_names,
                    normalization_type_string=normalization_type_string,
                    normalization_param_file_name=normalization_param_file_name,
                    min_normalized_value=min_normalized_value,
                    max_normalized_value=max_normalized_value).astype('float32')

        list_of_predictor_matrices, target_array = _select_batch(
            list_of_predictor_matrices=[radar_image_matrix, sounding_matrix],
            target_values=target_values,
            num_examples_per_batch=num_examples_per_batch,
            binarize_target=binarize_target, num_classes=num_classes)

        list_of_predictor_matrices, target_array = _augment_radar_images(
            list_of_predictor_matrices=list_of_predictor_matrices,
            target_array=target_array,
            x_translations_pixels=x_translations_pixels,
            y_translations_pixels=y_translations_pixels,
            ccw_rotation_angles_deg=ccw_rotation_angles_deg,
            noise_standard_deviation=noise_standard_deviation,
            num_noisings=num_noisings, flip_in_x=flip_in_x, flip_in_y=flip_in_y)

        radar_image_matrix = None
        sounding_matrix = None
        target_values = None

        if include_soundings:
            yield (list_of_predictor_matrices, target_array)
        else:
            yield (list_of_predictor_matrices[0], target_array)


def myrorss_generator_2d3d(option_dict):
    """Generates examples with both 2-D and 3-D radar images.

    Each example (storm object) consists of the following:

    - Storm-centered azimuthal shear (one 2-D image for each field)
    - Storm-centered reflectivity (one 3-D image)
    - Storm-centered sounding (optional)
    - Target value (class)

    M = number of rows in each reflectivity image
    N = number of columns in each reflectivity image

    :param option_dict: Dictionary with the following keys.
    option_dict['example_file_names']: See doc for `generator_2d_or_3d`.
    option_dict['num_examples_per_batch']: Same.
    option_dict['binarize_target']: Same.
    option_dict['loop_thru_files_once']: Same.
    option_dict['radar_field_names']: 1-D list of azimuthal-shear fields.  See
        `input_examples.read_example_file` for details.
    option_dict['radar_heights_m_agl']: 1-D numpy array of reflectivity heights
        (metres above ground level).  See `input_examples.read_example_file` for
        details.
    option_dict['sounding_field_names']: See doc for `generator_2d_or_3d`.
    option_dict['sounding_heights_m_agl']: Same.
    option_dict['first_storm_time_unix_sec']: Same.
    option_dict['last_storm_time_unix_sec']: Same.
    option_dict['num_grid_rows']: Number of rows in each reflectivity image
        (azimuthal-shear images will have twice as many rows).
    option_dict['num_grid_columns']: Number of columns in each reflectivity
        image (azimuthal-shear images will have twice as many columns).
    option_dict['normalization_type_string']: See doc for `generator_2d_or_3d`.
    option_dict['normalization_param_file_name']: Same.
    option_dict['min_normalized_value']: Same.
    option_dict['max_normalized_value']: Same.
    option_dict['class_to_sampling_fraction_dict']: Same.
    option_dict['x_translations_pixels']: Same.
    option_dict['y_translations_pixels']: Same.
    option_dict['ccw_rotation_angles_deg']: Same.
    option_dict['noise_standard_deviation']: Same.
    option_dict['num_noisings']: Same.
    option_dict['flip_in_x']: Same.
    option_dict['flip_in_y']: Same.

    :return: predictor_list: List with the following items.
    predictor_list[0] = reflectivity_image_matrix_dbz: numpy array
        (E x M x N x H_r x 1) of storm-centered reflectivity images.
    predictor_list[1] = az_shear_image_matrix_s01: numpy array (E x 2M x 2N x C)
        of storm-centered azimuthal-shear images.
    predictor_list[2] = sounding_matrix: numpy array (E x H_s x F_s) of storm-
        centered soundings.  If `sounding_field_names is None`, this item does
        not exist.

    :return: target_array: See doc for `generator_2d_or_3d`.
    """

    option_dict = check_generator_args(option_dict)

    example_file_names = option_dict[EXAMPLE_FILES_KEY]
    num_examples_per_batch = option_dict[NUM_EXAMPLES_PER_BATCH_KEY]

    azimuthal_shear_field_names = option_dict[RADAR_FIELDS_KEY]
    reflectivity_heights_m_agl = option_dict[RADAR_HEIGHTS_KEY]
    sounding_field_names = option_dict[SOUNDING_FIELDS_KEY]
    sounding_heights_m_agl = option_dict[SOUNDING_HEIGHTS_KEY]
    first_storm_time_unix_sec = option_dict[FIRST_STORM_TIME_KEY]
    last_storm_time_unix_sec = option_dict[LAST_STORM_TIME_KEY]
    num_grid_rows = option_dict[NUM_ROWS_KEY]
    num_grid_columns = option_dict[NUM_COLUMNS_KEY]

    normalization_type_string = option_dict[NORMALIZATION_TYPE_KEY]
    normalization_param_file_name = option_dict[NORMALIZATION_FILE_KEY]
    min_normalized_value = option_dict[MIN_NORMALIZED_VALUE_KEY]
    max_normalized_value = option_dict[MAX_NORMALIZED_VALUE_KEY]

    binarize_target = option_dict[BINARIZE_TARGET_KEY]
    loop_thru_files_once = option_dict[LOOP_ONCE_KEY]
    class_to_sampling_fraction_dict = option_dict[SAMPLING_FRACTIONS_KEY]

    x_translations_pixels = option_dict[X_TRANSLATIONS_KEY]
    y_translations_pixels = option_dict[Y_TRANSLATIONS_KEY]
    ccw_rotation_angles_deg = option_dict[ROTATION_ANGLES_KEY]
    noise_standard_deviation = option_dict[NOISE_STDEV_KEY]
    num_noisings = option_dict[NUM_NOISINGS_KEY]
    flip_in_x = option_dict[FLIP_X_KEY]
    flip_in_y = option_dict[FLIP_Y_KEY]

    this_example_dict = input_examples.read_example_file(
        netcdf_file_name=example_file_names[0], metadata_only=True)
    target_name = this_example_dict[input_examples.TARGET_NAME_KEY]

    class_to_batch_size_dict = _get_batch_size_by_class(
        num_examples_per_batch=num_examples_per_batch, target_name=target_name,
        class_to_sampling_fraction_dict=class_to_sampling_fraction_dict)

    num_classes = target_val_utils.target_name_to_num_classes(
        target_name=target_name, include_dead_storms=False)

    reflectivity_image_matrix_dbz = None
    az_shear_image_matrix_s01 = None
    sounding_matrix = None
    target_values = None

    file_index = 0
    include_soundings = False

    while True:
        if loop_thru_files_once and file_index >= len(example_file_names):
            raise StopIteration

        stop_generator = False
        while not stop_generator:
            if file_index == len(example_file_names):
                if loop_thru_files_once:
                    if target_values is None:
                        raise StopIteration
                    break

                file_index = 0

            class_to_rem_batch_size_dict = _get_remaining_batch_size_by_class(
                class_to_batch_size_dict=class_to_batch_size_dict,
                target_values_in_memory=target_values)

            print 'Reading data from: "{0:s}"...'.format(
                example_file_names[file_index])
            this_example_dict = input_examples.read_example_file(
                netcdf_file_name=example_file_names[file_index],
                include_soundings=sounding_field_names is not None,
                radar_field_names_to_keep=azimuthal_shear_field_names,
                radar_heights_to_keep_m_agl=reflectivity_heights_m_agl,
                sounding_field_names_to_keep=sounding_field_names,
                sounding_heights_to_keep_m_agl=sounding_heights_m_agl,
                first_time_to_keep_unix_sec=first_storm_time_unix_sec,
                last_time_to_keep_unix_sec=last_storm_time_unix_sec,
                num_rows_to_keep=num_grid_rows,
                num_columns_to_keep=num_grid_columns,
                class_to_num_examples_dict=class_to_rem_batch_size_dict)

            file_index += 1
            if this_example_dict is None:
                continue

            include_soundings = (
                input_examples.SOUNDING_MATRIX_KEY in this_example_dict)

            if target_values is None:
                reflectivity_image_matrix_dbz = (
                    this_example_dict[input_examples.REFL_IMAGE_MATRIX_KEY] + 0.
                )
                az_shear_image_matrix_s01 = (
                    this_example_dict[input_examples.AZ_SHEAR_IMAGE_MATRIX_KEY]
                    + 0.
                )
                target_values = (
                    this_example_dict[input_examples.TARGET_VALUES_KEY] + 0)

                if include_soundings:
                    sounding_matrix = (
                        this_example_dict[input_examples.SOUNDING_MATRIX_KEY]
                        + 0.
                    )
            else:
                reflectivity_image_matrix_dbz = numpy.concatenate(
                    (reflectivity_image_matrix_dbz,
                     this_example_dict[input_examples.REFL_IMAGE_MATRIX_KEY]),
                    axis=0)
                az_shear_image_matrix_s01 = numpy.concatenate((
                    az_shear_image_matrix_s01,
                    this_example_dict[input_examples.AZ_SHEAR_IMAGE_MATRIX_KEY]
                ), axis=0)
                target_values = numpy.concatenate((
                    target_values,
                    this_example_dict[input_examples.TARGET_VALUES_KEY]
                ))

                if include_soundings:
                    sounding_matrix = numpy.concatenate(
                        (sounding_matrix,
                         this_example_dict[input_examples.SOUNDING_MATRIX_KEY]),
                        axis=0)

            stop_generator = _check_stopping_criterion(
                num_examples_per_batch=num_examples_per_batch,
                class_to_batch_size_dict=class_to_batch_size_dict,
                class_to_sampling_fraction_dict=class_to_sampling_fraction_dict,
                target_values_in_memory=target_values)

        if class_to_sampling_fraction_dict is not None:
            indices_to_keep = dl_utils.sample_by_class(
                sampling_fraction_by_class_dict=class_to_sampling_fraction_dict,
                target_name=target_name, target_values=target_values,
                num_examples_total=num_examples_per_batch)

            reflectivity_image_matrix_dbz = reflectivity_image_matrix_dbz[
                indices_to_keep, ...]
            az_shear_image_matrix_s01 = az_shear_image_matrix_s01[
                indices_to_keep, ...]
            target_values = target_values[indices_to_keep]
            if include_soundings:
                sounding_matrix = sounding_matrix[indices_to_keep, ...]

        if normalization_type_string is not None:
            reflectivity_image_matrix_dbz = dl_utils.normalize_radar_images(
                radar_image_matrix=reflectivity_image_matrix_dbz,
                field_names=[radar_utils.REFL_NAME],
                normalization_type_string=normalization_type_string,
                normalization_param_file_name=normalization_param_file_name,
                min_normalized_value=min_normalized_value,
                max_normalized_value=max_normalized_value).astype('float32')

            az_shear_image_matrix_s01 = dl_utils.normalize_radar_images(
                radar_image_matrix=az_shear_image_matrix_s01,
                field_names=azimuthal_shear_field_names,
                normalization_type_string=normalization_type_string,
                normalization_param_file_name=normalization_param_file_name,
                min_normalized_value=min_normalized_value,
                max_normalized_value=max_normalized_value).astype('float32')

            if include_soundings:
                sounding_matrix = dl_utils.normalize_soundings(
                    sounding_matrix=sounding_matrix,
                    field_names=sounding_field_names,
                    normalization_type_string=normalization_type_string,
                    normalization_param_file_name=normalization_param_file_name,
                    min_normalized_value=min_normalized_value,
                    max_normalized_value=max_normalized_value).astype('float32')

        list_of_predictor_matrices, target_array = _select_batch(
            list_of_predictor_matrices=[
                reflectivity_image_matrix_dbz, az_shear_image_matrix_s01,
                sounding_matrix
            ],
            target_values=target_values,
            num_examples_per_batch=num_examples_per_batch,
            binarize_target=binarize_target, num_classes=num_classes)

        list_of_predictor_matrices, target_array = _augment_radar_images(
            list_of_predictor_matrices=list_of_predictor_matrices,
            target_array=target_array,
            x_translations_pixels=x_translations_pixels,
            y_translations_pixels=y_translations_pixels,
            ccw_rotation_angles_deg=ccw_rotation_angles_deg,
            noise_standard_deviation=noise_standard_deviation,
            num_noisings=num_noisings, flip_in_x=flip_in_x, flip_in_y=flip_in_y)

        reflectivity_image_matrix_dbz = None
        az_shear_image_matrix_s01 = None
        sounding_matrix = None
        target_values = None

        if include_soundings:
            yield (list_of_predictor_matrices, target_array)
        else:
            yield (list_of_predictor_matrices[:-1], target_array)


def layer_ops_to_field_height_pairs(list_of_operation_dicts):
    """Converts list of layer operations to list of field-height pairs.

    These are the radar field-height pairs needed for input to the layer
    operations.

    :param list_of_operation_dicts: See doc for
        `input_examples.reduce_examples_3d_to_2d`.
    :return: unique_radar_field_names: 1-D list of field names.
    :return: unique_radar_heights_m_agl: 1-D numpy array of unique heights
        (metres above ground level).
    """

    unique_radar_field_names = [
        d[input_examples.RADAR_FIELD_KEY] for d in list_of_operation_dicts
    ]
    unique_radar_field_names = list(set(unique_radar_field_names))

    min_heights_m_agl = numpy.array([
        d[input_examples.MIN_HEIGHT_KEY] for d in list_of_operation_dicts
    ], dtype=int)

    max_heights_m_agl = numpy.array([
        d[input_examples.MAX_HEIGHT_KEY] for d in list_of_operation_dicts
    ], dtype=int)

    min_overall_height_m_agl = numpy.min(min_heights_m_agl)
    max_overall_height_m_agl = numpy.max(max_heights_m_agl)
    num_overall_heights = 1 + int(numpy.round(
        (max_overall_height_m_agl - min_overall_height_m_agl) / KM_TO_METRES
    ))

    unique_radar_heights_m_agl = numpy.linspace(
        min_overall_height_m_agl, max_overall_height_m_agl,
        num=num_overall_heights, dtype=int)

    return unique_radar_field_names, unique_radar_heights_m_agl


def gridrad_generator_2d_reduced(option_dict, list_of_operation_dicts):
    """Generates examples with 2-D GridRad images.

    These 2-D images are produced by applying layer operations to the native 3-D
    images.  The layer operations are specified by `list_of_operation_dicts`.

    Each example (storm object) consists of the following:

    - Storm-centered radar images (one 2-D image for each layer operation)
    - Storm-centered sounding (optional)
    - Target value (class)

    :param option_dict: Dictionary with the following keys.
    option_dict['example_file_names']: See doc for `generator_2d_or_3d`.
    option_dict['num_examples_per_batch']: Same.
    option_dict['binarize_target']: Same.
    option_dict['loop_thru_files_once']: Same.
    option_dict['sounding_field_names']: Same.
    option_dict['sounding_heights_m_agl']: Same.
    option_dict['first_storm_time_unix_sec']: Same.
    option_dict['last_storm_time_unix_sec']: Same.
    option_dict['num_grid_rows']: Same.
    option_dict['num_grid_columns']: Same.
    option_dict['normalization_type_string']: Same.
    option_dict['normalization_param_file_name']: Same.
    option_dict['min_normalized_value']: Same.
    option_dict['max_normalized_value']: Same.
    option_dict['class_to_sampling_fraction_dict']: Same.
    option_dict['x_translations_pixels']: Same.
    option_dict['y_translations_pixels']: Same.
    option_dict['ccw_rotation_angles_deg']: Same.
    option_dict['noise_standard_deviation']: Same.
    option_dict['num_noisings']: Same.
    option_dict['flip_in_x']: Same.
    option_dict['flip_in_y']: Same.

    :param list_of_operation_dicts: See doc for
        `input_examples.reduce_examples_3d_to_2d`.

    If `sounding_field_names is None`...

    :return: radar_image_matrix: See doc for `generator_2d_or_3d`.
    :return: target_array: Same.

    If `sounding_field_names is not None`...

    :return: predictor_list: See doc for `generator_2d_or_3d`.
    :return: target_array: Same.
    """

    option_dict = check_generator_args(option_dict)

    example_file_names = option_dict[EXAMPLE_FILES_KEY]
    num_examples_per_batch = option_dict[NUM_EXAMPLES_PER_BATCH_KEY]

    sounding_field_names = option_dict[SOUNDING_FIELDS_KEY]
    sounding_heights_m_agl = option_dict[SOUNDING_HEIGHTS_KEY]
    first_storm_time_unix_sec = option_dict[FIRST_STORM_TIME_KEY]
    last_storm_time_unix_sec = option_dict[LAST_STORM_TIME_KEY]
    num_grid_rows = option_dict[NUM_ROWS_KEY]
    num_grid_columns = option_dict[NUM_COLUMNS_KEY]

    normalization_type_string = option_dict[NORMALIZATION_TYPE_KEY]
    normalization_param_file_name = option_dict[NORMALIZATION_FILE_KEY]
    min_normalized_value = option_dict[MIN_NORMALIZED_VALUE_KEY]
    max_normalized_value = option_dict[MAX_NORMALIZED_VALUE_KEY]

    binarize_target = option_dict[BINARIZE_TARGET_KEY]
    loop_thru_files_once = option_dict[LOOP_ONCE_KEY]
    class_to_sampling_fraction_dict = option_dict[SAMPLING_FRACTIONS_KEY]

    x_translations_pixels = option_dict[X_TRANSLATIONS_KEY]
    y_translations_pixels = option_dict[Y_TRANSLATIONS_KEY]
    ccw_rotation_angles_deg = option_dict[ROTATION_ANGLES_KEY]
    noise_standard_deviation = option_dict[NOISE_STDEV_KEY]
    num_noisings = option_dict[NUM_NOISINGS_KEY]
    flip_in_x = option_dict[FLIP_X_KEY]
    flip_in_y = option_dict[FLIP_Y_KEY]

    this_example_dict = input_examples.read_example_file(
        netcdf_file_name=example_file_names[0], metadata_only=True)
    target_name = this_example_dict[input_examples.TARGET_NAME_KEY]

    class_to_batch_size_dict = _get_batch_size_by_class(
        num_examples_per_batch=num_examples_per_batch, target_name=target_name,
        class_to_sampling_fraction_dict=class_to_sampling_fraction_dict)

    num_classes = target_val_utils.target_name_to_num_classes(
        target_name=target_name, include_dead_storms=False)

    unique_radar_field_names, unique_radar_heights_m_agl = (
        layer_ops_to_field_height_pairs(list_of_operation_dicts)
    )

    radar_image_matrix = None
    sounding_matrix = None
    target_values = None

    file_index = 0
    include_soundings = False
    radar_field_names_2d = []

    while True:
        if loop_thru_files_once and file_index >= len(example_file_names):
            raise StopIteration

        stop_generator = False
        while not stop_generator:
            if file_index == len(example_file_names):
                if loop_thru_files_once:
                    if target_values is None:
                        raise StopIteration
                    break

                file_index = 0

            class_to_rem_batch_size_dict = _get_remaining_batch_size_by_class(
                class_to_batch_size_dict=class_to_batch_size_dict,
                target_values_in_memory=target_values)

            print 'Reading data from: "{0:s}"...'.format(
                example_file_names[file_index])
            this_example_dict = input_examples.read_example_file(
                netcdf_file_name=example_file_names[file_index],
                include_soundings=sounding_field_names is not None,
                radar_field_names_to_keep=unique_radar_field_names,
                radar_heights_to_keep_m_agl=unique_radar_heights_m_agl,
                sounding_field_names_to_keep=sounding_field_names,
                sounding_heights_to_keep_m_agl=sounding_heights_m_agl,
                first_time_to_keep_unix_sec=first_storm_time_unix_sec,
                last_time_to_keep_unix_sec=last_storm_time_unix_sec,
                num_rows_to_keep=num_grid_rows,
                num_columns_to_keep=num_grid_columns,
                class_to_num_examples_dict=class_to_rem_batch_size_dict)

            file_index += 1
            if this_example_dict is None:
                continue

            this_example_dict = input_examples.reduce_examples_3d_to_2d(
                example_dict=this_example_dict,
                list_of_operation_dicts=list_of_operation_dicts)
            radar_field_names_2d = this_example_dict[
                input_examples.RADAR_FIELDS_KEY]

            include_soundings = (
                input_examples.SOUNDING_MATRIX_KEY in this_example_dict)

            if target_values is None:
                radar_image_matrix = (
                    this_example_dict[input_examples.RADAR_IMAGE_MATRIX_KEY]
                    + 0.
                )
                target_values = (
                    this_example_dict[input_examples.TARGET_VALUES_KEY] + 0)

                if include_soundings:
                    sounding_matrix = (
                        this_example_dict[input_examples.SOUNDING_MATRIX_KEY]
                        + 0.
                    )
            else:
                radar_image_matrix = numpy.concatenate(
                    (radar_image_matrix,
                     this_example_dict[input_examples.RADAR_IMAGE_MATRIX_KEY]),
                    axis=0)
                target_values = numpy.concatenate((
                    target_values,
                    this_example_dict[input_examples.TARGET_VALUES_KEY]
                ))

                if include_soundings:
                    sounding_matrix = numpy.concatenate(
                        (sounding_matrix,
                         this_example_dict[input_examples.SOUNDING_MATRIX_KEY]),
                        axis=0)

            stop_generator = _check_stopping_criterion(
                num_examples_per_batch=num_examples_per_batch,
                class_to_batch_size_dict=class_to_batch_size_dict,
                class_to_sampling_fraction_dict=class_to_sampling_fraction_dict,
                target_values_in_memory=target_values)

        if class_to_sampling_fraction_dict is not None:
            indices_to_keep = dl_utils.sample_by_class(
                sampling_fraction_by_class_dict=class_to_sampling_fraction_dict,
                target_name=target_name, target_values=target_values,
                num_examples_total=num_examples_per_batch)

            radar_image_matrix = radar_image_matrix[indices_to_keep, ...]
            target_values = target_values[indices_to_keep]
            if include_soundings:
                sounding_matrix = sounding_matrix[indices_to_keep, ...]

        if normalization_type_string is not None:
            radar_image_matrix = dl_utils.normalize_radar_images(
                radar_image_matrix=radar_image_matrix,
                field_names=radar_field_names_2d,
                normalization_type_string=normalization_type_string,
                normalization_param_file_name=normalization_param_file_name,
                min_normalized_value=min_normalized_value,
                max_normalized_value=max_normalized_value).astype('float32')

            if include_soundings:
                sounding_matrix = dl_utils.normalize_soundings(
                    sounding_matrix=sounding_matrix,
                    field_names=sounding_field_names,
                    normalization_type_string=normalization_type_string,
                    normalization_param_file_name=normalization_param_file_name,
                    min_normalized_value=min_normalized_value,
                    max_normalized_value=max_normalized_value).astype('float32')

        list_of_predictor_matrices, target_array = _select_batch(
            list_of_predictor_matrices=[radar_image_matrix, sounding_matrix],
            target_values=target_values,
            num_examples_per_batch=num_examples_per_batch,
            binarize_target=binarize_target, num_classes=num_classes)

        list_of_predictor_matrices, target_array = _augment_radar_images(
            list_of_predictor_matrices=list_of_predictor_matrices,
            target_array=target_array,
            x_translations_pixels=x_translations_pixels,
            y_translations_pixels=y_translations_pixels,
            ccw_rotation_angles_deg=ccw_rotation_angles_deg,
            noise_standard_deviation=noise_standard_deviation,
            num_noisings=num_noisings, flip_in_x=flip_in_x, flip_in_y=flip_in_y)

        radar_image_matrix = None
        sounding_matrix = None
        target_values = None

        if include_soundings:
            yield (list_of_predictor_matrices, target_array)
        else:
            yield (list_of_predictor_matrices[0], target_array)
