import os

import numpy as np
import tqdm
from absl import app, flags
from ml_collections import config_flags
from tensorboardX import SummaryWriter

from jaxrl.agents import BCLearner
from jaxrl.datasets import make_env_and_dataset
from jaxrl.evaluation import evaluate

FLAGS = flags.FLAGS

flags.DEFINE_string('env_name', 'halfcheetah-expert-v2', 'Environment name.')
flags.DEFINE_enum('dataset_name', 'd4rl', ['d4rl', 'awac', 'rl_unplugged'],
                  'Dataset name.')
flags.DEFINE_string('save_dir', './tmp/', 'Tensorboard logging dir.')
flags.DEFINE_integer('seed', 42, 'Random seed.')
flags.DEFINE_integer('eval_episodes', 10,
                     'Number of episodes used for evaluation.')
flags.DEFINE_integer('log_interval', 1000, 'Logging interval.')
flags.DEFINE_integer('eval_interval', 5000, 'Eval interval.')
flags.DEFINE_integer('batch_size', 256, 'Mini batch size.')
flags.DEFINE_integer('max_steps', int(1e6), 'Number of training steps.')
flags.DEFINE_float(
    'percentile', 100.0,
    'Dataset percentile (see https://arxiv.org/abs/2106.01345).')
flags.DEFINE_float('percentage', 100.0,
                   'Pencentage of the dataset to use for training.')
flags.DEFINE_boolean('tqdm', True, 'Use tqdm progress bar.')
flags.DEFINE_boolean('save_video', False, 'Save videos during evaluation.')
config_flags.DEFINE_config_file(
    'config',
    'configs/bc_default.py',
    'File path to the training hyperparameter configuration.',
    lock_config=False)


def main(_):
    summary_writer = SummaryWriter(
        os.path.join(FLAGS.save_dir, 'tb', str(FLAGS.seed)))

    video_save_folder = None if not FLAGS.save_video else os.path.join(
        FLAGS.save_dir, 'video', 'eval')

    env, dataset = make_env_and_dataset(FLAGS.env_name, FLAGS.seed,
                                        FLAGS.dataset_name, video_save_folder)

    if FLAGS.percentage < 100.0:
        dataset.take_random(FLAGS.percentage)

    if FLAGS.percentile < 100.0:
        dataset.take_top(FLAGS.percentile)

    kwargs = dict(FLAGS.config)
    kwargs['num_steps'] = FLAGS.max_steps
    agent = BCLearner(FLAGS.seed,
                      env.observation_space.sample()[np.newaxis],
                      env.action_space.sample()[np.newaxis], **kwargs)

    eval_returns = []
    for i in tqdm.tqdm(range(1, FLAGS.max_steps + 1),
                       smoothing=0.1,
                       disable=not FLAGS.tqdm):
        batch = dataset.sample(FLAGS.batch_size)

        update_info = agent.update(batch)

        if i % FLAGS.log_interval == 0:
            for k, v in update_info.items():
                summary_writer.add_scalar(f'training/{k}', v, i)
            summary_writer.flush()

        if i % FLAGS.eval_interval == 0:
            eval_stats = evaluate(agent, env, FLAGS.eval_episodes)

            for k, v in eval_stats.items():
                summary_writer.add_scalar(f'evaluation/average_{k}s', v, i)
            summary_writer.flush()

            eval_returns.append((i, eval_stats['return']))
            np.savetxt(os.path.join(FLAGS.save_dir, f'{FLAGS.seed}.txt'),
                       eval_returns,
                       fmt=['%d', '%.1f'])


if __name__ == '__main__':
    app.run(main)
