# Fluster - testing framework for decoders conformance
# Copyright (C) 2021, Fluendo, S.A.
#  Author: Manuel Jimeno Martínez <mjimeno@fluendo.com>, Fluendo, S.A.
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
from abc import ABC
from pathlib import Path

from fluster.codec import Codec, OutputFormat
from fluster.decoder import Decoder, register_decoder
from fluster.http.http_custom_server import HTTPServerHandler


class ChromiumDecoder(Decoder, ABC):
    """Generic class for Chromium decoder"""
    description = "This is an implementation for the Chromium decoder"


@register_decoder
class ChromiumH264(ChromiumDecoder):
    """H264 class for Chromium decoder"""
    provider = 'Chromium'
    codec = Codec.H264

    def __init__(self) -> None:
        super().__init__()
        if not self.name:
            self.name = f'{self.provider}-{self.codec.value}'
        self.description = f'{self.provider} {self.codec.value} decoder for Chromium'

    def decode(
            self,
            input_filepath: str,
            output_filepath: str,
            output_format: OutputFormat,
            timeout: int,
            verbose: bool,
    ) -> str:
        reference_decoder_path = Path("decoders/ldecod")
        if not reference_decoder_path.exists():
            raise RuntimeError(
                "Reference decoder does not exist, use [make h264_reference_decoder] command"
            )
        source = Path(input_filepath)
        if not source.exists():
            raise RuntimeError(
                f"The input file {input_filepath} not exist"
            )
        handler = HTTPServerHandler(
            reference_decoder_path,
            source,
            server_address=("0.0.0.0", 8000),
            environment="LD_LIBRARY_PATH=/opt/libva/lib",
        )
        total_frames, frames_with_error = handler.run()
        print(f"Total frames processed {total_frames}, frames with errors {frames_with_error}")
        return "True" if frames_with_error == 0 else "False"
