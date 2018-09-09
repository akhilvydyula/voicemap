import os
from keras.optimizers import Adam
from keras.callbacks import CSVLogger, ModelCheckpoint
import multiprocessing

from utils import preprocess_instances, NShotEvaluationCallback, BatchPreProcessor
from models import get_baseline_convolutional_encoder, build_siamese_net
from librispeech import LibriSpeechDataset
from config import LIBRISPEECH_SAMPLING_RATE, PATH


# Mute excessively verbose Tensorflow output
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'


##############
# Parameters #
##############
n_seconds = 3
downsampling = 4
batchsize = 32
model_n_filters = 32
model_embedding_dimension = 128
training_set = ['train-clean-100', 'train-clean-360']
validation_set = 'dev-clean'
num_epochs = 25
evaluate_every_n_batches = 500
num_evaluation_tasks = 500
n_shot_classification = 1
k_way_classification = 5

# Derived parameters
input_length = int(LIBRISPEECH_SAMPLING_RATE * n_seconds / downsampling)


###################
# Create datasets #
###################
train = LibriSpeechDataset(training_set, n_seconds)
valid = LibriSpeechDataset(validation_set, n_seconds, stochastic=False)

batch_preprocessor = BatchPreProcessor('siamese', preprocess_instances(downsampling))
train_generator = (batch_preprocessor(batch) for batch in train.yield_verification_batches(batchsize))
valid_generator = (batch_preprocessor(batch) for batch in valid.yield_verification_batches(batchsize))


################
# Define model #
################
encoder = get_baseline_convolutional_encoder(model_n_filters, model_embedding_dimension)
siamese = build_siamese_net(encoder, (input_length, 1))
opt = Adam(clipnorm=1.)
siamese.compile(loss='binary_crossentropy', optimizer=opt, metrics=['accuracy'])


#################
# Training Loop #
#################
siamese.fit_generator(
    generator=train_generator,
    steps_per_epoch=evaluate_every_n_batches,
    validation_data=valid_generator,
    validation_steps=100,
    epochs=num_epochs,
    workers=multiprocessing.cpu_count(),
    use_multiprocessing=True,
    callbacks=[
        # First generate custom n-shot classification metric
        NShotEvaluationCallback(
            num_evaluation_tasks, n_shot_classification, k_way_classification, valid,
            preprocessor=batch_preprocessor,
        ),
        # Then log and checkpoint
        CSVLogger(PATH + '/logs/baseline_convnet.csv'),
        ModelCheckpoint(
            PATH + '/models/baseline_convnet.hdf5',
            monitor='val_{}-shot_acc'.format(n_shot_classification),
            mode='max',
            save_best_only=True,
            verbose=True
        )
    ]
)
