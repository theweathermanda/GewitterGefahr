"""Methods for setting up, training, and applying upconvolution networks."""

import copy
import pickle
import numpy
import keras
from gewittergefahr.gg_utils import file_system_utils
from gewittergefahr.gg_utils import error_checking
from gewittergefahr.deep_learning import cnn
from gewittergefahr.deep_learning import testing_io
from gewittergefahr.deep_learning import training_validation_io as trainval_io

L1_WEIGHT = 0.
L2_WEIGHT = 0.001
SLOPE_FOR_RELU = 0.2
NUM_CONV_FILTER_ROWS = 3
NUM_CONV_FILTER_COLUMNS = 3
NUM_SMOOTHING_FILTER_ROWS = 5
NUM_SMOOTHING_FILTER_COLUMNS = 5

DEFAULT_SMOOTHING_RADIUS_PX = 1.
DEFAULT_HALF_SMOOTHING_ROWS = 2
DEFAULT_HALF_SMOOTHING_COLUMNS = 2

MIN_MSE_DECREASE_FOR_EARLY_STOP = 0.005
NUM_EPOCHS_FOR_EARLY_STOP = 6

CNN_FILE_KEY = 'cnn_file_name'
CNN_FEATURE_LAYER_KEY = 'cnn_feature_layer_name'
NUM_EPOCHS_KEY = 'num_epochs'
NUM_EXAMPLES_PER_BATCH_KEY = 'num_examples_per_batch'
NUM_TRAINING_BATCHES_KEY = 'num_training_batches_per_epoch'
TRAINING_FILES_KEY = 'training_example_file_names'
FIRST_TRAINING_TIME_KEY = 'first_training_time_unix_sec'
LAST_TRAINING_TIME_KEY = 'last_training_time_unix_sec'
NUM_VALIDATION_BATCHES_KEY = 'num_validation_batches_per_epoch'
VALIDATION_FILES_KEY = 'validation_example_file_names'
FIRST_VALIDATION_TIME_KEY = 'first_validation_time_unix_sec'
LAST_VALIDATION_TIME_KEY = 'last_validation_time_unix_sec'

METADATA_KEYS = [
    CNN_FILE_KEY, CNN_FEATURE_LAYER_KEY, NUM_EPOCHS_KEY,
    NUM_EXAMPLES_PER_BATCH_KEY, NUM_TRAINING_BATCHES_KEY, TRAINING_FILES_KEY,
    FIRST_TRAINING_TIME_KEY, LAST_TRAINING_TIME_KEY, NUM_VALIDATION_BATCHES_KEY,
    VALIDATION_FILES_KEY, FIRST_VALIDATION_TIME_KEY, LAST_VALIDATION_TIME_KEY
]


def create_smoothing_filter(
        num_channels, smoothing_radius_px=DEFAULT_SMOOTHING_RADIUS_PX,
        num_half_filter_rows=DEFAULT_HALF_SMOOTHING_ROWS,
        num_half_filter_columns=DEFAULT_HALF_SMOOTHING_COLUMNS):
    """Creates convolution filter for Gaussian smoothing.

    M = number of rows in filter
    N = number of columns in filter
    C = number of channels (or "variables" or "features") to smooth.  Each
        channel will be smoothed independently.

    :param num_channels: C in the above discussion.
    :param smoothing_radius_px: e-folding radius (pixels).
    :param num_half_filter_rows: Number of rows in one half of filter.  Total
        number of rows will be 2 * `num_half_filter_rows` + 1.
    :param num_half_filter_columns: Same but for columns.
    :return: weight_matrix: M-by-N-by-C-by-C numpy array of convolution weights.
    """

    error_checking.assert_is_integer(num_channels)
    error_checking.assert_is_greater(num_channels, 0)
    error_checking.assert_is_greater(smoothing_radius_px, 0.)
    error_checking.assert_is_integer(num_half_filter_rows)
    error_checking.assert_is_greater(num_half_filter_rows, 0)
    error_checking.assert_is_integer(num_half_filter_columns)
    error_checking.assert_is_greater(num_half_filter_columns, 0)

    num_filter_rows = 2 * num_half_filter_rows + 1
    num_filter_columns = 2 * num_half_filter_columns + 1

    row_offsets_unique = numpy.linspace(
        -num_half_filter_rows, num_half_filter_rows, num=num_filter_rows,
        dtype=float)
    column_offsets_unique = numpy.linspace(
        -num_half_filter_columns, num_half_filter_columns,
        num=num_filter_columns, dtype=float)

    column_offset_matrix, row_offset_matrix = numpy.meshgrid(
        column_offsets_unique, row_offsets_unique)

    pixel_offset_matrix = numpy.sqrt(
        row_offset_matrix ** 2 + column_offset_matrix ** 2)

    small_weight_matrix = numpy.exp(
        -pixel_offset_matrix ** 2 / (2 * smoothing_radius_px ** 2)
    )
    small_weight_matrix = small_weight_matrix / numpy.sum(small_weight_matrix)

    weight_matrix = numpy.zeros(
        (num_filter_rows, num_filter_columns, num_channels, num_channels)
    )

    for k in range(num_channels):
        weight_matrix[..., k, k] = small_weight_matrix

    return weight_matrix


def create_net(
        num_input_features, first_num_rows, first_num_columns,
        upsampling_factors, num_output_channels,
        use_activation_for_out_layer=False, use_bn_for_out_layer=True,
        use_transposed_conv=False, smoothing_radius_px=None):
    """Creates (but does not train) upconvnet.

    L = number of conv or deconv layers

    :param num_input_features: Number of input features.
    :param first_num_rows: Number of rows in input to first deconv layer.  The
        input features will be reshaped into a grid with this many rows.
    :param first_num_columns: Same but for columns.
    :param upsampling_factors: length-L numpy array of upsampling factors.  Must
        all be positive integers.
    :param num_output_channels: Number of channels in output images.
    :param use_activation_for_out_layer: Boolean flag.  If True, activation will
        be applied to output layer.
    :param use_bn_for_out_layer: Boolean flag.  If True, batch normalization
        will be applied to output layer.
    :param use_transposed_conv: Boolean flag.  If True, upsampling will be done
        with transposed-convolution layers.  If False, each upsampling will be
        done with an upsampling layer followed by a conv layer.
    :param smoothing_radius_px: Smoothing radius (pixels).  Gaussian smoothing
        with this e-folding radius will be done after each upsampling.  If
        `smoothing_radius_px is None`, no smoothing will be done.
    :return: model_object: Untrained instance of `keras.models.Model`.
    """

    error_checking.assert_is_integer(num_input_features)
    error_checking.assert_is_integer(first_num_rows)
    error_checking.assert_is_integer(first_num_columns)
    error_checking.assert_is_integer(num_output_channels)

    error_checking.assert_is_greater(num_input_features, 0)
    error_checking.assert_is_greater(first_num_rows, 0)
    error_checking.assert_is_greater(first_num_columns, 0)
    error_checking.assert_is_greater(num_output_channels, 0)

    error_checking.assert_is_integer_numpy_array(upsampling_factors)
    error_checking.assert_is_numpy_array(upsampling_factors, num_dimensions=1)
    error_checking.assert_is_geq_numpy_array(upsampling_factors, 1)

    error_checking.assert_is_boolean(use_activation_for_out_layer)
    error_checking.assert_is_boolean(use_bn_for_out_layer)
    error_checking.assert_is_boolean(use_transposed_conv)

    regularizer_object = keras.regularizers.l1_l2(l1=L1_WEIGHT, l2=L2_WEIGHT)
    input_layer_object = keras.layers.Input(shape=(num_input_features,))

    current_num_filters = int(numpy.round(
        num_input_features / (first_num_rows * first_num_columns)
    ))

    layer_object = keras.layers.Reshape(
        target_shape=(first_num_rows, first_num_columns, current_num_filters)
    )(input_layer_object)

    num_main_layers = len(upsampling_factors)

    for i in range(num_main_layers):
        this_upsampling_factor = upsampling_factors[i]

        if i == num_main_layers - 1:
            current_num_filters = num_output_channels + 0
        elif this_upsampling_factor == 1:
            current_num_filters = int(numpy.round(current_num_filters / 2))

        if use_transposed_conv:
            if this_upsampling_factor > 1:
                this_padding_arg = 'same'
            else:
                this_padding_arg = 'valid'

            layer_object = keras.layers.Conv2DTranspose(
                filters=current_num_filters,
                kernel_size=(NUM_CONV_FILTER_ROWS, NUM_CONV_FILTER_COLUMNS),
                strides=(this_upsampling_factor, this_upsampling_factor),
                padding=this_padding_arg, data_format='channels_last',
                dilation_rate=(1, 1), activation=None, use_bias=True,
                kernel_initializer='glorot_uniform', bias_initializer='zeros',
                kernel_regularizer=regularizer_object
            )(layer_object)

        else:
            if this_upsampling_factor > 1:
                try:
                    layer_object = keras.layers.UpSampling2D(
                        size=(this_upsampling_factor, this_upsampling_factor),
                        data_format='channels_last', interpolation='nearest'
                    )(layer_object)
                except:
                    layer_object = keras.layers.UpSampling2D(
                        size=(this_upsampling_factor, this_upsampling_factor),
                        data_format='channels_last'
                    )(layer_object)

            layer_object = keras.layers.Conv2D(
                filters=current_num_filters,
                kernel_size=(NUM_CONV_FILTER_ROWS, NUM_CONV_FILTER_COLUMNS),
                strides=(1, 1), padding='same', data_format='channels_last',
                dilation_rate=(1, 1), activation=None, use_bias=True,
                kernel_initializer='glorot_uniform', bias_initializer='zeros',
                kernel_regularizer=regularizer_object
            )(layer_object)

            if this_upsampling_factor == 1:
                layer_object = keras.layers.ZeroPadding2D(
                    padding=(1, 1), data_format='channels_last'
                )(layer_object)

        if smoothing_radius_px is not None:
            this_weight_matrix = create_smoothing_filter(
                smoothing_radius_px=smoothing_radius_px,
                num_channels=current_num_filters)

            this_bias_vector = numpy.zeros(current_num_filters)

            layer_object = keras.layers.Conv2D(
                filters=current_num_filters,
                kernel_size=this_weight_matrix.shape[:2],
                strides=(1, 1), padding='same', data_format='channels_last',
                dilation_rate=(1, 1), activation=None, use_bias=True,
                kernel_initializer='glorot_uniform', bias_initializer='zeros',
                kernel_regularizer=regularizer_object, trainable=False,
                weights=[this_weight_matrix, this_bias_vector]
            )(layer_object)

        if i < num_main_layers - 1 or use_activation_for_out_layer:
            layer_object = keras.layers.LeakyReLU(
                alpha=SLOPE_FOR_RELU
            )(layer_object)

        if i < num_main_layers - 1 or use_bn_for_out_layer:
            layer_object = keras.layers.BatchNormalization(
                axis=-1, center=True, scale=True
            )(layer_object)

    model_object = keras.models.Model(
        inputs=input_layer_object, outputs=layer_object)
    model_object.compile(
        loss=keras.losses.mean_squared_error, optimizer=keras.optimizers.Adam())

    model_object.summary()
    return model_object


def trainval_generator_2d_radar(
        option_dict, cnn_model_object, cnn_feature_layer_name,
        list_of_layer_operation_dicts=None):
    """Generates training or validation examples with 2-D radar images.

    E = number of examples in batch
    M = number of rows in spatial grid
    N = number of columns in spatial grid
    C = number of image channels
    Z = number of scalar features

    :param option_dict: See doc for `training_validation_io.generator_2d_or_3d`.
    :param cnn_model_object: Trained CNN (instance of `keras.models.Model` or
        `keras.models.Sequential`).  This will be used to turn images (generated
        by `training_validation_io.generator_2d_or_3d`) into 1-D feature
        vectors.
    :param cnn_feature_layer_name: Name of feature-generating layer in CNN.  For
        each image generated by `training_validation_io.generator_2d_or_3d`, the
        feature vector will be the output from this layer.
    :param list_of_layer_operation_dicts: See doc for
        `training_validation_io.gridrad_generator_2d_reduced`.
    :return: feature_matrix: E-by-Z numpy array of scalar features.  These will
        be inputs (predictors) for the upconvnet.
    :return: radar_matrix: E-by-M-by-N-by-C numpy array of radar images.  These
        will be outputs (targets) for the upconvnet.
    :raises: ValueError: if the first input tensor to `cnn_model_object` does
        not have exactly 2 spatial dimensions.
    """

    if isinstance(cnn_model_object.input, list):
        radar_input_tensor = cnn_model_object.input[0]
    else:
        radar_input_tensor = cnn_model_object.input

    these_dimensions = radar_input_tensor.get_shape().as_list()
    num_spatial_dimensions = len(these_dimensions) - 2

    if num_spatial_dimensions != 2:
        error_string = (
            'First input tensor to CNN should have 2 (not {0:d}) spatial '
            'dimensions.'
        ).format(num_spatial_dimensions)

        raise TypeError(error_string)

    option_dict[trainval_io.LOOP_ONCE_KEY] = False
    option_dict[trainval_io.X_TRANSLATIONS_KEY] = None
    option_dict[trainval_io.Y_TRANSLATIONS_KEY] = None
    option_dict[trainval_io.ROTATION_ANGLES_KEY] = None
    option_dict[trainval_io.NOISE_STDEV_KEY] = None
    option_dict[trainval_io.NUM_NOISINGS_KEY] = 0
    option_dict[trainval_io.FLIP_X_KEY] = False
    option_dict[trainval_io.FLIP_Y_KEY] = False

    partial_cnn_model_object = cnn.model_to_feature_generator(
        model_object=cnn_model_object,
        feature_layer_name=cnn_feature_layer_name)

    if list_of_layer_operation_dicts is None:
        cnn_generator_object = trainval_io.generator_2d_or_3d(option_dict)
    else:
        cnn_generator_object = trainval_io.gridrad_generator_2d_reduced(
            option_dict=option_dict,
            list_of_operation_dicts=list_of_layer_operation_dicts)

    while True:
        try:
            these_image_matrices = next(cnn_generator_object)[0]
        except StopIteration:
            break

        if isinstance(these_image_matrices, list):
            radar_matrix = these_image_matrices[0]
        else:
            radar_matrix = these_image_matrices

        feature_matrix = partial_cnn_model_object.predict(
            these_image_matrices, batch_size=radar_matrix.shape[0])

        yield (feature_matrix, radar_matrix)


def testing_generator_2d_radar(
        option_dict, num_examples_total, cnn_model_object,
        cnn_feature_layer_name, list_of_layer_operation_dicts=None):
    """Generates testing examples with 2-D radar images.

    :param option_dict: See doc for `testing_io.generator_2d_or_3d`.
    :param num_examples_total: Number of examples (storm objects) to read.
    :param cnn_model_object: See doc for `trainval_generator_2d_radar`.
    :param cnn_feature_layer_name: Same.
    :param list_of_layer_operation_dicts: Same.
    :return: feature_matrix: Same.
    :return: radar_matrix: Same.
    :raises: ValueError: if the first input tensor to `cnn_model_object` does
        not have exactly 2 spatial dimensions.
    """

    if isinstance(cnn_model_object.input, list):
        radar_input_tensor = cnn_model_object.input[0]
    else:
        radar_input_tensor = cnn_model_object.input

    these_dimensions = radar_input_tensor.get_shape().as_list()
    num_spatial_dimensions = len(these_dimensions) - 2

    if num_spatial_dimensions != 2:
        error_string = (
            'First input tensor to CNN should have 2 (not {0:d}) spatial '
            'dimensions.'
        ).format(num_spatial_dimensions)

        raise TypeError(error_string)

    partial_cnn_model_object = cnn.model_to_feature_generator(
        model_object=cnn_model_object,
        feature_layer_name=cnn_feature_layer_name)

    if list_of_layer_operation_dicts is None:
        cnn_generator_object = testing_io.generator_2d_or_3d(
            option_dict=option_dict, num_examples_total=num_examples_total)
    else:
        cnn_generator_object = testing_io.gridrad_generator_2d_reduced(
            option_dict=option_dict, num_examples_total=num_examples_total,
            list_of_operation_dicts=list_of_layer_operation_dicts)

    while True:
        try:
            this_storm_object_dict = next(cnn_generator_object)
        except StopIteration:
            break

        these_image_matrices = this_storm_object_dict[
            testing_io.INPUT_MATRICES_KEY]

        if isinstance(these_image_matrices, list):
            radar_matrix = these_image_matrices[0]
        else:
            radar_matrix = these_image_matrices

        feature_matrix = partial_cnn_model_object.predict(
            these_image_matrices, batch_size=radar_matrix.shape[0])

        yield (feature_matrix, radar_matrix)


def train_upconvnet(
        upconvnet_model_object, output_model_file_name, cnn_model_object,
        cnn_feature_layer_name, cnn_metadata_dict, num_epochs,
        num_examples_per_batch, num_training_batches_per_epoch,
        training_example_file_names, first_training_time_unix_sec,
        last_training_time_unix_sec, num_validation_batches_per_epoch,
        validation_example_file_names, first_validation_time_unix_sec,
        last_validation_time_unix_sec):
    """Trains upconvnet.

    :param upconvnet_model_object: Upconvnet to be trained (instance of
        `keras.models.Model` or `keras.models.Sequential`).
    :param output_model_file_name: Path to output file.  The model will be saved
        as an HDF5 file (extension should be ".h5", but this is not enforced).
    :param cnn_model_object: See doc for `trainval_generator_2d_radar`.
    :param cnn_feature_layer_name: Same.
    :param cnn_metadata_dict: Dictionary returned by `cnn.read_model_metadata`.
    :param num_epochs: Number of epochs.
    :param num_examples_per_batch: Number of examples in each training or
        validation batch.
    :param num_training_batches_per_epoch: Number of training batches furnished
        to model in each epoch.
    :param training_example_file_names: 1-D list of paths to files with training
        examples (inputs to CNN).  These files will be read by
        `input_examples.read_example_file`.
    :param first_training_time_unix_sec: First time in training period.
    :param last_training_time_unix_sec: Last time in training period.
    :param num_validation_batches_per_epoch: Number of validation batches
        furnished to model in each epoch.
    :param validation_example_file_names: 1-D list of paths to files with
        validation examples (inputs to CNN).  These files will be read by
        `input_examples.read_example_file`.
    :param first_validation_time_unix_sec: First time in validation period.
    :param last_validation_time_unix_sec: Last time in validation period.
    """

    file_system_utils.mkdir_recursive_if_necessary(
        file_name=output_model_file_name)

    if num_validation_batches_per_epoch is None:
        checkpoint_object = keras.callbacks.ModelCheckpoint(
            output_model_file_name, monitor='loss', verbose=1,
            save_best_only=False, save_weights_only=False, mode='min', period=1)
    else:
        checkpoint_object = keras.callbacks.ModelCheckpoint(
            output_model_file_name, monitor='val_loss', verbose=1,
            save_best_only=True, save_weights_only=False, mode='min', period=1)

    training_option_dict = copy.deepcopy(
        cnn_metadata_dict[cnn.TRAINING_OPTION_DICT_KEY]
    )

    training_option_dict[
        trainval_io.EXAMPLE_FILES_KEY] = training_example_file_names
    training_option_dict[
        trainval_io.NUM_EXAMPLES_PER_BATCH_KEY] = num_examples_per_batch
    training_option_dict[
        trainval_io.FIRST_STORM_TIME_KEY] = first_training_time_unix_sec
    training_option_dict[
        trainval_io.LAST_STORM_TIME_KEY] = last_training_time_unix_sec

    training_generator = trainval_generator_2d_radar(
        option_dict=training_option_dict, cnn_model_object=cnn_model_object,
        cnn_feature_layer_name=cnn_feature_layer_name,
        list_of_layer_operation_dicts=cnn_metadata_dict[
            cnn.LAYER_OPERATIONS_KEY]
    )

    validation_option_dict = copy.deepcopy(
        cnn_metadata_dict[cnn.TRAINING_OPTION_DICT_KEY]
    )

    validation_option_dict[
        trainval_io.EXAMPLE_FILES_KEY] = validation_example_file_names
    validation_option_dict[
        trainval_io.NUM_EXAMPLES_PER_BATCH_KEY] = num_examples_per_batch
    validation_option_dict[
        trainval_io.FIRST_STORM_TIME_KEY] = first_validation_time_unix_sec
    validation_option_dict[
        trainval_io.LAST_STORM_TIME_KEY] = last_validation_time_unix_sec

    validation_generator = trainval_generator_2d_radar(
        option_dict=training_option_dict, cnn_model_object=cnn_model_object,
        cnn_feature_layer_name=cnn_feature_layer_name,
        list_of_layer_operation_dicts=cnn_metadata_dict[
            cnn.LAYER_OPERATIONS_KEY]
    )

    early_stopping_object = keras.callbacks.EarlyStopping(
        monitor='val_loss', min_delta=MIN_MSE_DECREASE_FOR_EARLY_STOP,
        patience=NUM_EPOCHS_FOR_EARLY_STOP, verbose=1, mode='min')

    list_of_callback_objects = [checkpoint_object, early_stopping_object]

    upconvnet_model_object.fit_generator(
        generator=training_generator,
        steps_per_epoch=num_training_batches_per_epoch, epochs=num_epochs,
        verbose=1, callbacks=list_of_callback_objects,
        validation_data=validation_generator,
        validation_steps=num_validation_batches_per_epoch, workers=0)


def write_model_metadata(
        cnn_file_name, cnn_feature_layer_name, num_epochs,
        num_examples_per_batch, num_training_batches_per_epoch,
        training_example_file_names, first_training_time_unix_sec,
        last_training_time_unix_sec, num_validation_batches_per_epoch,
        validation_example_file_names, first_validation_time_unix_sec,
        last_validation_time_unix_sec, pickle_file_name):
    """Writes metadata to Pickle file.

    :param cnn_file_name: Path to file with trained CNN (readable by
        `cnn.read_model`).
    :param cnn_feature_layer_name: See doc for `train_upconvnet`.
    :param num_epochs: Same.
    :param num_examples_per_batch: Same.
    :param num_training_batches_per_epoch: Same.
    :param training_example_file_names: Same.
    :param first_training_time_unix_sec: Same.
    :param last_training_time_unix_sec: Same.
    :param num_validation_batches_per_epoch: Same.
    :param validation_example_file_names: Same.
    :param first_validation_time_unix_sec: Same.
    :param last_validation_time_unix_sec: Same.
    :param pickle_file_name: Path to output file.
    """

    error_checking.assert_is_string(cnn_file_name)
    error_checking.assert_is_string(cnn_feature_layer_name)
    error_checking.assert_is_integer(num_epochs)
    error_checking.assert_is_greater(num_epochs, 0)
    error_checking.assert_is_integer(num_examples_per_batch)
    error_checking.assert_is_greater(num_examples_per_batch, 0)
    error_checking.assert_is_integer(num_training_batches_per_epoch)
    error_checking.assert_is_greater(num_training_batches_per_epoch, 0)
    error_checking.assert_is_integer(num_validation_batches_per_epoch)
    error_checking.assert_is_greater(num_validation_batches_per_epoch, 0)

    error_checking.assert_is_string_list(training_example_file_names)
    error_checking.assert_is_numpy_array(
        numpy.array(training_example_file_names), num_dimensions=1)

    error_checking.assert_is_integer(first_training_time_unix_sec)
    error_checking.assert_is_integer(last_training_time_unix_sec)
    error_checking.assert_is_greater(
        last_training_time_unix_sec, first_training_time_unix_sec)

    error_checking.assert_is_string_list(validation_example_file_names)
    error_checking.assert_is_numpy_array(
        numpy.array(validation_example_file_names), num_dimensions=1)

    error_checking.assert_is_integer(first_validation_time_unix_sec)
    error_checking.assert_is_integer(last_validation_time_unix_sec)
    error_checking.assert_is_greater(
        last_validation_time_unix_sec, first_validation_time_unix_sec)

    metadata_dict = {
        CNN_FILE_KEY: cnn_file_name,
        CNN_FEATURE_LAYER_KEY: cnn_feature_layer_name,
        NUM_EPOCHS_KEY: num_epochs,
        NUM_EXAMPLES_PER_BATCH_KEY: num_examples_per_batch,
        NUM_TRAINING_BATCHES_KEY: num_training_batches_per_epoch,
        TRAINING_FILES_KEY: training_example_file_names,
        FIRST_TRAINING_TIME_KEY: first_training_time_unix_sec,
        LAST_TRAINING_TIME_KEY: last_training_time_unix_sec,
        NUM_VALIDATION_BATCHES_KEY: num_validation_batches_per_epoch,
        VALIDATION_FILES_KEY: validation_example_file_names,
        FIRST_VALIDATION_TIME_KEY: first_validation_time_unix_sec,
        LAST_VALIDATION_TIME_KEY: last_validation_time_unix_sec
    }

    file_system_utils.mkdir_recursive_if_necessary(file_name=pickle_file_name)

    pickle_file_handle = open(pickle_file_name, 'wb')
    pickle.dump(metadata_dict, pickle_file_handle)
    pickle_file_handle.close()


def read_model_metadata(pickle_file_name):
    """Reads metadata from Pickle file.

    :param pickle_file_name: Path to input file.
    :return: metadata_dict: Dictionary with the following keys.
    metadata_dict['cnn_file_name']: See doc for `read_model_metadata`.
    metadata_dict['cnn_feature_layer_name']: Same.
    metadata_dict['num_epochs']: Same.
    metadata_dict['num_examples_per_batch']: Same.
    metadata_dict['num_training_batches_per_epoch']: Same.
    metadata_dict['training_example_file_names']: Same.
    metadata_dict['first_training_time_unix_sec']: Same.
    metadata_dict['last_training_time_unix_sec']: Same.
    metadata_dict['num_validation_batches_per_epoch']: Same.
    metadata_dict['validation_example_file_names']: Same.
    metadata_dict['first_validation_time_unix_sec']: Same.
    metadata_dict['last_validation_time_unix_sec']: Same.

    :raises: ValueError: if any expected key is missing from the dictionary.
    """

    pickle_file_handle = open(pickle_file_name, 'rb')
    metadata_dict = pickle.load(pickle_file_handle)
    pickle_file_handle.close()

    missing_keys = list(set(METADATA_KEYS) - set(metadata_dict.keys()))
    if len(missing_keys) == 0:
        return metadata_dict

    error_string = (
        '\n{0:s}\nKeys listed above were expected, but not found, in file '
        '"{1:s}".'
    ).format(str(missing_keys), pickle_file_name)

    raise ValueError(error_string)


def apply_upconvnet(model_object, feature_matrix, num_examples_per_batch=100,
                    verbose=False):
    """Applies upconvnet to one or more feature vectors.

    E = number of examples
    Z = number of scalar features

    :param model_object: Trained upconvnet (instance of `keras.models.Model` or
        `keras.models.Sequential`).
    :param feature_matrix: E-by-Z numpy array of features (inputs to upconvnet).
    :param num_examples_per_batch: Number of examples per batch.  Will apply
        upconvnet to this many examples at once.  If
        `num_examples_per_batch is None`, will apply to all examples at once.
    :param verbose: Boolean flag.  If True, will print progress messages.
    :return: reconstructed_image_matrix: numpy array of reconstructed images.
        The array should have <= 2 dimensions, and the first axis should have
        length E.
    """

    error_checking.assert_is_numpy_array_without_nan(feature_matrix)
    error_checking.assert_is_numpy_array(feature_matrix, num_dimensions=2)

    num_examples = feature_matrix.shape[0]

    if num_examples_per_batch is None:
        num_examples_per_batch = num_examples + 0
    else:
        error_checking.assert_is_integer(num_examples_per_batch)
        error_checking.assert_is_greater(num_examples_per_batch, 0)

    num_examples_per_batch = min([num_examples_per_batch, num_examples])
    error_checking.assert_is_boolean(verbose)

    reconstructed_image_matrix = None

    for i in range(0, num_examples, num_examples_per_batch):
        this_first_index = i
        this_last_index = min(
            [i + num_examples_per_batch - 1, num_examples - 1]
        )

        these_indices = numpy.linspace(
            this_first_index, this_last_index,
            num=this_last_index - this_first_index + 1, dtype=int)

        if verbose:
            print (
                'Applying model to examples {0:d}-{1:d} of {2:d}...'
            ).format(this_first_index + 1, this_last_index + 1, num_examples)

        this_image_matrix = model_object.predict(
            feature_matrix[these_indices, ...], batch_size=len(these_indices)
        )

        if reconstructed_image_matrix is None:
            reconstructed_image_matrix = this_image_matrix + 0.
        else:
            reconstructed_image_matrix = numpy.concatenate(
                (reconstructed_image_matrix, this_image_matrix), axis=0)

    if verbose:
        print 'Have applied model to all {0:d} examples!'.format(num_examples)

    return reconstructed_image_matrix
