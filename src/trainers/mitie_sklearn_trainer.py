import cloudpickle
import datetime
import json
import os

from rasa_nlu.featurizers.mitie_featurizer import MITIEFeaturizer
from rasa_nlu.trainers.trainer import Trainer
from training_utils import write_training_metadata
from rasa_nlu.trainers import mitie_trainer_utils
from rasa_nlu.trainers import sklearn_trainer_utils


class MITIESklearnTrainer(Trainer):
    SUPPORTED_LANGUAGES = {"en"}

    def __init__(self, fe_file, language_name, max_num_threads=1):
        super(self.__class__, self).__init__("mitie_sklearn", language_name, max_num_threads)
        self.fe_file = fe_file
        self.featurizer = MITIEFeaturizer(self.fe_file)

    def start_and_end(self, text_tokens, entity_tokens):
        size = len(entity_tokens)
        max_loc = 1 + len(text_tokens) - size
        locs = [i for i in range(max_loc) if text_tokens[i:i + size] == entity_tokens]
        start, end = locs[0], locs[0] + len(entity_tokens)
        return start, end

    def train_entity_extractor(self, entity_examples):
        self.entity_extractor = mitie_trainer_utils.train_entity_extractor(entity_examples,
                                                                           self.fe_file,
                                                                           self.max_num_threads,)

    def train_intent_classifier(self, intent_examples, test_split_size=0.1):
        self.intent_classifier = sklearn_trainer_utils.train_intent_classifier(intent_examples,
                                                                               self.featurizer,
                                                                               self.max_num_threads,
                                                                               test_split_size)

    def persist(self, path, persistor=None, create_unique_subfolder=True):
        timestamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')

        if create_unique_subfolder:
            dir_name = os.path.join(path, "model_" + timestamp)
            os.mkdir(dir_name)
        else:
            dir_name = path

        data_file = os.path.join(dir_name, "training_data.json")
        classifier_file = os.path.join(dir_name, "intent_classifier.dat")
        entity_extractor_file = os.path.join(dir_name, "entity_extractor.dat")
        entity_synonyms_file = os.path.join(dir_name, "index.json") if self.training_data.entity_synonyms else None

        write_training_metadata(dir_name, timestamp, data_file, self.name, 'en',
                                classifier_file, entity_extractor_file, entity_synonyms_file,
                                self.fe_file)

        with open(data_file, 'w') as f:
            f.write(self.training_data.as_json(indent=2))

        if self.training_data.entity_synonyms:
            with open(entity_synonyms_file, 'w') as f:
                json.dump(self.training_data.entity_synonyms, f)

        if self.intent_classifier:
            with open(classifier_file, 'wb') as f:
                cloudpickle.dump(self.intent_classifier, f)

        self.entity_extractor.save_to_disk(entity_extractor_file, pure_model=True)

        if persistor is not None:
            persistor.send_tar_to_s3(dir_name)
