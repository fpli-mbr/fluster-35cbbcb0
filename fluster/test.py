# Fluster - testing framework for decoders conformance
# Copyright (C) 2020, Fluendo, S.A.
#  Author: Pablo Marcos Oltra <pmarcos@fluendo.com>, Fluendo, S.A.
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Library General Public
# License as published by the Free Software Foundation; either
# version 2 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Library General Public License for more details.
#
# You should have received a copy of the GNU Library General Public
# License along with this library; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place - Suite 330,
# Boston, MA 02111-1307, USA.

import os
from subprocess import TimeoutExpired
import unittest

from fluster.decoder import Decoder
from fluster.test_vector import TestVector, TestVectorResult
from fluster.utils import normalize_path


class Test(unittest.TestCase):
    '''Test suite for decoder tests'''
    # pylint: disable=too-many-instance-attributes

    def __init__(self, decoder: Decoder, test_suite, test_vector: TestVector, results_dir: str,
                 reference: bool, timeout: int, keep_files: bool, verbose: bool, by_frame: bool):
        self.decoder = decoder
        self.test_suite = test_suite
        self.test_vector = test_vector
        self.resources_dir = self.test_suite.resources_dir
        self.results_dir = results_dir
        self.reference = reference
        self.timeout = timeout
        self.keep_files = keep_files
        self.verbose = verbose
        self.by_frame = by_frame

        setattr(self, test_vector.name, self._test)
        super().__init__(test_vector.name)

    def _extract_raw_frame(self, frame_number: int, input_filepath: str, output_filepath: str) -> bool:
        cmd_tmpl = ("ffmpeg -y -pix_fmt {pix_fmt} -s {width}x{height} -i {raw_video_filepath}" +
                    "-vf select='eq(n\,{frame_number}\)' {output_filepath}")
        cmd = cmd_tmpl.format(pix_fmt=self.test_vector.output_format,
                              width=self.test_vector.width,
                              height=self.test_vector.height,
                              raw_video_filepath=self.test_vector.raw_video_filepath,
                              output_filepath=output_filepath)

        subprocess.check_output(command, stderr=subprocess.DEVNULL)

    def _test(self):
        output_filepath = os.path.join(
            self.results_dir, self.test_vector.name + '.yuv')
        input_filepath = os.path.join(self.resources_dir, self.test_suite.name,
                                      self.test_vector.name, self.test_vector.input_file)
        output_filepath = normalize_path(output_filepath)
        input_filepath = normalize_path(input_filepath)

        by_frame_results = []
        try:
            decode_args = (input_filepath, output_filepath, self.test_vector.output_format, self.timeout, self.verbose)
            if not by_frame:
                result = self.decoder.decode(*decode_args)
            else:
                last_frame = self._get_last_frame_number()
                for cur_frame in range(last_frame):
                    # TODO: Unhardcode this.
                    output_filepath = "/tmp/frame-%05d.raw"
                    # TODO: Use beautiful message.
                    if (not os.path.exists(output_filepath) and
                            not self._extract_raw_frame(cur_frame, input_filepath, output_filepath)):
                        raise

                    result = self.decode_frame(frame_number, *decode_args)
                    by_frame_results.append(result)

        except TimeoutExpired:
            if not by_frame:
                self.test_suite.test_vectors[self.test_vector.name].test_result = TestVectorResult.TIMEOUT
            else:
                self.test_suite.test_vectors[self.test_vector.name].test_result_by_frame.append(TestVectorResult.TIMEOUT)
            raise
        except Exception:
            if not by_frame:
                self.test_suite.test_vectors[self.test_vector.name].test_result = TestVectorResult.ERROR
            else:
                self.test_suite.test_vectors[self.test_vector.name].test_result_by_frame.append(TestVectorResult.ERROR)
            raise

        if not self.keep_files and os.path.exists(output_filepath) and \
                os.path.isfile(output_filepath):
            os.remove(output_filepath)

        if not self.reference:
            if not by_frame:
                self.test_suite.test_vectors[self.test_vector.name].test_result = TestVectorResult.FAILURE
                if self.test_vector.result.lower() == result.lower():
                    self.test_suite.test_vectors[self.test_vector.name].test_result = TestVectorResult.SUCCESS

                results = [result] if not by_frame else by_frame_results
                for result in results:
                    self.assertEqual(self.test_vector.result.lower(), result.lower(),
                                     self.test_vector.name)
            else:
                for cur_frame, result in enumerate(by_frame_results):
                    self.test_suite.test_vectors[self.test_vector.name].test_result_by_frame[cur_frame] =\
                        TestVectorResult.FAILURE

                    # Compare hash of extracted frame here.
                    if self.test_vector.result.lower() == result.lower():
                        self.test_suite.test_vectors[self.test_vector.name].test_result = TestVectorResult.SUCCESS


        else:
            self.test_suite.test_vectors[self.test_vector.name].result = result

    def _get_last_frame_number(self):
        # TODO: Unhardcode this and implement counting total frames on raw video bistream (like YUV video).
        return 3
