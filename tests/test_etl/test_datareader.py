from pathlib import Path

import pytest

from literev.libs.etl import DataReader

TEST_DIR = Path(__file__).parent.parent
SAMPLE_DATA_PATH = TEST_DIR / "data" / "test_sample.jsonl"
CORRUPTED_DATA_PATH = TEST_DIR / "data" / "corrupted.jsonl"


@pytest.fixture
def reader() -> DataReader:
    """Creates a DataReader object for testing."""
    return DataReader(file_path=SAMPLE_DATA_PATH)


@pytest.fixture
def sample_total_records():
    """Count total number of records in jsonl file."""
    non_blank_line_count = 0
    with open(SAMPLE_DATA_PATH) as f:
        for line in f:
            if line.strip():  # count only non-blank lines
                non_blank_line_count += 1
    return non_blank_line_count


# --------------Test DataReader--------------


def test_read_data_should_succeed(reader, sample_total_records):
    data = reader.read_data()
    assert len(list(data)) == sample_total_records


def test_not_supported_file_should_fail(reader):
    non_supported_extensions = [
        Path("non_supported_file.csv"),
        Path("non_supported_file.txt"),
        Path("non_supported_file.json"),
    ]
    for file in non_supported_extensions:
        with pytest.raises(NotImplementedError):
            reader.file_path = file
            reader.read_data()


def test_non_existent_file_should_fail():
    with pytest.raises(FileNotFoundError):
        DataReader(file_path="non_existent_file.jsonl")


def test_corrupted_file_should_fail(reader):
    reader.file_path = CORRUPTED_DATA_PATH
    with pytest.raises(Exception):
        corrupted_objs = [record for record in reader.read_data()]
        assert corrupted_objs, f"corrupted_objs = '{corrupted_objs}'"
