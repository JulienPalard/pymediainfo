# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import os
import sys
import unittest
import xml
import pickle
import threading
import json

import pytest

from pymediainfo import MediaInfo

os_is_nt = os.name in ("nt", "dos", "os2", "ce")

if sys.version_info < (3, 3):
    FileNotFoundError = IOError
if sys.version_info < (3, 2):
    unittest.TestCase.assertRegex = unittest.TestCase.assertRegexpMatches

data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

def _get_library_version():
    lib, handle, lib_version_str, lib_version = MediaInfo._get_library()
    lib.MediaInfo_Close(handle)
    lib.MediaInfo_Delete(handle)
    return lib_version_str, lib_version

class MediaInfoTest(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(data_dir, 'sample.xml'), 'r') as f:
            self.xml_data = f.read()
        self.mi = MediaInfo(self.xml_data)
    def test_populate_tracks(self):
        self.assertEqual(4, len(self.mi.tracks))
    def test_valid_video_track(self):
        for track in self.mi.tracks:
            if track.track_type == 'Video':
                self.assertEqual('DV', track.codec)
                self.assertEqual('Interlaced', track.scan_type)
                break
    def test_track_integer_attributes(self):
        for track in self.mi.tracks:
            if track.track_type == 'Audio':
                self.assertTrue(isinstance(track.duration, int))
                self.assertTrue(isinstance(track.bit_rate, int))
                self.assertTrue(isinstance(track.sampling_rate, int))
                break
    def test_track_other_attributes(self):
        for track in self.mi.tracks:
            if track.track_type == 'General':
                self.assertEqual(5, len(track.other_file_size))
                self.assertEqual(4, len(track.other_duration))
                break
    def test_load_mediainfo_from_string(self):
        self.assertEqual(4, len(self.mi.tracks))
    def test_getting_attribute_that_doesnot_exist(self):
        self.assertTrue(self.mi.tracks[0].does_not_exist is None)

class MediaInfoInvalidXMLTest(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(data_dir, 'invalid.xml'), 'r') as f:
            self.xml_data = f.read()
    def test_parse_invalid_xml(self):
        self.assertRaises(xml.etree.ElementTree.ParseError, MediaInfo, self.xml_data)

class MediaInfoLibraryTest(unittest.TestCase):
    def setUp(self):
        self.mi = MediaInfo.parse(os.path.join(data_dir, "sample.mp4"))
        self.non_full_mi = MediaInfo.parse(os.path.join(data_dir, "sample.mp4"), full=False)
    def test_can_parse_true(self):
        self.assertTrue(MediaInfo.can_parse())
    def test_track_count(self):
        self.assertEqual(len(self.mi.tracks), 3)
    def test_track_types(self):
        self.assertEqual(self.mi.tracks[1].track_type, "Video")
        self.assertEqual(self.mi.tracks[2].track_type, "Audio")
    def test_track_details(self):
        self.assertEqual(self.mi.tracks[1].format, "AVC")
        self.assertEqual(self.mi.tracks[2].format, "AAC")
        self.assertEqual(self.mi.tracks[1].duration, 958)
        self.assertEqual(self.mi.tracks[2].duration, 980)
    def test_full_option(self):
        self.assertEqual(self.mi.tracks[0].footersize, "59")
        self.assertEqual(self.non_full_mi.tracks[0].footersize, None)

class MediaInfoUnicodeXMLTest(unittest.TestCase):
    def setUp(self):
        self.mi = MediaInfo.parse(os.path.join(data_dir, "sample.mkv"))
    def test_parse_file_with_unicode_tags(self):
        self.assertEqual(
            self.mi.tracks[0].title,
            "Dès Noël où un zéphyr haï me vêt de glaçons "
            "würmiens je dîne d’exquis rôtis de bœuf au kir à "
            "l’aÿ d’âge mûr & cætera !"
        )

class MediaInfoUnicodeFileNameTest(unittest.TestCase):
    def setUp(self):
        self.mi = MediaInfo.parse(os.path.join(data_dir, "accentué.txt"))
    def test_parse_unicode_file(self):
        self.assertEqual(len(self.mi.tracks), 1)

class MediaInfoURLTest(unittest.TestCase):
    def setUp(self):
        self.mi = MediaInfo.parse("https://github.com/sbraz/pymediainfo/raw/master/tests/data/sample.mkv")
    def test_parse_url(self):
        self.assertEqual(len(self.mi.tracks), 2)

class MediaInfoPathlibTest(unittest.TestCase):
    def setUp(self):
        self.pathlib = pytest.importorskip("pathlib")
    def test_parse_pathlib_path(self):
        path = self.pathlib.Path(data_dir) / "sample.mp4"
        mi = MediaInfo.parse(path)
        self.assertEqual(len(mi.tracks), 3)
    @pytest.mark.skipif(os_is_nt, reason="Windows paths are URLs")
    def test_parse_non_existent_path_pathlib(self):
        path = self.pathlib.Path(data_dir) / "this file does not exist"
        self.assertRaises(FileNotFoundError, MediaInfo.parse, path)

class MediaInfoFilenameTypesTest(unittest.TestCase):
    def test_parse_filename_str(self):
        path = os.path.join(data_dir, "test.txt")
        filename, is_url = MediaInfo._parse_filename(path)
        # Windows paths are URLs
        if not os_is_nt:
            self.assertFalse(is_url)
        self.assertEqual(filename, path)
    def test_parse_filename_pathlib(self):
        pathlib = pytest.importorskip("pathlib")
        path = pathlib.Path(data_dir, "test.txt")
        filename, is_url = MediaInfo._parse_filename(path)
        self.assertFalse(is_url)
        self.assertEqual(filename, os.path.join(data_dir, "test.txt"))
    @pytest.mark.skipif(sys.version_info < (3, 6), reason="os.PathLike requires Python 3.6")
    def test_parse_filename_pathlike(self):
        class PathLikeObject(os.PathLike):
            def __fspath__(self):
                return os.path.join(data_dir, "test.txt")
        path = PathLikeObject()
        filename, is_url = MediaInfo._parse_filename(path)
        self.assertFalse(is_url)
        self.assertEqual(filename, os.path.join(data_dir, "test.txt"))
    def test_parse_filename_url(self):
        filename, is_url = MediaInfo._parse_filename("https://localhost")
        self.assertTrue(is_url)

class MediaInfoTestParseNonExistentFile(unittest.TestCase):
    @pytest.mark.skipif(os_is_nt, reason="Windows paths are URLs")
    def test_parse_non_existent_path(self):
        path = os.path.join(data_dir, "this file does not exist")
        self.assertRaises(FileNotFoundError, MediaInfo.parse, path)

class MediaInfoCoverDataTest(unittest.TestCase):
    def setUp(self):
        self.cover_mi = MediaInfo.parse(
                os.path.join(data_dir, "sample_with_cover.mp3"),
                cover_data=True
        )
        self.no_cover_mi = MediaInfo.parse(
                os.path.join(data_dir, "sample_with_cover.mp3")
        )
    def test_parse_cover_data(self):
        self.assertEqual(
                self.cover_mi.tracks[0].cover_data,
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAACXBIWXMAAAAAAA"
                "AAAQCEeRdzAAAADUlEQVR4nGP4x8DwHwAE/AH+QSRCQgAAAABJRU5ErkJggg=="
        )
    def test_parse_no_cover_data(self):
        lib_version_str, lib_version = _get_library_version()
        if lib_version < (18, 3):
            pytest.skip("The Cover_Data option is not supported by this library version "
                "(v{} detected, v18.03 required)".format(lib_version_str)
            )
        self.assertEqual(self.no_cover_mi.tracks[0].cover_data, None)

class MediaInfoTrackParsingTest(unittest.TestCase):
    def test_track_parsing(self):
        mi = MediaInfo.parse(os.path.join(data_dir, "issue55.flv"))
        self.assertEqual(len(mi.tracks), 2)

class MediaInfoRuntimeErrorTest(unittest.TestCase):
    def test_parse_invalid_url(self):
        # This is the easiest way to cause a parsing error
        # since non-existent files return a different exception
        self.assertRaises(RuntimeError, MediaInfo.parse,
                "unsupportedscheme://")

class MediaInfoSlowParseTest(unittest.TestCase):
    def setUp(self):
        self.mi = MediaInfo.parse(
                os.path.join(data_dir, "vbr_requires_parsespeed_1.mp4"),
                parse_speed=1
        )
    def test_slow_parse_speed(self):
        self.assertEqual(self.mi.tracks[2].stream_size, "3353 / 45")

class MediaInfoEqTest(unittest.TestCase):
    def setUp(self):
        self.mp3_mi = MediaInfo.parse(os.path.join(data_dir, "sample_with_cover.mp3"))
        self.mp3_other_mi = MediaInfo.parse(os.path.join(data_dir, "sample_with_cover.mp3"))
        self.mp4_mi = MediaInfo.parse(os.path.join(data_dir, "sample.mp4"))
    def test_eq(self):
        self.assertEqual(self.mp3_mi.tracks[0], self.mp3_other_mi.tracks[0])
        self.assertEqual(self.mp3_mi, self.mp3_other_mi)
        self.assertNotEqual(self.mp3_mi.tracks[0], self.mp4_mi.tracks[0])
        self.assertNotEqual(self.mp3_mi, self.mp4_mi)
    def test_pickle_unpickle(self):
        pickled_track = pickle.dumps(self.mp4_mi.tracks[0])
        self.assertEqual(self.mp4_mi.tracks[0], pickle.loads(pickled_track))
        pickled_mi = pickle.dumps(self.mp4_mi)
        self.assertEqual(self.mp4_mi, pickle.loads(pickled_mi))

class MediaInfoTextOutputTest(unittest.TestCase):
    def setUp(self):
        self.mi = MediaInfo.parse(os.path.join(data_dir, "sample.mp4"), text=True)
    def test_text_output(self):
        self.assertRegex(self.mi, r"Stream size\s+: 373836\b")

class MediaInfoLegacyStreamDisplayTest(unittest.TestCase):
    def setUp(self):
        self.mi = MediaInfo.parse(os.path.join(data_dir, "aac_he_v2.aac"))
        self.legacy_mi = MediaInfo.parse(os.path.join(data_dir, "aac_he_v2.aac"), legacy_stream_display=True)
    def test_legacy_stream_display(self):
        self.assertEqual(self.mi.tracks[1].channel_s, 2)
        self.assertEqual(self.legacy_mi.tracks[1].channel_s, "2 / 1 / 1")

class MediaInfoOptionsTest(unittest.TestCase):
    def setUp(self):
        lib_version_str, lib_version = _get_library_version()
        if lib_version < (19, 9):
            pytest.skip("The Reset option is not supported by this library version "
                "(v{} detected, v19.09 required)".format(lib_version_str)
            )
        self.raw_language_mi = MediaInfo.parse(
            os.path.join(data_dir, "sample.mkv"),
            mediainfo_options={"Language": "raw"},
        )
        # Parsing the file without the custom options afterwards
        # allows us to check that the "Reset" option worked
        # https://github.com/MediaArea/MediaInfoLib/issues/1128
        self.normal_mi = MediaInfo.parse(
            os.path.join(data_dir, "sample.mkv"),
        )
    def test_mediainfo_options(self):
        self.assertEqual(self.normal_mi.tracks[1].other_language[0], "English")
        self.assertEqual(self.raw_language_mi.tracks[1].language, "en")

# Unittests can't be parametrized
# https://github.com/pytest-dev/pytest/issues/541
@pytest.mark.parametrize("test_file", ["sample.mkv", "sample.mp4", "sample_with_cover.mp3"])
def test_thread_safety(test_file):
    lib_version_str, lib_version = _get_library_version()
    if lib_version < (20, 3):
        pytest.skip("This version of the library is not thread-safe "
            "(v{} detected, v20.03 required)".format(lib_version_str)
        )
    expected_result = MediaInfo.parse(os.path.join(data_dir, test_file))
    results = []
    lock = threading.Lock()
    def target():
        try:
            result = MediaInfo.parse(os.path.join(data_dir, test_file))
            with lock:
                results.append(result)
        except:
            pass
    threads = []
    thread_count = 100
    for i in range(thread_count):
        t = threading.Thread(target=target)
        t.start()
        threads.append(t)
    for t in threads:
        t.join()
    # Each thread should have produced a result
    assert len(results) == thread_count
    maxDiff = None
    for r in results:
        # Test dicts first because they will show a diff
        # in case they don't match
        assert r.to_data() == expected_result.to_data()
        assert r == expected_result

class MediaInfoOutputTest(unittest.TestCase):
    def test_text_output(self):
        mi = MediaInfo.parse(os.path.join(data_dir, "sample.mp4"), output="")
        self.assertRegex(mi, r"Stream size\s+: 373836\b")
    def test_json_output(self):
        lib_version_str, lib_version = _get_library_version()
        if lib_version < (18, 3):
            pytest.skip("This version of the library does not support JSON output "
                "(v{} detected, v18.03 required)".format(lib_version_str)
            )
        mi = MediaInfo.parse(os.path.join(data_dir, "sample.mp4"), output="JSON")
        parsed = json.loads(mi)
        self.assertEqual(parsed["media"]["track"][0]["FileSize"], "404567")
    def test_parameter_output(self):
        mi = MediaInfo.parse(os.path.join(data_dir, "sample.mp4"), output="General;%FileSize%")
        self.assertEqual(mi, "404567")
