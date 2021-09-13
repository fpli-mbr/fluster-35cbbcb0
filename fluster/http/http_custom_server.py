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
import cgi
import io
import os
import shutil
import threading

from urllib.parse import parse_qs
from http.server import SimpleHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Tuple, List, Optional, Dict, Any, Union

from fluster.http.chromium_launcher import ChromiumLauncher
from fluster.image.raw_buffer import RawBuffer

__version__ = "0.1"

from fluster.image.raw_video import RawVideo


class ImageHTTPRequestHandler(SimpleHTTPRequestHandler):
    """Custom Request Handler"""

    GUID_FIELD = "guid"
    HEADERS = "headers"
    REFERENCE_DECODER = "{} -s -i {} -o {}"
    CONVERT_TO_MP4 = "ffmpeg -i {} -vcodec copy {}"

    server_version = "ImageHTTP/" + __version__
    guid_resources: Dict[str, Dict[str, Any]] = {}
    debug: bool = False
    decoder_path: Path = Path()
    input_file_path: Path = Path()

    def __init__(
        self,
        request: bytes,
        client_address: Tuple[str, int],
        server: HTTPServer,
        **kwargs: Union[str, Path, None],
    ) -> None:
        kwargs["directory"] = os.path.join(os.getcwd(), "fluster", "http")
        super().__init__(request, client_address, server, **kwargs)

    def do_GET(self) -> None:  # pylint: disable=invalid-name
        """Overload of the function that processes HTTP requests of type GET"""
        if self.path.split("?", 1)[0] == "/decoded_frame.html":
            result, info, buffer = self.decoded_frame_get(
                parse_qs(self.path.split("?", 1)[1])
            )
            if result:
                self._write_buffer(buffer)
            else:
                self._write_buffer(bytes(info, "utf-8"))
            return
        super().do_GET()

    def do_POST(self) -> None:  # pylint: disable=invalid-name
        """Overload of the function that processes HTTP requests of type POST"""
        headers = None
        try:
            if self.path == "/coded_file_to_test.html":
                result, info, headers = self.start_test_file(
                    str(self.input_file_path))
            elif self.path == "/clean_intermediate_files.html":
                result, info = self.clean_intermediate_files()
            else:
                result = False
                info = f"The request file {self.path} is not supported"
        except RuntimeError as error:
            print(error)
            info = str(error)
            result = False

        if result:
            self._write_buffer(bytes(info, "utf-8"), headers)
        else:
            self._write_buffer(bytes(info, "utf-8"))

    def get_header_values(self) -> Dict[str, Any]:
        """Returns a dictionary with the header fields included in the HTTP message of type POST"""
        values = {}
        content_type, property_dict = cgi.parse_header(
            self.headers["content-type"])
        property_dict["boundary"] = bytes(
            property_dict["boundary"], "utf-8"
        )  # type: ignore

        if content_type == "multipart/form-data":
            multipart_data = cgi.parse_multipart(
                self.rfile, property_dict  # type: ignore
            )
            for key, value in multipart_data.items():
                values[key] = value[0]
            return values

        raise RuntimeError("Content_type is not supported")

    def prepare_test(self, input_file: str, values: Dict[str, Any]) -> Dict[str, Any]:
        """It runs reference decoder and FFmpeg to create the decoded file and MP4 file"""
        root_directory = self.directory  # type: ignore
        guid = values["guid"]
        target_path = Path(self.directory, guid)  # type: ignore
        source_file_path = Path(input_file)
        name = os.path.splitext(source_file_path.name)[0]

        target_raw_file_path = os.path.join(target_path, name + ".yuv420")
        target_mp4_file_path = os.path.join(target_path, name + ".mp4")

        if not target_path.exists():
            os.makedirs(target_path)

        create_decoded_file = ImageHTTPRequestHandler.REFERENCE_DECODER.format(
            ImageHTTPRequestHandler.decoder_path, source_file_path, target_raw_file_path
        )
        create_mp4_file = ImageHTTPRequestHandler.CONVERT_TO_MP4.format(
            source_file_path, target_mp4_file_path
        )

        os.system(f"{create_decoded_file}\n{create_mp4_file}")

        values = {
            "name": name,
            "raw_file_path": Path(target_raw_file_path),
            "raw_video": None,
            "headers": [
                ["coded_file", os.path.relpath(
                    target_mp4_file_path, root_directory)],
                ["yuv_file", os.path.relpath(
                    target_raw_file_path, root_directory)],
            ],
        }

        self.guid_resources[guid] = values

        return values

    def start_test_file(self, filename: str) -> Tuple[bool, str, Optional[List[Any]]]:
        """It processes the POST request that indicates the start of the test by the client."""
        try:
            values = self.get_header_values()
            if ImageHTTPRequestHandler.GUID_FIELD not in values:
                raise RuntimeError("The field GUID is not present")
            guid_values = self.prepare_test(filename, values)
        except RuntimeError as error_exception:
            return False, str(error_exception), None

        return True, "Success", guid_values["headers"]

    def decoded_frame_get(
        self, values: Dict[str, Any]
    ) -> Tuple[bool, str, Optional[bytes]]:
        """It processes the GET request to retrieve for a specific frame."""
        try:
            guid = values[ImageHTTPRequestHandler.GUID_FIELD][0]
            position = int(values["frame"][0])
            if self.guid_resources[guid]["raw_video"] is None:
                self.guid_resources[guid]["raw_video"] = RawVideo(
                    self.guid_resources[guid]["raw_file_path"].read_bytes(),
                    self.guid_resources[guid]["name"],
                    int(values["width"][0]),
                    int(values["height"][0]),
                    RawBuffer.Type.YUV420,
                )
            raw_image = (
                self.guid_resources[guid]["raw_video"]
                .frames[position]
                .default_raw_buffer
            )

        except RuntimeError as error_exception:
            return False, str(error_exception), None

        return True, "Success", raw_image.buffer

    def clean_intermediate_files(self) -> Tuple[bool, str]:
        """It processes the POST request that indicates the finish of the test by the client and cleanses
        the intermediate files."""
        try:
            values = self.get_header_values()
            if ImageHTTPRequestHandler.GUID_FIELD not in values:
                raise RuntimeError("The field GUID is not present")
            guid = values[ImageHTTPRequestHandler.GUID_FIELD]
            root_directory = self.directory  # type: ignore
            shutil.rmtree(Path(root_directory, guid), ignore_errors=True)
            HTTPServerHandler.total_frames = int(values["frames"])
            HTTPServerHandler.frames_with_errors = int(values["errors"])
            if not self.debug:
                self.shutdown_server()
        except RuntimeError as error_exception:
            return False, str(error_exception)

        return True, "Success"

    def _write_buffer(
        self, buffer: Optional[bytes], headers: Optional[List[Any]] = None
    ) -> None:
        buffer_to_send = io.BytesIO()
        if buffer:
            buffer_to_send.write(buffer)
        length = buffer_to_send.tell()
        buffer_to_send.seek(0)
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.send_header("Content-Length", str(length))
        if headers:
            for header in headers:
                self.send_header(header[0], header[1])
        self.end_headers()
        if buffer_to_send:
            self.copyfile(buffer_to_send, self.wfile)  # type: ignore
            buffer_to_send.close()

    def shutdown_server(self) -> None:
        """Spawns a thread that triggers the TCPServer.shutdown method"""
        assassin = threading.Thread(target=self.server.shutdown)
        assassin.daemon = True
        assassin.start()


class HTTPServerHandler:
    """Definition of the class in charge of coordinating the execution of the server and the browser."""

    total_frames: int = 0
    frames_with_errors: int = 0

    def __init__(
        self,
        decoder_path: Path,
        input_file_path: Path,
        server_address: Tuple[str, int] = ("localhost", 8000),
        environment: Optional[str] = None,
        debug: bool = False,
        unstable: bool = True,
    ):
        self._server_address = server_address
        self._chromium: ChromiumLauncher = ChromiumLauncher(
            server_address, environment, hardware_acceleration=True, unstable=unstable
        )
        self._httpd = HTTPServer(server_address, ImageHTTPRequestHandler)
        ImageHTTPRequestHandler.debug = debug
        ImageHTTPRequestHandler.decoder_path = decoder_path
        ImageHTTPRequestHandler.input_file_path = input_file_path
        self._chromium.run()

    def run(self) -> Tuple[int, int]:
        """Start the HTTP server and the browser."""
        self._httpd.serve_forever()
        self._chromium.stop()
        return HTTPServerHandler.total_frames, HTTPServerHandler.frames_with_errors


if __name__ == "__main__":
    reference_decoder_path = Path("decoders/ldecod")
    if not reference_decoder_path.exists():
        raise RuntimeError(
            "Reference decoder does not exist, use [make h264_reference_decoder] command"
        )
    source = Path("resources/H264-min/AUD_MW_E/AUD_MW_E.264")
    handler = HTTPServerHandler(
        reference_decoder_path,
        source,
        server_address=("0.0.0.0", 8000),
        environment="LD_LIBRARY_PATH=/opt/libva/lib",
        # debug=True,
        # unstable=True,
    )
    print(f"result for {source} ", handler.run())
