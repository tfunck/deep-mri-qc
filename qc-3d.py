from keras.models import Sequential
from keras.layers import Dense, Dropout, Activation, Conv3D, MaxPooling3D, Flatten, BatchNormalization
from keras.callbacks import ModelCheckpoint

import numpy as np
import h5py
import pickle

import keras.backend as K

import matplotlib.pyplot as plt

from sklearn.model_selection import StratifiedKFold, StratifiedShuffleSplit

from custom_loss import sensitivity, specificity

workdir = '/data1/data/deepqc/'

image_size = (192, 256, 192)


def qc_model():
    nb_classes = 3

    conv_size = (3, 3, 3)
    pool_size = (2, 2, 2)

    model = Sequential()

    model.add(Conv3D(6, conv_size, activation='relu', strides=[2, 2, 2], input_shape=(image_size[0], image_size[1], image_size[2], 1)))
    # model.add(Dropout(0.2))
    # model.add(Conv3D(16, conv_size, activation='relu'))
    # model.add(Dropout(0.2))
    # model.add(BatchNormalization())
    # model.add(MaxPooling3D(pool_size=pool_size))

    # model.add(Conv3D(32, conv_size, activation='relu'))
    # model.add(Dropout(0.2))
    model.add(Conv3D(16, conv_size, strides=[2, 2, 2], activation='relu'))
    # model.add(Dropout(0.2))
    # model.add(BatchNormalization())
    # model.add(MaxPooling3D(pool_size=pool_size))

    # model.add(Conv3D(64, conv_size, activation='relu'))
    # model.add(Dropout(0.3))
    model.add(Conv3D(32, conv_size, strides=[2, 2, 2], activation='relu'))
    # model.add(Dropout(0.3))
    # model.add(BatchNormalization())
    # model.add(MaxPooling3D(pool_size=pool_size))
#
    model.add(Conv3D(32, conv_size, strides=[2, 2, 2], activation='relu'))
    # model.add(Dropout(0.4))
    # model.add(MaxPooling3D(pool_size=pool_size))

    # model.add(Conv3D(64, conv_size, activation='relu'))
    # # model.add(Dropout(0.4))
    # model.add(MaxPooling3D(pool_size=pool_size))

    model.add(Conv3D(32, conv_size, strides=[2, 2, 2], activation='relu'))
    model.add(Dropout(0.3))

    model.add(Conv3D(32, conv_size, activation='relu'))
    model.add(Dropout(0.3))

    model.add(Conv3D(32, (1, 1, 1), activation='relu'))

    model.add(Flatten())
    model.add(Dense(32, activation='relu'))
    model.add(Dropout(0.5))

    # model.add(Conv3D(256, (1, 1, 1), activation=('relu')))
    # model.add(Dropout(0.5))
    # model.add(Conv3D(nb_classes, (1, 1, 1), activation=('relu')))
    # model.add(Dropout(0.5))
    # model.add(Flatten())
    model.add(Dense(nb_classes))
    model.add(Activation('softmax'))

    model.compile(loss='categorical_crossentropy',
                  optimizer='adam',
                  metrics=["accuracy", sensitivity, specificity])

    return model

def batch(indices, f):
    images = f['MRI']
    labels = f['qc_label']    #already in one-hot

    while True:
        np.random.shuffle(indices)

        for index in indices:
            try:
                # print(images[index, ...][np.newaxis, ...].shape)
                yield (np.reshape(images[index, ...], image_size + (1,))[np.newaxis, ...], labels[index, ...][np.newaxis, ...])
            except:
                yield (np.reshape(images[index, ...], image_size + (1,))[np.newaxis, ...])

def plot_training_error(hist):
    epoch_num = range(len(hist.history['acc']))
    train_error = np.subtract(1, np.array(hist.history['acc']))
    test_error  = np.subtract(1, np.array(hist.history['val_acc']))

    plt.clf()
    plt.plot(epoch_num, train_error, label='Training Error')
    plt.plot(epoch_num, test_error, label="Validation Error")
    plt.legend(shadow=True)
    plt.xlabel("Training Epoch Number")
    plt.ylabel("Error")
    plt.savefig(workdir + 'results.png')
    plt.close()

if __name__ == "__main__":

    abide_indices = pickle.load(open(workdir + 'abide_indices.pkl', 'rb'))
    ds030_indices = pickle.load(open(workdir + 'ds030_indices.pkl', 'rb'))

    f = h5py.File(workdir + 'deepqc.hdf5', 'r')

    # ping_indices = list(range(0, ping_end_index))
    # abide_indices = list(range(ping_end_index, abide_end_index))
    # ibis_indices = list(range(abide_end_index, ibis_end_index))
    # ds030_indices = list(range(ibis_end_index, ds030_end_index))

    # print('ping:', ping_indices)
    # print('abide:', abide_indices)
    # print('ibis:', ibis_indices)
    # print('ds030', ds030_indices)

    # train_indices = ping_indices + abide_indices + ibis_indices
    train_indices = abide_indices

    # print('PING samples:', len(ping_indices))
    # print('ABIDE samples:', len(abide_indices))
    # print('IBIS samples:', len(ibis_indices))
    # print('training samples:', len(train_indices), len(ping_indices) + len(abide_indices) + len(ibis_indices))


    train_labels = np.zeros((len(abide_indices), 3))
    print('labels shape:', train_labels.shape)

    good_subject_index = 0
    for index in train_indices:
        label = f['qc_label'][index, ...]
        # print(label)
        train_labels[good_subject_index, ...] = label
        good_subject_index += 1

    skf = StratifiedShuffleSplit(n_splits=1, test_size = 0.1)

    for train, val in skf.split(train_indices, train_labels):
        train_indices = train
        validation_indices = val

    test_indices = ds030_indices

    print('train:', train_indices)
    print('test:', test_indices)


    # define model
    model = qc_model()

    # print summary of model
    model.summary()

    num_epochs = 300

    model_checkpoint = ModelCheckpoint( workdir + 'best_qc_model.hdf5',
                                        monitor="val_acc",
                                        save_best_only=True)

    hist = model.fit_generator(
        batch(train_indices, f),
        len(train_indices),
        epochs=num_epochs,
        callbacks=[model_checkpoint],
        validation_data=batch(validation_indices, f),
        validation_steps=len(validation_indices),
        use_multiprocessing=True
    )

    model.load_weights(workdir + 'best_qc_model.hdf5')
    model.save(workdir + 'qc_model.hdf5')

    predicted = []
    actual = []

    for index in test_indices:
        scores = model.test_on_batch(f['MRI'][index, ...], f['qc_label'][index, ...])
        print(scores)

    plot_training_error(hist)