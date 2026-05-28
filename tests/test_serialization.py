import json
import tempfile
import unittest

from pathlib import Path
from unittest.mock import patch


from agentron.agent import Agent
from agentron.serialization import auto_write_messages, read_session_data, write_messages
from agentron.utils.message import make_user_message


class WriteMessagesTests(unittest.TestCase):
    def test_write_messages_appends_messages_to_existing_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / 'messages.jsonl'
            destination.write_text('{"existing":true}\n')
            messages = [make_user_message('alpha'), make_user_message('beta')]

            write_messages(messages, destination)

            lines = destination.read_text().splitlines()
            self.assertEqual(lines[0], '{"existing":true}')
            self.assertEqual(json.loads(lines[1]), messages[0])
            self.assertEqual(json.loads(lines[2]), messages[1])

    def test_write_messages_adds_missing_trailing_newline_before_append(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / 'messages.jsonl'
            destination.write_text('{"existing":true}')
            message = make_user_message('alpha')

            write_messages([message], destination)

            lines = destination.read_text().splitlines()
            self.assertEqual(lines[0], '{"existing":true}')
            self.assertEqual(json.loads(lines[1]), message)

    def test_write_messages_writes_header_for_empty_file_when_session_details_are_provided(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / 'messages.jsonl'
            message = make_user_message('alpha')

            with patch('agentron.serialization.time.time', return_value=123.456):
                write_messages(
                    [message],
                    destination,
                    session_id='session-123',
                    metadata={'title': 'test'},
                )

            lines = destination.read_text().splitlines()
            self.assertEqual(
                json.loads(lines[0]),
                {
                    'type': 'header',
                    'version': 1,
                    'session_id': 'session-123',
                    'created': 123456,
                    'metadata': {'title': 'test'},
                },
            )
            self.assertEqual(json.loads(lines[1]), message)

    def test_write_messages_does_not_write_header_when_appending_to_existing_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / 'messages.jsonl'
            destination.write_text('{"existing":true}\n')
            message = make_user_message('alpha')

            with patch('agentron.serialization.time.time', return_value=123.456):
                write_messages(
                    [message],
                    destination,
                    session_id='session-123',
                    metadata={'title': 'test'},
                )

            lines = destination.read_text().splitlines()
            self.assertEqual(lines[0], '{"existing":true}')
            self.assertEqual(json.loads(lines[1]), message)
            self.assertEqual(len(lines), 2)

    def test_write_messages_does_not_insert_blank_line_for_empty_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / 'messages.jsonl'
            destination.write_text('')
            message = make_user_message('alpha')

            write_messages([message], destination)

            self.assertEqual(destination.read_text(), json.dumps(message, separators=(',', ':')) + '\n')


class _TrackingFile:
    def __init__(self, wrapped):
        self._wrapped = wrapped
        self.close_calls = 0

    def write(self, text: str) -> int:
        return self._wrapped.write(text)

    def flush(self) -> None:
        self._wrapped.flush()

    def close(self) -> None:
        self.close_calls += 1
        self._wrapped.close()

    @property
    def closed(self) -> bool:
        return self._wrapped.closed


class AutoWriteMessagesTests(unittest.TestCase):
    def test_auto_write_messages_appends_existing_and_new_messages(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            existing_message = make_user_message('alpha')
            agent = Agent(messages=[existing_message])
            session_file = Path(temp_dir) / agent.session_id / 'session.jsonl'
            session_file.parent.mkdir()
            session_file.write_text('{"existing":true}\n')

            auto_write_messages(agent, Path(temp_dir))

            initial_lines = session_file.read_text().splitlines()
            self.assertEqual(initial_lines[0], '{"existing":true}')
            self.assertEqual(json.loads(initial_lines[1]), existing_message)

            new_message = make_user_message('beta')
            agent._push_message(new_message)

            updated_lines = session_file.read_text().splitlines()
            self.assertEqual(updated_lines[0], '{"existing":true}')
            self.assertEqual(json.loads(updated_lines[1]), existing_message)
            self.assertEqual(json.loads(updated_lines[2]), new_message)

            agent.finalize()

    def test_auto_write_messages_uses_session_file_when_given_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            destination_dir = Path(temp_dir)
            agent = Agent(
                session_id='session-123',
                messages=[make_user_message('alpha')],
                metadata={'title': 'test'},
            )

            with patch('agentron.serialization.time.time', return_value=123.456):
                auto_write_messages(agent, destination_dir)

            session_file = destination_dir / 'session-123' / 'session.jsonl'
            self.assertTrue(session_file.exists())
            lines = session_file.read_text().splitlines()
            self.assertEqual(
                json.loads(lines[0]),
                {
                    'type': 'header',
                    'version': 1,
                    'session_id': 'session-123',
                    'created': 123456,
                    'metadata': {'title': 'test'},
                },
            )
            self.assertEqual(json.loads(lines[1]), agent.messages[0])

            agent.finalize()

    def test_auto_write_messages_closes_on_finalize_and_stops_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            destination_dir = Path(temp_dir)
            agent = Agent()
            session_file = destination_dir / agent.session_id / 'session.jsonl'
            session_file.parent.mkdir()
            wrapped_file = session_file.open('a', encoding='utf-8')
            tracking_file = _TrackingFile(wrapped_file)

            with (
                patch('agentron.serialization.Path.open', return_value=tracking_file),
                patch(
                    'agentron.serialization.time.time',
                    return_value=123.456,
                ),
            ):
                auto_write_messages(agent, destination_dir)

                self.assertFalse(tracking_file.closed)

                agent.finalize()

                self.assertTrue(tracking_file.closed)
                self.assertEqual(tracking_file.close_calls, 1)

                agent._push_message(make_user_message('ignored'))

            lines = session_file.read_text().splitlines()
            self.assertEqual(
                json.loads(lines[0]),
                {
                    'type': 'header',
                    'version': 1,
                    'session_id': agent.session_id,
                    'created': 123456,
                    'metadata': {},
                },
            )
            self.assertEqual(len(lines), 1)

    def test_auto_write_messages_raises_for_missing_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            destination_dir = Path(temp_dir) / 'missing'
            agent = Agent()

            with self.assertRaisesRegex(ValueError, f'Path {destination_dir} does not exist.'):
                auto_write_messages(agent, destination_dir)

    def test_auto_write_messages_raises_for_file_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            destination_file = Path(temp_dir) / 'messages.jsonl'
            destination_file.write_text('')
            agent = Agent()

            with self.assertRaisesRegex(ValueError, f'Path {destination_file} is not a directory.'):
                auto_write_messages(agent, destination_file)


class ReadSessionDataTests(unittest.TestCase):
    def test_read_session_data_returns_header_and_messages(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            session_file = Path(temp_dir) / 'session.jsonl'
            message_a = make_user_message('alpha')
            message_b = make_user_message('beta')
            session_file.write_text(
                '\n'.join(
                    [
                        json.dumps(
                            {
                                'type': 'header',
                                'version': 1,
                                'session_id': 'session-123',
                                'created': 123456,
                                'metadata': {'title': 'test'},
                            },
                            separators=(',', ':'),
                        ),
                        json.dumps(message_a, separators=(',', ':')),
                        '',
                        json.dumps(message_b, separators=(',', ':')),
                        '',
                    ]
                )
            )

            session_data = read_session_data(session_file)

            self.assertEqual(
                session_data.header,
                {
                    'type': 'header',
                    'version': 1,
                    'session_id': 'session-123',
                    'created': 123456,
                    'metadata': {'title': 'test'},
                },
            )
            self.assertEqual(session_data.messages, [message_a, message_b])

    def test_read_session_data_raises_for_empty_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            session_file = Path(temp_dir) / 'session.jsonl'
            session_file.write_text('')

            with self.assertRaisesRegex(ValueError, 'Session file is empty.'):
                read_session_data(session_file)

    def test_read_session_data_raises_for_invalid_header_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            session_file = Path(temp_dir) / 'session.jsonl'
            session_file.write_text('{"type":"header"\n')

            with self.assertRaisesRegex(ValueError, 'Failed to parse session header as JSON.'):
                read_session_data(session_file)

    def test_read_session_data_raises_when_first_line_is_not_a_header(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            session_file = Path(temp_dir) / 'session.jsonl'
            session_file.write_text(json.dumps(make_user_message('alpha'), separators=(',', ':')) + '\n')

            with self.assertRaisesRegex(ValueError, 'First line of session file must be a header object.'):
                read_session_data(session_file)

    def test_read_session_data_raises_for_invalid_message_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            session_file = Path(temp_dir) / 'session.jsonl'
            session_file.write_text(
                '\n'.join(
                    [
                        json.dumps(
                            {
                                'type': 'header',
                                'version': 1,
                                'session_id': 'session-123',
                                'created': 123456,
                                'metadata': {},
                            },
                            separators=(',', ':'),
                        ),
                        '{"type":"user","content":',
                        '',
                    ]
                )
            )

            with self.assertRaisesRegex(ValueError, 'Failed to parse message line as JSON.'):
                read_session_data(session_file)
