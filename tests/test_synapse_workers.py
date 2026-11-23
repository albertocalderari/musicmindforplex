"""Dependency probing and worker cleanup must not fail once per library track."""
from queue import Empty
from unittest.mock import Mock, patch

import pytest

from musicmind.analysis import synapse_analyze as analysis


@pytest.mark.parametrize('returncode,available', [(0, True), (1, False)])
def test_vi_probes_actual_algorithm(returncode, available):
    with patch.object(analysis.os.path, 'exists', return_value=True), patch('subprocess.run', return_value=Mock(returncode=returncode)) as run:
        assert analysis.vi_model_available() is available
        assert 'TensorflowPredictMusiCNN' in run.call_args.args[0][-1]


@pytest.mark.parametrize('mode', ['success', 'crash', 'timeout', 'interrupt'])
def test_worker_resources_closed(mode):
    process, queue = Mock(), Mock()
    process.exitcode = 1
    process.is_alive.return_value = mode == 'timeout'
    result = {'synapse': ('ok', {'bpm': 120}), 'vi': None}
    queue.get.return_value = result
    if mode == 'crash':
        queue.get.side_effect = Empty
    if mode == 'interrupt':
        process.join.side_effect = [KeyboardInterrupt, None]
    with patch('multiprocessing.Process', return_value=process), patch('multiprocessing.Queue', return_value=queue):
        if mode == 'interrupt':
            with pytest.raises(KeyboardInterrupt):
                analysis.analyze_one('test.mp3')
        else:
            actual = analysis.analyze_one('test.mp3')
            if mode == 'success':
                assert actual == result
            else:
                assert actual['synapse'][0] == 'error'
                assert actual['vi'] is None
    process.close.assert_called_once()
    queue.close.assert_called_once()
    queue.join_thread.assert_called_once()
    if mode == 'timeout':
        process.terminate.assert_called_once()
        process.kill.assert_called_once()
