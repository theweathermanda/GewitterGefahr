"""Methods for training and applying a CNN (convolutional neural network).

--- NOTATION ---

In this module, the following letters will be used to denote matrix dimensions.

K = number of classes (possible values of target variable)
E = number of examples
M = number of pixel rows per image
N = number of pixel columns per image
D = number of pixel depths per image
C = number of channels (predictor variables) per image
"""

import keras.losses
import keras.optimizers
from keras.models import Sequential
from keras.callbacks import ModelCheckpoint
from gewittergefahr.deep_learning import deep_learning_utils as dl_utils
from gewittergefahr.deep_learning import cnn_utils
from gewittergefahr.deep_learning import keras_metrics
from gewittergefahr.deep_learning import training_validation_io
from gewittergefahr.gg_utils import file_system_utils
from gewittergefahr.gg_utils import error_checking

DEFAULT_NUM_INPUT_ROWS = 32
DEFAULT_NUM_INPUT_COLUMNS = 32

CUSTOM_OBJECT_DICT_FOR_READING_MODEL = {
    'accuracy': keras_metrics.accuracy,
    'binary_accuracy': keras_metrics.binary_accuracy,
    'binary_csi': keras_metrics.binary_csi,
    'binary_frequency_bias': keras_metrics.binary_frequency_bias,
    'binary_pod': keras_metrics.binary_pod,
    'binary_pofd': keras_metrics.binary_pofd,
    'binary_success_ratio': keras_metrics.binary_success_ratio,
    'binary_focn': keras_metrics.binary_focn
}

LIST_OF_METRIC_FUNCTIONS = [
    keras_metrics.accuracy, keras_metrics.binary_accuracy,
    keras_metrics.binary_csi, keras_metrics.binary_frequency_bias,
    keras_metrics.binary_pod, keras_metrics.binary_pofd,
    keras_metrics.binary_success_ratio, keras_metrics.binary_focn]

# TODO(thunderhoser): should play with Adam optimizer, per DJ Gagne.


def get_mnist_architecture(num_classes, num_input_channels=3):
    """Creates CNN with architecture used in the following example.

    This is a 2-D CNN, which means that it performs 2-D convolution.

    https://github.com/keras-team/keras/blob/master/examples/mnist_cnn.py

    :param num_classes: Number of target classes.
    :param num_input_channels: Number of input channels (predictor variables).
    :return: model_object: Instance of `keras.models.Sequential` with the
        aforementioned architecture.
    """

    error_checking.assert_is_integer(num_classes)
    error_checking.assert_is_geq(num_classes, 2)

    model_object = Sequential()

    layer_object = cnn_utils.get_2d_conv_layer(
        num_output_filters=32, num_kernel_rows=3, num_kernel_columns=3,
        num_rows_per_stride=1, num_columns_per_stride=1,
        padding_type=cnn_utils.NO_PADDING_TYPE, activation_function='relu',
        is_first_layer=True, num_input_rows=DEFAULT_NUM_INPUT_ROWS,
        num_input_columns=DEFAULT_NUM_INPUT_COLUMNS,
        num_input_channels=num_input_channels)
    model_object.add(layer_object)

    layer_object = cnn_utils.get_2d_conv_layer(
        num_output_filters=64, num_kernel_rows=3, num_kernel_columns=3,
        num_rows_per_stride=1, num_columns_per_stride=1,
        padding_type=cnn_utils.NO_PADDING_TYPE, activation_function='relu')
    model_object.add(layer_object)

    layer_object = cnn_utils.get_2d_pooling_layer(
        num_rows_in_window=2, num_columns_in_window=2,
        pooling_type=cnn_utils.MAX_POOLING_TYPE, num_rows_per_stride=2,
        num_columns_per_stride=2)
    model_object.add(layer_object)

    layer_object = cnn_utils.get_dropout_layer(dropout_fraction=0.25)
    model_object.add(layer_object)

    layer_object = cnn_utils.get_flattening_layer()
    model_object.add(layer_object)

    layer_object = cnn_utils.get_fully_connected_layer(
        num_output_units=128, activation_function='relu')
    model_object.add(layer_object)

    layer_object = cnn_utils.get_dropout_layer(dropout_fraction=0.5)
    model_object.add(layer_object)

    layer_object = cnn_utils.get_fully_connected_layer(
        num_output_units=num_classes, activation_function='softmax')
    model_object.add(layer_object)

    model_object.compile(
        loss=keras.losses.categorical_crossentropy,
        optimizer=keras.optimizers.Adadelta(), metrics=LIST_OF_METRIC_FUNCTIONS)

    model_object.summary()
    return model_object


def get_swirlnet_architecture(num_classes, num_input_channels=3):
    """Creates CNN with architecture similar to the following example.

    https://github.com/djgagne/swirlnet/blob/master/notebooks/
    deep_swirl_tutorial.ipynb

    :param num_classes: Number of target classes.
    :param num_input_channels: Number of input channels (predictor variables).
    :return: model_object: Instance of `keras.models.Sequential` with the
        aforementioned architecture.
    """

    error_checking.assert_is_integer(num_classes)
    error_checking.assert_is_geq(num_classes, 2)

    model_object = Sequential()
    regularizer_object = cnn_utils.get_weight_regularizer(
        l1_penalty=0, l2_penalty=0.01)

    # Input to this layer is E x 32 x 32 x C.
    layer_object = cnn_utils.get_2d_conv_layer(
        num_output_filters=16, num_kernel_rows=5, num_kernel_columns=5,
        num_rows_per_stride=1, num_columns_per_stride=1,
        padding_type=cnn_utils.YES_PADDING_TYPE,
        kernel_weight_regularizer=regularizer_object,
        activation_function='relu', is_first_layer=True,
        num_input_rows=DEFAULT_NUM_INPUT_ROWS,
        num_input_columns=DEFAULT_NUM_INPUT_COLUMNS,
        num_input_channels=num_input_channels)
    model_object.add(layer_object)

    # Input to this layer is E x 32 x 32 x 16.
    layer_object = cnn_utils.get_dropout_layer(dropout_fraction=0.1)
    model_object.add(layer_object)

    # Input to this layer is E x 32 x 32 x 16.
    layer_object = cnn_utils.get_2d_pooling_layer(
        num_rows_in_window=2, num_columns_in_window=2,
        pooling_type=cnn_utils.MEAN_POOLING_TYPE, num_rows_per_stride=2,
        num_columns_per_stride=2)
    model_object.add(layer_object)

    # Input to this layer is E x 16 x 16 x 16.
    layer_object = cnn_utils.get_2d_conv_layer(
        num_output_filters=32, num_kernel_rows=5, num_kernel_columns=5,
        num_rows_per_stride=1, num_columns_per_stride=1,
        padding_type=cnn_utils.YES_PADDING_TYPE,
        kernel_weight_regularizer=regularizer_object,
        activation_function='relu')
    model_object.add(layer_object)

    # Input to this layer is E x 16 x 16 x 32.
    layer_object = cnn_utils.get_dropout_layer(dropout_fraction=0.1)
    model_object.add(layer_object)

    # Input to this layer is E x 16 x 16 x 32.
    layer_object = cnn_utils.get_2d_pooling_layer(
        num_rows_in_window=2, num_columns_in_window=2,
        pooling_type=cnn_utils.MEAN_POOLING_TYPE, num_rows_per_stride=2,
        num_columns_per_stride=2)
    model_object.add(layer_object)

    # Input to this layer is E x 8 x 8 x 32.
    layer_object = cnn_utils.get_2d_conv_layer(
        num_output_filters=64, num_kernel_rows=3, num_kernel_columns=3,
        num_rows_per_stride=1, num_columns_per_stride=1,
        padding_type=cnn_utils.YES_PADDING_TYPE,
        kernel_weight_regularizer=regularizer_object,
        activation_function='relu')
    model_object.add(layer_object)

    # Input to this layer is E x 8 x 8 x 64.
    layer_object = cnn_utils.get_dropout_layer(dropout_fraction=0.1)
    model_object.add(layer_object)

    # Input to this layer is E x 8 x 8 x 64.
    layer_object = cnn_utils.get_2d_pooling_layer(
        num_rows_in_window=2, num_columns_in_window=2,
        pooling_type=cnn_utils.MEAN_POOLING_TYPE, num_rows_per_stride=2,
        num_columns_per_stride=2)
    model_object.add(layer_object)

    # Input to this layer is E x 4 x 4 x 64.
    layer_object = cnn_utils.get_flattening_layer()
    model_object.add(layer_object)

    # Input to this layer is length-1024.
    layer_object = cnn_utils.get_fully_connected_layer(
        num_output_units=num_classes, activation_function='softmax')
    model_object.add(layer_object)

    model_object.compile(
        loss=keras.losses.categorical_crossentropy,
        optimizer=keras.optimizers.Adadelta(), metrics=LIST_OF_METRIC_FUNCTIONS)

    model_object.summary()
    return model_object


def train_2d_cnn(
        model_object, output_file_name, num_epochs,
        num_training_batches_per_epoch, top_input_dir_name, radar_source,
        radar_field_names, num_examples_per_batch, num_examples_per_time,
        first_train_time_unix_sec, last_train_time_unix_sec, min_lead_time_sec,
        max_lead_time_sec, min_target_distance_metres,
        max_target_distance_metres, event_type_string, radar_heights_m_asl=None,
        reflectivity_heights_m_asl=None, wind_speed_percentile_level=None,
        wind_speed_class_cutoffs_kt=None, normalize_by_batch=False,
        normalization_dict=dl_utils.DEFAULT_NORMALIZATION_DICT,
        percentile_offset_for_normalization=
        dl_utils.DEFAULT_PERCENTILE_OFFSET_FOR_NORMALIZATION,
        class_fractions_to_sample=None, num_validation_batches_per_epoch=None,
        first_validn_time_unix_sec=None, last_validn_time_unix_sec=None):
    """Trains 2-D CNN (one that performs 2-D convolution).

    :param model_object: Instance of `keras.models.Sequential`.
    :param output_file_name: Path to output file (HDF5 format).  The model will
        be saved here after every epoch.
    :param num_epochs: Number of epochs.
    :param num_training_batches_per_epoch: Number of training batches per epoch.
    :param top_input_dir_name: See documentation for
        `training_validation_io.storm_image_generator`.
    :param radar_source: Same.
    :param radar_field_names: Same.
    :param num_examples_per_batch: Same.
    :param num_examples_per_time: Same.
    :param first_train_time_unix_sec: First image time for training.
        Examples will be created for random times in
        `first_train_time_unix_sec`...`last_train_time_unix_sec`.
    :param last_train_time_unix_sec: See above.
    :param min_lead_time_sec: See doc for
        `training_validation_io.storm_image_generator`.
    :param max_lead_time_sec: Same.
    :param min_target_distance_metres: Same.
    :param max_target_distance_metres: Same.
    :param event_type_string: Same.
    :param radar_heights_m_asl: Same.
    :param reflectivity_heights_m_asl: Same.
    :param wind_speed_percentile_level: Same.
    :param wind_speed_class_cutoffs_kt: Same.
    :param normalize_by_batch: Same.
    :param normalization_dict: Same.
    :param percentile_offset_for_normalization: Same.
    :param class_fractions_to_sample: Same.
    :param num_validation_batches_per_epoch: Number of validation batches per
        epoch.
    :param first_validn_time_unix_sec: First image time for validation.
        Examples will be created for random times in
        `first_validn_time_unix_sec`...`last_validn_time_unix_sec`.
    :param last_validn_time_unix_sec: See above.
    """

    # TODO(thunderhoser): Allow loss function to be weighted.

    error_checking.assert_is_integer(num_epochs)
    error_checking.assert_is_geq(num_epochs, 1)
    error_checking.assert_is_integer(num_training_batches_per_epoch)
    error_checking.assert_is_geq(num_training_batches_per_epoch, 1)
    file_system_utils.mkdir_recursive_if_necessary(file_name=output_file_name)

    if num_validation_batches_per_epoch is None:
        checkpoint_object = ModelCheckpoint(
            output_file_name, monitor='loss', verbose=1, save_best_only=False,
            save_weights_only=False, mode='min', period=1)

        model_object.fit_generator(
            generator=training_validation_io.storm_image_generator(
                top_directory_name=top_input_dir_name,
                radar_source=radar_source, radar_field_names=radar_field_names,
                num_examples_per_batch=num_examples_per_batch,
                num_examples_per_image_time=num_examples_per_time,
                first_image_time_unix_sec=first_train_time_unix_sec,
                last_image_time_unix_sec=last_train_time_unix_sec,
                min_lead_time_sec=min_lead_time_sec,
                max_lead_time_sec=max_lead_time_sec,
                min_target_distance_metres=min_target_distance_metres,
                max_target_distance_metres=max_target_distance_metres,
                event_type_string=event_type_string,
                radar_heights_m_asl=radar_heights_m_asl,
                reflectivity_heights_m_asl=reflectivity_heights_m_asl,
                wind_speed_percentile_level=wind_speed_percentile_level,
                wind_speed_class_cutoffs_kt=wind_speed_class_cutoffs_kt,
                normalize_by_batch=normalize_by_batch,
                normalization_dict=normalization_dict,
                percentile_offset_for_normalization=
                percentile_offset_for_normalization,
                class_fractions_to_sample=class_fractions_to_sample),
            steps_per_epoch=num_training_batches_per_epoch, epochs=num_epochs,
            verbose=1, callbacks=[checkpoint_object])

    else:
        error_checking.assert_is_integer(num_validation_batches_per_epoch)
        error_checking.assert_is_geq(num_validation_batches_per_epoch, 1)

        checkpoint_object = ModelCheckpoint(
            output_file_name, monitor='val_loss', verbose=1,
            save_best_only=True, save_weights_only=False, mode='min', period=1)

        model_object.fit_generator(
            generator=training_validation_io.storm_image_generator(
                top_directory_name=top_input_dir_name,
                radar_source=radar_source, radar_field_names=radar_field_names,
                num_examples_per_batch=num_examples_per_batch,
                num_examples_per_image_time=num_examples_per_time,
                first_image_time_unix_sec=first_train_time_unix_sec,
                last_image_time_unix_sec=last_train_time_unix_sec,
                min_lead_time_sec=min_lead_time_sec,
                max_lead_time_sec=max_lead_time_sec,
                min_target_distance_metres=min_target_distance_metres,
                max_target_distance_metres=max_target_distance_metres,
                event_type_string=event_type_string,
                radar_heights_m_asl=radar_heights_m_asl,
                reflectivity_heights_m_asl=reflectivity_heights_m_asl,
                wind_speed_percentile_level=wind_speed_percentile_level,
                wind_speed_class_cutoffs_kt=wind_speed_class_cutoffs_kt,
                normalize_by_batch=normalize_by_batch,
                normalization_dict=normalization_dict,
                percentile_offset_for_normalization=
                percentile_offset_for_normalization,
                class_fractions_to_sample=class_fractions_to_sample),
            steps_per_epoch=num_training_batches_per_epoch, epochs=num_epochs,
            verbose=1, callbacks=[checkpoint_object],
            validation_data=training_validation_io.storm_image_generator(
                top_directory_name=top_input_dir_name,
                radar_source=radar_source, radar_field_names=radar_field_names,
                num_examples_per_batch=num_examples_per_batch,
                num_examples_per_image_time=num_examples_per_time,
                first_image_time_unix_sec=first_validn_time_unix_sec,
                last_image_time_unix_sec=last_validn_time_unix_sec,
                min_lead_time_sec=min_lead_time_sec,
                max_lead_time_sec=max_lead_time_sec,
                min_target_distance_metres=min_target_distance_metres,
                max_target_distance_metres=max_target_distance_metres,
                event_type_string=event_type_string,
                radar_heights_m_asl=radar_heights_m_asl,
                reflectivity_heights_m_asl=reflectivity_heights_m_asl,
                wind_speed_percentile_level=wind_speed_percentile_level,
                wind_speed_class_cutoffs_kt=wind_speed_class_cutoffs_kt,
                normalize_by_batch=normalize_by_batch,
                normalization_dict=normalization_dict,
                percentile_offset_for_normalization=
                percentile_offset_for_normalization,
                class_fractions_to_sample=class_fractions_to_sample),
            validation_steps=num_validation_batches_per_epoch)
